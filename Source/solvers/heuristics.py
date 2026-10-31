"""RELAXED_CELL_DISTANCE: reverse BFS trên đồ thị ô gồm cạnh teleport.

Mỗi ô không-void là một đỉnh. Cạnh bước 1/2 ô cho phép bỏ qua ô giữa.
Split thêm cạnh từ cả các ô trước nước lăn tới T, vì lăn và teleport
thuộc cùng một action. Cạnh teleport có hướng nên phải dựng reverse graph.
"""
from collections import deque
from collections.abc import Callable

from engine import occupied_cells
from models import Coord, Level, State, SwitchType

DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


class RelaxedCellDistance:
    def __init__(self, level: Level,
                 budget_check: Callable[[bool], None] | None = None) -> None:
        def check(index: int = 0) -> None:
            if budget_check is not None:
                budget_check(index % 256 == 0)

        cells: set[Coord] = set()
        scanned_tiles = 0
        for r, row in enumerate(level.grid):
            for c, tile in enumerate(row):
                if scanned_tiles % 256 == 0:
                    check(scanned_tiles)
                if tile != ".":
                    cells.add((r, c))
                scanned_tiles += 1
        if level.goal not in cells:
            raise ValueError("Goal không thuộc đồ thị ô hợp lệ.")
        reverse: dict[Coord, set[Coord]] = {}
        for index, cell in enumerate(cells):
            check(index)
            reverse[cell] = set()
        for index, (r, c) in enumerate(cells):
            check(index)
            for dr, dc in DIRECTIONS:
                for distance in (1, 2):
                    neighbor = r + dr * distance, c + dc * distance
                    if neighbor in cells:
                        reverse[neighbor].add((r, c))
        for index, switch in enumerate(level.switches):
            check(index)
            if switch.type != SwitchType.SPLIT:
                continue
            r, c = switch.cell
            predecessors = {(r, c)}
            for dr, dc in DIRECTIONS:
                for distance in (1, 2):
                    predecessors.add((r + dr * distance, c + dc * distance))
            for predecessor in predecessors & cells:
                for destination in switch.destinations:
                    if destination not in reverse:
                        raise ValueError("Đích split không thuộc bàn.")
                    reverse[destination].add(predecessor)
        distances = {level.goal: 0}
        frontier = deque([level.goal])
        visited_count = 0
        while frontier:
            check(visited_count)
            cell = frontier.popleft()
            visited_count += 1
            for predecessor in reverse[cell]:
                if predecessor not in distances:
                    distances[predecessor] = distances[cell] + 1
                    frontier.append(predecessor)
        check(0)
        self.unreachable_distance = len(cells)
        self.distances: dict[Coord, int] = {}
        for index, cell in enumerate(cells):
            check(index)
            self.distances[cell] = distances.get(cell, len(cells))
        check(0)

    def __call__(self, state: State) -> int:
        return max(self.distances.get(cell, self.unreachable_distance)
                   for cell in occupied_cells(state))
