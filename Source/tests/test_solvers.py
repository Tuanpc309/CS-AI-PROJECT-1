"""Kiểm tra tối ưu, replay, teleport heuristic và xử lý ngân sách/status."""
from collections import deque
from pathlib import Path
import tracemalloc

import pytest

from engine import available_actions, transition
from experiments.plot_results import aggregate
from experiments.run_all import LEVEL_IDS, row_from_result, verify_solution
from loader import load_level
from models import (
    Action, Algorithm, CostPolicy, Level, Orientation, SearchConfig,
    SearchResult, SearchStatus, State, Switch, SwitchType, TransitionStatus,
)
from solvers import solve, step_cost
from solvers.heuristics import RelaxedCellDistance

LEVEL_DIR = Path(__file__).resolve().parents[1] / "levels"
FAST_CONFIG = SearchConfig(measure_memory=False)


@pytest.mark.parametrize("algorithm", list(Algorithm))
def test_empty_solution_and_invalid_start_are_distinct(algorithm):
    level, _ = load_level(LEVEL_DIR / "basic_01.json")
    goal_state = State.merged(level.goal)
    empty = solve(level, goal_state, algorithm, FAST_CONFIG)
    assert empty.status == SearchStatus.FOUND
    assert empty.actions == ()
    assert empty.solution_length == empty.solution_cost == empty.expanded_nodes == 0
    assert empty.movement_count == empty.selection_count == 0
    invalid = solve(level, State.merged((0, 0)), algorithm, FAST_CONFIG)
    assert invalid.status == SearchStatus.ERROR
    assert invalid.solution_length is None and invalid.solution_cost is None
    assert "INVALID" in invalid.metadata["message"] or "VOID" in invalid.metadata["message"]


@pytest.mark.parametrize("level_id", LEVEL_IDS)
def test_all_algorithms_use_engine_and_unit_optimum(level_id):
    level, start = load_level(LEVEL_DIR / f"{level_id}.json")
    results = {algorithm: solve(level, start, algorithm, FAST_CONFIG) for algorithm in Algorithm}
    expected = SearchStatus.NO_SOLUTION if level_id.startswith("no_solution_") else SearchStatus.FOUND
    assert all(result.status == expected for result in results.values())
    for result in results.values():
        assert verify_solution(level, start, result, CostPolicy.UNIT) is None
        assert result.total_time_seconds == result.preprocessing_time_seconds + result.search_time_seconds
        if expected == SearchStatus.NO_SOLUTION:
            assert result.solution_length is None and result.solution_cost is None
    if expected == SearchStatus.FOUND:
        assert results[Algorithm.BFS].solution_length == results[Algorithm.UCS].solution_length
        assert results[Algorithm.UCS].solution_cost == results[Algorithm.ASTAR].solution_cost
        assert results[Algorithm.DFS].solution_length >= results[Algorithm.BFS].solution_length


def test_weighted_search_can_choose_longer_but_cheaper_route():
    level, start = load_level(LEVEL_DIR / "fragile_02.json")
    config = SearchConfig(cost_policy=CostPolicy.FRAGILE_PENALTY, measure_memory=False)
    bfs = solve(level, start, Algorithm.BFS, config)
    ucs = solve(level, start, Algorithm.UCS, config)
    astar = solve(level, start, "A*", config)
    assert bfs.status == ucs.status == astar.status == SearchStatus.FOUND
    assert bfs.solution_length < ucs.solution_length
    assert ucs.solution_cost < bfs.solution_cost
    assert astar.solution_cost == ucs.solution_cost
    assert verify_solution(level, start, ucs, config.cost_policy) is None
    assert verify_solution(level, start, astar, config.cost_policy) is None


def test_fragile_cost_counts_new_footprint_once_and_ignores_stationary_cube():
    level = Level("two_fragile", ("FOOG",), (0, 0), (0, 3))
    old = State.merged((0, 0))
    step = transition(level, old, Action.RIGHT)
    assert step.status == TransitionStatus.VALID
    assert step_cost(level, old, Action.RIGHT, step.next_state, step.events, CostPolicy.FRAGILE_PENALTY) == 3
    cube_level = Level("cube_cost", ("FFFOFG",), (0, 0), (0, 5))
    old = State.split(((0, 0), (0, 2)), active_cube=1)
    step = transition(cube_level, old, Action.RIGHT)
    assert step.status == TransitionStatus.VALID
    assert step_cost(cube_level, old, Action.RIGHT, step.next_state, step.events, CostPolicy.FRAGILE_PENALTY) == 3
    selected = transition(cube_level, step.next_state, Action.SWITCH)
    assert step_cost(cube_level, step.next_state, Action.SWITCH, selected.next_state,
                     selected.events, CostPolicy.FRAGILE_PENALTY) == 1
    moved = transition(cube_level, selected.next_state, Action.RIGHT)
    assert moved.status == TransitionStatus.VALID
    assert step_cost(cube_level, selected.next_state, Action.RIGHT, moved.next_state,
                     moved.events, CostPolicy.FRAGILE_PENALTY) == 1


def test_teleport_edges_include_cells_before_roll_to_split():
    level = Level("teleport_bound", ("FFFT......FFGFF",), (0, 0), (0, 12), switches=(
        Switch("split", (0, 3), SwitchType.SPLIT, destinations=((0, 10), (0, 14))),
    ))
    before = State.merged((0, 1), Orientation.H)
    after = transition(level, before, Action.RIGHT)
    assert after.status == TransitionStatus.VALID
    heuristic = RelaxedCellDistance(level)
    # Chỉ thêm T->đích sẽ cho h(before)=3 > 1+h(after)=2, mất consistency.
    assert heuristic(before) == 2
    assert heuristic(after.next_state) == 1
    assert heuristic(before) <= 1 + heuristic(after.next_state)
    result = solve(level, before, Algorithm.UCS, FAST_CONFIG)
    assert result.status == SearchStatus.FOUND
    assert heuristic(before) <= result.solution_cost


