"""Web solutions use the real Python solvers and replay full immutable states."""
from http.client import HTTPConnection
import json
import threading
from time import monotonic, sleep

import pytest

import browser_api
import webapp
from engine import is_goal
from models import Algorithm, SearchResult, SearchStatus, SessionPhase
from webapp import Catalog, GameServer, WebSession


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


@pytest.fixture
def session(catalog):
    session = WebSession(catalog, "basic_01", sync_solver=True)
    yield session
    session.close()


def solve_now(session, algorithm="BFS", policy="UNIT", **extra):
    return session.command("solve", {"algorithm": algorithm, "cost_policy": policy, **extra})


def replay(session, algorithm="BFS", policy="UNIT"):
    state = session.command("replay_start", {"algorithm": algorithm, "cost_policy": policy})
    actions = []
    while state["replay"]["active"]:
        state = session.command("replay_step", {})
        actions.append(state["replay"]["action"])
    return state, actions


def test_all_algorithms_keep_results_for_one_current_state_origin(session):
    session.command("move", {"action": "RIGHT"})
    origin = session.game.current_state
    session.command("pause", {})
    for algorithm in Algorithm:
        state = solve_now(session, algorithm.value)
        result = state["solver"]["results"][f"{algorithm.value}:UNIT"]
        assert result["status"] == "FOUND"
        assert result["actions"] == ["RIGHT"]
        assert result["metadata"]["replay_verified"] is True
        assert state["solver"]["origin_moves"] == 1
        assert state["solver"]["busy"] is False
        state, actions = replay(session, algorithm.value)
        assert actions == ["RIGHT"]
        assert state["moves"] == 2
        assert state["phase"] == "WON"
        assert is_goal(session.game.level, session.game.current_state)
    assert len(state["solver"]["results"]) == 4
    state = session.command("replay_start", {"algorithm": "BFS"})
    assert session.game.current_state == origin
    assert state["moves"] == 1


@pytest.mark.parametrize("level_id, policy", [
    ("switch_01", "UNIT"), ("split_02", "UNIT"), ("combined_02", "UNIT"),
    ("fragile_02", "FRAGILE_PENALTY"),
])
def test_replay_restores_bridges_cubes_active_and_counter(catalog, level_id, policy):
    session = WebSession(catalog, level_id, sync_solver=True)
    try:
        # Capture a real intermediate origin with modified bridge flags / active cube.
        if level_id == "switch_01":
            for direction in ("UP", "UP"):
                session.command("move", {"action": direction})
        elif level_id == "split_02":
            for direction in ("RIGHT", "RIGHT", "RIGHT", "RIGHT", "SWITCH"):
                session.command("move", {"action": direction})
        origin = session.game.current_state
        origin_moves = session.game.action_count
        state = solve_now(session, "ASTAR", policy)
        result = state["solver"]["results"][f"ASTAR:{policy}"]
        assert result["status"] == "FOUND"
        for _ in range(2):
            started = session.command("replay_start", {"algorithm": "ASTAR", "cost_policy": policy})
            assert session.game.current_state == origin
            assert started["moves"] == origin_moves
            state = started
            actions = []
            while state["replay"]["active"]:
                state = session.command("replay_step", {})
                actions.append(state["replay"]["action"])
            assert state["phase"] == "WON"
            assert actions == result["actions"]
            assert state["moves"] == origin_moves + result["solution_length"]
        if level_id == "split_02":
            assert origin.active_cube == 1
            assert result["selection_count"] >= 1
        if level_id == "fragile_02":
            assert result["solution_cost"] == 11
    finally:
        session.close()


def test_manual_changes_invalidate_but_invalid_action_keeps_results(session):
    solve_now(session)
    assert session.command("move", {"action": "SWITCH"})["solver"]["results"]
    assert not session.command("move", {"action": "RIGHT"})["solver"]["results"]
    solve_now(session)
    assert not session.command("undo", {})["solver"]["results"]
    solve_now(session)
    assert not session.command("restart", {})["solver"]["results"]
    solve_now(session)
    assert not session.command("load", {"level": "split_01"})["solver"]["results"]


