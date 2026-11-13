"""Checks on a drafted letter before it can be stored."""

from __future__ import annotations

import json
import re

from screen.ai_prompt import CLINICIAN_WORD_LIMIT, FAMILY_WORD_LIMIT, facts
from scripts.verify import PATTERNS, _scrub

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
PROTOCOL = {"3", "5", "10"}


def canon(token: str) -> str:
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    if token.startswith("0") and not token.startswith("0."):
        token = token.lstrip("0") or "0"
    return token


def allowed_numbers(session: dict) -> set[str]:
    blob = json.dumps(facts(session), ensure_ascii=False)
    allowed = {canon(token) for token in _NUMBER.findall(blob)}
    age = (session.get("participant") or {}).get("age_y")
    if isinstance(age, (int, float)) and not isinstance(age, bool):
        allowed.add(canon(format(age, "g")))
    allowed.add(canon(str(len(session.get("flags") or []))))
    allowed.update(PROTOCOL)
    return allowed


def check(text: str, session: dict, kind: str = "family_letter") -> list[str]:
    """Problems that block storing this text. Empty means it may be stored."""
    if kind == "family_letter":
        limit = FAMILY_WORD_LIMIT
    elif kind == "clinician_brief":
        limit = CLINICIAN_WORD_LIMIT
    else:
        raise ValueError(f"unknown kind: {kind}")

    problems = []
    scrubbed = _scrub(text or "")
    for pattern in PATTERNS:
        match = pattern.search(scrubbed)
        if match:
            problems.append(f"honesty: {match.group(0)}")

    words = re.findall(r"\S+", text or "")
    if len(words) > limit:
        problems.append(f"word limit: {len(words)} words, limit {limit}")

    allowed = allowed_numbers(session)
    seen = set()
    for token in _NUMBER.findall(text or ""):
        key = canon(token)
        if key in allowed or key in seen:
            continue
        seen.add(key)
        problems.append(f"number not in facts: {token}")
    return problems
