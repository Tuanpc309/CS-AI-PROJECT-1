"""Chạy các lượt độc lập, kiểm tra replay rồi ghi CSV và môi trường thực tế.

Từ Source: python -m experiments.run_all --output ../results/raw
Mặc định 12 màn × (4 UNIT + 2 weighted) × 3 lượt = 216 lượt.
Có thể chạy nhanh: --levels basic_01 split_01 --runs 1 --algorithms BFS ASTAR
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import importlib.metadata
import json
import multiprocessing as mp
from pathlib import Path
import platform
from queue import Empty
import sys
from time import monotonic

from engine import is_goal, transition
from loader import load_level
from models import (
    Action, Algorithm, CostPolicy, Level, SearchConfig, SearchResult,
    SearchStatus, State, TransitionStatus,
)
from solvers.common import normalize_algorithm, step_cost

SOURCE_DIR = Path(__file__).resolve().parents[1]
LEVEL_IDS = (
    "basic_01", "basic_02", "fragile_01", "fragile_02", "switch_01", "switch_02",
    "split_01", "split_02", "combined_01", "combined_02", "no_solution_01", "no_solution_02",
)
CSV_FIELDS = (
    "level_id", "group", "algorithm", "run_id", "expected_status", "status",
    "preprocessing_time_s", "search_time_s", "total_time_s", "peak_memory_bytes",
    "expanded_nodes", "solution_length", "movement_count", "selection_count",
    "solution_cost", "cost_policy", "heuristic",
)


def verify_solution(level: Level, start_state: State, result: SearchResult,
                    policy: CostPolicy) -> str | None:
    """Chạy lại qua engine sau phép đo; không tin lời giải chỉ vì status FOUND."""
    if result.status != SearchStatus.FOUND:
        return None
    state = start_state
    cost = 0
    for index, action in enumerate(result.actions):
        step = transition(level, state, action)
        if step.status not in (TransitionStatus.VALID, TransitionStatus.WIN) or step.next_state is None:
            return f"Replay lỗi ở action {index + 1}: {action.value}, {step.status.value}."
        cost += step_cost(level, state, action, step.next_state, step.events, policy)
        state = step.next_state
    if not is_goal(level, state):
        return "Replay không kết thúc ở goal."
    selection_count = sum(action == Action.SWITCH for action in result.actions)
    if (result.solution_length != len(result.actions)
            or result.selection_count != selection_count
            or result.movement_count != len(result.actions) - selection_count
            or result.solution_cost != cost):
        return "Length/count/cost trong SearchResult không khớp replay."
    return None


def run_once(level: Level, start_state: State, algorithm: Algorithm,
             config: SearchConfig, request_id: str) -> SearchResult:
    """Process mới cho mỗi lượt; time của process startup không nằm trong metrics."""
    from worker import search_worker
    context = mp.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=search_worker,
                              args=(request_id, level, start_state, algorithm, config, queue))
    result: SearchResult | None = None
    # Guard bên ngoài để không treo nếu worker hỏng. Đây không là search time.
    guard_deadline = monotonic() + config.time_limit_seconds + 15.0
    try:
        process.start()
        while result is None:
            try:
                received_id, received_result = queue.get(timeout=0.2)
                if received_id != request_id or not isinstance(received_result, SearchResult):
                    result = SearchResult(SearchStatus.ERROR, metadata={
                        "message": "Worker trả kết quả sai hợp đồng queue.",
                        "metrics_available": False,
                    })
                else:
                    result = received_result
            except Empty:
                if not process.is_alive():
                    result = SearchResult(SearchStatus.ERROR, metadata={
                        "message": f"Worker kết thúc nhưng không trả kết quả; exit code {process.exitcode}.",
                        "metrics_available": False,
                    })
                elif monotonic() > guard_deadline:
                    result = SearchResult(SearchStatus.TIMEOUT, metadata={
                        "message": "Guard đã dừng worker không phản hồi; chưa thu được metrics.",
                        "outer_guard": True, "metrics_available": False,
                    })
    except Exception as error:
        result = SearchResult(SearchStatus.ERROR, metadata={
            "message": f"Không chạy được worker: {error}",
            "error_type": type(error).__name__, "metrics_available": False,
        })
    finally:
        if process.pid is not None:
            process.join(timeout=2.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=2.0)
        process.close()
        queue.close()
        queue.join_thread()
    assert result is not None
    reason = verify_solution(level, start_state, result, CostPolicy(config.cost_policy))
    if reason:
        result = replace(result, status=SearchStatus.ERROR, actions=(), solution_length=None,
                         movement_count=None, selection_count=None, solution_cost=None,
                         metadata={**result.metadata, "message": reason, "replay_verified": False})
    elif result.status == SearchStatus.FOUND:
        result = replace(result, metadata={**result.metadata, "replay_verified": True})
    return result


def expected_status(level_id: str) -> SearchStatus:
    if level_id not in LEVEL_IDS:
        raise ValueError(f"Chưa có expected_status độc lập cho màn {level_id!r}; bổ sung manifest trước khi đo.")
    return SearchStatus.NO_SOLUTION if level_id.startswith("no_solution_") else SearchStatus.FOUND


def row_from_result(level: Level, algorithm: Algorithm, policy: CostPolicy,
                    run_id: int, result: SearchResult) -> dict:
    group = "no_solution" if level.id.startswith("no_solution_") else level.id.rsplit("_", 1)[0]
    measured = result.metadata.get("metrics_available", True)
    return {
        "level_id": level.id, "group": group, "algorithm": algorithm.value,
        "run_id": run_id, "expected_status": expected_status(level.id).value,
        "status": result.status.value,
        "preprocessing_time_s": result.preprocessing_time_seconds if measured else None,
        "search_time_s": result.search_time_seconds if measured else None,
        "total_time_s": result.total_time_seconds if measured else None,
        "peak_memory_bytes": result.peak_memory_bytes if measured else None,
        "expanded_nodes": result.expanded_nodes if measured else None, "solution_length": result.solution_length,
        "movement_count": result.movement_count, "selection_count": result.selection_count,
        "solution_cost": result.solution_cost, "cost_policy": policy.value,
        "heuristic": "RELAXED_CELL_DISTANCE" if algorithm == Algorithm.ASTAR else "NONE",
    }


def environment_metadata(args: argparse.Namespace, configurations: list[tuple[Algorithm, CostPolicy]],
                         paths: list[Path]) -> dict:
    packages = {}
    for name in ("matplotlib", "pytest"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version, "python_executable": sys.executable,
        "platform": platform.platform(), "machine": platform.machine(),
        "processor": platform.processor(), "packages": packages,
        "memory_measurement": "peak Python allocations measured by tracemalloc.start(1), not total process RAM",
        "timing": "perf_counter; total=preprocessing+search; excludes spawn/load/replay",
        "expanded_definition": "valid non-goal pop that generates successors; stale heap entries excluded",
        "runs_per_configuration": args.runs, "time_limit_seconds": args.time_limit,
        "memory_limit_bytes": int(args.memory_limit_mib * 1024 * 1024),
        "memory_check_interval": 256, "process_start_method": "spawn",
        "levels": [path.name for path in paths],
        "configurations": [{"algorithm": alg.value, "cost_policy": policy.value}
                           for alg, policy in configurations],
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=SOURCE_DIR.parent / "results" / "raw")
    parser.add_argument("--levels", nargs="+", default=list(LEVEL_IDS), help="IDs hoặc đường dẫn JSON trong bộ 12 màn")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--algorithms", nargs="+", default=[alg.value for alg in Algorithm])
    parser.add_argument("--policies", nargs="+", default=[policy.value for policy in CostPolicy])
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--memory-limit-mib", type=float, default=256.0)
    args = parser.parse_args(argv)
    if args.runs < 1 or args.time_limit <= 0 or args.memory_limit_mib <= 0:
        parser.error("runs phải >= 1; các ngân sách phải > 0.")
    try:
        algorithms = list(dict.fromkeys(normalize_algorithm(value) for value in args.algorithms))
        policies = list(dict.fromkeys(CostPolicy(value.upper()) for value in args.policies))
    except ValueError as error:
        parser.error(str(error))
    configurations = [(alg, policy) for policy in policies for alg in algorithms
                      if policy == CostPolicy.UNIT or alg in (Algorithm.UCS, Algorithm.ASTAR)]
    if not configurations:
        parser.error("Weighted benchmark chỉ chạy UCS/A*; cấu hình đang chọn không có lượt phù hợp.")
    paths = []
    levels = []
    for value in args.levels:
        candidate = Path(value)
        path = candidate if candidate.is_file() else SOURCE_DIR / "levels" / f"{candidate.stem}.json"
        if not path.is_file():
            parser.error(f"Không tìm thấy màn: {path}")
        try:
            level, start = load_level(path)
            expected_status(level.id)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        paths.append(path.resolve())
        levels.append((level, start))
    args.output.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output / "metadata.json"
    metadata_path.write_text(json.dumps(environment_metadata(args, configurations, paths),
                                        ensure_ascii=False, indent=2), encoding="utf-8")
    config_base = {
        "time_limit_seconds": args.time_limit,
        "memory_limit_bytes": int(args.memory_limit_mib * 1024 * 1024),
        "measure_memory": True,
    }
    total_runs = len(levels) * len(configurations) * args.runs
    unexpected_count = 0
    run_details = []
    with (args.output / "runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        counter = 0
        for level, start in levels:
            for algorithm, policy in configurations:
                config = SearchConfig(cost_policy=policy, **config_base)
                for run_id in range(1, args.runs + 1):
                    counter += 1
                    request_id = f"{level.id}:{algorithm.value}:{policy.value}:{run_id}"
                    result = run_once(level, start, algorithm, config, request_id)
                    writer.writerow(row_from_result(level, algorithm, policy, run_id, result))
                    handle.flush()
                    unexpected_count += result.status != expected_status(level.id)
                    run_details.append({"request_id": request_id, "metadata": result.metadata,
                                        "actions": [action.value for action in result.actions]})
                    metric_text = (f"{result.total_time_seconds:.6f}s, expanded={result.expanded_nodes}"
                                   if result.metadata.get("metrics_available", True) else "metrics unavailable")
                    print(f"[{counter}/{total_runs}] {request_id}: {result.status.value}, {metric_text}", flush=True)
    (args.output / "run_details.json").write_text(json.dumps(run_details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã ghi {total_runs} lượt vào {args.output.resolve()}; {unexpected_count} lượt trái dự kiến.")
    return 1 if unexpected_count else 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
