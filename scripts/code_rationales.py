#!/usr/bin/env python3
"""Code rationale categories and summarize rationale shifts for a run."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from statistics import mean
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from offtherails_pilot.rationale_coding import code_rationale
from offtherails_pilot.io_utils import atomic_write_csv


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def mean_field(rows: List[Dict[str, object]], field: str) -> float:
    if not rows:
        return 0.0
    return mean(float(row[field]) for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir

    results_path = run_dir / "results_long.csv"
    rows = load_rows(results_path)

    coded_rows: List[Dict[str, object]] = []
    for row in rows:
        first_codes = code_rationale(row.get("rationale_first", ""))
        final_codes = code_rationale(row.get("rationale_final", ""))
        new_row = dict(row)
        for label in first_codes:
            new_row[f"first_{label}"] = first_codes[label]
            new_row[f"final_{label}"] = final_codes[label]
            new_row[f"shift_to_{label}"] = int(
                not first_codes[label] and bool(final_codes[label])
            )
        coded_rows.append(new_row)

    atomic_write_csv(run_dir / "results_with_rationale_codes.csv", coded_rows)

    summary_rows: List[Dict[str, object]] = []
    categories = list(code_rationale("").keys())
    by_condition = {}
    for row in coded_rows:
        by_condition.setdefault(row["revision_condition_id"], []).append(row)

    for condition, group in sorted(by_condition.items()):
        summary: Dict[str, object] = {
            "revision_condition_id": condition,
            "n_rows": len(group),
        }
        for label in categories:
            summary[f"first_{label}_rate"] = mean_field(group, f"first_{label}")
            summary[f"final_{label}_rate"] = mean_field(group, f"final_{label}")
            summary[f"shift_to_{label}_rate"] = mean_field(group, f"shift_to_{label}")
        summary_rows.append(summary)

    atomic_write_csv(run_dir / "rationale_summary.csv", summary_rows)
    print(f"Wrote {run_dir / 'results_with_rationale_codes.csv'}")
    print(f"Wrote {run_dir / 'rationale_summary.csv'}")


if __name__ == "__main__":
    main()
