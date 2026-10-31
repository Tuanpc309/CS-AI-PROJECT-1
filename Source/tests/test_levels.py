"""Bộ màn có lời giải thật và thực sự dùng cơ chế được phân công.

BFS nhỏ ở đây là phép kiểm tra độc lập với bốn implementation solver:
không sử dụng expected_status hoặc witness để dẫn hướng tìm kiếm.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import available_actions, is_goal, occupied_cells, transition
from loader import load_level
from models import Action, Mode, Orientation, TransitionStatus


LEVELS = Path(__file__).resolve().parents[1] / "levels"
# Các chuỗi được xác nhận bằng replay qua engine, không phải đoán từ hình bàn.
WITNESSES = {
    "basic_01": "RIGHT RIGHT",
    "basic_02": "RIGHT RIGHT DOWN RIGHT DOWN RIGHT RIGHT",
    "fragile_01": "RIGHT RIGHT RIGHT RIGHT",
    "fragile_02": "RIGHT RIGHT RIGHT RIGHT RIGHT RIGHT",
    "switch_01": "UP UP DOWN DOWN RIGHT RIGHT RIGHT RIGHT",
    "switch_02": "RIGHT RIGHT RIGHT RIGHT",
    "split_01": "RIGHT RIGHT RIGHT RIGHT RIGHT UP SWITCH LEFT DOWN RIGHT RIGHT",
    "split_02": "RIGHT RIGHT RIGHT RIGHT SWITCH LEFT LEFT LEFT SWITCH RIGHT UP DOWN RIGHT RIGHT",
    "combined_01": "UP UP DOWN DOWN RIGHT RIGHT RIGHT RIGHT RIGHT RIGHT",
    "combined_02": "RIGHT RIGHT RIGHT SWITCH LEFT LEFT LEFT LEFT LEFT DOWN DOWN RIGHT SWITCH RIGHT RIGHT RIGHT",
}
UNSOLVABLE = ("no_solution_01", "no_solution_02")


def breadth_first(level, start, max_switches=None):
    """Trả path hoặc None và toàn bộ states được ghi nhận trước khi dừng.

    Với ngân sách SWITCH, số lượt chọn là một phần của node kiểm tra.
    Đây là ràng buộc phụ để chứng minh màn không giải được bằng một cube.
    """
    first = (start, 0)
    frontier = deque([first])
    parents = {first: None}
    while frontier:
        state, selections = key = frontier.popleft()
        if is_goal(level, state):
            path = []
            while parents[key] is not None:
                previous, action = parents[key]
                path.append(action)
                key = previous
            return tuple(reversed(path)), {item[0] for item in parents}
        for action in available_actions(state):
            count = selections + int(action == Action.SWITCH)
            if max_switches is not None and count > max_switches:
                continue
            result = transition(level, state, action)
            if result.status not in (TransitionStatus.VALID, TransitionStatus.WIN):
                continue
            next_key = (result.next_state, count if max_switches is not None else 0)
            if next_key not in parents:
                parents[next_key] = ((state, selections), action)
                frontier.append(next_key)
    return None, {item[0] for item in parents}


def witness_trace(name):
    level, state = load_level(LEVELS / f"{name}.json")
    states = [state]
    results = []
    for token in WITNESSES[name].split():
        before = state
        result = transition(level, state, Action(token))
        assert result.status in (TransitionStatus.VALID, TransitionStatus.WIN), (name, token, result)
        assert result.next_state is not None
        assert before == states[-1], "transition không được sửa input"
        state = result.next_state
        states.append(state)
        results.append(result)
    assert is_goal(level, state)
    assert results[-1].status == TransitionStatus.WIN
    return level, states, results


def fragile_cost(level, states, actions):
    total = 0
    for old, new, action in zip(states, states[1:], actions):
        new_cells = set(occupied_cells(new)) - set(occupied_cells(old))
        total += 3 if action != Action.SWITCH and any(level.tile_at(p) == "O" for p in new_cells) else 1
    return total


def test_exact_fixed_catalog_and_size_limits():
    assert {p.stem for p in LEVELS.glob("*.json")} == set(WITNESSES) | set(UNSOLVABLE)
    for path in LEVELS.glob("*.json"):
        level, start = load_level(path)
        assert level.id == path.stem
        assert level.height <= 8 and level.width <= 10
        assert len(level.bridges) <= 3
        assert sum(s.type.value == "SPLIT" for s in level.switches) <= 2
        assert start.anchor == level.start and start.orientation == Orientation.U


@pytest.mark.parametrize("name", WITNESSES)
def test_solvable_catalog_has_shortest_engine_verified_witness(name):
    level, states, _ = witness_trace(name)
    found, _ = breadth_first(level, states[0])
    assert found is not None
    assert len(found) == len(WITNESSES[name].split())


@pytest.mark.parametrize("name,minimum_states", [("no_solution_01", 3), ("no_solution_02", 50)])
def test_unsolvable_catalog_exhausts_the_reachable_graph(name, minimum_states):
    level, start = load_level(LEVELS / f"{name}.json")
    found, reached = breadth_first(level, start)
    assert found is None
    assert len(reached) >= minimum_states
    if name == "no_solution_02":
        assert len({state.bridges for state in reached}) == 2


def test_basic_02_uses_both_lying_orientations():
    _, states, _ = witness_trace("basic_02")
    assert {Orientation.H, Orientation.V} <= {s.orientation for s in states}


def test_fragile_01_requires_entry_while_lying_and_offers_an_upright_loss():
    level, start = load_level(LEVELS / "fragile_01.json")
    valid = [a for a in available_actions(start)
             if transition(level, start, a).status in (TransitionStatus.VALID, TransitionStatus.WIN)]
    assert valid == [Action.RIGHT]
    first = transition(level, start, Action.RIGHT).next_state
    assert first.orientation == Orientation.H
    assert any(level.tile_at(p) == "O" for p in occupied_cells(first))
    _, reached = breadth_first(level, start)
    assert any(transition(level, state, action).reason == "FRAGILE_UPRIGHT"
               for state in reached for action in available_actions(state))


def test_fragile_02_has_longer_but_cheaper_safe_route():
    level, short_states, _ = witness_trace("fragile_02")
    short = tuple(Action(t) for t in WITNESSES["fragile_02"].split())
    assert len(short) == 6 and fragile_cost(level, short_states, short) == 12
    safe = (Action.DOWN,) + (Action.RIGHT,) * 9 + (Action.UP,)
    state = short_states[0]
    safe_states = [state]
    for action in safe:
        result = transition(level, state, action)
        assert result.status in (TransitionStatus.VALID, TransitionStatus.WIN)
        state = result.next_state
        safe_states.append(state)
    assert is_goal(level, state)
    assert len(safe) == 11 and fragile_cost(level, safe_states, safe) == 11


def test_soft_toggle_level_revisits_the_same_position_with_different_bridges():
    _, states, results = witness_trace("switch_01")
    assert states[0].anchor == states[4].anchor
    assert states[0].orientation == states[4].orientation
    assert states[0].bridges == (False,) and states[4].bridges == (True,)
    assert any(event.kind == "SWITCH_PRESSED" and event.object_id == "soft_gate"
               for result in results for event in result.events)


def test_heavy_level_allows_lying_without_activation_then_opens_when_upright():
    level, states, results = witness_trace("switch_02")
    assert states[1].bridges == (False,)
    assert states[2].orientation == Orientation.U
    assert level.tile_at(states[2].anchor) == "X"
    assert states[2].bridges == (True,)
    assert any(event.object_id == "heavy_gate" and event.kind == "SWITCH_PRESSED"
               for event in results[1].events)
    _, reached = breadth_first(level, states[0])
    assert any(state.mode == Mode.MERGED and state.orientation != Orientation.U
               and state.bridges == (False,)
               and any(level.tile_at(p) == "X" for p in occupied_cells(state))
               for state in reached)


@pytest.mark.parametrize("name,max_switches", [("split_01", 0), ("split_02", 1)])
def test_split_levels_require_control_changes_and_rejoin(name, max_switches):
    level, states, results = witness_trace(name)
    events = [event.kind for result in results for event in result.events]
    assert "SPLIT" in events and "MERGE" in events
    assert any(s.mode == Mode.SPLIT for s in states)
    limited_path, _ = breadth_first(level, states[0], max_switches=max_switches)
    assert limited_path is None


def test_combined_01_uses_fragile_and_both_switch_types():
    level, states, results = witness_trace("combined_01")
    pressed = {event.object_id for result in results for event in result.events
               if event.kind == "SWITCH_PRESSED"}
    assert {"soft_entry", "heavy_exit"} <= pressed
    assert any(level.tile_at(p) == "O" for state in states for p in occupied_cells(state))
    assert states[-1].bridges == (True, True)


def test_combined_02_closes_return_gate_on_its_successful_path():
    level, states, results = witness_trace("combined_02")
    index = next(i for i, bridge in enumerate(level.bridges) if bridge.id == "return_gate")
    assert states[0].bridges[index] is True
    assert states[-1].bridges[index] is False
    assert any(event.kind == "BRIDGE_CHANGED" and event.object_id == "return_gate"
               for result in results for event in result.events)
    assert any(event.kind == "SPLIT" for result in results for event in result.events)
    assert any(event.kind == "MERGE" for result in results for event in result.events)
