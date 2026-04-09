#!/usr/bin/env python3
"""Build paper-facing analysis artifacts and figures for a pilot run."""

from __future__ import annotations

import argparse
import csv
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from offtherails_pilot.io_utils import atomic_write_csv
from offtherails_pilot.prompts import SYSTEM_PROMPT, render_first_pass_prompt, render_revision_prompt


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def word_count(text: str) -> int:
    return len(text.split())


def sentence_count(text: str) -> int:
    return len([part for part in re.split(r"[.!?]+", text) if part.strip()])


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def render_markdown_table(rows: Sequence[Dict[str, object]], columns: Sequence[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, divider]
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                values.append(f"{value:.3f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def prompt_feature_rows(
    conditions: List[Dict[str, str]],
    revision_schema_mode: str,
) -> List[Dict[str, object]]:
    rhetorical_gravity = {
        "generic_reconsider": "low",
        "moral_checklist": "medium",
        "secular_self_examination": "medium",
        "matched_secular_reflective": "high",
        "christian_identity_only": "medium",
        "christian_examen": "high",
    }
    reflective_ids = {
        "secular_self_examination",
        "matched_secular_reflective",
        "christian_examen",
    }
    rows: List[Dict[str, object]] = []
    for condition in conditions:
        condition_id = condition["revision_condition_id"]
        instruction = condition["condition_instruction"]
        has_christian_markers = any(
            marker in instruction.lower()
            for marker in ("christian", "confession", "examen")
        )
        rows.append(
            {
                "revision_condition_id": condition_id,
                "short_label": condition["short_label"],
                "identity_invocation": yes_no(
                    condition_id in {"christian_identity_only", "christian_examen"}
                ),
                "christian_lexical_markers": yes_no(has_christian_markers),
                "reflective_introspective_structure": yes_no(condition_id in reflective_ids),
                "retrospective_self_review": yes_no(condition_id in reflective_ids),
                "explicit_checklist": yes_no(condition_id == "moral_checklist"),
                "rhetorical_gravity": rhetorical_gravity[condition_id],
                "sentence_count": sentence_count(instruction),
                "instruction_word_count": word_count(instruction),
                "output_constraints": f"{revision_schema_mode}_json",
                "condition_instruction": instruction,
            }
        )
    return rows


def gold_geometry_rows(items: List[Dict[str, str]]) -> List[Dict[str, object]]:
    rows = []
    for outcome, gold_field, eval_field in [
        ("permissibility", "gold_perm_binary", "binary_eval_perm"),
        ("intention", "gold_intent_binary", "binary_eval_intent"),
    ]:
        positive = negative = ambiguous = 0
        for item in items:
            if int(item[eval_field]) == 0 or item[gold_field] == "":
                ambiguous += 1
            elif int(item[gold_field]) == 1:
                positive += 1
            else:
                negative += 1
        rows.append(
            {
                "summary_scope": "gold_item_geometry",
                "outcome": outcome,
                "positive": positive,
                "negative": negative,
                "ambiguous": ambiguous,
                "wrong_before": "",
                "correct_before": "",
                "ambiguous_excluded_before": "",
            }
        )
    return rows


def first_pass_evaluability_rows(results_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    by_item: Dict[str, Dict[str, str]] = {}
    for row in results_rows:
        by_item.setdefault(row["item_id"], row)

    rows = []
    for outcome, status_field in [
        ("permissibility", "perm_status_before"),
        ("intention", "intent_status_before"),
    ]:
        wrong = correct = ambiguous = 0
        for row in by_item.values():
            status = row[status_field]
            if status == "wrong":
                wrong += 1
            elif status == "correct":
                correct += 1
            else:
                ambiguous += 1
        rows.append(
            {
                "summary_scope": "first_pass_evaluability",
                "outcome": outcome,
                "positive": "",
                "negative": "",
                "ambiguous": "",
                "wrong_before": wrong,
                "correct_before": correct,
                "ambiguous_excluded_before": ambiguous,
            }
        )
    return rows


def bootstrap_mean(values: Sequence[float], resamples: int, seed: int) -> Tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(values)
    observed = sum(values) / n if values else 0.0
    if not values:
        return 0.0, 0.0, 0.0
    draws = []
    for _ in range(resamples):
        sample = [values[rng.randrange(n)] for __ in range(n)]
        draws.append(sum(sample) / n)
    draws.sort()
    low = draws[int(0.025 * resamples)]
    high = draws[int(0.975 * resamples)]
    return observed, low, high


def overall_bootstrap_rows(
    results_rows: List[Dict[str, str]],
    resamples: int,
    seed: int,
) -> List[Dict[str, object]]:
    by_condition: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in results_rows:
        if row["parse_status_revision"] == "ok":
            by_condition[row["revision_condition_id"]].append(row)

    rows = []
    for offset, condition in enumerate(sorted(by_condition)):
        group = by_condition[condition]
        perm_deltas = [
            float(row["perm_distance_final"]) - float(row["perm_distance_first"])
            for row in group
        ]
        intent_deltas = [
            float(row["intent_distance_final"]) - float(row["intent_distance_first"])
            for row in group
        ]
        perm_mean, perm_low, perm_high = bootstrap_mean(perm_deltas, resamples, seed + offset)
        intent_mean, intent_low, intent_high = bootstrap_mean(
            intent_deltas, resamples, seed + 100 + offset
        )
        over_revision = sum(int(row["changed_any_answer"]) for row in group) / len(group)
        rows.append(
            {
                "revision_condition_id": condition,
                "n_items": len(group),
                "perm_distance_mean_delta": perm_mean,
                "perm_distance_ci_low": perm_low,
                "perm_distance_ci_high": perm_high,
                "intent_distance_mean_delta": intent_mean,
                "intent_distance_ci_low": intent_low,
                "intent_distance_ci_high": intent_high,
                "over_revision_rate": over_revision,
            }
        )
    return rows


def pairwise_bootstrap_rows(
    results_rows: List[Dict[str, str]],
    base_condition: str,
    resamples: int,
    seed: int,
) -> Tuple[List[Dict[str, object]], Dict[Tuple[str, str], List[float]]]:
    by_condition: Dict[str, Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in results_rows:
        if row["parse_status_revision"] == "ok":
            by_condition[row["revision_condition_id"]][row["item_id"]] = row

    base_rows = by_condition[base_condition]
    pairwise_rows: List[Dict[str, object]] = []
    raw_differences: Dict[Tuple[str, str], List[float]] = {}
    controls = [condition for condition in sorted(by_condition) if condition != base_condition]
    for offset, control in enumerate(controls):
        control_rows = by_condition[control]
        shared_item_ids = sorted(set(base_rows) & set(control_rows))
        for metric_name, row_field in [
            ("perm_distance_final", "perm_distance_final"),
            ("intent_distance_final", "intent_distance_final"),
        ]:
            diffs = [
                float(base_rows[item_id][row_field]) - float(control_rows[item_id][row_field])
                for item_id in shared_item_ids
            ]
            observed, low, high = bootstrap_mean(diffs, resamples, seed + 1000 + offset)
            raw_differences[(control, metric_name)] = diffs
            pairwise_rows.append(
                {
                    "baseline_condition": control,
                    "comparison_condition": base_condition,
                    "metric": metric_name,
                    "n_items": len(shared_item_ids),
                    "mean_difference": observed,
                    "ci_low": low,
                    "ci_high": high,
                    "ci_excludes_zero": int((low > 0.0) or (high < 0.0)),
                    "better_if_negative": "yes",
                }
            )
    return pairwise_rows, raw_differences


def select_case_rows(
    results_rows: List[Dict[str, str]],
    items: List[Dict[str, str]],
    top_n: int = 3,
) -> List[Dict[str, object]]:
    by_item: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in results_rows:
        if row["parse_status_revision"] == "ok":
            by_item[row["item_id"]].append(row)
    item_lookup = {item["item_id"]: item for item in items}

    scored_items = []
    for item_id, group in by_item.items():
        by_condition = {row["revision_condition_id"]: row for row in group}
        if "christian_examen" not in by_condition:
            continue
        examen_distance = float(by_condition["christian_examen"]["perm_distance_final"])
        control_distances = [
            float(row["perm_distance_final"])
            for condition_id, row in by_condition.items()
            if condition_id != "christian_examen"
        ]
        if not control_distances:
            continue
        scored_items.append(
            (
                sum(control_distances) / len(control_distances) - examen_distance,
                item_id,
                by_condition["christian_examen"]["scenario_id"],
            )
        )

    selected: List[Tuple[float, str, str]] = []
    used_scenarios = set()
    for contrast, item_id, scenario_id in sorted(scored_items, reverse=True):
        if scenario_id in used_scenarios:
            continue
        selected.append((contrast, item_id, scenario_id))
        used_scenarios.add(scenario_id)
        if len(selected) == top_n:
            break

    output_rows: List[Dict[str, object]] = []
    for rank, (contrast, item_id, _scenario_id) in enumerate(selected, start=1):
        item_rows = sorted(
            by_item[item_id],
            key=lambda row: (
                row["revision_condition_id"] != "christian_examen",
                row["revision_condition_id"],
            ),
        )
        exemplar = item_rows[0]
        scenario_text = item_lookup[item_id]["scenario_text"]
        output_rows.append(
            {
                "case_rank": rank,
                "item_id": item_id,
                "scenario_id": exemplar["scenario_id"],
                "scenario_text": scenario_text,
                "selection_contrast": contrast,
                "row_type": "first_pass",
                "label": "First Pass",
                "revision_condition_id": "",
                "permissibility_score": exemplar["permissibility_first"],
                "intention_score": exemplar["negative_intended_first"],
                "confidence": exemplar["confidence_first"],
                "rationale": exemplar["rationale_first"],
                "gold_perm_mean": exemplar["gold_perm_mean"],
                "gold_intent_mean": exemplar["gold_intent_mean"],
            }
        )
        output_rows.append(
            {
                "case_rank": rank,
                "item_id": item_id,
                "scenario_id": exemplar["scenario_id"],
                "scenario_text": scenario_text,
                "selection_contrast": contrast,
                "row_type": "gold",
                "label": "Human Mean",
                "revision_condition_id": "",
                "permissibility_score": exemplar["gold_perm_mean"],
                "intention_score": exemplar["gold_intent_mean"],
                "confidence": "",
                "rationale": "",
                "gold_perm_mean": exemplar["gold_perm_mean"],
                "gold_intent_mean": exemplar["gold_intent_mean"],
            }
        )
        for row in item_rows:
            output_rows.append(
            {
                "case_rank": rank,
                "item_id": item_id,
                "scenario_id": row["scenario_id"],
                "scenario_text": scenario_text,
                "selection_contrast": contrast,
                "row_type": "revision",
                "label": row["revision_condition_id"],
                "revision_condition_id": row["revision_condition_id"],
                "permissibility_score": row["permissibility_final"],
                    "intention_score": row["negative_intended_final"],
                    "confidence": row["confidence_final"],
                    "rationale": row["rationale_final"],
                    "gold_perm_mean": row["gold_perm_mean"],
                    "gold_intent_mean": row["gold_intent_mean"],
                }
            )
    return output_rows


def write_prompt_appendix(
    output_path: Path,
    items: List[Dict[str, str]],
    conditions: List[Dict[str, str]],
    rating_scale_max: int,
) -> None:
    placeholder_item = {"scenario_text": "{scenario_text}", "agent_name": "{agent_name}"}
    first_pass_prompt = render_first_pass_prompt(placeholder_item, scale_max=rating_scale_max)
    revision_wrapper = render_revision_prompt(
        placeholder_item,
        first_pass_json="{first_pass_json}",
        condition_instruction="{condition_instruction}",
        scale_max=rating_scale_max,
        schema_mode="minimal",
    )
    lines = [
        "## Appendix A: Full Prompt Texts",
        "",
        "### Shared System Prompt",
        "",
        "```text",
        SYSTEM_PROMPT,
        "```",
        "",
        "### First-Pass Prompt Template",
        "",
        "```text",
        first_pass_prompt,
        "```",
        "",
        "### Revision Wrapper Template",
        "",
        "```text",
        revision_wrapper,
        "```",
        "",
        "### Revision Condition Instructions",
        "",
    ]
    for condition in conditions:
        lines.extend(
            [
                f"#### `{condition['revision_condition_id']}`",
                "",
                "```text",
                condition["condition_instruction"],
                "```",
                "",
            ]
        )
    write_markdown(output_path, "\n".join(lines))


def write_case_appendix(
    output_path: Path,
    case_rows: List[Dict[str, object]],
) -> None:
    grouped: Dict[int, List[Dict[str, object]]] = defaultdict(list)
    for row in case_rows:
        grouped[int(row["case_rank"])].append(row)

    lines = ["## Appendix B: Worked Qualitative Cases", ""]
    for case_rank in sorted(grouped):
        case_group = grouped[case_rank]
        scenario_text = str(case_group[0]["scenario_text"]).strip()
        table_rows = []
        for row in case_group:
            table_rows.append(
                {
                    "Label": row["label"],
                    "Permissibility": row["permissibility_score"],
                    "Intention": row["intention_score"],
                    "Confidence": row["confidence"],
                    "Rationale": row["rationale"],
                }
            )
        lines.extend(
            [
                f"### Case {case_rank}: `{case_group[0]['item_id']}`",
                "",
                scenario_text,
                "",
                render_markdown_table(
                    table_rows,
                    ["Label", "Permissibility", "Intention", "Confidence", "Rationale"],
                ),
                "",
            ]
        )
    write_markdown(output_path, "\n".join(lines))


def draw_protocol_figure(path: Path, condition_count: int) -> None:
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 3)
    ax.axis("off")

    boxes = [
        (0.4, 1.1, 1.8, 0.8, "Scenario"),
        (2.8, 1.1, 2.1, 0.8, "First-pass JSON"),
        (5.5, 1.1, 2.4, 0.8, f"Replay cached first pass\ninto {condition_count} revision prompts"),
        (8.6, 1.1, 1.8, 0.8, "Revised JSON"),
    ]
    for x, y, width, height, label in boxes:
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                width,
                height,
                boxstyle="round,pad=0.02,rounding_size=0.06",
                linewidth=1.4,
                edgecolor="#2c3e50",
                facecolor="#f7f4ec",
            )
        )
        ax.text(x + width / 2, y + height / 2, label, ha="center", va="center", fontsize=11)

    arrows = [
        ((2.2, 1.5), (2.8, 1.5)),
        ((4.9, 1.5), (5.5, 1.5)),
        ((7.9, 1.5), (8.6, 1.5)),
    ]
    for start, end in arrows:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=14, linewidth=1.2))

    ax.text(
        5.55,
        0.55,
        "Same cached first pass reused across conditions.\nManipulated variable: revision framing only.",
        ha="left",
        va="center",
        fontsize=10,
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_main_results_figure(path: Path, bootstrap_rows: List[Dict[str, object]]) -> None:
    label_map = {
        "generic_reconsider": "Generic",
        "moral_checklist": "Checklist",
        "secular_self_examination": "Secular\nSelf-Exam",
        "matched_secular_reflective": "Matched\nSecular",
        "christian_identity_only": "Christian\nIdentity",
        "christian_examen": "Christian\nExamen",
    }
    ordered = sorted(bootstrap_rows, key=lambda row: list(label_map).index(row["revision_condition_id"]))
    x_positions = list(range(len(ordered)))

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), sharey=False)
    specs = [
        ("perm_distance_mean_delta", "perm_distance_ci_low", "perm_distance_ci_high", "Permissibility"),
        ("intent_distance_mean_delta", "intent_distance_ci_low", "intent_distance_ci_high", "Intention"),
    ]
    for ax, (value_key, low_key, high_key, title) in zip(axes, specs):
        values = [float(row[value_key]) for row in ordered]
        lows = [float(row[low_key]) for row in ordered]
        highs = [float(row[high_key]) for row in ordered]
        errors = [
            [value - low for value, low in zip(values, lows)],
            [high - value for value, high in zip(values, highs)],
        ]
        colors = ["#b86b4b" if row["revision_condition_id"] == "christian_examen" else "#4c7a8a" for row in ordered]
        ax.errorbar(
            x_positions,
            values,
            yerr=errors,
            fmt="o",
            color="#1f2d3d",
            ecolor="#1f2d3d",
            elinewidth=1.3,
            capsize=4,
        )
        ax.scatter(x_positions, values, s=70, c=colors, zorder=3)
        ax.axhline(0.0, color="#555555", linewidth=1.0, linestyle="--")
        ax.set_xticks(x_positions)
        ax.set_xticklabels([label_map[row["revision_condition_id"]] for row in ordered], fontsize=9)
        ax.set_title(title)
        ax.set_ylabel("Final distance - first-pass distance")
        ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_pairwise_distribution_figure(
    path: Path,
    pairwise_differences: Dict[Tuple[str, str], List[float]],
) -> None:
    label_map = {
        "generic_reconsider": "Generic",
        "moral_checklist": "Checklist",
        "secular_self_examination": "Secular Self-Exam",
        "matched_secular_reflective": "Matched Secular",
        "christian_identity_only": "Christian Identity",
    }
    controls = [condition for condition in label_map if (condition, "perm_distance_final") in pairwise_differences]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), sharey=False)
    specs = [
        ("perm_distance_final", "Permissibility"),
        ("intent_distance_final", "Intention"),
    ]
    rng = random.Random(7)
    for ax, (metric, title) in zip(axes, specs):
        data = [pairwise_differences[(condition, metric)] for condition in controls]
        ax.boxplot(data, patch_artist=True, widths=0.55, boxprops={"facecolor": "#e7d7c1"})
        for index, diffs in enumerate(data, start=1):
            jitter = [index + (rng.random() - 0.5) * 0.18 for _ in diffs]
            ax.scatter(jitter, diffs, s=12, alpha=0.55, color="#2f4b5a")
        ax.axhline(0.0, color="#555555", linewidth=1.0, linestyle="--")
        ax.set_xticks(range(1, len(controls) + 1))
        ax.set_xticklabels([label_map[condition] for condition in controls], rotation=20, ha="right")
        ax.set_title(f"Christian Examen - Control\n{title} final distance")
        ax.set_ylabel("Paired item-level difference")
        ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--items-file", default=str(ROOT / "data" / "items_offtherails_core.csv"))
    parser.add_argument("--conditions-file", default=str(ROOT / "data" / "revision_conditions.csv"))
    parser.add_argument("--figures-dir", default=str(ROOT / "paper" / "figures"))
    parser.add_argument("--generated-dir", default=str(ROOT / "paper" / "generated"))
    parser.add_argument("--bootstrap-resamples", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260408)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    figures_dir = Path(args.figures_dir)
    if not figures_dir.is_absolute():
        figures_dir = ROOT / figures_dir
    generated_dir = Path(args.generated_dir)
    if not generated_dir.is_absolute():
        generated_dir = ROOT / generated_dir

    items = load_csv_rows(Path(args.items_file))
    conditions = load_csv_rows(Path(args.conditions_file))
    results_rows = load_csv_rows(run_dir / "results_long.csv")
    manifest_rows = load_csv_rows(run_dir / "run_manifest.csv")
    revision_schema_mode = (
        manifest_rows[0].get("revision_schema_mode", "minimal")
        if manifest_rows
        else "minimal"
    )
    rating_scale_max = int(items[0]["gold_scale_max"])

    prompt_rows = prompt_feature_rows(conditions, revision_schema_mode)
    geometry_rows = gold_geometry_rows(items) + first_pass_evaluability_rows(results_rows)
    bootstrap_rows = overall_bootstrap_rows(
        results_rows,
        resamples=args.bootstrap_resamples,
        seed=args.bootstrap_seed,
    )
    pairwise_rows, pairwise_differences = pairwise_bootstrap_rows(
        results_rows,
        base_condition="christian_examen",
        resamples=args.bootstrap_resamples,
        seed=args.bootstrap_seed,
    )
    case_rows = select_case_rows(results_rows, items)

    atomic_write_csv(run_dir / "prompt_design_matrix.csv", prompt_rows)
    atomic_write_csv(run_dir / "dataset_geometry_summary.csv", geometry_rows)
    atomic_write_csv(run_dir / "bootstrap_summary.csv", bootstrap_rows)
    atomic_write_csv(run_dir / "pairwise_bootstrap.csv", pairwise_rows)
    atomic_write_csv(run_dir / "case_studies.csv", case_rows)

    write_markdown(
        generated_dir / "prompt_design_matrix.md",
        "## Prompt Design Matrix\n\n"
        + render_markdown_table(
            prompt_rows,
            [
                "short_label",
                "identity_invocation",
                "christian_lexical_markers",
                "reflective_introspective_structure",
                "retrospective_self_review",
                "explicit_checklist",
                "rhetorical_gravity",
                "sentence_count",
                "instruction_word_count",
                "output_constraints",
            ],
        ),
    )
    write_markdown(
        generated_dir / "dataset_geometry_table.md",
        "## Dataset Geometry and Evaluability\n\n"
        + render_markdown_table(
            geometry_rows,
            [
                "summary_scope",
                "outcome",
                "positive",
                "negative",
                "ambiguous",
                "wrong_before",
                "correct_before",
                "ambiguous_excluded_before",
            ],
        ),
    )
    write_markdown(
        generated_dir / "main_results_with_uncertainty.md",
        "## Main Results With Uncertainty\n\n"
        + render_markdown_table(
            bootstrap_rows,
            [
                "revision_condition_id",
                "perm_distance_mean_delta",
                "perm_distance_ci_low",
                "perm_distance_ci_high",
                "intent_distance_mean_delta",
                "intent_distance_ci_low",
                "intent_distance_ci_high",
                "over_revision_rate",
            ],
        )
        + "\n\n## Christian Examen Pairwise Bootstrap\n\n"
        + render_markdown_table(
            pairwise_rows,
            [
                "baseline_condition",
                "comparison_condition",
                "metric",
                "mean_difference",
                "ci_low",
                "ci_high",
                "ci_excludes_zero",
            ],
        ),
    )
    write_prompt_appendix(generated_dir / "prompt_appendix.md", items, conditions, rating_scale_max)
    write_case_appendix(generated_dir / "case_appendix.md", case_rows)

    draw_protocol_figure(figures_dir / "protocol_schematic.png", len(conditions))
    draw_main_results_figure(figures_dir / "main_quantitative_results.png", bootstrap_rows)
    draw_pairwise_distribution_figure(
        figures_dir / "paired_difference_distribution.png",
        pairwise_differences,
    )

    print(f"Wrote paper artifacts for {run_dir}")


if __name__ == "__main__":
    main()
