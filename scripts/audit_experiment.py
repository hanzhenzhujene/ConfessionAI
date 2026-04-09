#!/usr/bin/env python3
"""Audit dataset and run settings for methodological risks."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from offtherails_pilot.prompts import render_first_pass_prompt
from offtherails_pilot.dataset_checks import summarize_binary_balance


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def detect_prompt_scale(example_item: Dict[str, str]) -> str:
    prompt = render_first_pass_prompt(example_item, scale_max=int(example_item["gold_scale_max"]))
    match = re.search(r"Rate both statements on (1-\d) scales\.", prompt)
    return match.group(1) if match else "unknown"


def severity_rank(label: str) -> int:
    return {"INFO": 0, "WARN": 1, "FAIL": 2}[label]


def add_finding(findings: List[Dict[str, str]], severity: str, title: str, detail: str) -> None:
    findings.append(
        {
            "severity": severity,
            "title": title,
            "detail": detail,
        }
    )


def audit_dataset(
    items: List[Dict[str, str]],
    findings: List[Dict[str, str]],
    analysis_profile: str,
) -> None:
    prompt_scale = detect_prompt_scale(items[0]) if items else "unknown"
    balance = summarize_binary_balance(items)
    perm_pos = balance["perm_pos"]
    perm_neg = balance["perm_neg"]
    perm_amb = balance["perm_amb"]
    intent_pos = balance["intent_pos"]
    intent_neg = balance["intent_neg"]
    intent_amb = balance["intent_amb"]

    dataset_scale = items[0]["gold_scale_max"] if items else "unknown"
    if prompt_scale != f"1-{dataset_scale}":
        add_finding(
            findings,
            "FAIL",
            "Prompt template and dataset scale disagree",
            f"The rendered prompt reports {prompt_scale} while the dataset metadata reports 1-{dataset_scale}.",
        )
    if dataset_scale != "5":
        add_finding(
            findings,
            "FAIL",
            "Prompt scale is not benchmark-aligned",
            f"The items file uses a 1-{dataset_scale} scoring space while OffTheRails human ratings are sourced from a 1-5 study. This run is an adapted variant, not a direct benchmark-aligned evaluation.",
        )
    if perm_pos == 0 or perm_neg == 0:
        add_finding(
            findings,
            "FAIL" if analysis_profile == "binary_primary" else "WARN",
            "Permissibility gold labels are one-sided",
            f"Permissibility gold labels are pos={perm_pos}, neg={perm_neg}, ambiguous={perm_amb}. Binary self-correction on permissibility is not decision-balanced.",
        )
    if intent_pos == 0 or intent_neg == 0:
        add_finding(
            findings,
            "FAIL" if analysis_profile == "binary_primary" else "WARN",
            "Intention gold labels are one-sided",
            f"Intention gold labels are pos={intent_pos}, neg={intent_neg}, ambiguous={intent_amb}. Binary self-correction on intention is not decision-balanced.",
        )
    if perm_amb > 0 or intent_amb > 0:
        add_finding(
            findings,
            "WARN",
            "Many items are excluded from binary scoring",
            f"Ambiguous binary items: permissibility={perm_amb}, intention={intent_amb}. Continuous distance metrics are more trustworthy than binary correction rates on this subset.",
        )


def infer_revision_schema_mode(
    manifest_rows: List[Dict[str, str]],
    results_rows: List[Dict[str, str]],
) -> str:
    if manifest_rows:
        schema_mode = manifest_rows[0].get("revision_schema_mode", "").strip()
        if schema_mode:
            return schema_mode
    if any(
        row.get("first_focus", "").strip() or row.get("neglected_factor", "").strip()
        for row in results_rows
    ):
        return "reflective_metadata"
    return "minimal"


def infer_first_pass_format(manifest_rows: List[Dict[str, str]]) -> str:
    if manifest_rows:
        format_name = manifest_rows[0].get("first_pass_format", "").strip()
        if format_name:
            return format_name
    return "joint_dual_statement"


def infer_expected_count(
    manifest_rows: List[Dict[str, str]],
    manifest_field: str,
    fallback: int,
) -> int:
    if manifest_rows:
        raw_value = manifest_rows[0].get(manifest_field, "").strip()
        if raw_value.isdigit():
            return int(raw_value)
    return fallback


def audit_protocol(
    first_pass_format: str,
    revision_schema_mode: str,
    findings: List[Dict[str, str]],
) -> None:
    if first_pass_format == "joint_dual_statement":
        add_finding(
            findings,
            "WARN",
            "Permissibility and intention are elicited jointly",
            "The current protocol asks the model to rate permissibility and intention in one JSON response. OffTheRails originally elicits these judgments separately, so this is a benchmark adaptation rather than a direct reproduction.",
        )
    if revision_schema_mode == "reflective_metadata":
        add_finding(
            findings,
            "FAIL",
            "Revision schema injects self-examination into all conditions",
            "Every revision condition is forced to emit fields such as first_focus and neglected_factor. That bakes reflective structure into the controls and weakens the causal contrast against Christian reflective framing.",
        )


def audit_run(run_dir: Path, findings: List[Dict[str, str]]) -> None:
    manifest_path = run_dir / "run_manifest.csv"
    results_path = run_dir / "results_long.csv"
    first_pass_path = run_dir / "first_pass_cache.csv"
    summary_path = run_dir / "condition_summary.csv"

    manifest_rows = load_csv_rows(manifest_path) if manifest_path.exists() else []
    results_rows = load_csv_rows(results_path) if results_path.exists() else []
    first_pass_rows = load_csv_rows(first_pass_path) if first_pass_path.exists() else []
    summary_rows = load_csv_rows(summary_path) if summary_path.exists() else []
    first_pass_format = infer_first_pass_format(manifest_rows)
    revision_schema_mode = infer_revision_schema_mode(manifest_rows, results_rows)
    analysis_profile = (
        manifest_rows[0].get("analysis_profile", "continuous_primary")
        if manifest_rows
        else "continuous_primary"
    )
    audit_protocol(first_pass_format, revision_schema_mode, findings)

    if len(manifest_rows) != 1:
        add_finding(
            findings,
            "WARN",
            "Manifest does not have exactly one row",
            f"run_manifest.csv contains {len(manifest_rows)} rows for this run directory.",
        )
    first_pass_unique = {row["item_id"] for row in first_pass_rows}
    if len(first_pass_unique) != len(first_pass_rows):
        add_finding(
            findings,
            "FAIL",
            "First-pass cache contains duplicate item rows",
            f"first_pass_cache.csv has {len(first_pass_rows)} rows but only {len(first_pass_unique)} unique item IDs.",
        )
    first_pass_invalid = sum(row["parse_status_first"] != "ok" for row in first_pass_rows)
    if first_pass_invalid:
        add_finding(
            findings,
            "FAIL",
            "First-pass parsing failures remain",
            f"{first_pass_invalid} first-pass rows still have parse_status_first != ok.",
        )
    expected_items = infer_expected_count(manifest_rows, "item_count", len(first_pass_unique))
    expected_conditions = infer_expected_count(
        manifest_rows,
        "condition_count",
        len({row["revision_condition_id"] for row in results_rows}),
    )
    if expected_items and len(first_pass_rows) != expected_items:
        add_finding(
            findings,
            "FAIL",
            "First-pass cache is incomplete",
            f"Expected {expected_items} first-pass rows, found {len(first_pass_rows)}.",
        )
    expected_results = expected_items * expected_conditions if expected_items and expected_conditions else 0
    if expected_results and len(results_rows) != expected_results:
        add_finding(
            findings,
            "FAIL",
            "Revision results are incomplete",
            f"Expected {expected_results} revision rows, found {len(results_rows)}.",
        )
    unique_keys = {(row["item_id"], row["revision_condition_id"]) for row in results_rows}
    if len(unique_keys) != len(results_rows):
        add_finding(
            findings,
            "FAIL",
            "Revision rows contain duplicate keys",
            f"results_long.csv has {len(results_rows)} rows but only {len(unique_keys)} unique item-condition keys.",
        )
    invalid = sum(row["parse_status_revision"] != "ok" for row in results_rows)
    if invalid:
        add_finding(
            findings,
            "FAIL",
            "Revision parsing failures remain",
            f"{invalid} revision rows still have parse_status_revision != ok.",
        )

    if summary_rows:
        if manifest_rows:
            manifest_scale = manifest_rows[0].get("rating_scale_max", "")
            result_scales = {row.get("gold_scale_max", "") for row in results_rows}
            if manifest_scale and (len(result_scales) != 1 or manifest_scale not in result_scales):
                add_finding(
                    findings,
                    "FAIL",
                    "Run manifest scale and result scale disagree",
                    f"Manifest rating_scale_max={manifest_scale}, result scales={sorted(result_scales)}.",
                )
            elif not manifest_scale:
                add_finding(
                    findings,
                    "WARN",
                    "Run manifest is missing rating scale metadata",
                    "run_manifest.csv does not record rating_scale_max, so scale alignment cannot be fully audited from provenance alone.",
                )
        if expected_conditions and len(summary_rows) != expected_conditions:
            add_finding(
                findings,
                "FAIL",
                "Condition summary is incomplete",
                f"Expected {expected_conditions} condition summary rows, found {len(summary_rows)}.",
            )
        for row in summary_rows:
            if int(row["perm_n_wrong_before"]) < 10:
                add_finding(
                    findings,
                    "FAIL" if analysis_profile == "binary_primary" else "WARN",
                    f"Too few permissibility errors for {row['revision_condition_id']}",
                    f"perm_n_wrong_before={row['perm_n_wrong_before']}. Net correction gain is not statistically meaningful at this denominator.",
                )
            if int(row["intent_n_wrong_before"]) < 10:
                add_finding(
                    findings,
                    "FAIL" if analysis_profile == "binary_primary" else "WARN",
                    f"Too few intention errors for {row['revision_condition_id']}",
                    f"intent_n_wrong_before={row['intent_n_wrong_before']}. Intention correction metrics are not decision-stable on this run.",
                )
            if float(row["over_revision_rate"]) > 0.5:
                add_finding(
                    findings,
                    "WARN",
                    f"High over-revision in {row['revision_condition_id']}",
                    f"over_revision_rate={float(row['over_revision_rate']):.3f}. This condition changes answers frequently and may be measuring prompt-induced volatility rather than correction.",
                )


def write_markdown(path: Path, findings: List[Dict[str, str]]) -> None:
    ordered = sorted(findings, key=lambda item: (-severity_rank(item["severity"]), item["title"]))
    lines = [
        "# Experiment Audit",
        "",
        f"- Findings: `{len(ordered)}`",
        "",
    ]
    for finding in ordered:
        lines.append(f"## [{finding['severity']}] {finding['title']}")
        lines.append("")
        lines.append(finding["detail"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items-file", default=str(ROOT / "data" / "items_offtherails_core.csv"))
    parser.add_argument("--run-dir", default=str(ROOT / "results" / "pilot_qwen25_core80"))
    args = parser.parse_args()

    items = load_csv_rows(Path(args.items_file))
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir

    manifest_rows = load_csv_rows(run_dir / "run_manifest.csv") if (run_dir / "run_manifest.csv").exists() else []
    analysis_profile = (
        manifest_rows[0].get("analysis_profile", "continuous_primary")
        if manifest_rows
        else "continuous_primary"
    )
    findings: List[Dict[str, str]] = []
    audit_dataset(items, findings, analysis_profile)
    audit_run(run_dir, findings)
    report_path = run_dir / "audit_report.md"
    write_markdown(report_path, findings)

    print(f"Wrote audit report to {report_path}")
    for finding in sorted(findings, key=lambda item: (-severity_rank(item["severity"]), item["title"])):
        print(f"[{finding['severity']}] {finding['title']}: {finding['detail']}")


if __name__ == "__main__":
    main()
