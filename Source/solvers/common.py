"""Phần dùng chung: cost, truy vết, ngân sách và phép đo cho bốn solver.

Thuật toán chọn node nằm ở từng file riêng. Module này không tự quyết định
nước đi hợp lệ: mọi successor đều được hỏi qua Game Engine.
"""
from __future__ import annotations

from time import perf_counter
import tracemalloc
from typing import Iterable

from engine import available_actions, occupied_cells, state_key, transition
from models import (
    Action, Algorithm, CostPolicy, GameEvent, Level, SearchConfig, SearchResult,
    SearchStatus, State, TransitionStatus,
)


class BudgetExceeded(Exception):
    """Dừng có kiểm soát, khác với lỗi chương trình hoặc màn vô nghiệm."""

    def __init__(self, status: SearchStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


def normalize_algorithm(algorithm: Algorithm | str) -> Algorithm:
    if isinstance(algorithm, Algorithm):
        return algorithm
    name = str(algorithm).strip().upper()
    if name in {"A*", "A_STAR", "A-STAR"}:
        name = "ASTAR"
    return Algorithm(name)


def step_cost(level: Level, state: State, action: Action, next_state: State,
              events: Iterable[GameEvent] = (),
              policy: CostPolicy = CostPolicy.UNIT) -> int:
    """Phạt 3 khi bước mới chiếm fragile, chỉ phạt một lần mỗi action.

    SWITCH luôn có cost 1. Không phạt ô fragile mà cube kia đứng yên trên đó.
    events có trong API để cùng hợp đồng, policy này chỉ dùng footprint.
    """
    selected_policy = CostPolicy(policy)
    if selected_policy == CostPolicy.UNIT or action == Action.SWITCH:
        return 1
    newly_occupied = set(occupied_cells(next_state)) - set(occupied_cells(state))
    return 3 if any(level.tile_at(cell) == "O" for cell in newly_occupied) else 1


class SearchSession:
    """Dữ liệu riêng một lượt, không cache hoặc chia sẻ giữa các thuật toán.

    tracemalloc là công cụ cấp tiến trình. GUI/benchmark gọi solve trong
    process riêng; không gọi nhiều solve đồng thời trong cùng tiến trình.
    """

    def __init__(self, level: Level, start: State, algorithm: Algorithm,
                 config: SearchConfig) -> None:
        self.level = level
        self.start = state_key(start)
        self.algorithm = algorithm
        self.config = config
        self.policy = CostPolicy(config.cost_policy)
        self.expanded = 0
        self.preprocessing_seconds = 0.0
        self.search_seconds = 0.0
        self.phase = "search"
        self.tracing = bool(config.measure_memory)
        if self.tracing:
            # Một phép đo độc lập; worker không bật tracing trước solve.
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            tracemalloc.start(1)
        self.started = self.phase_started = perf_counter()
        self.parents: dict[State, tuple[State, Action, int] | None] = {}
        self.parents[self.start] = None

    def _close_phase(self) -> None:
        now = perf_counter()
        elapsed = now - self.phase_started
        if self.phase == "preprocessing":
            self.preprocessing_seconds += elapsed
        else:
            self.search_seconds += elapsed
        self.phase_started = now

    def begin_preprocessing(self) -> None:
        self._close_phase()
        self.phase = "preprocessing"

    def end_preprocessing(self) -> None:
        self._close_phase()
        self.phase = "search"

    def check_budget(self, check_memory: bool = False) -> None:
        """Time mỗi pop; memory mỗi chu kỳ và trong tiền xử lý."""
        if perf_counter() - self.started >= self.config.time_limit_seconds:
            raise BudgetExceeded(SearchStatus.TIMEOUT, "Đã vượt ngân sách thời gian tìm kiếm.")
        if check_memory and self.tracing:
            peak = tracemalloc.get_traced_memory()[1]
            if peak > self.config.memory_limit_bytes:
                raise BudgetExceeded(SearchStatus.MEMORY_LIMIT, "Đã vượt ngân sách bộ nhớ Python được theo dõi.")

    def expand(self) -> None:
        next_expanded = self.expanded + 1
        if next_expanded % self.config.memory_check_interval == 0:
            self.check_budget(check_memory=True)
        # Nếu ngân sách chặn trước khi sinh successors, node chưa được đếm.
        self.expanded = next_expanded

    def successors(self, state: State, reverse: bool = False):
        actions = available_actions(state)
        if reverse:
            actions = reversed(actions)
        for action in actions:
            result = transition(self.level, state, action)
            if result.status in (TransitionStatus.VALID, TransitionStatus.WIN):
                if result.next_state is None:
                    raise RuntimeError("Engine trả VALID/WIN nhưng thiếu next_state.")
                child = state_key(result.next_state)
                cost = step_cost(self.level, state, action, child, result.events, self.policy)
                yield action, child, cost

    def remember(self, parent: State, action: Action, child: State, cost: int) -> None:
        self.parents[child] = (parent, action, cost)

    def finish(self, status: SearchStatus, goal: State | None = None,
               message: str = "", error_type: str | None = None) -> SearchResult:
        actions: tuple[Action, ...] = ()
        solution_cost: int | None = None
        if status == SearchStatus.FOUND:
            if goal is None:
                raise RuntimeError("Kết quả FOUND cần có goal state.")
            reversed_actions: list[Action] = []
            solution_cost = 0
            cursor = goal
            while self.parents[cursor] is not None:
                parent, action, cost = self.parents[cursor]  # type: ignore[misc]
                reversed_actions.append(action)
                solution_cost += cost
                cursor = parent
            actions = tuple(reversed(reversed_actions))
        # Truy vết cũng thuộc search time và ngân sách.
        if status in (SearchStatus.FOUND, SearchStatus.NO_SOLUTION):
            self.check_budget(check_memory=True)
        self._close_phase()
        peak = tracemalloc.get_traced_memory()[1] if self.tracing else 0
        if self.tracing:
            tracemalloc.stop()
        messages = {
            SearchStatus.FOUND: "Đã tìm thấy lời giải.",
            SearchStatus.NO_SOLUTION: "Đã duyệt hết không gian đạt tới được; màn không có lời giải.",
        }
        metadata = {
            "algorithm": self.algorithm.value,
            "cost_policy": self.policy.value,
            "heuristic": "RELAXED_CELL_DISTANCE" if self.algorithm == Algorithm.ASTAR else "NONE",
            "message": message or messages.get(status, status.value),
            "time_limit_seconds": self.config.time_limit_seconds,
            "memory_limit_bytes": self.config.memory_limit_bytes,
            "memory_check_interval": self.config.memory_check_interval,
            "memory_measurement": "peak Python allocations measured by tracemalloc" if self.tracing else "disabled",
            "metrics_available": True,
        }
        if error_type:
            metadata["error_type"] = error_type
        found = status == SearchStatus.FOUND
        selection_count = sum(action == Action.SWITCH for action in actions) if found else None
        return SearchResult(
            status=status, actions=actions,
            preprocessing_time_seconds=self.preprocessing_seconds,
            search_time_seconds=self.search_seconds,
            total_time_seconds=self.preprocessing_seconds + self.search_seconds,
            peak_memory_bytes=peak, expanded_nodes=self.expanded,
            solution_length=len(actions) if found else None,
            movement_count=len(actions) - selection_count if found else None,
            selection_count=selection_count, solution_cost=solution_cost,
            metadata=metadata,
        )
