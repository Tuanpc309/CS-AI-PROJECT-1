"""Cơ chế động dùng chung; không chứa controller hay thuật toán tìm kiếm."""
from __future__ import annotations

from dataclasses import replace

from geometry import occupied_cells
from models import EffectOperation, GameEvent, Level, Mode, Orientation, State, Switch, SwitchType


def support_failure(level: Level, state: State) -> str | None:
    """Kiểm tra cả khối và cube đang đứng yên sau khi cầu thay đổi."""
    if len(state.bridges) != len(level.bridges):
        return "BRIDGE_FLAGS_MISMATCH"
    for cell in occupied_cells(state):
        if not level.in_bounds(cell):
            return "OUT_OF_BOUNDS"
        tile = level.tile_at(cell)
        if tile == ".":
            return "VOID"
        if tile == "B":
            index = level.bridge_index_at(cell)
            if index is None or not state.bridges[index]:
                return "BRIDGE_DISABLED"
        if (tile == "O" and state.mode == Mode.MERGED
                and state.orientation == Orientation.U):
            return "FRAGILE_UPRIGHT"
    return None


def eligible_switches(level: Level, state: State) -> tuple[Switch, ...]:
    cells = occupied_cells(state)
    upright = state.mode == Mode.MERGED and state.orientation == Orientation.U
    return tuple(switch for switch in level.switches
                 if switch.cell in cells
                 and (switch.type == SwitchType.SOFT or upright))


def apply_effects(level: Level, old: State, candidate: State) -> tuple[State, tuple[GameEvent, ...]]:
    """Nhấn mới = eligible mới trừ cũ. TOGGLE parity trước, SET sau."""
    old_ids = {switch.id for switch in eligible_switches(level, old)}
    pressed = tuple(switch for switch in eligible_switches(level, candidate)
                    if switch.id not in old_ids)
    events = [GameEvent("SWITCH_PRESSED", switch.id) for switch in pressed]
    index_by_id = {bridge.id: index for index, bridge in enumerate(level.bridges)}
    toggle_counts: dict[str, int] = {}
    setters: dict[str, bool] = {}
    for switch in pressed:
        for effect in switch.effects:
            if effect.operation == EffectOperation.TOGGLE:
                toggle_counts[effect.bridge_id] = toggle_counts.get(effect.bridge_id, 0) + 1
            else:
                setters[effect.bridge_id] = effect.operation == EffectOperation.SET_OPEN
    flags = list(candidate.bridges)
    for bridge_id, count in toggle_counts.items():
        if count % 2:
            index = index_by_id[bridge_id]
            flags[index] = not flags[index]
    for bridge_id, enabled in setters.items():
        flags[index_by_id[bridge_id]] = enabled
    for index, (before, after) in enumerate(zip(candidate.bridges, flags)):
        if before != after:
            events.append(GameEvent("BRIDGE_CHANGED", level.bridges[index].id))
    candidate = replace(candidate, bridges=tuple(flags))
    for switch in pressed:
        if switch.type == SwitchType.SPLIT:
            candidate = State.split(switch.destinations, 0, candidate.bridges)
            events.append(GameEvent("SPLIT", switch.id))
    return candidate, tuple(events)
