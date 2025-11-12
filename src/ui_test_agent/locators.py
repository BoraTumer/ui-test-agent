from __future__ import annotations

import re
from typing import Dict, List, Tuple

ROLE_PATTERN = re.compile(r"role=([a-zA-Z0-9_-]+)(\[(.+)\])?")
ATTR_PATTERN = re.compile(r"([a-zA-Z0-9_-]+)=['\"]?([^'\"]+)['\"]?")


def locator_candidates(raw: str) -> List[str]:
    parts = [part.strip() for part in raw.split("|") if part.strip()]
    return sorted(parts, key=_score_selector)


def _score_selector(selector: str) -> Tuple[int, int]:
    checks = [
        ("data-testid", 0),
        ("role=", 1),
        ("#", 2),
        ("[name", 3),
        ("[placeholder", 4),
        ("text=", 5),
    ]
    clean = selector.strip()
    for needle, score in checks:
        if needle == "#" and clean.startswith("#"):
            return (score, len(clean))
        if needle == "role=" and clean.startswith("role="):
            return (score, len(clean))
        if needle in clean:
            return (score, len(clean))
    if "nth-child" in clean:
        return (9, len(clean))
    return (6, len(clean))


def parse_role(raw: str) -> Tuple[str, Dict[str, str]]:
    match = ROLE_PATTERN.fullmatch(raw.strip())
    if not match:
        raise ValueError(f"Invalid role selector: {raw}")
    role = match.group(1)
    attrs_str = match.group(3) or ""
    attrs: Dict[str, str] = {}
    for attr_match in ATTR_PATTERN.finditer(attrs_str):
        attrs[attr_match.group(1)] = attr_match.group(2)
    return role, attrs
