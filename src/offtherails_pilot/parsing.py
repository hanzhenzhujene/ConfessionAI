"""Strict response parsing and validation."""

from __future__ import annotations

import json
from typing import Dict, Iterable, Tuple

FIRST_FOCUS_VALUES = {
    "outcome",
    "intention",
    "means_side_effect",
    "avoidability",
    "omission_commission",
    "other",
}

NEGLECTED_FACTOR_VALUES = {
    "intention",
    "means_side_effect",
    "avoidability",
    "omission_commission",
    "none",
    "other",
}

ENUM_NORMALIZATION = {
    "outcomes": "outcome",
    "intent": "intention",
    "side_effect": "means_side_effect",
    "means_vs_side_effect": "means_side_effect",
    "means_end": "means_side_effect",
    "means_end_structure": "means_side_effect",
    "means/end structure": "means_side_effect",
    "omission": "omission_commission",
    "commission": "omission_commission",
    "omission_vs_commission": "omission_commission",
    "avoidability_of_harm": "avoidability",
}

INTENTION_KEY_ALIASES = (
    "negative_outcome_intended_agreement",
    "negative_outcome_intention_agreement",
    "negative_outcome_intentioned_agreement",
)


def _count_words(text: str) -> int:
    return len([token for token in text.strip().split() if token])


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("bool is not a valid integer score")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"cannot coerce to int: {value!r}")


def _ensure_range(name: str, value: int, valid: Iterable[int]) -> int:
    if value not in set(valid):
        raise ValueError(f"{name} out of range: {value}")
    return value


def strict_load_json(raw_text: str) -> Dict[str, object]:
    text = raw_text.strip()
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("response must be a JSON object")
    return obj


def _normalize_enum(value: object) -> str:
    text = str(value).strip().lower()
    return ENUM_NORMALIZATION.get(text, text)


def _get_first_present(obj: Dict[str, object], keys: Iterable[str]) -> object:
    for key in keys:
        if key in obj:
            return obj[key]
    raise KeyError(f"missing keys: {tuple(keys)}")


def parse_first_pass_response(raw_text: str, rating_scale_max: int) -> Dict[str, object]:
    obj = strict_load_json(raw_text)
    permissibility = _ensure_range(
        "permissibility_agreement",
        _to_int(obj["permissibility_agreement"]),
        range(1, rating_scale_max + 1),
    )
    intention = _ensure_range(
        "negative_outcome_intended_agreement",
        _to_int(_get_first_present(obj, INTENTION_KEY_ALIASES)),
        range(1, rating_scale_max + 1),
    )
    confidence = _ensure_range("confidence", _to_int(obj["confidence"]), range(1, 6))
    rationale = str(obj["rationale_short"]).strip()
    if not rationale:
        raise ValueError("rationale_short cannot be empty")
    if _count_words(rationale) > 25:
        raise ValueError("rationale_short exceeds 25 words")
    return {
        "permissibility_agreement": permissibility,
        "negative_outcome_intended_agreement": intention,
        "confidence": confidence,
        "rationale_short": rationale,
    }


def parse_revision_response(
    raw_text: str,
    rating_scale_max: int,
    require_reflection_fields: bool = False,
) -> Dict[str, object]:
    obj = strict_load_json(raw_text)
    first_focus = ""
    neglected_factor = ""
    if require_reflection_fields:
        first_focus = _normalize_enum(obj["first_focus"])
        neglected_factor = _normalize_enum(obj["neglected_factor"])
    else:
        if "first_focus" in obj:
            first_focus = _normalize_enum(obj["first_focus"])
        if "neglected_factor" in obj:
            neglected_factor = _normalize_enum(obj["neglected_factor"])
    if first_focus and first_focus not in FIRST_FOCUS_VALUES:
        raise ValueError(f"invalid first_focus: {first_focus}")
    if neglected_factor and neglected_factor not in NEGLECTED_FACTOR_VALUES:
        raise ValueError(f"invalid neglected_factor: {neglected_factor}")
    permissibility = _ensure_range(
        "permissibility_agreement",
        _to_int(obj["permissibility_agreement"]),
        range(1, rating_scale_max + 1),
    )
    intention = _ensure_range(
        "negative_outcome_intended_agreement",
        _to_int(_get_first_present(obj, INTENTION_KEY_ALIASES)),
        range(1, rating_scale_max + 1),
    )
    confidence = _ensure_range("confidence", _to_int(obj["confidence"]), range(1, 6))
    rationale = str(obj["rationale_short"]).strip()
    if not rationale:
        raise ValueError("rationale_short cannot be empty")
    if _count_words(rationale) > 35:
        raise ValueError("rationale_short exceeds 35 words")
    return {
        "first_focus": first_focus,
        "neglected_factor": neglected_factor,
        "permissibility_agreement": permissibility,
        "negative_outcome_intended_agreement": intention,
        "confidence": confidence,
        "rationale_short": rationale,
    }


def try_parse_first_pass(raw_text: str, rating_scale_max: int) -> Tuple[str, Dict[str, object]]:
    try:
        return "ok", parse_first_pass_response(raw_text, rating_scale_max=rating_scale_max)
    except Exception:
        return "invalid", {}


def try_parse_revision(
    raw_text: str,
    rating_scale_max: int,
    require_reflection_fields: bool = False,
) -> Tuple[str, Dict[str, object]]:
    try:
        return "ok", parse_revision_response(
            raw_text,
            rating_scale_max=rating_scale_max,
            require_reflection_fields=require_reflection_fields,
        )
    except Exception:
        return "invalid", {}
