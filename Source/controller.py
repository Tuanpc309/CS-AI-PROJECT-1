"""Điều phối phiên chơi. Không vẽ giao diện và không tự cài luật game."""
from __future__ import annotations

from pathlib import Path
from time import monotonic

from engine import is_goal, transition
from loader import load_level
from models import (Action, Algorithm, CostPolicy, Level, SearchConfig, SearchResult,
                    SearchStatus, SessionPhase, State, TransitionStatus)
from worker import SearchJob, start_search


REASON_TEXT = {
    "OUT_OF_BOUNDS": "Khối đã ra ngoài bàn.",
    "VOID": "Một phần khối nằm trên khoảng trống.",
    "BRIDGE_DISABLED": "Cầu chưa bật hoặc đã bị tắt dưới khối.",
    "FRAGILE_UPRIGHT": "Khối đứng trên ô fragile và bị rơi.",
    "CUBE_OVERLAP": "Hai cube không được chồng lên cùng ô.",
    "SWITCH_REQUIRES_SPLIT": "Chỉ đổi cube khi khối đã được tách.",
    "TERMINAL_STATE": "Màn đã hoàn thành; hãy chọn màn hoặc Restart.",
    "UNKNOWN_ACTION": "Thao tác không hợp lệ.",
    "BRIDGE_FLAGS_MISMATCH": "Trạng thái cầu không khớp cấu hình màn.",
    "SPLIT_NOT_CANONICAL": "Hai cube kề nhau phải được ghép thành khối.",
    "INVALID_STATE": "Dữ liệu trạng thái không hợp lệ.",
    "INVALID_MERGED_STATE": "Dữ liệu khối chưa tách không hợp lệ.",
    "INVALID_SPLIT_STATE": "Dữ liệu hai cube không hợp lệ.",
    "INVALID_BRIDGE_FLAGS": "Dữ liệu cầu không hợp lệ.",
    "INVALID_COORDINATES": "Tọa độ khối không hợp lệ.",
}


