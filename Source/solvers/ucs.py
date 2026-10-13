"""UCS tự cài: ưu tiên g, cập nhật best_g và bỏ entry heap lỗi thời."""
import heapq
from itertools import count

from engine import is_goal
from models import SearchStatus, State
from .common import SearchSession


def search(session: SearchSession) -> tuple[SearchStatus, State | None]:
    tie_breaker = count()
    frontier = [(0, next(tie_breaker), session.start)]
    best_g = {session.start: 0}
    while frontier:
        session.check_budget()
        g, _, state = heapq.heappop(frontier)
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
                heapq.heappush(frontier, (new_g, next(tie_breaker), child))
    return SearchStatus.NO_SOLUTION, None
