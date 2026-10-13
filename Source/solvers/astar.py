"""A* tự cài: f=g+h, best_g, tie counter và reopen khi có g tốt hơn."""
import heapq
from itertools import count

from engine import is_goal
from models import SearchStatus, State
from .common import SearchSession
from .heuristics import RelaxedCellDistance


def search(session: SearchSession) -> tuple[SearchStatus, State | None]:
    session.begin_preprocessing()
    heuristic = RelaxedCellDistance(session.level, session.check_budget)
    session.end_preprocessing()
    tie_breaker = count()
    frontier = [(heuristic(session.start), next(tie_breaker), 0, session.start)]
    best_g = {session.start: 0}
    # Không dùng closed-set để chặn reopen: một đường có g nhỏ hơn luôn cập nhật.
    while frontier:
        session.check_budget()
        _, _, g, state = heapq.heappop(frontier)
        if g != best_g[state]:
            continue
        if is_goal(session.level, state):
            return SearchStatus.FOUND, state
        session.expand()
        for action, child, cost in session.successors(state):
            new_g = g + cost
            if new_g < best_g.get(child, float("inf")):
                best_g[child] = new_g
                session.remember(state, action, child, cost)
                heapq.heappush(frontier, (new_g + heuristic(child), next(tie_breaker), new_g, child))
    return SearchStatus.NO_SOLUTION, None