def test_bad_load_preserves_previous_solution(session):
    before = solve_now(session)
    with pytest.raises(ValueError):
        session.command("load", {"level": "missing"})
    assert session.snapshot() == before


def test_no_solution_and_budget_statuses_are_not_found(catalog, session):
    session.load("no_solution_02")
    result = solve_now(session)["solver"]["results"]["BFS:UNIT"]
    assert result["status"] == "NO_SOLUTION"
    assert result["solution_length"] is None
    with pytest.raises(ValueError):
        replay(session)
    session.load("basic_01")
    result = solve_now(session, time_limit_seconds=0)["solver"]["results"]["BFS:UNIT"]
    assert result["status"] == "TIMEOUT"
    result = solve_now(session, memory_limit_bytes=0)["solver"]["results"]["BFS:UNIT"]
    assert result["status"] == "MEMORY_LIMIT"


def test_memory_unavailable_is_explicit_not_zero(session, monkeypatch):
    monkeypatch.setattr(session, "_memory_available", lambda: False)
    result = solve_now(session)["solver"]["results"]["BFS:UNIT"]
    assert result["status"] == "FOUND"
    assert result["peak_memory_bytes"] is None
    assert result["metadata"]["memory_available"] is False
    assert result["expanded_nodes"] == 2


def test_engine_rejects_corrupt_found_solution(session, monkeypatch):
    corrupt = SearchResult(SearchStatus.FOUND, actions=(), solution_length=0,
                           movement_count=0, selection_count=0, solution_cost=0)
    monkeypatch.setattr(webapp, "solve", lambda *args: corrupt)
    result = solve_now(session)["solver"]["results"]["BFS:UNIT"]
    assert result["status"] == "ERROR"
    assert result["metadata"]["replay_verified"] is False
    with pytest.raises(ValueError):
        replay(session)


@pytest.mark.parametrize("payload", [
    {"algorithm": "Dijkstra"}, {"algorithm": []}, {"algorithm": "BFS", "cost_policy": []},
    {"algorithm": "BFS", "cost_policy": "CHEAP"}, {"algorithm": "BFS", "time_limit_seconds": True},
    {"algorithm": "BFS", "time_limit_seconds": 31}, {"algorithm": "BFS", "time_limit_seconds": float("nan")},
    {"algorithm": "BFS", "memory_limit_bytes": -1},
])
def test_invalid_search_parameters_are_transactional(session, payload):
    initial = session.snapshot()
    with pytest.raises(ValueError):
        session.command("solve", payload)
    assert session.snapshot() == initial


def test_stop_replay_keeps_valid_current_state_and_results(session):
    solve_now(session)
    session.command("replay_start", {"algorithm": "BFS"})
    with pytest.raises(ValueError):
        session.command("move", {"action": "UP"})
    state = session.command("replay_step", {})
    intermediate = session.game.current_state
    assert state["phase"] == "REPLAYING"
    stopped = session.command("replay_stop", {})
    assert stopped["phase"] == "PLAYING"
    assert session.game.current_state == intermediate
    assert stopped["solver"]["results"]
    assert not session.command("move", {"action": "RIGHT"})["solver"]["results"]


def test_empty_goal_solution(session):
    session.command("move", {"action": "RIGHT"})
    session.command("move", {"action": "RIGHT"})
    result = solve_now(session)["solver"]["results"]["BFS:UNIT"]
    assert result["status"] == "FOUND"
    assert result["actions"] == []
    state, actions = replay(session)
    assert actions == []
    assert state["phase"] == "WON"
    assert state["moves"] == 2


