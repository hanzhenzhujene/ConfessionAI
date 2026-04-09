#!/usr/bin/env python3
"""Reparse and rescore an existing run using the latest parser rules."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from offtherails_pilot.parsing import try_parse_revision
from offtherails_pilot.io_utils import atomic_write_csv
from offtherails_pilot.scoring import add_scoring_fields


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def detect_revision_schema_mode(run_dir: Path, rows: List[Dict[str, str]]) -> str:
    manifest_path = run_dir / "run_manifest.csv"
    if manifest_path.exists():
        manifest_rows = load_rows(manifest_path)
        if manifest_rows:
            schema_mode = manifest_rows[0].get("revision_schema_mode", "").strip()
            if schema_mode:
                return schema_mode
    if any(row.get("first_focus", "").strip() or row.get("neglected_factor", "").strip() for row in rows):
        return "reflective_metadata"
    return "minimal"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--items-file", default=str(ROOT / "data" / "items_offtherails_core.csv"))
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir

    results_path = run_dir / "results_long.csv"
    rows = load_rows(results_path)
    revision_schema_mode = detect_revision_schema_mode(run_dir, rows)
    items_by_id: Dict[str, Dict[str, str]] = {}
    items_path = Path(args.items_file)
    if not items_path.is_absolute():
        items_path = ROOT / items_path
    if items_path.exists():
        items_by_id = {
            row["item_id"]: row for row in load_rows(items_path)
        }

    repaired = 0
    still_invalid = 0
    new_rows: List[Dict[str, object]] = []
    for row in rows:
        item_metadata = items_by_id.get(row["item_id"], {})
        for key in (
            "gold_perm_mean",
            "gold_intent_mean",
            "gold_scale_min",
            "gold_scale_max",
            "gold_scale_mode",
            "gold_perm_binary",
            "gold_intent_binary",
            "binary_eval_perm",
            "binary_eval_intent",
            "scenario_id",
            "means_side_effect",
            "evitability",
            "agency_mode",
        ):
            if (key not in row or str(row.get(key, "")).strip() == "") and key in item_metadata:
                row[key] = item_metadata[key]

        status, parsed = try_parse_revision(
            row["raw_revision"],
            rating_scale_max=int(row["gold_scale_max"]),
            require_reflection_fields=revision_schema_mode == "reflective_metadata",
        )
        row["parse_status_revision"] = status
        if status == "ok":
            row["first_focus"] = parsed["first_focus"]
            row["neglected_factor"] = parsed["neglected_factor"]
            row["permissibility_final"] = parsed["permissibility_agreement"]
            row["negative_intended_final"] = parsed["negative_outcome_intended_agreement"]
            row["confidence_final"] = parsed["confidence"]
            row["rationale_final"] = parsed["rationale_short"]
            row = add_scoring_fields(row)
            repaired += 1
        else:
            still_invalid += 1
        new_rows.append(row)

    atomic_write_csv(results_path, new_rows)
    print(f"Repaired rows parsed successfully: {repaired}")
    print(f"Rows still invalid: {still_invalid}")


if __name__ == "__main__":
    main()