@pytest.mark.parametrize("level_id", ("switch_01", "split_01", "split_02", "combined_02", "no_solution_02"))
def test_heuristic_consistency_on_actual_reachable_transitions(level_id):
    level, start = load_level(LEVEL_DIR / f"{level_id}.json")
    heuristic = RelaxedCellDistance(level)
    assert heuristic(State.merged(level.goal, bridges=start.bridges)) == 0
    queue = deque([start])
    visited = {start}
    split_seen = False
    while queue:
        state = queue.popleft()
        for action in available_actions(state):
            step = transition(level, state, action)
            if step.status not in (TransitionStatus.VALID, TransitionStatus.WIN):
                continue
            child = step.next_state
            split_seen |= action == Action.SWITCH
            for policy in CostPolicy:
                cost = step_cost(level, state, action, child, step.events, policy)
                assert heuristic(state) <= cost + heuristic(child)
            if child not in visited:
                visited.add(child)
                queue.append(child)
    if "split" in level_id or level_id == "combined_02":
        assert split_seen


@pytest.mark.parametrize("algorithm", list(Algorithm))
def test_budget_failure_never_claims_no_solution_and_tracing_stops(algorithm):
    level, start = load_level(LEVEL_DIR / "basic_01.json")
    timed_out = solve(level, start, algorithm, SearchConfig(time_limit_seconds=0))
    assert timed_out.status == SearchStatus.TIMEOUT
    assert timed_out.solution_length is None and timed_out.solution_cost is None
    assert not tracemalloc.is_tracing()
    memory_limited = solve(level, start, algorithm, SearchConfig(memory_limit_bytes=1))
    assert memory_limited.status == SearchStatus.MEMORY_LIMIT
    assert memory_limited.peak_memory_bytes > 1
    assert memory_limited.solution_length is None
    assert not tracemalloc.is_tracing()


def test_unexpected_solver_exception_is_error_not_no_solution(monkeypatch):
    from solvers import bfs
    level, start = load_level(LEVEL_DIR / "basic_01.json")

    def broken_search(_session):
        raise RuntimeError("Intentional test failure")

    monkeypatch.setattr(bfs, "search", broken_search)
    result = solve(level, start, Algorithm.BFS)
    assert result.status == SearchStatus.ERROR
    assert result.metadata["error_type"] == "RuntimeError"
    assert result.solution_length is None
    assert not tracemalloc.is_tracing()


@pytest.mark.parametrize("algorithm", (Algorithm.UCS, Algorithm.ASTAR))
def test_cheaper_route_updates_parents_skips_stale_heap_and_reopens(monkeypatch, algorithm):
    """Đồ thị nhỏ độc lập để kiểm tra priority; không kiểm tra luật lăn ở đây.

    A* dùng một h admissible nhưng inconsistent để buộc mở lại A.
    S->A=3, S->B=1, B->A=1, A->G=1: đường rẻ nhất có cost 3.
    """
    from solvers.common import SearchSession
    from solvers import astar
    level = Level("priority_graph", ("FFFG",), (0, 0), (0, 3))
    start, a, b, goal = (State.merged((0, index)) for index in range(4))
    edges = {
        start: ((Action.UP, a, 3), (Action.RIGHT, b, 1)),
        b: ((Action.LEFT, a, 1), (Action.DOWN, goal, 3)),
        a: ((Action.RIGHT, goal, 1),), goal: (),
    }

    def graph_successors(_session, state, reverse=False):
        return iter(reversed(edges[state]) if reverse else edges[state])

    monkeypatch.setattr(SearchSession, "successors", graph_successors)
    if algorithm == Algorithm.ASTAR:
        h = {start: 0, a: 0, b: 2, goal: 0}
        monkeypatch.setattr(astar, "RelaxedCellDistance", lambda _level, _check: h.__getitem__)
    result = solve(level, start, algorithm, FAST_CONFIG)
    assert result.status == SearchStatus.FOUND
    assert result.solution_cost == 3
    assert result.actions == (Action.RIGHT, Action.LEFT, Action.RIGHT)
    assert result.expanded_nodes == (4 if algorithm == Algorithm.ASTAR else 3)


def test_summary_keeps_no_solution_complete_but_hides_partial_medians():
    level, _ = load_level(LEVEL_DIR / "no_solution_01.json")
    rows = []
    for run_id in range(1, 4):
        complete = SearchResult(SearchStatus.NO_SOLUTION, search_time_seconds=run_id,
                                total_time_seconds=run_id, peak_memory_bytes=4096, expanded_nodes=3)
        rows.append({key: "" if value is None else str(value)
                     for key, value in row_from_result(level, Algorithm.BFS, CostPolicy.UNIT, run_id, complete).items()})
    summary = aggregate(rows, expected_runs=3)[0]
    assert summary["completion_status"] == "COMPLETE"
    assert summary["total_time_s"] == 2
    assert summary["solution_length"] == summary["solution_cost"] == ""
    rows[-1]["status"] = "TIMEOUT"
    summary = aggregate(rows, expected_runs=3)[0]
    assert summary["completion_status"] == "INCOMPLETE"
    assert summary["completed_runs"] == 2
    assert summary["total_time_s"] == ""
    assert "TIMEOUT:1" in summary["status_counts"]
