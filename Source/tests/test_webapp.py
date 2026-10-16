"""Browser adapter integration: actual engine transitions, undo, grading and HTTP."""
from http.client import HTTPConnection
import json
import threading

import pytest

from engine import is_goal
from models import Algorithm, SearchConfig, SessionPhase
from solvers import solve
from webapp import Catalog, GameServer, UNDO_LIMIT, WebSession


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def action(session, direction):
    return session.command("move", {"action": direction})


def test_pause_blocks_moves_and_resume_restores_play(catalog):
    session = WebSession(catalog, "basic_01")
    initial = session.game.current_state
    assert session.command("pause", {})["phase"] == "PAUSED"
    action(session, "RIGHT")
    assert session.game.current_state == initial
    assert session.game.action_count == 0
    assert not session.history
    session.command("resume", {})
    assert action(session, "RIGHT")["moves"] == 1


def test_loss_undo_recovers_last_valid_state_without_losing_a_move(catalog):
    session = WebSession(catalog, "basic_01")
    action(session, "RIGHT")
    previous = session.game.current_state
    lost = action(session, "UP")
    assert lost["phase"] == "LOST"
    assert lost["fallenState"] is not None
    recovered = session.command("undo", {})
    assert recovered["phase"] == "PLAYING"
    assert recovered["moves"] == 1
    assert session.game.current_state == previous
    assert recovered["undos"] == UNDO_LIMIT - 1
    assert action(session, "RIGHT")["phase"] == "WON"


def test_undo_restores_bridge_flags_and_split_selection(catalog):
    session = WebSession(catalog, "switch_01")
    action(session, "UP")
    previous = session.game.current_state
    action(session, "UP")
    assert session.game.current_state.bridges != previous.bridges
    session.command("undo", {})
    assert session.game.current_state == previous
    session.load("split_02")
    for direction in ["RIGHT"] * 4:
        action(session, direction)
    previous = session.game.current_state
    action(session, "SWITCH")
    assert session.game.current_state.active_cube != previous.active_cube
    session.command("undo", {})
    assert session.game.current_state == previous
    # Also undo the bridge-switching movement of cube A.
    assert session.command("undo", {})["moves"] == 3
    assert session.game.current_state.bridges != previous.bridges


def test_undo_limit_invalid_action_and_restart(catalog):
    session = WebSession(catalog, "basic_01")
    action(session, "SWITCH")
    assert not session.history
    assert session.undos == UNDO_LIMIT
    for _ in range(UNDO_LIMIT):
        action(session, "RIGHT")
        session.command("undo", {})
    action(session, "RIGHT")
    previous = session.game.current_state
    assert not session.command("undo", {})["canUndo"]
    assert session.game.current_state == previous
    restarted = session.command("restart", {})
    assert restarted["undos"] == UNDO_LIMIT
    assert restarted["moves"] == 0
    assert not restarted["canUndo"]


@pytest.mark.parametrize("extra_pairs, expected_stars", [(0, 3), (1, 2), (2, 1)])
def test_stars_are_based_on_real_optimal_action_count(catalog, extra_pairs, expected_stars):
    session = WebSession(catalog, "basic_01")
    for _ in range(extra_pairs):
        action(session, "RIGHT")
        action(session, "LEFT")
    action(session, "RIGHT")
    result = action(session, "RIGHT")
    assert result["phase"] == "WON"
    assert result["level"]["optimal"] == 2
    assert result["moves"] == 2 + 2 * extra_pairs
    assert result["stars"] == expected_stars


@pytest.mark.parametrize("level_id", list(Catalog().paths))
def test_browser_catalog_replays_through_existing_engine(catalog, level_id):
    session = WebSession(catalog, level_id)
    result = solve(session.game.level, session.game.initial_state, Algorithm.BFS,
                   SearchConfig(measure_memory=False))
    if level_id.startswith("no_solution_"):
        assert not result.found
        assert session.snapshot()["stars"] is None
        return
    assert result.found
    for direction in result.actions:
        action(session, direction.value)
    assert session.game.phase == SessionPhase.WON
    assert is_goal(session.game.level, session.game.current_state)
    assert session.snapshot()["stars"] == 3
    assert session.game.action_count == result.solution_length


