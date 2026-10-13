"""Tạo bảng median và PNG, giữ rõ TIMEOUT/ERROR và màn vô nghiệm.

Từ Source:
python -m experiments.plot_results --input ../results/raw/runs.csv --output ../results
Chỉ tổng hợp metric khi đủ số lượt và tất cả khớp expected_status.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import os
from pathlib import Path
from statistics import median
import sys

from .run_all import CSV_FIELDS, LEVEL_IDS

METRICS = (
    "preprocessing_time_s", "search_time_s", "total_time_s", "peak_memory_bytes",
    "expanded_nodes", "solution_length", "movement_count", "selection_count", "solution_cost",
)
DETERMINISTIC = ("expanded_nodes", "solution_length", "movement_count", "selection_count", "solution_cost")
SUMMARY_FIELDS = (
    "level_id", "group", "algorithm", "cost_policy", "expected_status", "completion_status",
    "completed_runs", "expected_runs", "observed_runs", "status_counts", *METRICS,
    "peak_memory_mib", "heuristic",
)
ALGORITHM_ORDER = ("BFS", "DFS", "UCS", "ASTAR")
COLORS = {"BFS": "#3b82f6", "DFS": "#f59e0b", "UCS": "#10b981", "ASTAR": "#8b5cf6"}


def read_runs(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(CSV_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV thiếu các cột: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV chưa có dữ liệu lượt chạy.")
    return rows


def aggregate(rows: list[dict[str, str]], expected_runs: int) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["level_id"], row["cost_policy"], row["algorithm"]].append(row)
    summaries = []
    for (level_id, policy, algorithm), items in groups.items():
        expected_statuses = {item["expected_status"] for item in items}
        if len(expected_statuses) != 1:
            raise ValueError(f"Expected status mâu thuẫn tại {level_id}/{policy}/{algorithm}.")
        expected_status = next(iter(expected_statuses))
        counts = Counter(item["status"] for item in items)
        valid = [item for item in items if item["status"] == expected_status]
        run_ids = [int(item["run_id"]) for item in items]
        complete = (len(items) == expected_runs and len(valid) == expected_runs
                    and set(run_ids) == set(range(1, expected_runs + 1)))
        deterministic = all(len({item[metric] for item in valid}) <= 1 for metric in DETERMINISTIC)
        if complete and deterministic:
            completion = "COMPLETE"
        elif complete:
            completion = "INCONSISTENT"
        else:
            completion = "INCOMPLETE"
        result = {
            "level_id": level_id, "group": items[0]["group"], "algorithm": algorithm,
            "cost_policy": policy, "expected_status": expected_status,
            "completion_status": completion, "completed_runs": len(valid),
            "expected_runs": expected_runs, "observed_runs": len(items),
            "status_counts": "; ".join(f"{status}:{count}" for status, count in sorted(counts.items())),
            "heuristic": items[0]["heuristic"],
        }
        for metric in METRICS:
            values = [float(item[metric]) for item in items if item[metric] != ""]
            result[metric] = median(values) if completion == "COMPLETE" and len(values) == expected_runs else ""
        result["peak_memory_mib"] = result["peak_memory_bytes"] / 1024 ** 2 if result["peak_memory_bytes"] != "" else ""
        summaries.append(result)
    level_order = {level_id: index for index, level_id in enumerate(LEVEL_IDS)}
    algorithm_order = {algorithm: index for index, algorithm in enumerate(ALGORITHM_ORDER)}
    return sorted(summaries, key=lambda row: (
        row["cost_policy"], level_order.get(row["level_id"], 999), row["level_id"],
        algorithm_order.get(row["algorithm"], 999),
    ))


def write_table(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def plot_metric(rows: list[dict], metric: str, title: str, ylabel: str,
                output: Path) -> None:
    if "MPLCONFIGDIR" not in os.environ:
        config_dir = output.parent.parent / ".cache" / "matplotlib"
        config_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(config_dir.resolve())
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    level_ids = list(dict.fromkeys(row["level_id"] for row in rows))
    algorithms = [algorithm for algorithm in ALGORITHM_ORDER if any(row["algorithm"] == algorithm for row in rows)]
    if not level_ids or not algorithms:
        return
    lookup = {(row["level_id"], row["algorithm"]): row for row in rows}
    bar_width = 0.8 / len(algorithms)
    fig, axis = plt.subplots(figsize=(max(10, len(level_ids) * 1.65), 6.5), layout="constrained")
    numeric_values = [row[metric] for row in rows if row.get(metric, "") != ""]
    maximum = max(numeric_values, default=1)
    marker_height = maximum * 0.03 if maximum > 0 else 0.03
    for algorithm_index, algorithm in enumerate(algorithms):
        for level_index, level_id in enumerate(level_ids):
            x = level_index - 0.4 + bar_width * (algorithm_index + 0.5)
            row = lookup.get((level_id, algorithm))
            if row is not None and row.get(metric, "") != "":
                axis.bar(x, row[metric], width=bar_width * 0.92, color=COLORS[algorithm], zorder=3)
                continue
            if row is None:
                label = "MISSING"
            elif row["completion_status"] == "COMPLETE" and row["expected_status"] == "NO_SOLUTION":
                label = "NO SOL"
            elif row["completion_status"] == "INCONSISTENT":
                label = "UNSTABLE"
            else:
                failed = [part.split(":")[0] for part in row["status_counts"].split("; ")
                          if part.split(":")[0] != row["expected_status"]]
                label = "/".join(failed) if failed else "PARTIAL"
            # Không vẽ cột 0 cho failure: ký hiệu x và nhãn tường minh.
            axis.scatter([x], [marker_height], marker="x", color="#6b7280", s=25, zorder=4)
            axis.annotate(label, (x, marker_height), xytext=(0, 5), textcoords="offset points",
                          ha="center", va="bottom", rotation=90, fontsize=7, color="#4b5563")
    axis.set_xticks(range(len(level_ids)), [level_id.replace("_", "\n", 1) for level_id in level_ids])
    axis.set_ylabel(ylabel)
    axis.set_title(title + "\nMedian of complete runs; x = unavailable result", pad=12)
    axis.set_ylim(0, maximum * 1.22 if maximum > 0 else 1)
    axis.grid(axis="y", color="#e5e7eb", zorder=0)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(handles=[Patch(color=COLORS[algorithm], label="A*" if algorithm == "ASTAR" else algorithm)
                         for algorithm in algorithms], loc="upper left", ncol=len(algorithms))
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("../results"))
    parser.add_argument("--expected-runs", type=int, help="Override số lượt/cấu hình; mặc định đọc metadata.json")
    args = parser.parse_args(argv)
    try:
        rows = read_runs(args.input)
        metadata_path = args.input.parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        expected_runs = args.expected_runs or metadata.get("runs_per_configuration") or max(int(row["run_id"]) for row in rows)
        if expected_runs < 1:
            raise ValueError("expected-runs phải >= 1.")
        summary = aggregate(rows, expected_runs)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    tables = args.output / "tables"
    plots = args.output / "plots"
    tables.mkdir(parents=True, exist_ok=True)
    plots.mkdir(parents=True, exist_ok=True)
    unit = [row for row in summary if row["cost_policy"] == "UNIT"]
    weighted = [row for row in summary if row["cost_policy"] == "FRAGILE_PENALTY"]
    write_table(tables / "all_summary.csv", summary)
    write_table(tables / "unit_summary.csv", unit)
    write_table(tables / "weighted_summary.csv", weighted)
    plot_metric(unit, "total_time_s", "UNIT — total preprocessing + search time", "Seconds", plots / "unit_total_time.png")
    plot_metric(unit, "peak_memory_mib", "UNIT — peak tracked Python memory", "MiB (tracemalloc, not process RAM)", plots / "unit_peak_memory.png")
    plot_metric(unit, "expanded_nodes", "UNIT — expanded nodes", "Expanded nodes", plots / "unit_expanded_nodes.png")
    plot_metric(unit, "solution_length", "UNIT — solution length including SWITCH", "Actions", plots / "unit_solution_length.png")
    plot_metric(weighted, "solution_cost", "FRAGILE_PENALTY — optimal solution cost", "Cost", plots / "weighted_solution_cost.png")
    incomplete = [row for row in summary if row["completion_status"] != "COMPLETE"]
    notes = [
        "# Cách đọc kết quả thực nghiệm", "",
        f"Số lượt dự kiến mỗi cấu hình: {expected_runs}. Có {len(summary)} cấu hình, {len(incomplete)} cấu hình chưa COMPLETE.", "",
        "COMPLETE: đủ lượt, mọi status đúng expected_status, metrics xác định ổn định. Chỉ nhóm này có median.",
        "INCOMPLETE: thiếu lượt, có TIMEOUT/MEMORY_LIMIT/ERROR hoặc status trái dự kiến; xem status_counts.",
        "INCONSISTENT: các lượt hoàn tất nhưng length/cost/expanded không ổn định; điều tra trước khi dùng báo cáo.", "",
        "NO_SOLUTION đúng dự kiến là một lượt hoàn tất hợp lệ, có time/memory/expanded; length/cost để trống.",
        "Ký hiệu x trên biểu đồ không phải kết quả bằng 0. NO SOL là không tồn tại length/cost; các nhãn khác là kết quả thiếu/thất bại.",
        "Thời gian chính = preprocessing + search. Peak memory chỉ là Python allocations theo tracemalloc; không phải tổng RAM tiến trình.",
        "Các giá trị UNIT và FRAGILE_PENALTY tối ưu mục tiêu khác nhau. So UCS/A* theo cùng policy.", "",
        "Dữ liệu gốc và environment nằm trong results/raw/runs.csv, run_details.json và metadata.json.",
    ]
    (tables / "README.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(f"Đã ghi bảng vào {tables.resolve()} và PNG vào {plots.resolve()}.")
    if incomplete:
        print(f"Có {len(incomplete)} cấu hình thiếu/thất bại/không ổn định; giữ status thật và không tổng hợp median.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
