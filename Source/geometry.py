"""Hình học của khối: các hàm này không kiểm tra loại ô hay công tắc."""
from __future__ import annotations

from models import Action, Coord, Mode, Orientation, State

MOVEMENT_ACTIONS = (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT)
DELTAS = {Action.UP: (-1, 0), Action.DOWN: (1, 0),
          Action.LEFT: (0, -1), Action.RIGHT: (0, 1)}


def occupied_cells(state: State) -> tuple[Coord, ...]:
    """Giữ thứ tự A/B khi SPLIT; anchor H/V là ô trái/trên."""
    if state.mode == Mode.SPLIT:
        return state.cubes
    r, c = state.anchor
    if state.orientation == Orientation.U:
        return ((r, c),)
    if state.orientation == Orientation.H:
        return ((r, c), (r, c + 1))
    if state.orientation == Orientation.V:
        return ((r, c), (r + 1, c))
    raise ValueError("Tư thế không hợp lệ")


def roll(state: State, action: Action) -> State:
    """Áp bảng 12 phép lăn lên khối nguyên; chưa kết luận VALID/LOSS."""
    if state.mode != Mode.MERGED or action not in MOVEMENT_ACTIONS:
        raise ValueError("roll cần khối nguyên và một hướng di chuyển")
    r, c = state.anchor
    table = {
        Orientation.U: {
            Action.UP: (r - 2, c, Orientation.V),
            Action.DOWN: (r + 1, c, Orientation.V),
            Action.LEFT: (r, c - 2, Orientation.H),
            Action.RIGHT: (r, c + 1, Orientation.H)},
        Orientation.H: {
            Action.UP: (r - 1, c, Orientation.H),
            Action.DOWN: (r + 1, c, Orientation.H),
            Action.LEFT: (r, c - 1, Orientation.U),
            Action.RIGHT: (r, c + 2, Orientation.U)},
        Orientation.V: {
            Action.UP: (r - 1, c, Orientation.U),
            Action.DOWN: (r + 2, c, Orientation.U),
            Action.LEFT: (r, c - 1, Orientation.V),
            Action.RIGHT: (r, c + 1, Orientation.V)},
    }
    nr, nc, orientation = table[state.orientation][action]
    return State.merged((nr, nc), orientation, state.bridges)


def adjacent(a: Coord, b: Coord) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def move_cube(state: State, action: Action) -> State | None:
    """None nghĩa là chồng ô; hai cube kề cạnh được ghép ngay."""
    if state.mode != Mode.SPLIT or action not in MOVEMENT_ACTIONS:
        raise ValueError("move_cube cần state SPLIT và một hướng")
    dr, dc = DELTAS[action]
    cubes = list(state.cubes)
    r, c = cubes[state.active_cube]
    cubes[state.active_cube] = (r + dr, c + dc)
    a, b = cubes
    if a == b:
        return None
    if adjacent(a, b):
        orientation = Orientation.H if a[0] == b[0] else Orientation.V
        anchor = (min(a[0], b[0]), min(a[1], b[1]))
        return State.merged(anchor, orientation, state.bridges)
    return State.split((a, b), state.active_cube, state.bridges)


def move(state: State, action: Action) -> State | None:
    return roll(state, action) if state.mode == Mode.MERGED else move_cube(state, action)
