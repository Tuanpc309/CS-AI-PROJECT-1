"""Đọc JSON và từ chối màn sai trước khi chạy GUI hoặc solver."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geometry import adjacent
from models import Bridge, BridgeEffect, Coord, EffectOperation, Level, State, Switch, SwitchType


class LevelFormatError(ValueError):
    """Dữ liệu màn không tuân thủ schema trong README mục 8."""


def _object(value: Any, context: str, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise LevelFormatError(f"{context}: phải là object")
    if any(not isinstance(key, str) for key in value):
        raise LevelFormatError(f"{context}: tên trường phải là chuỗi")
    missing = required - value.keys()
    unknown = value.keys() - required - (optional or set())
    if missing:
        raise LevelFormatError(f"{context}: thiếu trường {', '.join(sorted(missing))}")
    if unknown:
        raise LevelFormatError(f"{context}: trường không hỗ trợ {', '.join(sorted(unknown))}")
    return value


def _identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LevelFormatError(f"{context}: ID phải là chuỗi không rỗng")
    return value


def _coord(value: Any, context: str, grid: tuple[str, ...]) -> Coord:
    if not isinstance(value, list) or len(value) != 2 or any(type(n) is not int for n in value):
        raise LevelFormatError(f"{context}: tọa độ phải là mảng hai số nguyên (không phải bool)")
    cell = (value[0], value[1])
    if not 0 <= cell[0] < len(grid) or not 0 <= cell[1] < len(grid[0]):
        raise LevelFormatError(f"{context}: tọa độ ngoài bàn {cell}")
    return cell


def _array(value: Any, context: str) -> list:
    if not isinstance(value, list):
        raise LevelFormatError(f"{context}: phải là mảng")
    return value


def initial_state(level: Level) -> State:
    """Thứ tự flags trùng tuple bridges đã được sort theo ID."""
    return State.merged(level.start, bridges=tuple(bridge.initial_enabled for bridge in level.bridges))


def level_from_dict(data: Any) -> tuple[Level, State]:
    """Validate toàn bộ schema rồi mới tạo các frozen dataclass."""
    data = _object(data, "level", {"id", "grid", "start", "goal", "bridges", "switches"}, {"biomeId"})
    biome_id = data.get("biomeId", "forest")
    if biome_id not in ("forest", "dusk", "neon", "cavern", "celestial"):
        raise LevelFormatError("biomeId: biome không được nhận diện")
    level_id = _identifier(data["id"], "level.id")
    rows = _array(data["grid"], "grid")
    if not rows or any(not isinstance(row, str) or not row for row in rows):
        raise LevelFormatError("grid: cần ít nhất một hàng không rỗng")
    if any(len(row) != len(rows[0]) for row in rows):
        raise LevelFormatError("grid: các hàng phải dài bằng nhau")
    if any(tile not in ".FGOBSXT" for row in rows for tile in row):
        raise LevelFormatError("grid: ký tự ô không được nhận diện")
    grid = tuple(rows)
    start = _coord(data["start"], "start", grid)
    goal = _coord(data["goal"], "goal", grid)
    if grid[start[0]][start[1]] != "F":
        raise LevelFormatError("start: phải nằm trên F thuần")
    goal_cells = {(r, c) for r, row in enumerate(grid) for c, tile in enumerate(row) if tile == "G"}
    if goal_cells != {goal}:
        raise LevelFormatError("goal: cần đúng một G trùng trường goal")

    bridges: list[Bridge] = []
    bridge_ids: set[str] = set()
    bridge_cells: set[Coord] = set()
    for i, item in enumerate(_array(data["bridges"], "bridges")):
        context = f"bridges[{i}]"
        item = _object(item, context, {"id", "cells", "initial_enabled"})
        bridge_id = _identifier(item["id"], context + ".id")
        if bridge_id in bridge_ids:
            raise LevelFormatError(f"{context}: bridge ID trùng {bridge_id}")
        bridge_ids.add(bridge_id)
        if type(item["initial_enabled"]) is not bool:
            raise LevelFormatError(f"{context}: initial_enabled phải là bool")
        cells = tuple(_coord(cell, context + ".cells", grid)
                      for cell in _array(item["cells"], context + ".cells"))
        if not cells:
            raise LevelFormatError(f"{context}: bridge cần ít nhất một ô")
        if len(set(cells)) != len(cells) or any(cell in bridge_cells for cell in cells):
            raise LevelFormatError(f"{context}: mỗi ô B chỉ thuộc một bridge")
        if any(grid[r][c] != "B" for r, c in cells):
            raise LevelFormatError(f"{context}: bridge phải nằm trên B")
        bridge_cells.update(cells)
        bridges.append(Bridge(bridge_id, tuple(sorted(cells)), item["initial_enabled"]))
    expected_bridges = {(r, c) for r, row in enumerate(grid) for c, tile in enumerate(row) if tile == "B"}
    if bridge_cells != expected_bridges:
        raise LevelFormatError("bridges: mỗi ô B phải có đúng một định nghĩa")

    switches: list[Switch] = []
    switch_ids: set[str] = set()
    switch_cells: set[Coord] = set()
    setters: dict[str, EffectOperation] = {}
    tile_for_type = {SwitchType.SOFT: "S", SwitchType.HEAVY: "X", SwitchType.SPLIT: "T"}
    for i, item in enumerate(_array(data["switches"], "switches")):
        context = f"switches[{i}]"
        item = _object(item, context, {"id", "cell", "type", "effects"}, {"destinations"})
        switch_id = _identifier(item["id"], context + ".id")
        if switch_id in switch_ids:
            raise LevelFormatError(f"{context}: switch ID trùng {switch_id}")
        switch_ids.add(switch_id)
        cell = _coord(item["cell"], context + ".cell", grid)
        if cell in switch_cells:
            raise LevelFormatError(f"{context}: một ô chỉ có một switch")
        switch_cells.add(cell)
        try:
            switch_type = SwitchType(item["type"])
        except (ValueError, TypeError):
            raise LevelFormatError(f"{context}: type phải là SOFT/HEAVY/SPLIT") from None
        if grid[cell[0]][cell[1]] != tile_for_type[switch_type]:
            raise LevelFormatError(f"{context}: switch type không khớp ký tự grid")
        effects: list[BridgeEffect] = []
        for j, effect in enumerate(_array(item["effects"], context + ".effects")):
            effect_context = f"{context}.effects[{j}]"
            effect = _object(effect, effect_context, {"bridge_id", "operation"})
            bridge_id = _identifier(effect["bridge_id"], effect_context + ".bridge_id")
            if bridge_id not in bridge_ids:
                raise LevelFormatError(f"{effect_context}: bridge không tồn tại {bridge_id}")
            try:
                operation = EffectOperation(effect["operation"])
            except (ValueError, TypeError):
                raise LevelFormatError(f"{effect_context}: operation không hợp lệ") from None
            if operation != EffectOperation.TOGGLE:
                if bridge_id in setters and setters[bridge_id] != operation:
                    raise LevelFormatError(f"{effect_context}: SET_OPEN/SET_CLOSED mâu thuẫn trên {bridge_id}")
                setters[bridge_id] = operation
            effects.append(BridgeEffect(bridge_id, operation))
        destinations: tuple[Coord, ...] = ()
        if switch_type == SwitchType.SPLIT:
            if "destinations" not in item:
                raise LevelFormatError(f"{context}: SPLIT cần destinations")
            destinations = tuple(_coord(point, context + ".destinations", grid)
                                 for point in _array(item["destinations"], context + ".destinations"))
            if len(destinations) != 2:
                raise LevelFormatError(f"{context}: SPLIT cần đúng hai destinations")
            if destinations[0] == destinations[1] or adjacent(*destinations):
                raise LevelFormatError(f"{context}: destinations phải khác nhau và không kề cạnh")
            if any(grid[r][c] != "F" for r, c in destinations):
                raise LevelFormatError(f"{context}: destinations phải nằm trên F thuần")
        elif "destinations" in item:
            raise LevelFormatError(f"{context}: SOFT/HEAVY không có destinations")
        switches.append(Switch(switch_id, cell, switch_type, tuple(effects), destinations))
    expected_switches = {(r, c) for r, row in enumerate(grid) for c, tile in enumerate(row) if tile in "SXT"}
    if switch_cells != expected_switches:
        raise LevelFormatError("switches: mỗi ô S/X/T phải có đúng một định nghĩa")
    level = Level(level_id, grid, start, goal,
                  tuple(sorted(bridges, key=lambda item: item.id)),
                  tuple(sorted(switches, key=lambda item: item.id)), biome_id)
    return level, initial_state(level)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise LevelFormatError(f"JSON: trường bị lặp {key}")
        result[key] = value
    return result


def load_level(path: str | Path) -> tuple[Level, State]:
    try:
        with Path(path).open("r", encoding="utf-8-sig") as stream:
            data = json.load(stream, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LevelFormatError(f"Không đọc được màn {path}: {error}") from error
    return level_from_dict(data)
