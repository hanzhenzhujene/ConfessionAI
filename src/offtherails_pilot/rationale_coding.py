"""Lightweight keyword coding for short rationales."""

from __future__ import annotations

import re
from typing import Dict


PATTERNS = {
    "outcome": re.compile(
        r"\b(outcome|consequence|benefit|harm|inconvenience|distress|burden|frustration|cost|damage|effect|effects)\b",
        re.IGNORECASE,
    ),
    "intention": re.compile(
        r"\b(intent|intended|intention|motive|motives|purpose|aimed|aim|meant)\b",
        re.IGNORECASE,
    ),
    "structure": re.compile(
        r"\b(means|side effect|side-effect|means-end|means/end|as a means)\b",
        re.IGNORECASE,
    ),
    "responsibility": re.compile(
        r"\b(avoidable|avoidability|avoid|could have|prevent|prevented|preventable|responsibility|responsible|omission|commission|failed to)\b",
        re.IGNORECASE,
    ),
    "meta_revision": re.compile(
        r"\b(initially|at first|first\b|overlooked|neglected|focused on|reconsidered|re-examined|reexamined|haste|surface impression)\b",
        re.IGNORECASE,
    ),
}


def code_rationale(text: str) -> Dict[str, int]:
    rationale = text.strip()
    return {
        name: int(bool(pattern.search(rationale)))
        for name, pattern in PATTERNS.items()
    }
