"""BFS tự cài: FIFO và visited khi enqueue, tối ưu tổng số actions."""
from collections import deque

from engine import is_goal
from models import SearchStatus, State
from .common import SearchSession


def search(session: SearchSession) -> tuple[SearchStatus, State | None]:
    frontier = deque([session.start])
    visited = {session.start}
    while frontier:
        session.check_budget()
        state = frontier.popleft()
        if is_goal(session.level, state):
            return SearchStatus.FOUND, state
        session.expand()
        for action, child, cost in session.successors(state):
            if child not in visited:
                visited.add(child)
                session.remember(state, action, child, cost)
                frontier.append(child)
    return SearchStatus.NO_SOLUTION, None