def test_passcodes_unique_and_bad_load_keeps_session(catalog):
    assert len({item["passcode"] for item in catalog.items}) == len(catalog.items)
    session = WebSession(catalog, "basic_01")
    old = session.snapshot()
    with pytest.raises(ValueError):
        session.command("load", {"level": "../../main.py"})
    assert session.snapshot() == old


def test_campaign_is_default_and_keeps_all_legacy_levels(catalog):
    assert catalog.default == "campaign_01"
    main = [item for item in catalog.items if item["collection"] == "campaign"]
    assert [item["id"] for item in main] == [f"campaign_{i:02d}" for i in range(1, 31)]
    assert [item["number"] for item in main] == list(range(1,31))
    assert [item["difficulty"] for item in main] == [i//6+1 for i in range(30)]
    assert all(item["difficultyLabel"] and item["mechanics"] for item in main)
    assert len([item for item in catalog.items if item["collection"] == "extra"]) == 13
    assert all(catalog.optimum(item["id"]) is not None for item in main)


def test_explicit_initial_level_overrides_campaign_default(catalog):
    custom = Catalog(catalog.paths["split_02"])
    assert custom.default == "split_02"
    assert WebSession(custom, custom.default).snapshot()["level"]["id"] == "split_02"


@pytest.fixture
def http_server(catalog):
    server = GameServer(("127.0.0.1", 0), catalog)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def send(server, path, body=None, token="", origin=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    headers = {"Content-Type": "application/json", "X-Session": token}
    if origin:
        headers["Origin"] = origin
    connection.request("POST" if body is not None else "GET", path,
                       json.dumps(body) if body is not None else None, headers)
    response = connection.getresponse()
    content = response.read()
    result = json.loads(content) if "application/json" in response.getheader("Content-Type", "") else content
    status = response.status
    connection.close()
    return status, result


def test_http_isolates_tabs_and_rejects_foreign_or_invalid_requests(http_server):
    server = http_server
    status, first = send(server, "/api/session", {"level": "basic_01"})
    assert status == 200
    _, second = send(server, "/api/session", {"level": "basic_01"})
    assert first["session"] != second["session"]
    status, moved = send(server, "/api/command", {"command": "move", "action": "RIGHT"}, first["session"])
    assert status == 200 and moved["moves"] == 1
    _, untouched = send(server, "/api/command", {"command": "state"}, second["session"])
    assert untouched["moves"] == 0
    assert send(server, "/api/command", {"command": "restart"}, "bad-token")[0] == 410
    assert send(server, "/api/command", {"command": "restart"}, first["session"], "https://example.com")[0] == 403
    assert send(server, "/api/session", {"level": []})[0] == 400
    assert send(server, "/api/command", {"command": "load", "level": []}, first["session"])[0] == 400
    assert send(server, "/api/session", ["bad-shape"])[0] == 400
    assert send(server, "/../main.py")[0] == 404
    assert send(server, "/")[0] == 200
    assert send(server, "/board.js")[0] == 200
    assert send(server, "/transport.js")[0] == 200
    assert send(server, "/rolling.js")[0] == 200
    status, campaign = send(server, "/api/session", {})
    assert status == 200 and campaign["level"]["id"] == "campaign_01"
    assert campaign["level"]["difficulty"] == 1
    assert campaign["level"]["biomeId"] == "forest"
    assert campaign["level"]["width"] == len(campaign["level"]["grid"][0])
    assert campaign["level"]["height"] == len(campaign["level"]["grid"])
    for asset in ["/motion.js", "/camera.js", "/gestures.js", "/biomes.js", "/profiles.js", "/profile-ui.js", "/run-clock.js", "/impact.js", "/landing-dust.js", "/wind.js", "/vendor/three.module.js", "/vendor/three.core.js"]:
        assert send(server,asset)[0] == 200
