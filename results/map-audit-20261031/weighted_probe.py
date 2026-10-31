"""Two explanatory weighted-cost probes after the UNIT audit, fresh processes."""
from dataclasses import asdict
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Source"))
from experiments.run_all import run_once
from loader import load_level
from models import Algorithm, CostPolicy, SearchConfig
from webapp import Catalog


def main():
    catalog = Catalog()
    config = SearchConfig(cost_policy=CostPolicy.FRAGILE_PENALTY, time_limit_seconds=5,
                          memory_limit_bytes=256 * 1024 ** 2, measure_memory=True)
    records = {}
    for key in ("fragile_02", "campaign_30"):
        level, state = load_level(catalog.paths[key])
        records[key] = {}
        for algorithm in Algorithm:
            result = run_once(level, state, algorithm, config, f"weighted-{key}-{algorithm.value}")
            records[key][algorithm.value] = asdict(result)
            print(key, algorithm.value, result.status.value, result.solution_length, result.solution_cost,
                  result.expanded_nodes, flush=True)
    Path(__file__).with_name("weighted-probes.json").write_text(json.dumps({
        "config": asdict(config), "note": "One exploratory fresh-process run per configuration; FOUND replay-verified.",
        "levels": records}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
