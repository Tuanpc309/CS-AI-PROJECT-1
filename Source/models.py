"""Dữ liệu chung: engine, solver và GUI dùng cùng các kiểu bất biến."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

Coord = tuple[int, int]


class Mode(str, Enum):
    MERGED = "MERGED"
    SPLIT = "SPLIT"


class Orientation(str, Enum):
    U = "U"
    H = "H"
    V = "V"


class Action(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    SWITCH = "SWITCH"


class SwitchType(str, Enum):
    SOFT = "SOFT"
    HEAVY = "HEAVY"
    SPLIT = "SPLIT"


class EffectOperation(str, Enum):
    TOGGLE = "TOGGLE"
    SET_OPEN = "SET_OPEN"
    SET_CLOSED = "SET_CLOSED"


class TransitionStatus(str, Enum):
    VALID = "VALID"
    WIN = "WIN"
    LOSS = "LOSS"
    INVALID_ACTION = "INVALID_ACTION"


class SearchStatus(str, Enum):
    FOUND = "FOUND"
    NO_SOLUTION = "NO_SOLUTION"
    TIMEOUT = "TIMEOUT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    ERROR = "ERROR"


class Algorithm(str, Enum):
    BFS = "BFS"
    DFS = "DFS"
    UCS = "UCS"
    ASTAR = "ASTAR"


class CostPolicy(str, Enum):
    UNIT = "UNIT"
    FRAGILE_PENALTY = "FRAGILE_PENALTY"


class SessionPhase(str, Enum):
    PLAYING = "PLAYING"
    WON = "WON"
    LOST = "LOST"
    SOLVING = "SOLVING"
    REPLAYING = "REPLAYING"


@dataclass(frozen=True, slots=True)
class Bridge:
    id: str
    cells: tuple[Coord, ...]
    initial_enabled: bool


@dataclass(frozen=True, slots=True)
class BridgeEffect:
    bridge_id: str
    operation: EffectOperation


@dataclass(frozen=True, slots=True)
class Switch:
    id: str
    cell: Coord
    type: SwitchType
    effects: tuple[BridgeEffect, ...] = ()
    destinations: tuple[Coord, ...] = ()


@dataclass(frozen=True, slots=True)
class Level:
    id: str
    grid: tuple[str, ...]
    start: Coord
    goal: Coord
    bridges: tuple[Bridge, ...] = ()
    switches: tuple[Switch, ...] = ()

    @property
    def height(self) -> int:
        return len(self.grid)

    @property
    def width(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    def in_bounds(self, cell: Coord) -> bool:
        r, c = cell
        return 0 <= r < self.height and 0 <= c < self.width

    def tile_at(self, cell: Coord) -> str:
        return self.grid[cell[0]][cell[1]] if self.in_bounds(cell) else "."

    def bridge_index_at(self, cell: Coord) -> int | None:
        for index, bridge in enumerate(self.bridges):
            if cell in bridge.cells:
                return index
        return None


@dataclass(frozen=True, slots=True)
class State:
    mode: Mode
    anchor: Coord | None = None
    orientation: Orientation | None = None
    cubes: tuple[Coord, ...] = ()
    active_cube: int | None = None
    bridges: tuple[bool, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.bridges, tuple) or any(type(x) is not bool for x in self.bridges):
            raise ValueError("bridges phải là tuple các giá trị bool")
        if self.mode == Mode.MERGED:
            if self.anchor is None or self.orientation is None or self.cubes or self.active_cube is not None:
                raise ValueError("State MERGED cần anchor/orientation, không có cubes/active_cube")
            coords = (self.anchor,)
        elif self.mode == Mode.SPLIT:
            if self.anchor is not None or self.orientation is not None or len(self.cubes) != 2 or self.active_cube not in (0, 1):
                raise ValueError("State SPLIT cần hai cubes và active_cube 0/1")
            if self.cubes[0] == self.cubes[1]:
                raise ValueError("Hai cubes không được chồng ô")
            coords = self.cubes
        else:
            raise ValueError("Mode không hợp lệ")
        if not isinstance(self.cubes, tuple):
            raise ValueError("cubes phải là tuple")
        for cell in coords:
            if not isinstance(cell, tuple) or len(cell) != 2 or any(type(n) is not int for n in cell):
                raise ValueError("Tọa độ phải là tuple hai số nguyên")

    @classmethod
    def merged(cls, anchor: Coord, orientation: Orientation = Orientation.U,
               bridges: tuple[bool, ...] = ()) -> State:
        return cls(Mode.MERGED, anchor, orientation, bridges=bridges)

    @classmethod
    def split(cls, cubes: tuple[Coord, Coord], active_cube: int = 0,
              bridges: tuple[bool, ...] = ()) -> State:
        return cls(Mode.SPLIT, cubes=cubes, active_cube=active_cube, bridges=bridges)


@dataclass(frozen=True, slots=True)
class GameEvent:
    kind: str
    object_id: str = ""


@dataclass(frozen=True, slots=True)
class TransitionResult:
    status: TransitionStatus
    next_state: State | None = None
    reason: str | None = None
    events: tuple[GameEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchConfig:
    cost_policy: CostPolicy = CostPolicy.UNIT
    time_limit_seconds: float = 30.0
    memory_limit_bytes: int = 256 * 1024 * 1024
    measure_memory: bool = True
    memory_check_interval: int = 256

    def __post_init__(self) -> None:
        if self.time_limit_seconds < 0 or self.memory_limit_bytes < 0 or self.memory_check_interval < 1:
            raise ValueError("Ngân sách không được âm; chu kỳ kiểm tra phải >= 1")


@dataclass(frozen=True, slots=True)
class SearchResult:
    status: SearchStatus
    actions: tuple[Action, ...] = ()
    preprocessing_time_seconds: float = 0.0
    search_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
    peak_memory_bytes: int = 0
    expanded_nodes: int = 0
    solution_length: int | None = None
    movement_count: int | None = None
    selection_count: int | None = None
    solution_cost: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return self.status == SearchStatus.FOUND
