"""Kiểm tra vòng đời phiên chơi; luật chi tiết có bộ test engine riêng."""
from pathlib import Path

import pytest

import controller as controller_module
from controller import GameController
from engine import is_goal
from models import Action, Algorithm, SearchResult, SearchStatus, SessionPhase
from solvers import solve

LEVELS = Path(__file__).resolve().parents[1] / "levels"


@pytest.fixture
def game():
    controller = GameController()
    controller.load(LEVELS / "basic_01.json")
    yield controller
    controller.close()


def solution(actions=(Action.RIGHT, Action.RIGHT)):
    return SearchResult(SearchStatus.FOUND, actions, solution_length=len(actions),
                        movement_count=len(actions), selection_count=0, solution_cost=len(actions))


def prepare_replay(game, result):
    game.solution_snapshot = game.current_state
    game._solution_action_count = game.action_count
    game._accept_result(result)


def finish_replay(game):
    assert game.begin_replay()
    for i in range(len(game.last_result.actions) + 1):
        assert game.advance_replay(game._next_replay_at)


def test_loss_keeps_last_valid_state_and_restart_recovers(game):
    initial = game.current_state
    assert game.handle_action(Action.UP)
    assert game.phase == SessionPhase.LOST
    assert game.current_state == initial
    assert not game.handle_action(Action.RIGHT)
    assert game.restart()
    assert game.phase == SessionPhase.PLAYING
    assert game.current_state == initial
    assert game.action_count == 0


def test_invalid_action_preserves_solution_but_valid_move_invalidates(game):
    prepare_replay(game, solution())
    assert game.handle_action(Action.SWITCH)
    assert game.can_replay
    assert game.handle_action(Action.RIGHT)
    assert game.last_result is None
    assert game.solution_snapshot is None
    assert not game.can_replay


def test_load_failure_is_transactional(game, tmp_path):
    bad = tmp_path / "invalid.json"
    bad.write_text('{"grid": []}', encoding="utf-8")
    old = game.level, game.current_state, game.level_path
    with pytest.raises(ValueError):
        game.load(bad)
    assert (game.level, game.current_state, game.level_path) == old


def test_replay_restores_snapshot_and_counts_manual_plus_solution_steps(game):
    game.handle_action(Action.RIGHT)
    snapshot = game.current_state
    prepare_replay(game, solution((Action.RIGHT,)))
    finish_replay(game)
    assert game.phase == SessionPhase.WON
    assert is_goal(game.level, game.current_state)
    assert game.action_count == 2
    # Phát lại lần nữa phải trở về cùng snapshot và không cộng dồn counter.
    assert game.begin_replay()
    assert game.current_state == snapshot
    assert game.action_count == 1
    game.advance_replay(game._next_replay_at)
    game.advance_replay(game._next_replay_at)
    assert game.action_count == 2


def test_bad_replay_does_not_commit_loss(game):
    initial = game.current_state
    prepare_replay(game, solution((Action.UP,)))
    assert game.begin_replay()
    assert game.advance_replay(game._next_replay_at)
    assert game.current_state == initial
    assert game.phase == SessionPhase.PLAYING
    assert game.last_result is None
    assert "Lỗi replay" in game.message


def test_empty_solution_replays_terminal_goal(game):
    game.handle_action(Action.RIGHT)
    game.handle_action(Action.RIGHT)
    prepare_replay(game, solution(()))
    finish_replay(game)
    assert game.phase == SessionPhase.WON
    assert game.action_count == 2


def test_busy_guard_and_worker_result_contract(game, monkeypatch):
    class Job:
        def __init__(self, request_id):
            self.request_id = request_id
            self.delivered = False
        def poll(self):
            if not self.delivered:
                self.delivered = True
                return self.request_id, solution()
        def reap(self):
            return True
    monkeypatch.setattr(controller_module, "start_search", lambda request_id, *args: Job(request_id))
    assert game.begin_solve(Algorithm.BFS)
    assert game.busy
    assert not game.restart()
    assert not game.load(LEVELS / "split_01.json")
    assert not game.handle_action(Action.RIGHT)
    assert not game.begin_solve(Algorithm.ASTAR)
    assert game.poll_solver()
    assert game.phase == SessionPhase.PLAYING
    assert game.can_replay
    game.poll_solver()  # dọn job đã trả kết quả


@pytest.mark.parametrize("level_id", ["switch_01", "split_02", "combined_02"])
def test_advanced_replay_then_restart_restores_all_state(game, level_id):
    game.load(LEVELS / f"{level_id}.json")
    initial = game.current_state
    result = solve(game.level, initial, Algorithm.BFS)
    assert result.found
    prepare_replay(game, result)
    finish_replay(game)
    assert is_goal(game.level, game.current_state)
    assert game.action_count == result.solution_length
    assert game.restart()
    assert game.current_state == initial
    assert game.last_result is None
    assert game.action_count == 0
