"""Exploratory map audit. Does not modify source levels or previous benchmarks."""
from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Source"))

from experiments.run_all import run_once
from loader import load_level
from models import Algorithm, CostPolicy, SearchConfig
from webapp import Catalog

OUT = Path(__file__).resolve().parent


def main():
    catalog = Catalog()
    config = SearchConfig(time_limit_seconds=5.0, memory_limit_bytes=256 * 1024 ** 2,
                          measure_memory=True)
    payload = {"metadata": {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "run_count_per_configuration": 1, "config": asdict(config),
        "measurement": "Fresh process per algorithm/level; tracemalloc enabled; solver timings exclude process startup; all FOUND paths replay-verified by experiments.run_all.run_once.",
        "caveat": "Exploratory single-run timings are not statistically conclusive. Compare expanded nodes and solution lengths first. Timeouts are not no-solution proofs.",
    }, "levels": []}
    csv_rows = []
    for index, item in enumerate(catalog.items):
        level, initial = load_level(catalog.paths[item["id"]])
        counts = {tile: sum(row.count(tile) for row in level.grid) for tile in "FOBSXTG"}
        record = {**item, "source": catalog.paths[level.id].relative_to(ROOT).as_posix(),
                  "width": level.width, "height": level.height,
                  "tile_count": sum(counts.values()), "tile_counts": counts,
                  "bridge_groups": len(level.bridges), "switch_count": len(level.switches),
                  "grid": list(level.grid), "start": list(level.start), "goal": list(level.goal),
                  "results": {}}
        for algorithm in Algorithm:
            result = run_once(level, initial, algorithm, config, f"audit-{level.id}-{algorithm.value}")
            result_dict = asdict(result)
            record["results"][algorithm.value] = result_dict
            csv_rows.append({"level_id": level.id, "title": item["title"], "collection": item["collection"],
                             "chapter": item["chapter"], "width": level.width, "height": level.height,
                             "tile_count": record["tile_count"], "algorithm": algorithm.value,
                             "cost_policy": "UNIT", "status": result.status.value,
                             "solution_length": result.solution_length, "solution_cost": result.solution_cost,
                             "expanded_nodes": result.expanded_nodes,
                             "total_time_seconds": result.total_time_seconds,
                             "search_time_seconds": result.search_time_seconds,
                             "preprocessing_time_seconds": result.preprocessing_time_seconds,
                             "peak_memory_bytes": result.peak_memory_bytes,
                             "replay_verified": result.metadata.get("replay_verified")})
        payload["levels"].append(record)
        (OUT / "audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{index+1:02}/{len(catalog.items)} {level.id}: " + ", ".join(
            f"{name} {value['status']} L={value['solution_length']} N={value['expanded_nodes']}" for name, value in record["results"].items()), flush=True)
    with (OUT / "runs.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)

    summary = {"counts": {"levels": len(payload["levels"]), "runs": len(csv_rows)}, "chapters": []}
    for chapter in range(1, 6):
        group = [item for item in payload["levels"] if item["collection"] == "campaign" and item["chapter"] == chapter]
        lengths = [item["results"]["BFS"]["solution_length"] for item in group]
        summary["chapters"].append({"chapter": chapter, "maps": len(group),
            "tiles_min": min(item["tile_count"] for item in group), "tiles_max": max(item["tile_count"] for item in group),
            "bfs_length_min": min(lengths), "bfs_length_max": max(lengths),
            "bfs_length_median": statistics.median(lengths),
            "bfs_expanded_min": min(item["results"]["BFS"]["expanded_nodes"] for item in group),
            "bfs_expanded_max": max(item["results"]["BFS"]["expanded_nodes"] for item in group),
            "astar_expanded_min": min(item["results"]["ASTAR"]["expanded_nodes"] for item in group),
            "astar_expanded_max": max(item["results"]["ASTAR"]["expanded_nodes"] for item in group),
        })
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
