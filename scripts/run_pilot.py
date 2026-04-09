#!/usr/bin/env python3
"""Run the OffTheRails moral self-correction pilot against Ollama."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from offtherails_pilot.ollama_client import OllamaClient
from offtherails_pilot.dataset_checks import evaluate_analysis_profile
from offtherails_pilot.parsing import try_parse_first_pass, try_parse_revision
from offtherails_pilot.io_utils import append_csv_row, upsert_csv_row
from offtherails_pilot.prompts import (
    DEFAULT_REVISION_SCHEMA_MODE,
    FIRST_PASS_PROMPT_VERSION,
    FIRST_PASS_FORMAT,
    REVISION_PROMPT_VERSION,
    SYSTEM_PROMPT,
    render_first_pass_prompt,
    render_revision_prompt,
)
from offtherails_pilot.scoring import add_scoring_fields


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sanitize_model_name(model: str) -> str:
    return model.replace(":", "_").replace("/", "_").replace(".", "_")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def select_smoke_test_item_ids(items: List[Dict[str, str]], limit: int = 5) -> List[str]:
    uncovered = {
        ("means_side_effect", "means"),
        ("means_side_effect", "side_effect"),
        ("evitability", "evitable"),
        ("evitability", "inevitable"),
        ("agency_mode", "commission"),
        ("agency_mode", "omission"),
    }
    selected: List[Dict[str, str]] = []
    remaining = items[:]
    while uncovered and remaining and len(selected) < limit:
        best_item = None
        best_cover = set()
        for item in remaining:
            cover = {
                (field, item[field])
                for field in ("means_side_effect", "evitability", "agency_mode")
                if (field, item[field]) in uncovered
            }
            if len(cover) > len(best_cover):
                best_item = item
                best_cover = cover
        if best_item is None:
            break
        selected.append(best_item)
        remaining.remove(best_item)
        uncovered -= best_cover
    for item in remaining:
        if len(selected) >= limit:
            break
        selected.append(item)
    item_ids = [item["item_id"] for item in selected[:limit]]
    if uncovered:
        raise ValueError(f"Smoke-test item selection failed to cover: {sorted(uncovered)}")
    return item_ids


def call_with_retry(
    client: OllamaClient,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    top_p: float,
    seed: int,
    max_tokens: int,
    parse_mode: str,
    rating_scale_max: int,
    require_reflection_fields: bool = False,
) -> Tuple[str, str, Dict[str, object]]:
    last_raw = ""
    for _ in range(2):
        raw_text, _meta = client.chat_json(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
        )
        last_raw = raw_text
        if parse_mode == "first":
            status, parsed = try_parse_first_pass(
                raw_text, rating_scale_max=rating_scale_max
            )
        else:
            status, parsed = try_parse_revision(
                raw_text,
                rating_scale_max=rating_scale_max,
                require_reflection_fields=require_reflection_fields,
            )
        if status == "ok":
            return status, raw_text, parsed
    return "invalid", last_raw, {}


def load_existing_first_pass(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    rows = load_csv_rows(path)
    return {row["item_id"]: row for row in rows}


def load_existing_results(path: Path) -> Dict[Tuple[str, str], Dict[str, str]]:
    if not path.exists():
        return {}
    rows = load_csv_rows(path)
    return {(row["item_id"], row["revision_condition_id"]): row for row in rows}


def load_existing_manifest_row(path: Path, run_id: str, model_name: str) -> Dict[str, str]:
    if not path.exists():
        return {}
    rows = load_csv_rows(path)
    for row in rows:
        if row["run_id"] == run_id and row["model_name"] == model_name:
            return row
    return {}


def preflight_analysis_profile(
    items: List[Dict[str, str]],
    analysis_profile: str,
    allow_paper_unsafe: bool,
) -> None:
    issues = evaluate_analysis_profile(items, analysis_profile)
    if issues and not allow_paper_unsafe:
        joined = "\n".join(f"- {issue}" for issue in issues)
        raise ValueError(
            "Preflight blocked this run because the selected analysis profile is paper-unsafe for the current items file.\n"
            f"{joined}\n"
            "Use --allow-paper-unsafe to override intentionally."
        )
    for issue in issues:
        print(f"[preflight] {issue}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items-file", default=str(ROOT / "data" / "items_offtherails_core.csv"))
    parser.add_argument("--conditions-file", default=str(ROOT / "data" / "revision_conditions.csv"))
    parser.add_argument("--results-root", default=str(ROOT / "results"))
    parser.add_argument("--backend", default="ollama")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=220)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--rating-scale-max", type=int, default=5)
    parser.add_argument(
        "--analysis-profile",
        choices=["continuous_primary", "binary_primary"],
        default="continuous_primary",
    )
    parser.add_argument("--allow-paper-unsafe", action="store_true")
    parser.add_argument(
        "--revision-schema-mode",
        choices=["minimal", "reflective_metadata"],
        default=DEFAULT_REVISION_SCHEMA_MODE,
    )
    args = parser.parse_args()

    items = load_csv_rows(Path(args.items_file))
    conditions = load_csv_rows(Path(args.conditions_file))
    item_scale_values = {row["gold_scale_max"] for row in items}
    if len(item_scale_values) != 1 or str(args.rating_scale_max) not in item_scale_values:
        raise ValueError(
            f"items file scale {sorted(item_scale_values)} does not match --rating-scale-max={args.rating_scale_max}"
        )
    preflight_analysis_profile(
        items,
        analysis_profile=args.analysis_profile,
        allow_paper_unsafe=args.allow_paper_unsafe,
    )
    smoke_item_ids = set(select_smoke_test_item_ids(items))

    run_id = args.run_id or (
        dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        + "_"
        + sanitize_model_name(args.model)
    )
    run_dir = Path(args.results_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    first_pass_path = run_dir / "first_pass_cache.csv"
    results_long_path = run_dir / "results_long.csv"
    manifest_path = run_dir / "run_manifest.csv"

    first_pass_cache = load_existing_first_pass(first_pass_path)
    existing_results = load_existing_results(results_long_path)

    client = OllamaClient()
    existing_manifest = load_existing_manifest_row(manifest_path, run_id, args.model)
    started_at = existing_manifest.get("started_at_utc", now_utc())
    model_version = client.resolve_model_version(args.model)

    first_pass_fieldnames = [
        "run_id",
        "model_name",
        "item_id",
        "raw_first_pass",
        "parse_status_first",
        "permissibility_first",
        "negative_intended_first",
        "confidence_first",
        "rationale_first",
    ]
    results_fieldnames = [
        "run_id",
        "model_name",
        "item_id",
        "scenario_id",
        "revision_condition_id",
        "means_side_effect",
        "evitability",
        "agency_mode",
        "raw_revision",
        "parse_status_revision",
        "first_focus",
        "neglected_factor",
        "permissibility_first",
        "negative_intended_first",
        "confidence_first",
        "rationale_first",
        "permissibility_final",
        "negative_intended_final",
        "confidence_final",
        "rationale_final",
        "gold_perm_mean",
        "gold_intent_mean",
        "gold_scale_min",
        "gold_scale_max",
        "gold_scale_mode",
        "gold_perm_binary",
        "gold_intent_binary",
        "binary_eval_perm",
        "binary_eval_intent",
        "perm_status_before",
        "perm_status_after",
        "intent_status_before",
        "intent_status_after",
        "perm_corrected",
        "perm_flipped_wrong",
        "intent_corrected",
        "intent_flipped_wrong",
        "changed_any_answer",
        "perm_distance_first",
        "perm_distance_final",
        "intent_distance_first",
        "intent_distance_final",
        "perm_distance_improved",
        "perm_distance_worsened",
        "intent_distance_improved",
        "intent_distance_worsened",
    ]

    ordered_items = sorted(items, key=lambda row: (row["item_id"] not in smoke_item_ids, row["item_id"]))
    if args.max_items > 0:
        ordered_items = ordered_items[: args.max_items]

    for index, item in enumerate(ordered_items, start=1):
        print(f"[{index}/{len(ordered_items)}] first pass {item['item_id']}")
        cached_first = first_pass_cache.get(item["item_id"])
        if cached_first is None:
            status, raw_text, parsed = call_with_retry(
                client=client,
                model=args.model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=render_first_pass_prompt(item, scale_max=args.rating_scale_max),
                temperature=args.temperature,
                top_p=args.top_p,
                seed=args.seed,
                max_tokens=args.max_tokens,
                parse_mode="first",
                rating_scale_max=args.rating_scale_max,
            )
            cached_first = {
                "run_id": run_id,
                "model_name": args.model,
                "item_id": item["item_id"],
                "raw_first_pass": raw_text,
                "parse_status_first": status,
                "permissibility_first": parsed.get("permissibility_agreement", ""),
                "negative_intended_first": parsed.get(
                    "negative_outcome_intended_agreement", ""
                ),
                "confidence_first": parsed.get("confidence", ""),
                "rationale_first": parsed.get("rationale_short", ""),
            }
            append_csv_row(first_pass_path, cached_first, first_pass_fieldnames)
            first_pass_cache[item["item_id"]] = cached_first

        if cached_first["parse_status_first"] != "ok":
            raise RuntimeError(f"First-pass parsing failed for {item['item_id']}")

        first_pass_json = cached_first["raw_first_pass"].strip()

        for condition in conditions:
            key = (item["item_id"], condition["revision_condition_id"])
            if key in existing_results:
                continue
            print(
                f"    revision {condition['revision_condition_id']} for {item['item_id']}"
            )
            status, raw_text, parsed = call_with_retry(
                client=client,
                model=args.model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=render_revision_prompt(
                    item,
                    first_pass_json=first_pass_json,
                    condition_instruction=condition["condition_instruction"],
                    scale_max=args.rating_scale_max,
                    schema_mode=args.revision_schema_mode,
                ),
                temperature=args.temperature,
                top_p=args.top_p,
                seed=args.seed,
                max_tokens=args.max_tokens,
                parse_mode="revision",
                rating_scale_max=args.rating_scale_max,
                require_reflection_fields=args.revision_schema_mode
                == "reflective_metadata",
            )
            result_row: Dict[str, object] = {
                "run_id": run_id,
                "model_name": args.model,
                "item_id": item["item_id"],
                "scenario_id": item["scenario_id"],
                "revision_condition_id": condition["revision_condition_id"],
                "means_side_effect": item["means_side_effect"],
                "evitability": item["evitability"],
                "agency_mode": item["agency_mode"],
                "raw_revision": raw_text,
                "parse_status_revision": status,
                "first_focus": parsed.get("first_focus", ""),
                "neglected_factor": parsed.get("neglected_factor", ""),
                "permissibility_first": int(cached_first["permissibility_first"]),
                "negative_intended_first": int(cached_first["negative_intended_first"]),
                "confidence_first": int(cached_first["confidence_first"]),
                "rationale_first": cached_first["rationale_first"],
                "permissibility_final": parsed.get("permissibility_agreement", ""),
                "negative_intended_final": parsed.get(
                    "negative_outcome_intended_agreement", ""
                ),
                "confidence_final": parsed.get("confidence", ""),
                "rationale_final": parsed.get("rationale_short", ""),
                "gold_perm_mean": item["gold_perm_mean"],
                "gold_intent_mean": item["gold_intent_mean"],
                "gold_scale_min": item["gold_scale_min"],
                "gold_scale_max": item["gold_scale_max"],
                "gold_scale_mode": item["gold_scale_mode"],
                "gold_perm_binary": item["gold_perm_binary"],
                "gold_intent_binary": item["gold_intent_binary"],
                "binary_eval_perm": item["binary_eval_perm"],
                "binary_eval_intent": item["binary_eval_intent"],
                "perm_status_before": "",
                "perm_status_after": "",
                "intent_status_before": "",
                "intent_status_after": "",
                "perm_corrected": "",
                "perm_flipped_wrong": "",
                "intent_corrected": "",
                "intent_flipped_wrong": "",
                "changed_any_answer": "",
                "perm_distance_first": "",
                "perm_distance_final": "",
                "intent_distance_first": "",
                "intent_distance_final": "",
                "perm_distance_improved": "",
                "perm_distance_worsened": "",
                "intent_distance_improved": "",
                "intent_distance_worsened": "",
            }
            if status == "ok":
                result_row = add_scoring_fields(result_row)
            append_csv_row(results_long_path, result_row, results_fieldnames)
            existing_results[key] = result_row

    completed_at = now_utc()
    manifest_row = {
        "run_id": run_id,
        "run_group": "offtherails_core_80",
        "backend": args.backend,
        "model_name": args.model,
        "model_version": model_version,
        "prompt_language": "English",
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "rating_scale_max": args.rating_scale_max,
        "analysis_profile": args.analysis_profile,
        "first_pass_format": FIRST_PASS_FORMAT,
        "first_pass_prompt_version": FIRST_PASS_PROMPT_VERSION,
        "revision_prompt_version": REVISION_PROMPT_VERSION,
        "revision_schema_mode": args.revision_schema_mode,
        "item_count": len(ordered_items),
        "condition_count": len(conditions),
        "items_file": args.items_file,
        "conditions_file": args.conditions_file,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
    }
    upsert_csv_row(
        manifest_path,
        manifest_row,
        key_fields=["run_id", "model_name"],
        fieldnames=list(manifest_row.keys()),
    )
    print(f"Completed run {run_id}")
    print(f"Run directory: {run_dir}")


if __name__ == "__main__":
    main()
