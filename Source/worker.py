"""Chạy solver ở process riêng; không import hoặc thao tác Tkinter."""
from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass
from queue import Empty
from time import monotonic
from typing import Any

from models import Algorithm, Level, SearchConfig, SearchResult, SearchStatus, State


def search_worker(request_id: int, level: Level, state: State,
                  algorithm: Algorithm, config: SearchConfig, output_queue: Any) -> None:
    """Hàm cấp module để Windows spawn có thể import lại một cách an toàn."""
    try:
        from solvers import solve
        result = solve(level, state, algorithm, config)
    except Exception as exc:
        result = SearchResult(SearchStatus.ERROR, metadata={
            "message": f"{type(exc).__name__}: {exc}", "metrics_available": False})
    output_queue.put((request_id, result))


@dataclass
class SearchJob:
    request_id: int
    process: Any
    queue: Any
    started_at: float
    time_limit: float
    empty_exit_polls: int = 0
    stopped: bool = False
    reaped: bool = False

    def poll(self) -> tuple[int, SearchResult] | None:
        if self.reaped:
            return None
        try:
            item = self.queue.get_nowait()
            if (not isinstance(item, tuple) or len(item) != 2
                    or item[0] != self.request_id or not isinstance(item[1], SearchResult)):
                return self.request_id, SearchResult(SearchStatus.ERROR, metadata={
                    "message": "Worker trả dữ liệu sai hợp đồng.", "metrics_available": False})
            return item
        except Empty:
            pass
        # Cho queue feeder vài lượt event loop để bàn giao sau khi process kết thúc.
        if not self.process.is_alive() and self.process.exitcode is not None:
            self.empty_exit_polls += 1
            if self.empty_exit_polls >= 5:
                return self.request_id, SearchResult(SearchStatus.ERROR, metadata={
                    "message": f"Worker kết thúc không trả kết quả (exit={self.process.exitcode}).",
                    "metrics_available": False})
        if monotonic() - self.started_at > self.time_limit + 15:
            self.stop()
            return self.request_id, SearchResult(SearchStatus.TIMEOUT, metadata={
                "message": "Worker vượt thời gian chờ bảo vệ; chưa có số liệu tìm kiếm hoàn chỉnh.",
                "metrics_available": False})
        return None

    def stop(self) -> None:
        if self.reaped:
            return
        if self.process.is_alive():
            self.process.terminate()
        self.stopped = True

    def reap(self) -> bool:
        """Không chặn event loop: chỉ dọn handle khi process đã kết thúc."""
        if self.reaped:
            return True
        if self.process.is_alive():
            return False
        self.process.join(timeout=0)
        self.queue.close()
        self.queue.cancel_join_thread()
        self.process.close()
        self.reaped = True
        return True


def start_search(request_id: int, level: Level, state: State,
                 algorithm: Algorithm, config: SearchConfig) -> SearchJob:
    context = mp.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=search_worker,
        args=(request_id, level, state, algorithm, config, queue), daemon=True)
    try:
        process.start()
    except Exception:
        queue.close()
        process.close()
        raise
    return SearchJob(request_id, process, queue, monotonic(), config.time_limit_seconds)
