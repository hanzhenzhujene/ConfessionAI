"""Dataset-level checks for analysis profiles and label balance."""

from __future__ import annotations

from typing import Dict, List


def summarize_binary_balance(items: List[Dict[str, str]]) -> Dict[str, int]:
    return {
        "perm_pos": sum(row.get("gold_perm_binary", "") == "1" for row in items),
        "perm_neg": sum(row.get("gold_perm_binary", "") == "0" for row in items),
        "perm_amb": sum(row.get("binary_eval_perm", "") == "0" for row in items),
        "intent_pos": sum(row.get("gold_intent_binary", "") == "1" for row in items),
        "intent_neg": sum(row.get("gold_intent_binary", "") == "0" for row in items),
        "intent_amb": sum(row.get("binary_eval_intent", "") == "0" for row in items),
    }


def evaluate_analysis_profile(items: List[Dict[str, str]], analysis_profile: str) -> List[str]:
    if not items:
        return ["Items file is empty."]

    issues: List[str] = []
    scales = {row.get("gold_scale_max", "") for row in items}
    balance = summarize_binary_balance(items)

    if analysis_profile == "binary_primary":
        if scales != {"5"}:
            issues.append(
                "Binary-primary runs require benchmark-aligned 1-5 ratings in the items file."
            )
        if balance["perm_pos"] == 0 or balance["perm_neg"] == 0:
            issues.append(
                "Permissibility gold labels are one-sided, so binary self-correction on permissibility is not paper-safe."
            )
        if balance["intent_pos"] == 0 or balance["intent_neg"] == 0:
            issues.append(
                "Intention gold labels are one-sided, so binary self-correction on intention is not paper-safe."
            )
        if balance["perm_pos"] < 10 or balance["perm_neg"] < 10:
            issues.append(
                "Permissibility does not have at least 10 positive and 10 negative gold items."
            )
        if balance["intent_pos"] < 10 or balance["intent_neg"] < 10:
            issues.append(
                "Intention does not have at least 10 positive and 10 negative gold items."
            )
    elif analysis_profile == "continuous_primary":
        if scales != {"5"}:
            issues.append(
                "This run uses an adapted rating scale rather than the benchmark-aligned 1-5 scale."
            )
    else:
        issues.append(f"Unknown analysis profile: {analysis_profile}")

    return issues