def test_cancel_and_busy_guards(session, monkeypatch):
    class Job:
        reaped = False
        def poll(self):
            return None
        def stop(self):
            self.stopped = True
        def reap(self):
            self.reaped = True
            return True
    job = Job()
    monkeypatch.setattr(webapp, "start_search", lambda *args: job)
    session.sync_solver = False
    initial = session.game.current_state
    state = solve_now(session)
    assert state["phase"] == "SOLVING"
    assert state["solver"]["can_cancel"] is True
    assert state["solver"]["active"] == {"algorithm": "BFS", "cost_policy": "UNIT"}
    with pytest.raises(ValueError):
        session.command("restart", {})
    assert session.game.current_state == initial
    stopped = session.command("solve_cancel", {})
    assert job.stopped
    assert stopped["solver"]["busy"] is False
    assert stopped["solver"]["results"]["BFS:UNIT"]["status"] == "CANCELLED"
    assert stopped["solver"]["results"]["BFS:UNIT"]["peak_memory_bytes"] is None
    session.command("state", {})  # reaps the fake job before fixture cleanup


def test_cancel_replaces_previous_attempt_for_same_algorithm(session, monkeypatch):
    assert solve_now(session)["solver"]["results"]["BFS:UNIT"]["status"] == "FOUND"
    class Job:
        reaped = False
        def poll(self):
            return None
        def stop(self):
            pass
        def reap(self):
            self.reaped = True
            return True
    monkeypatch.setattr(webapp, "start_search", lambda *args: Job())
    session.sync_solver = False
    solve_now(session)
    stopped = session.command("solve_cancel", {})
    assert stopped["solver"]["results"]["BFS:UNIT"]["status"] == "CANCELLED"
    with pytest.raises(ValueError):
        replay(session)
    session.command("state", {})


def test_static_dispatch_runs_same_solver_without_spawn(catalog, monkeypatch):
    monkeypatch.setattr(browser_api, "_catalog", catalog)
    monkeypatch.setattr(browser_api, "_sessions", {})
    def call(path, body, token=""):
        return json.loads(browser_api.browser_dispatch(json.dumps(dict(path=path, body=body, token=token))))
    created = call("/api/session", {"level": "basic_01"})["body"]
    token = created["session"]
    assert browser_api._sessions[token].sync_solver
    assert created["solver"]["can_cancel"] is False
    for algorithm in Algorithm:
        response = call("/api/command", {"command": "solve", "algorithm": algorithm.value}, token)
        assert response["status"] == 200
        assert response["body"]["solver"]["results"][f"{algorithm.value}:UNIT"]["status"] == "FOUND"
    assert call("/api/command", {"command": "solve", "algorithm": []}, token)["status"] == 400


def test_http_spawn_solution_and_replay(catalog):
    server = GameServer(("127.0.0.1", 0), catalog)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def call(body, token="", path="/api/command"):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("POST", path, json.dumps(body),
                           {"Content-Type": "application/json", "X-Session": token})
        response = connection.getresponse()
        value = json.loads(response.read())
        connection.close()
        return response.status, value
    try:
        _, created = call({"level": "basic_01"}, path="/api/session")
        token = created["session"]
        assert created["solver"]["can_cancel"] is True
        _, state = call({"command": "solve", "algorithm": "ASTAR"}, token)
        deadline = monotonic() + 15
        while state["solver"]["busy"] and monotonic() < deadline:
            sleep(.02)
            _, state = call({"command": "solve_poll"}, token)
        assert state["solver"]["results"]["ASTAR:UNIT"]["status"] == "FOUND"
        assert state["solver"]["results"]["ASTAR:UNIT"]["metadata"]["memory_available"]
        _, state = call({"command": "replay_start", "algorithm": "ASTAR"}, token)
        while state["replay"]["active"]:
            _, state = call({"command": "replay_step"}, token)
        assert state["phase"] == "WON"
        assert state["moves"] == 2
        assert call({"command": "solve", "algorithm": []}, token)[0] == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
