"""Public API: solve(level, start_state, algorithm, config) -> SearchResult."""
from __future__ import annotations

from engine import validate_state
from models import Algorithm, Level, SearchConfig, SearchResult, SearchStatus, State
from .common import BudgetExceeded, SearchSession, normalize_algorithm, step_cost
from . import astar, bfs, dfs, ucs


def solve(level: Level, start_state: State, algorithm: Algorithm | str,
          config: SearchConfig | None = None) -> SearchResult:
    """Chạy đúng một thuật toán, trả status kể cả khi có lỗi hoặc hết ngân sách.

    Chạy mỗi lượt trong process mới khi đo chính thức. Không chia sẻ cache
    heuristic hoặc frontier giữa các lời gọi.
    """
    config = config if config is not None else SearchConfig()
    try:
        selected_algorithm = normalize_algorithm(algorithm)
        session = SearchSession(level, start_state, selected_algorithm, config)
    except Exception as error:
        return SearchResult(SearchStatus.ERROR, metadata={
            "message": str(error), "error_type": type(error).__name__,
            "algorithm": str(algorithm), "cost_policy": str(config.cost_policy),
            "metrics_available": False,
        })
    try:
        session.check_budget(check_memory=True)
        reason = validate_state(level, start_state)
        if reason is not None:
            raise ValueError(f"Start state không hợp lệ: {reason}")
        implementations = {
            Algorithm.BFS: bfs.search, Algorithm.DFS: dfs.search,
            Algorithm.UCS: ucs.search, Algorithm.ASTAR: astar.search,
        }
        status, goal = implementations[selected_algorithm](session)
        return session.finish(status, goal)
    except BudgetExceeded as error:
        return session.finish(error.status, message=str(error))
    except Exception as error:
        return session.finish(SearchStatus.ERROR, message=str(error), error_type=type(error).__name__)


__all__ = ["solve", "step_cost"]
