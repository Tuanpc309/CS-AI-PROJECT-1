"""Kiểm tra Windows spawn thật, chuyển kết quả và đóng child process."""
from pathlib import Path
from time import monotonic, sleep

import pytest

from loader import load_level
from models import Algorithm, SearchConfig, SearchStatus
from worker import start_search


@pytest.mark.parametrize("algorithm", list(Algorithm))
def test_spawn_worker_returns_verified_basic_solution_and_reaps(algorithm):
    path = Path(__file__).resolve().parents[1] / "levels" / "basic_01.json"
    level, state = load_level(path)
    job = start_search(17, level, state, algorithm, SearchConfig())
    try:
        deadline = monotonic() + 15
        item = None
        while item is None and monotonic() < deadline:
            item = job.poll()
            sleep(.01)
        assert item is not None, "Worker không phản hồi"
        request_id, result = item
        assert request_id == 17
        assert result.status == SearchStatus.FOUND
        assert result.solution_length == 2
        job.process.join(timeout=3)
        assert job.reap()
        assert job.reap()  # cleanup an toàn nếu được gọi lại
        assert job.poll() is None
    finally:
        job.stop()
        if not job.reaped:
            job.process.join(timeout=3)
            job.reap()
