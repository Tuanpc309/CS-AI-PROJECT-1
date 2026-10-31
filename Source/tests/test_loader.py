"""Loader từ chối schema sai trước khi state được dùng trong tìm kiếm."""
from copy import deepcopy
import json

import pytest

from loader import LevelFormatError, initial_state, level_from_dict, load_level
from models import Mode, Orientation


def basic():
    return {"id": "basic", "grid": [".......", ".FFFGF.", "......."],
            "start": [1, 1], "goal": [1, 4], "bridges": [], "switches": []}


def dynamic():
    return {"id": "dynamic", "grid": ["FFFGFFF", "FBBSXTF", "FFFFFFF"],
            "start": [0, 0], "goal": [0, 3],
            "bridges": [
                {"id": "z", "cells": [[1, 1]], "initial_enabled": False},
                {"id": "a", "cells": [[1, 2]], "initial_enabled": True}],
            "switches": [
                {"id": "soft", "cell": [1, 3], "type": "SOFT", "effects": [{"bridge_id": "z", "operation": "TOGGLE"}]},
                {"id": "heavy", "cell": [1, 4], "type": "HEAVY", "effects": [{"bridge_id": "a", "operation": "SET_OPEN"}]},
                {"id": "split", "cell": [1, 5], "type": "SPLIT", "effects": [], "destinations": [[2, 0], [2, 6]]}]}


def test_roundtrip_sorted_flags_and_frozen_tuples(tmp_path):
    path = tmp_path / "level.json"
    path.write_text(json.dumps(dynamic()), encoding="utf-8")
    level, state = load_level(path)
    assert [bridge.id for bridge in level.bridges] == ["a", "z"]
    assert [switch.id for switch in level.switches] == ["heavy", "soft", "split"]
    assert state.bridges == (True, False)
    assert state == initial_state(level)
    assert state.mode == Mode.MERGED and state.orientation == Orientation.U
    assert isinstance(level.grid, tuple) and isinstance(level.switches[-1].destinations, tuple)


@pytest.mark.parametrize("field,value", [
    ("grid", []), ("grid", ["F", "FFG"]), ("grid", ["F?G"]),
    ("grid", ["FFF", "FFF", "FFF"]),
    ("start", [True, 1]), ("start", [1.0, 1]), ("start", [-1, 1]),
    ("start", [1, 4]), ("goal", [1, 2]), ("id", ""),
    ("bridges", {}), ("switches", None),
])
def test_malformed_basic(field, value):
    data = basic()
    data[field] = value
    with pytest.raises(LevelFormatError):
        level_from_dict(data)


def test_missing_unknown_and_duplicate_json_keys(tmp_path):
    data = basic()
    del data["bridges"]
    with pytest.raises(LevelFormatError, match="thiếu"):
        level_from_dict(data)
    data = basic()
    data["unsupported"] = True
    with pytest.raises(LevelFormatError, match="không hỗ trợ"):
        level_from_dict(data)
    path = tmp_path / "duplicates.json"
    path.write_text('{"id":"a","id":"b"}', encoding="utf-8")
    with pytest.raises(LevelFormatError, match="lặp"):
        load_level(path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(LevelFormatError, match="Không đọc được"):
        load_level(path)


@pytest.mark.parametrize("change", [
    "duplicate_bridge_id", "duplicate_bridge_cell", "missing_bridge", "bridge_on_floor",
    "invalid_bool", "unknown_bridge", "wrong_switch_type", "duplicate_switch_id",
    "duplicate_switch_cell", "missing_switch", "missing_split_destinations", "adjacent_destinations",
    "overlap_destinations", "destination_on_special", "destinations_on_soft",
    "contradictory_set", "invalid_operation", "invalid_type", "bool_coordinate",
])
def test_malformed_dynamic(change):
    data = deepcopy(dynamic())
    if change == "duplicate_bridge_id":
        data["bridges"][1]["id"] = "z"
    elif change == "duplicate_bridge_cell":
        data["bridges"][1]["cells"] = [[1, 1]]
    elif change == "missing_bridge":
        data["bridges"].pop()
    elif change == "bridge_on_floor":
        data["bridges"][0]["cells"] = [[0, 0]]
    elif change == "invalid_bool":
        data["bridges"][0]["initial_enabled"] = 0
    elif change == "unknown_bridge":
        data["switches"][0]["effects"][0]["bridge_id"] = "missing"
    elif change == "wrong_switch_type":
        data["switches"][0]["type"] = "HEAVY"
    elif change == "duplicate_switch_id":
        data["switches"][1]["id"] = "soft"
    elif change == "duplicate_switch_cell":
        data["switches"][1]["cell"] = [1, 3]
    elif change == "missing_switch":
        data["switches"].pop()
    elif change == "missing_split_destinations":
        del data["switches"][2]["destinations"]
    elif change == "adjacent_destinations":
        data["switches"][2]["destinations"] = [[2, 0], [2, 1]]
    elif change == "overlap_destinations":
        data["switches"][2]["destinations"] = [[2, 0], [2, 0]]
    elif change == "destination_on_special":
        data["switches"][2]["destinations"] = [[0, 3], [2, 6]]
    elif change == "destinations_on_soft":
        data["switches"][0]["destinations"] = []
    elif change == "contradictory_set":
        data["switches"][0]["effects"].append({"bridge_id": "a", "operation": "SET_CLOSED"})
    elif change == "invalid_operation":
        data["switches"][0]["effects"][0]["operation"] = "OPEN"
    elif change == "invalid_type":
        data["switches"][0]["type"] = "UNKNOWN"
    elif change == "bool_coordinate":
        data["switches"][0]["cell"] = [True, 3]
    with pytest.raises(LevelFormatError):
        level_from_dict(data)


def test_unreachable_level_is_valid():
    data = basic()
    data["grid"][1] = ".F..G.."
    level, state = level_from_dict(data)
    assert level.start == state.anchor
