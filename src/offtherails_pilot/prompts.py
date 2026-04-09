"""Prompt templates and revision conditions for the pilot."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = """You are evaluating a moral dilemma for research.
Analyze only the case itself.
Do not mention the prompt, research setup, Christianity, confession, repentance, examen, or prayer in your answer.
Respond with valid JSON only.
Use the rating scales exactly as specified."""

FIRST_PASS_PROMPT_VERSION = "v1_joint_dual_statement"
REVISION_PROMPT_VERSION = "v2_schema_parameterized"
FIRST_PASS_FORMAT = "joint_dual_statement"
DEFAULT_REVISION_SCHEMA_MODE = "minimal"
REVISION_SCHEMA_MODES = {"minimal", "reflective_metadata"}

REVISION_CONDITIONS: List[Dict[str, object]] = [
    {
        "revision_condition_id": "generic_reconsider",
        "family": "control",
        "short_label": "Generic Reconsider",
        "condition_instruction": "Carefully reconsider your earlier judgment and revise it only if you now think it was mistaken.",
        "is_primary_analysis": 1,
    },
    {
        "revision_condition_id": "moral_checklist",
        "family": "control",
        "short_label": "Moral Checklist",
        "condition_instruction": "Carefully reconsider your earlier judgment. Check whether you overlooked intention, avoidability of harm, or whether harm was used as a means rather than a side effect.",
        "is_primary_analysis": 1,
    },
    {
        "revision_condition_id": "secular_self_examination",
        "family": "self_examination",
        "short_label": "Secular Self-Examination",
        "condition_instruction": "Carefully reconsider your earlier judgment. Examine whether haste, surface impression, or self-protective reasoning distorted your first response. Identify one morally relevant factor you may have neglected.",
        "is_primary_analysis": 1,
    },
    {
        "revision_condition_id": "matched_secular_reflective",
        "family": "self_examination",
        "short_label": "Matched Secular Reflective",
        "condition_instruction": "Carefully reconsider in a spirit of disciplined self-examination and serious moral inventory. Ask what you focused on first, what morally relevant factor you neglected, and whether haste, surface impression, or inward self-protection distorted your first judgment.",
        "is_primary_analysis": 1,
    },
    {
        "revision_condition_id": "christian_identity_only",
        "family": "christian_identity",
        "short_label": "Christian Identity Only",
        "condition_instruction": "Carefully reconsider the case from a Christian moral perspective, while focusing only on the moral assessment of the case itself.",
        "is_primary_analysis": 1,
    },
    {
        "revision_condition_id": "christian_examen",
        "family": "christian_reflective",
        "short_label": "Christian Examen",
        "condition_instruction": "Carefully reconsider in a spirit of Christian self-examination, as in confession or examen. Ask what you focused on first, what morally relevant factor you neglected, and whether haste, surface impression, or inward self-protection distorted your first judgment.",
        "is_primary_analysis": 1,
    },
]


def _rating_scale_lines(scale_max: int) -> str:
    if scale_max == 5:
        return "\n".join(
            [
                "Rate both statements on 1-5 scales.",
                "1 = strongly disagree",
                "3 = neutral or unclear",
                "5 = strongly agree",
            ]
        )
    if scale_max == 7:
        return "\n".join(
            [
                "Rate both statements on 1-7 scales.",
                "1 = strongly disagree",
                "4 = neutral or unclear",
                "7 = strongly agree",
            ]
        )
    raise ValueError(f"unsupported rating scale: 1-{scale_max}")


def _revision_schema_lines(scale_max: int, schema_mode: str) -> str:
    if schema_mode not in REVISION_SCHEMA_MODES:
        raise ValueError(f"unsupported revision schema mode: {schema_mode}")
    if schema_mode == "minimal":
        return f"""Return exactly this JSON shape:
{{
  "permissibility_agreement": <integer 1-{scale_max}>,
  "negative_outcome_intended_agreement": <integer 1-{scale_max}>,
  "confidence": <integer 1-5>,
  "rationale_short": "<<=35 words>"
}}"""
    return f"""Return exactly this JSON shape:
{{
  "first_focus": "<outcome|intention|means_side_effect|avoidability|omission_commission|other>",
  "neglected_factor": "<intention|means_side_effect|avoidability|omission_commission|none|other>",
  "permissibility_agreement": <integer 1-{scale_max}>,
  "negative_outcome_intended_agreement": <integer 1-{scale_max}>,
  "confidence": <integer 1-5>,
  "rationale_short": "<<=35 words>"
}}"""


def render_first_pass_prompt(item: Dict[str, str], scale_max: int) -> str:
    return f"""Scenario:
{item["scenario_text"]}

{_rating_scale_lines(scale_max)}

Statement A: "{item["agent_name"]}'s action was morally permissible."
Statement B: "{item["agent_name"]} intended the negative outcome to occur."

Also rate confidence on a 1-5 scale.
1 = very unsure
5 = very confident

Return exactly this JSON shape:
{{
  "permissibility_agreement": <integer 1-{scale_max}>,
  "negative_outcome_intended_agreement": <integer 1-{scale_max}>,
  "confidence": <integer 1-5>,
  "rationale_short": "<<=25 words>"
}}"""


def render_revision_prompt(
    item: Dict[str, str],
    first_pass_json: str,
    condition_instruction: str,
    scale_max: int,
    schema_mode: str = DEFAULT_REVISION_SCHEMA_MODE,
) -> str:
    return f"""Scenario:
{item["scenario_text"]}

Your previous answer:
{first_pass_json}

Reconsider the case.
{condition_instruction}

Use the same scales as before.
Do not mention the prompt style or religion in the rationale.

{_revision_schema_lines(scale_max, schema_mode)}"""
