"""Facts and prompts for the screening letters. No model call lives here."""

from __future__ import annotations

import json
from pathlib import Path

FAMILY_WORD_LIMIT = 160
CLINICIAN_WORD_LIMIT = 140
KINDS = ("family_letter", "clinician_brief")
TASK_ORDER = ("gait", "tug", "sts5", "sls", "tandem", "hop")

_SOURCES: dict | None = None


def sources() -> dict:
    global _SOURCES
    if _SOURCES is None:
        path = Path(__file__).resolve().parents[1] / "data" / "sources.json"
        _SOURCES = json.loads(path.read_text(encoding="utf-8"))
    return _SOURCES


def source_name(source_id: str) -> str:
    if source_id == "nodal-rule":
        return "NODAL screening rule"
    entry = sources().get(source_id)
    if isinstance(entry, dict) and entry.get("citation"):
        return str(entry["citation"])
    return source_id


def _metrics(session: dict) -> list[dict]:
    tasks = session.get("tasks") or {}
    order = [name for name in TASK_ORDER if name in tasks]
    order += sorted(name for name in tasks if name not in TASK_ORDER)
    rows = []
    for name in order:
        for metric in (tasks.get(name) or {}).get("metrics") or []:
            ref = metric.get("ref") if isinstance(metric.get("ref"), dict) else None
            cutoff = metric.get("cutoff") if isinstance(metric.get("cutoff"), dict) else None
            rows.append({
                "id": metric.get("id"),
                "side": metric.get("side"),
                "value": metric.get("value"),
                "unit": metric.get("unit"),
                "status": metric.get("status"),
                "norm_mean": None if ref is None else ref.get("mean"),
                "norm_z": None if ref is None else ref.get("z"),
                "cutoff": None if cutoff is None else {
                    "op": cutoff.get("op"),
                    "threshold": cutoff.get("threshold"),
                    "met": cutoff.get("met"),
                    "source": source_name(str(cutoff.get("source_id") or "")),
                },
            })
    return rows


def _flags(session: dict) -> list[dict]:
    rows = []
    for flag in session.get("flags") or []:
        names = []
        for source_id in flag.get("source_ids") or []:
            name = source_name(str(source_id))
            if name not in names:
                names.append(name)
        rows.append({
            "title": flag.get("title"),
            "evidence": flag.get("evidence"),
            "sources": names,
        })
    return rows


def facts(session: dict) -> dict:
    """Only the fields a letter may use. No video, paths, or ids."""
    participant = session.get("participant") or {}
    qc = session.get("qc") or {}
    out = {
        "display_name": participant.get("display_name"),
        "group": participant.get("group"),
        "age_band": participant.get("age_band"),
        "sex": participant.get("sex"),
        "metrics": _metrics(session),
        "flags": _flags(session),
        "qc": {
            "status": qc.get("status"),
            "confidence": qc.get("confidence"),
            "notes": list(qc.get("notes") or []),
        },
        "suggested_pathway": session.get("suggested_pathway"),
    }
    if session.get("review"):
        out["review"] = session["review"]
    return out


def _screening_rules() -> str:
    return (
        "This is screening. It does not diagnose. "
        "No reassurance or alarm beyond the facts. "
        "Use no number that is not in the facts. "
        'Return JSON with keys "en" and "ar". '
        "The ar text is a machine translation pending native review."
    )


def build_prompt(session: dict, kind: str) -> tuple[str, str]:
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")
    qc_status = ((session.get("qc") or {}).get("status"))
    if kind == "family_letter" and qc_status == "insufficient":
        ask = (
            "Write only a recapture letter: the capture should be repeated, and why, "
            "from the qc notes. Do not describe other results, flags, or a pathway. "
            f"At most {FAMILY_WORD_LIMIT} words. "
            "Plain words for a reading age near 12. "
            "The reader is a parent or guardian when group is child, otherwise the participant."
        )
    elif kind == "family_letter":
        ask = (
            "Write a letter to a parent or guardian when group is child, "
            "otherwise to the participant. "
            f"At most {FAMILY_WORD_LIMIT} words. "
            "Plain words for a reading age near 12. "
            "Say what was measured. "
            "For each result a clinician will look at, give one line on why. "
            "Give the suggested next step as a suggestion. "
            "Say that a clinician decides."
        )
    else:
        ask = (
            "Write a brief for a clinician. "
            f"At most {CLINICIAN_WORD_LIMIT} words. "
            "Each flag with its evidence and source, the QC confidence, "
            "the suggested pathway, and what was not measured or has no reference."
        )
    system = ask + " " + _screening_rules()
    user = json.dumps(facts(session), ensure_ascii=False, indent=2)
    return system, user