class GameController:
    def __init__(self) -> None:
        self.level: Level | None = None
        self.initial_state: State | None = None
        self.current_state: State | None = None
        self.level_path: Path | None = None
        self.phase = SessionPhase.PLAYING
        self.message = "Chọn một màn để bắt đầu."
        self.action_count = 0
        self.last_result: SearchResult | None = None
        self.solution_snapshot: State | None = None
        self.last_events: tuple = ()
        self._request_id = 0
        self._job: SearchJob | None = None
        self._retired_jobs: list[SearchJob] = []
        self._replay_index = 0
        self._next_replay_at = 0.0
        self._solution_action_count = 0

    @property
    def busy(self) -> bool:
        return self.phase in (SessionPhase.SOLVING, SessionPhase.REPLAYING)

    @property
    def can_replay(self) -> bool:
        return bool(not self.busy and self.last_result and self.last_result.found
                    and self.solution_snapshot is not None)

    def _clear_result(self) -> None:
        self.last_result = None
        self.solution_snapshot = None
        self._replay_index = 0
        self._solution_action_count = 0

    def load(self, path: str | Path) -> bool:
        if self.busy:
            return False
        # Load xong mới đổi phiên, để file lỗi không làm mất màn đang chơi.
        level, state = load_level(path)
        self.level, self.initial_state, self.current_state = level, state, state
        self.level_path = Path(path)
        self.phase = SessionPhase.PLAYING
        self.action_count = 0
        self.last_events = ()
        self._request_id += 1
        self._clear_result()
        self.message = f"Màn {level.id}: dùng phím mũi tên; Space đổi cube sau khi tách."
        return True

    def restart(self) -> bool:
        if self.busy or self.initial_state is None:
            return False
        self.current_state = self.initial_state
        self.phase = SessionPhase.PLAYING
        self.action_count = 0
        self.last_events = ()
        self._request_id += 1
        self._clear_result()
        self.message = "Đã khôi phục toàn bộ trạng thái ban đầu."
        return True

    def handle_action(self, action: Action) -> bool:
        if self.phase != SessionPhase.PLAYING or self.level is None or self.current_state is None:
            return False
        result = transition(self.level, self.current_state, action)
        if result.status == TransitionStatus.INVALID_ACTION:
            self.message = REASON_TEXT.get(result.reason or "", result.reason or "Thao tác không áp dụng.")
            return True
        self._clear_result()
        self.last_events = result.events
        if result.status == TransitionStatus.LOSS:
            self.phase = SessionPhase.LOST
            self.message = REASON_TEXT.get(result.reason or "", result.reason or "Khối bị rơi.") + " Nhấn Restart."
        else:
            self.current_state = result.next_state
            self.action_count += 1
            if result.status == TransitionStatus.WIN:
                self.phase = SessionPhase.WON
                self.message = f"Hoàn thành màn trong {self.action_count} thao tác!"
            elif result.events:
                self.message = " · ".join(self._event_text(e.kind, e.object_id) for e in result.events)
            else:
                self.message = "Đang chơi. Mũi tên để lăn, Space đổi cube."
        return True

    @staticmethod
    def _event_text(kind: str, object_id: str) -> str:
        labels = {"SWITCH_PRESSED": "Nhấn công tắc", "BRIDGE_CHANGED": "Cầu đổi trạng thái",
                  "SPLIT": "Tách khối", "MERGE": "Ghép khối"}
        return (labels.get(kind, kind) + " " + object_id).strip()

    def begin_solve(self, algorithm: Algorithm, policy: CostPolicy = CostPolicy.UNIT,
                    config: SearchConfig | None = None) -> bool:
        if self.busy or self.phase == SessionPhase.LOST or self.level is None or self.current_state is None:
            return False
        self._clear_result()
        self.solution_snapshot = self.current_state
        self._solution_action_count = self.action_count
        self._request_id += 1
        actual_config = config or SearchConfig(cost_policy=policy)
        try:
            self._job = start_search(self._request_id, self.level, self.current_state, algorithm, actual_config)
        except Exception as exc:
            self.solution_snapshot = None
            self.message = f"Không khởi động được solver: {exc}"
            return True
        self.phase = SessionPhase.SOLVING
        self.message = f"Đang giải bằng {algorithm.value.replace('ASTAR', 'A*')} từ trạng thái hiện tại…"
        return True

    def poll_solver(self) -> bool:
        self._retired_jobs = [job for job in self._retired_jobs if not job.reap()]
        if self._job is None:
            return False
        item = self._job.poll()
        if item is None:
            return False
        self._retired_jobs.append(self._job)
        self._job = None
        request_id, result = item
        if request_id != self._request_id:
            return False
        self._accept_result(result)
        return True

    def _accept_result(self, result: SearchResult) -> None:
        self.last_result = result
        self.phase = SessionPhase.WON if self.level and self.current_state and is_goal(self.level, self.current_state) else SessionPhase.PLAYING
        if result.status == SearchStatus.FOUND:
            self.message = f"Tìm thấy lời giải: {result.solution_length} thao tác, cost {result.solution_cost}. Nhấn Replay để xem."
        elif result.status == SearchStatus.NO_SOLUTION:
            self.message = "Đã duyệt hết: không có lời giải từ trạng thái này."
        elif result.status == SearchStatus.TIMEOUT:
            self.message = "Hết ngân sách thời gian; chưa thể kết luận màn vô nghiệm."
        elif result.status == SearchStatus.MEMORY_LIMIT:
            self.message = "Đạt ngưỡng bộ nhớ; chưa thể kết luận màn vô nghiệm."
        else:
            self.message = "Solver gặp lỗi: " + str(result.metadata.get("message", "Xem dữ liệu lỗi."))

    def begin_replay(self) -> bool:
        if not self.can_replay:
            return False
        self.current_state = self.solution_snapshot
        self.action_count = self._solution_action_count
        self.last_events = ()
        self._replay_index = 0
        self._next_replay_at = monotonic()
        self.phase = SessionPhase.REPLAYING
        self.message = "Đang phát lại lời giải…"
        return True

    def advance_replay(self, now: float | None = None) -> bool:
        if self.phase != SessionPhase.REPLAYING or self.last_result is None:
            return False
        actual_now = monotonic() if now is None else now
        if actual_now < self._next_replay_at:
            return False
        assert self.level is not None and self.current_state is not None
        actions = self.last_result.actions
        if self._replay_index >= len(actions):
            if is_goal(self.level, self.current_state):
                self.phase = SessionPhase.WON
                self.message = "Replay hoàn tất: khối đã vào goal."
            else:
                self.phase = SessionPhase.PLAYING
                self.message = "Lỗi replay: chuỗi action không kết thúc tại goal."
                self._clear_result()
            return True
        result = transition(self.level, self.current_state, actions[self._replay_index])
        if result.status not in (TransitionStatus.VALID, TransitionStatus.WIN) or result.next_state is None:
            self.phase = SessionPhase.PLAYING
            reason = REASON_TEXT.get(result.reason or "", result.reason or "Action không hợp lệ.")
            self.message = f"Lỗi replay ở bước {self._replay_index + 1}: {reason}"
            self._clear_result()
            return True
        self.current_state = result.next_state
        self.action_count += 1
        self.last_events = result.events
        self._replay_index += 1
        self._next_replay_at = actual_now + .25
        self.message = f"Replay {self._replay_index}/{len(actions)}: {actions[self._replay_index - 1].value}"
        return True

    def close(self) -> None:
        if self._job:
            self._job.stop()
            self._retired_jobs.append(self._job)
            self._job = None
        for job in self._retired_jobs:
            job.stop()
            # Đóng cửa sổ là lúc duy nhất chờ ngắn để dọn child process.
            job.process.join(timeout=.3)
            job.reap()
        self._retired_jobs.clear()
