"""Nguồn luật duy nhất cho chơi tay, replay và mọi solver."""
from __future__ import annotations

from dataclasses import replace

from advanced import apply_effects, support_failure
from geometry import MOVEMENT_ACTIONS, adjacent, move, occupied_cells
from models import Action, GameEvent, Level, Mode, Orientation, State, TransitionResult, TransitionStatus


def available_actions(state: State) -> tuple[Action, ...]:
    return MOVEMENT_ACTIONS + ((Action.SWITCH,) if state.mode == Mode.SPLIT else ())


def state_key(state: State) -> State:
    return state


def validate_state(level: Level, state: State) -> str | None:
    """None = hợp lệ; reason code ngắn cho solver/controller cùng sử dụng.

    Không chạy lại effects: một state là ảnh chụp sau transition, không phải
    một lượt nhấn switch mới. Goal là một start state hợp lệ cho solver.
    """
    if not isinstance(state, State) or not isinstance(state.mode, Mode):
        return "INVALID_STATE"
    if not isinstance(state.bridges, tuple) or any(type(flag) is not bool for flag in state.bridges):
        return "INVALID_BRIDGE_FLAGS"
    if len(state.bridges) != len(level.bridges):
        return "BRIDGE_FLAGS_MISMATCH"
    if state.mode == Mode.MERGED:
        if (not isinstance(state.orientation, Orientation) or state.anchor is None
                or state.cubes != () or state.active_cube is not None):
            return "INVALID_MERGED_STATE"
        cells = (state.anchor,)
    else:
        if (state.anchor is not None or state.orientation is not None
                or not isinstance(state.cubes, tuple) or len(state.cubes) != 2
                or type(state.active_cube) is not int or state.active_cube not in (0, 1)):
            return "INVALID_SPLIT_STATE"
        cells = state.cubes
    if any(not isinstance(cell, tuple) or len(cell) != 2
           or any(type(n) is not int for n in cell) for cell in cells):
        return "INVALID_COORDINATES"
    if state.mode == Mode.SPLIT:
        if state.cubes[0] == state.cubes[1]:
            return "CUBE_OVERLAP"
        if adjacent(*state.cubes):
            return "SPLIT_NOT_CANONICAL"
    return support_failure(level, state)


def is_goal(level: Level, state: State) -> bool:
    return (isinstance(state, State) and state.mode == Mode.MERGED and state.orientation == Orientation.U
            and state.anchor == level.goal and validate_state(level, state) is None)


def transition(level: Level, state: State, action: Action) -> TransitionResult:
    """Tạo state mới, không sửa input. LOSS/INVALID không commit next_state."""
    failure = validate_state(level, state)
    if failure:
        return TransitionResult(TransitionStatus.INVALID_ACTION, reason=failure)
    if is_goal(level, state):
        return TransitionResult(TransitionStatus.INVALID_ACTION, reason="TERMINAL_STATE")
    try:
        action = Action(action)
    except (ValueError, TypeError):
        return TransitionResult(TransitionStatus.INVALID_ACTION, reason="UNKNOWN_ACTION")
    if action == Action.SWITCH:
        if state.mode != Mode.SPLIT:
            return TransitionResult(TransitionStatus.INVALID_ACTION, reason="SWITCH_REQUIRES_SPLIT")
        return TransitionResult(TransitionStatus.VALID,
                                replace(state, active_cube=1 - state.active_cube))
    candidate = move(state, action)
    if candidate is None:
        return TransitionResult(TransitionStatus.INVALID_ACTION, reason="CUBE_OVERLAP")
    events = ()
    if state.mode == Mode.SPLIT and candidate.mode == Mode.MERGED:
        events = (GameEvent("MERGE"),)
    failure = support_failure(level, candidate)
    if failure:
        return TransitionResult(TransitionStatus.LOSS, reason=failure, events=events)
    candidate, effect_events = apply_effects(level, state, candidate)
    events += effect_events
    failure = support_failure(level, candidate)
    if failure:
        return TransitionResult(TransitionStatus.LOSS, reason=failure, events=events)
    status = TransitionStatus.WIN if is_goal(level, candidate) else TransitionStatus.VALID
    return TransitionResult(status, candidate, events=events)
