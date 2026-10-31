"""Kiểm tra luật thật, nhất là các tương tác dễ làm solver sai."""
from dataclasses import FrozenInstanceError

import pytest

from engine import available_actions, is_goal, occupied_cells, state_key, transition, validate_state
from geometry import roll
from models import (Action, Bridge, BridgeEffect, EffectOperation, Level, Mode,
                    Orientation, State, Switch, SwitchType, TransitionStatus)


def board(tiles=None, bridges=(), switches=()):
    rows = [list("FFFFFFFFF") for _ in range(9)]
    rows[0][0] = "G"
    for (r, c), tile in (tiles or {}).items():
        rows[r][c] = tile
    return Level("test", tuple("".join(row) for row in rows), (4, 4), (0, 0), bridges, switches)


@pytest.mark.parametrize("orientation,action,anchor,result_orientation", [
    (Orientation.U, Action.UP, (2, 4), Orientation.V),
    (Orientation.U, Action.DOWN, (5, 4), Orientation.V),
    (Orientation.U, Action.LEFT, (4, 2), Orientation.H),
    (Orientation.U, Action.RIGHT, (4, 5), Orientation.H),
    (Orientation.H, Action.UP, (3, 4), Orientation.H),
    (Orientation.H, Action.DOWN, (5, 4), Orientation.H),
    (Orientation.H, Action.LEFT, (4, 3), Orientation.U),
    (Orientation.H, Action.RIGHT, (4, 6), Orientation.U),
    (Orientation.V, Action.UP, (3, 4), Orientation.U),
    (Orientation.V, Action.DOWN, (6, 4), Orientation.U),
    (Orientation.V, Action.LEFT, (4, 3), Orientation.V),
    (Orientation.V, Action.RIGHT, (4, 5), Orientation.V),
])
def test_twelve_roll_transitions(orientation, action, anchor, result_orientation):
    state = State.merged((4, 4), orientation)
    result = transition(board(), state, action)
    assert result.status == TransitionStatus.VALID
    assert result.next_state == State.merged(anchor, result_orientation)
    assert state == State.merged((4, 4), orientation)


def test_geometry_footprint_and_immutable_key():
    state = State.merged((2, 3), Orientation.H)
    assert occupied_cells(state) == ((2, 3), (2, 4))
    assert occupied_cells(State.merged((2, 3), Orientation.V)) == ((2, 3), (3, 3))
    assert state_key(state) is state
    assert hash(state) == hash(State.merged((2, 3), Orientation.H))
    with pytest.raises(FrozenInstanceError):
        state.anchor = (1, 1)


@pytest.mark.parametrize("tiles,state,action,reason", [
    ({(4, 6): "."}, State.merged((4, 4)), Action.RIGHT, "VOID"),
    ({}, State.merged((0, 4)), Action.UP, "OUT_OF_BOUNDS"),
    ({(4, 3): "O"}, State.merged((4, 4), Orientation.H), Action.LEFT, "FRAGILE_UPRIGHT"),
])
def test_loss_does_not_commit_candidate(tiles, state, action, reason):
    result = transition(board(tiles), state, action)
    assert result.status == TransitionStatus.LOSS
    assert result.next_state is None
    assert result.reason == reason


def test_lying_block_and_cube_can_use_fragile():
    result = transition(board({(4, 6): "O"}), State.merged((4, 4)), Action.RIGHT)
    assert result.status == TransitionStatus.VALID
    state = State.split(((4, 4), (1, 1)))
    result = transition(board({(4, 5): "O"}), state, Action.RIGHT)
    assert result.status == TransitionStatus.VALID


def test_goal_requires_merged_upright_and_is_terminal():
    level = board()
    win = transition(level, State.merged((0, 1), Orientation.H), Action.LEFT)
    assert win.status == TransitionStatus.WIN
    assert is_goal(level, win.next_state)
    assert validate_state(level, win.next_state) is None
    assert transition(level, win.next_state, Action.RIGHT).reason == "TERMINAL_STATE"
    assert not is_goal(level, State.merged((0, 0), Orientation.H))
    assert not is_goal(level, State.split(((0, 0), (4, 4))))


def test_soft_repress_and_inactive_cube_do_not_retrigger():
    bridge = Bridge("gate", ((8, 8),), False)
    switch = Switch("soft", (2, 2), SwitchType.SOFT,
                    (BridgeEffect("gate", EffectOperation.TOGGLE),))
    level = board({(8, 8): "B", (2, 2): "S"}, (bridge,), (switch,))
    first = transition(level, State.merged((2, 1), bridges=(False,)), Action.RIGHT)
    assert first.next_state.bridges == (True,)
    assert {event.kind for event in first.events} == {"SWITCH_PRESSED", "BRIDGE_CHANGED"}
    leave = transition(level, first.next_state, Action.DOWN)
    repress = transition(level, leave.next_state, Action.UP)
    assert repress.next_state.bridges == (False,)
    split = State.split(((2, 2), (4, 4)), 1, (True,))
    moved = transition(level, split, Action.UP)
    assert moved.next_state.bridges == (True,)
    assert moved.events == ()
    changed_selection = transition(level, split, Action.SWITCH)
    assert changed_selection.next_state.active_cube == 0
    assert changed_selection.next_state.bridges == (True,)
    assert changed_selection.events == ()


