#!/usr/bin/env python3
"""Summarize a completed pilot run."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from offtherails_pilot.scoring import summarize_rows, write_csv


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_report(
    path: Path,
    overall: List[Dict[str, object]],
    run_dir: Path,
    analysis_profile: str,
) -> None:
    lines = [
        "# Run Report",
        "",
        f"- Run directory: `{run_dir}`",
        f"- Conditions summarized: `{len(overall)}`",
        f"- Analysis profile: `{analysis_profile}`",
        "",
    ]
    if analysis_profile == "continuous_primary":
        lines.extend(
            [
                "## Recommended Reading",
                "",
                "Treat the continuous distance metrics as primary on this run.",
                "Negative mean deltas indicate movement closer to the human mean.",
                "",
                "## Continuous Primary Summary",
                "",
                "| Condition | Perm net closer | Perm mean delta | Intent net closer | Intent mean delta | Over-revision |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in overall:
            lines.append(
                "| {revision_condition_id} | {perm_distance_net_improvement_rate:.3f} | {perm_distance_mean_delta:.3f} | {intent_distance_net_improvement_rate:.3f} | {intent_distance_mean_delta:.3f} | {over_revision_rate:.3f} |".format(
                    **row
                )
            )
        lines.append("")
    else:
        lines.extend(
            [
                "## Recommended Reading",
                "",
                "Treat the binary correction metrics as primary on this run.",
                "",
            ]
        )
    lines.extend(
        [
            "## Overall by condition",
            "",
            "| Condition | Perm wrong n | Perm correct n | Perm correction | Perm flip | Perm net | Perm closer | Perm farther | Perm net closer | Perm mean delta | Intent wrong n | Intent correct n | Intent correction | Intent flip | Intent net | Intent closer | Intent farther | Intent net closer | Intent mean delta | Over-revision |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in overall:
        lines.append(
            "| {revision_condition_id} | {perm_n_wrong_before} | {perm_n_correct_before} | {perm_error_correction_rate:.3f} | {perm_harmful_flip_rate:.3f} | {perm_net_correction_gain:.3f} | {perm_distance_improved_rate:.3f} | {perm_distance_worsened_rate:.3f} | {perm_distance_net_improvement_rate:.3f} | {perm_distance_mean_delta:.3f} | {intent_n_wrong_before} | {intent_n_correct_before} | {intent_error_correction_rate:.3f} | {intent_harmful_flip_rate:.3f} | {intent_net_correction_gain:.3f} | {intent_distance_improved_rate:.3f} | {intent_distance_worsened_rate:.3f} | {intent_distance_net_improvement_rate:.3f} | {intent_distance_mean_delta:.3f} | {over_revision_rate:.3f} |".format(
                **row
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    results_path = run_dir / "results_long.csv"
    manifest_path = run_dir / "run_manifest.csv"
    rows = load_csv_rows(results_path)
    manifest_rows = load_csv_rows(manifest_path) if manifest_path.exists() else []
    analysis_profile = (
        manifest_rows[0].get("analysis_profile", "continuous_primary")
        if manifest_rows
        else "continuous_primary"
    )
    overall = summarize_rows(rows, ["revision_condition_id"])
    slice_summary = summarize_rows(
        rows,
        ["revision_condition_id", "means_side_effect", "evitability", "agency_mode"],
    )

    write_csv(str(run_dir / "condition_summary.csv"), overall)
    write_csv(str(run_dir / "slice_summary.csv"), slice_summary)
    write_report(run_dir / "run_report.md", overall, run_dir, analysis_profile)
    print(f"Wrote summaries to {run_dir}")


if __name__ == "__main__":
    main()
