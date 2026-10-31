"""DFS iterative: tránh recursion và lưu full-state visited khi push."""
from engine import is_goal
from models import SearchStatus, State
from .common import SearchSession


def search(session: SearchSession) -> tuple[SearchStatus, State | None]:
    frontier = [session.start]
    visited = {session.start}
    while frontier:
        session.check_budget()
        state = frontier.pop()
        if is_goal(session.level, state):
            return SearchStatus.FOUND, state
        session.expand()
        # Đảo thứ tự push để ưu tiên pop UP, DOWN, LEFT, RIGHT, SWITCH.
        for action, child, cost in session.successors(state, reverse=True):
            if child not in visited:
                visited.add(child)
                session.remember(state, action, child, cost)
                frontier.append(child)
    return SearchStatus.NO_SOLUTION, None
