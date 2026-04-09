#!/usr/bin/env python3
"""Build benchmark-aligned and adapted OffTheRails core tables."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from offtherails_pilot.prompts import REVISION_CONDITIONS
from offtherails_pilot.scoring import binary_label_from_gold_mean

SOURCE_REPO = "https://github.com/cicl-stanford/moral-evals"
DEFAULT_SOURCE_DIR = ROOT / ".cache" / "moral-evals-source"
OUTPUT_DIR = ROOT / "data"

HUMAN_CODE_MAP = {
    "causal_structure": {"cc": 1, "coc": 0},
    "evitability": {"evitable": 1, "inevitable": 0},
    "action": {"action_yes": 1, "prevention_no": 0},
}

TEXT_FACTOR_MAP = {
    "source_structure_code": {"cc": "means", "coc": "side_effect"},
    "action": {"action_yes": "commission", "prevention_no": "omission"},
}


def remap_score(value: float, target_scale_max: int) -> float:
    if target_scale_max == 5:
        return value
    if target_scale_max == 7:
        return 1.0 + (value - 1.0) * 1.5
    raise ValueError(f"unsupported target scale: 1-{target_scale_max}")


def ensure_source_repo(source_dir: Path) -> str:
    if not source_dir.exists():
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", SOURCE_REPO, str(source_dir)],
            check=True,
        )
    commit = subprocess.check_output(
        ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    return commit


def load_batch_items(source_dir: Path, target_scale_max: int) -> List[Dict[str, str]]:
    batch_dir = source_dir / "offtherails" / "prolific-exp-2"
    ratings_path = batch_dir / "data_long_format.csv"
    ratings = list(csv.DictReader(ratings_path.open(newline="", encoding="utf-8")))

    items: List[Dict[str, str]] = []
    for split in range(5):
        batch_path = batch_dir / f"batch_{split}.json"
        with batch_path.open(encoding="utf-8") as handle:
            batch_items = json.load(handle)
        for batch_item in batch_items:
            source_structure_code, evitability, action = batch_item["condition"].split("_", 2)
            matched_ratings = [
                row
                for row in ratings
                if int(row["split"]) == split
                and int(row["scenario_id"]) == int(batch_item["scenario_id"])
                and int(row["causal_structure"])
                == HUMAN_CODE_MAP["causal_structure"][source_structure_code]
                and int(row["evitability"]) == HUMAN_CODE_MAP["evitability"][evitability]
                and int(row["action"]) == HUMAN_CODE_MAP["action"][action]
            ]
            if not matched_ratings:
                raise ValueError(
                    f"No human ratings matched split={split} scenario={batch_item['scenario_id']} condition={batch_item['condition']}"
                )

            perm_ratings = [int(row["permissibility_rating"]) for row in matched_ratings]
            intent_ratings = [int(row["intention_rating"]) for row in matched_ratings]

            gold_perm_mean_raw = statistics.mean(perm_ratings)
            gold_intent_mean_raw = statistics.mean(intent_ratings)
            gold_perm_sd_raw = statistics.stdev(perm_ratings)
            gold_intent_sd_raw = statistics.stdev(intent_ratings)

            gold_perm_mean = remap_score(gold_perm_mean_raw, target_scale_max)
            gold_intent_mean = remap_score(gold_intent_mean_raw, target_scale_max)
            scale_factor = 1.0 if target_scale_max == 5 else 1.5
            gold_perm_sd = gold_perm_sd_raw * scale_factor
            gold_intent_sd = gold_intent_sd_raw * scale_factor
            gold_perm_binary, binary_eval_perm = binary_label_from_gold_mean(
                gold_perm_mean, scale_max=target_scale_max
            )
            gold_intent_binary, binary_eval_intent = binary_label_from_gold_mean(
                gold_intent_mean, scale_max=target_scale_max
            )

            agent_name = batch_item["context"].split(",", 1)[0].strip()
            scenario_text = " ".join(
                [
                    batch_item["context"].strip(),
                    batch_item["opportunity"].strip(),
                    batch_item["structure_sentence"].strip(),
                    batch_item["evitability_sentence"].strip(),
                    batch_item["action_sentence"].strip(),
                ]
            )
            items.append(
                {
                    "benchmark": "offtherails",
                    "split": "core_80",
                    "item_id": f"otr_s{int(batch_item['scenario_id']):02d}_{batch_item['condition']}",
                    "scenario_id": str(batch_item["scenario_id"]),
                    "scenario_order": str(batch_item["scenario_id"]),
                    "source_structure_code": source_structure_code,
                    "means_side_effect": TEXT_FACTOR_MAP["source_structure_code"][source_structure_code],
                    "evitability": evitability,
                    "agency_mode": TEXT_FACTOR_MAP["action"][action],
                    "severity": "mild",
                    "gold_scale_min": "1",
                    "gold_scale_max": str(target_scale_max),
                    "gold_scale_mode": "benchmark_aligned"
                    if target_scale_max == 5
                    else "adapted_rescaled",
                    "agent_name": agent_name,
                    "scenario_text": scenario_text,
                    "gold_perm_mean": f"{gold_perm_mean:.6f}",
                    "gold_perm_sd": f"{gold_perm_sd:.6f}",
                    "gold_intent_mean": f"{gold_intent_mean:.6f}",
                    "gold_intent_sd": f"{gold_intent_sd:.6f}",
                    "gold_perm_binary": "" if gold_perm_binary is None else str(gold_perm_binary),
                    "gold_intent_binary": "" if gold_intent_binary is None else str(gold_intent_binary),
                    "binary_eval_perm": str(binary_eval_perm),
                    "binary_eval_intent": str(binary_eval_intent),
                }
            )
    return sorted(items, key=lambda row: row["item_id"])


def validate_items(items: List[Dict[str, str]]) -> None:
    if len(items) != 80:
        raise ValueError(f"Expected 80 items, found {len(items)}")
    item_ids = {item["item_id"] for item in items}
    if len(item_ids) != 80:
        raise ValueError("Item IDs are not unique")

    condition_cells = {
        (
            item["means_side_effect"],
            item["evitability"],
            item["agency_mode"],
        )
        for item in items
    }
    expected_cells = {
        ("means", "evitable", "commission"),
        ("means", "evitable", "omission"),
        ("means", "inevitable", "commission"),
        ("means", "inevitable", "omission"),
        ("side_effect", "evitable", "commission"),
        ("side_effect", "evitable", "omission"),
        ("side_effect", "inevitable", "commission"),
        ("side_effect", "inevitable", "omission"),
    }
    if condition_cells != expected_cells:
        raise ValueError(f"Unexpected condition cells: {sorted(condition_cells)}")


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_provenance(path: Path, source_commit: str) -> None:
    payload = {
        "source_repo": SOURCE_REPO,
        "source_commit": source_commit,
        "source_note": "Prepared from offtherails/prolific-exp-2 batch files and human long-format ratings. This workspace writes both a benchmark-aligned 1-5 table and an adapted 1-7 rescaled table.",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    source_commit = ensure_source_repo(source_dir)
    items_1to5 = load_batch_items(source_dir, target_scale_max=5)
    items_1to7 = load_batch_items(source_dir, target_scale_max=7)
    validate_items(items_1to5)
    validate_items(items_1to7)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_DIR / "items_offtherails_core.csv", items_1to5)
    write_csv(OUTPUT_DIR / "items_offtherails_core_1to5.csv", items_1to5)
    write_csv(OUTPUT_DIR / "items_offtherails_core_1to7_adapted.csv", items_1to7)
    write_csv(OUTPUT_DIR / "revision_conditions.csv", REVISION_CONDITIONS)
    write_provenance(OUTPUT_DIR / "source_provenance.json", source_commit)
    print(f"Wrote {len(items_1to5)} items to {OUTPUT_DIR / 'items_offtherails_core.csv'}")
    print(f"Wrote {len(items_1to5)} items to {OUTPUT_DIR / 'items_offtherails_core_1to5.csv'}")
    print(f"Wrote {len(items_1to7)} items to {OUTPUT_DIR / 'items_offtherails_core_1to7_adapted.csv'}")
    print(f"Wrote {len(REVISION_CONDITIONS)} revision conditions to {OUTPUT_DIR / 'revision_conditions.csv'}")


if __name__ == "__main__":
    main()