def test_heavy_requires_upright():
    bridge = Bridge("gate", ((8, 8),), False)
    switch = Switch("heavy", (2, 4), SwitchType.HEAVY,
                    (BridgeEffect("gate", EffectOperation.SET_OPEN),))
    level = board({(8, 8): "B", (2, 4): "X"}, (bridge,), (switch,))
    lying = transition(level, State.merged((2, 3), bridges=(False,)), Action.RIGHT)
    assert lying.next_state.bridges == (False,)
    standing = transition(level, State.merged((2, 2), Orientation.H, (False,)), Action.RIGHT)
    assert standing.next_state.bridges == (True,)
    cube = transition(level, State.split(((2, 3), (4, 4)), bridges=(False,)), Action.RIGHT)
    assert cube.next_state.bridges == (False,)


def test_toggle_parity_and_set_overrides_toggle():
    bridge = Bridge("gate", ((8, 8),), False)
    effect = BridgeEffect("gate", EffectOperation.TOGGLE)
    switches = (Switch("a", (2, 2), SwitchType.SOFT, (effect,)),
                Switch("b", (2, 3), SwitchType.SOFT, (effect,)))
    level = board({(8, 8): "B", (2, 2): "S", (2, 3): "S"}, (bridge,), switches)
    result = transition(level, State.merged((2, 1), bridges=(False,)), Action.RIGHT)
    assert result.next_state.bridges == (False,)
    assert [event.kind for event in result.events] == ["SWITCH_PRESSED", "SWITCH_PRESSED"]
    switches = (switches[0], Switch("b", (2, 3), SwitchType.SOFT,
                (BridgeEffect("gate", EffectOperation.SET_CLOSED),)))
    level = board({(8, 8): "B", (2, 2): "S", (2, 3): "S"}, (bridge,), switches)
    assert transition(level, State.merged((2, 1), bridges=(False,)), Action.RIGHT).next_state.bridges == (False,)


def test_closed_bridge_cannot_be_rescued_by_same_step_switch():
    bridge = Bridge("gate", ((2, 3),), False)
    switch = Switch("soft", (2, 2), SwitchType.SOFT,
                    (BridgeEffect("gate", EffectOperation.SET_OPEN),))
    level = board({(2, 2): "S", (2, 3): "B"}, (bridge,), (switch,))
    result = transition(level, State.merged((2, 1), bridges=(False,)), Action.RIGHT)
    assert result.status == TransitionStatus.LOSS
    assert result.reason == "BRIDGE_DISABLED"
    assert result.events == ()


def test_closing_bridge_under_inactive_cube_causes_loss():
    bridge = Bridge("gate", ((4, 4),), True)
    switch = Switch("soft", (2, 2), SwitchType.SOFT,
                    (BridgeEffect("gate", EffectOperation.SET_CLOSED),))
    level = board({(4, 4): "B", (2, 2): "S"}, (bridge,), (switch,))
    state = State.split(((2, 1), (4, 4)), bridges=(True,))
    result = transition(level, state, Action.RIGHT)
    assert result.status == TransitionStatus.LOSS
    assert result.reason == "BRIDGE_DISABLED"
    assert result.next_state is None
    assert {event.kind for event in result.events} == {"SWITCH_PRESSED", "BRIDGE_CHANGED"}
    assert state.bridges == (True,)


def test_split_teleport_identity_and_rejoin():
    switch = Switch("split", (2, 4), SwitchType.SPLIT, destinations=((1, 1), (4, 4)))
    level = board({(2, 4): "T"}, switches=(switch,))
    lying = transition(level, State.merged((2, 3)), Action.RIGHT)
    assert lying.next_state.mode == Mode.MERGED
    split = transition(level, State.merged((2, 2), Orientation.H), Action.RIGHT)
    assert split.next_state == State.split(((1, 1), (4, 4)), 0)
    assert [event.kind for event in split.events] == ["SWITCH_PRESSED", "SPLIT"]
    state = State.split(((4, 2), (4, 4)))
    merged = transition(level, state, Action.RIGHT)
    assert merged.next_state == State.merged((4, 3), Orientation.H)
    assert merged.events[0].kind == "MERGE"
    vertical = transition(level, State.split(((2, 4), (4, 4))), Action.DOWN)
    assert vertical.next_state == State.merged((3, 4), Orientation.V)
    diagonal = transition(level, State.split(((1, 1), (2, 3))), Action.RIGHT)
    assert diagonal.next_state.mode == Mode.SPLIT
    assert diagonal.next_state.cubes == ((1, 2), (2, 3))


def test_actions_state_validation_and_invalid_inputs():
    assert available_actions(State.merged((4, 4))) == (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT)
    split = State.split(((1, 1), (4, 4)))
    assert available_actions(split)[-1] == Action.SWITCH
    assert transition(board(), State.merged((4, 4)), Action.SWITCH).status == TransitionStatus.INVALID_ACTION
    assert transition(board(), split, "BAD").reason == "UNKNOWN_ACTION"
    assert validate_state(board(), State.split(((1, 1), (1, 2)))) == "SPLIT_NOT_CANONICAL"
    assert validate_state(board(), State.merged((4, 4), bridges=(True,))) == "BRIDGE_FLAGS_MISMATCH"
    assert state_key(split) != State.split(split.cubes, 1)
    assert state_key(State.merged((4, 4), bridges=(True,))) != State.merged((4, 4), bridges=(False,))
