#!/usr/bin/env python3
"""Profile available OffTheRails source data for methodological planning."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def classify_mean(mean_value: float) -> str:
    if mean_value <= 2.0:
        return "neg"
    if mean_value >= 4.0:
        return "pos"
    return "amb"


def profile_exp2(source_dir: Path) -> Dict[str, object]:
    rows = load_csv_rows(source_dir / "offtherails" / "prolific-exp-2" / "data_long_format.csv")
    grouped = defaultdict(lambda: {"perm": [], "intent": []})
    for row in rows:
        key = (
            row["split"],
            row["scenario_id"],
            row["causal_structure"],
            row["evitability"],
            row["action"],
        )
        grouped[key]["perm"].append(int(row["permissibility_rating"]))
        grouped[key]["intent"].append(int(row["intention_rating"]))

    all_groups = len(grouped)
    supported = {key: value for key, value in grouped.items() if len(value["perm"]) >= 20}
    sparse = all_groups - len(supported)

    perm_balance = Counter()
    intent_balance = Counter()
    split_counts = Counter()
    for key, value in supported.items():
        split_counts[key[0]] += 1
        perm_balance[classify_mean(sum(value["perm"]) / len(value["perm"]))] += 1
        intent_balance[classify_mean(sum(value["intent"]) / len(value["intent"]))] += 1

    return {
        "all_item_cells": all_groups,
        "supported_item_cells": len(supported),
        "sparse_item_cells": sparse,
        "supported_group_size_min": min(len(value["perm"]) for value in supported.values()),
        "supported_group_size_max": max(len(value["perm"]) for value in supported.values()),
        "supported_by_split": dict(sorted(split_counts.items())),
        "supported_perm_balance": dict(perm_balance),
        "supported_intent_balance": dict(intent_balance),
    }


def profile_exp1(source_dir: Path) -> Dict[str, object]:
    rows = load_csv_rows(source_dir / "offtherails" / "prolific-exp-1" / "data_combined_long_format.csv")
    return {
        "row_count": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "note": "Experiment 1 contains target-event valence ratings (rating/structure/type/strength), not direct permissibility and intention judgments. It is not a drop-in replacement for the self-correction benchmark.",
    }


def write_markdown(path: Path, exp1: Dict[str, object], exp2: Dict[str, object]) -> None:
    lines = [
        "# OffTheRails Source Profile",
        "",
        "## Experiment 2",
        "",
        f"- All item cells in long-format table: `{exp2['all_item_cells']}`",
        f"- Supported item cells with >=20 human ratings: `{exp2['supported_item_cells']}`",
        f"- Sparse item cells excluded from reliable aggregation: `{exp2['sparse_item_cells']}`",
        f"- Supported group size range: `{exp2['supported_group_size_min']}` to `{exp2['supported_group_size_max']}`",
        f"- Supported cells by split: `{exp2['supported_by_split']}`",
        f"- Supported permissibility balance: `{exp2['supported_perm_balance']}`",
        f"- Supported intention balance: `{exp2['supported_intent_balance']}`",
        "",
        "Interpretation: the well-supported Experiment 2 subset is exactly the current 80-item core, and it is not decision-balanced enough for binary-primary self-correction claims.",
        "",
        "## Experiment 1",
        "",
        f"- Row count: `{exp1['row_count']}`",
        f"- Columns: `{exp1['columns']}`",
        "",
        exp1["note"],
        "",
        "## Recommendation",
        "",
        "Use Experiment 2 core items with benchmark-aligned 1-5 prompts for continuous-primary analysis.",
        "Do not promote binary net correction gain to the headline result on this subset.",
        "If a binary-primary main experiment is required, use a different evaluation set or add new human annotation for a more balanced set of dilemmas.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default=str(ROOT / ".cache" / "moral-evals-source"))
    parser.add_argument("--output-json", default=str(ROOT / "data" / "offtherails_source_profile.json"))
    parser.add_argument("--output-md", default=str(ROOT / "data" / "offtherails_source_profile.md"))
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    exp2 = profile_exp2(source_dir)
    exp1 = profile_exp1(source_dir)

    output_json = Path(args.output_json)
    if not output_json.is_absolute():
        output_json = ROOT / output_json
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps({"experiment_2": exp2, "experiment_1": exp1}, indent=2),
        encoding="utf-8",
    )

    output_md = Path(args.output_md)
    if not output_md.is_absolute():
        output_md = ROOT / output_md
    output_md.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(output_md, exp1, exp2)
    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")


if __name__ == "__main__":
    main()
