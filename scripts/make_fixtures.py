"""Write the two shell fixtures from raw values.

The script holds participant, visit, qc, and each metric's id, side, value,
and unit. screen.flags.apply fills ref, cutoff, status, flags, and the pathway.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screen import flags

SAMPLES = ROOT / "data" / "samples"
NOTE = "Illustrative shell fixture. Hand-written fixture; replaced by pipeline output."


def metric(metric_id: str, value: float, unit: str, side: str | None = None) -> dict:
    return {"id": metric_id, "side": side, "value": value, "unit": unit}


def task(rows: list[dict], curves: bool = False) -> dict:
    body = {"metrics": rows}
    if curves:
        body["curves"] = {}
    return body


def shell(participant: dict, visit: dict, qc: dict, tasks: dict, history: list) -> dict:
    return {
        "schema": "nodal-screen/session@1",
        "provenance": "synthetic",
        "provenance_note": NOTE,
        "participant": participant,
        "visit": visit,
        "qc": qc,
        "tasks": tasks,
        "flags": [],
        "suggested_pathway": {"code": "ROUTINE", "reason_flag_ids": []},
        "review": None,
        "history": history,
        "ai_texts": {},
    }


RAW = [
    shell(
        {
            "pid": "SYN-C-0007",
            "display_name": "Child 7",
            "group": "child",
            "age_y": 7,
            "age_band": "6-7",
            "sex": "F",
            "height_m": 1.22,
            "segment": {"site": "PHC-1", "nationality_group": "UAE national"},
            "consent": {"type": "guardian+assent", "date": "2026-11-14", "language": "ar"},
        },
        {
            "visit_id": "V1",
            "date": "2026-11-14",
            "site": "PHC-1",
            "kit": "M1, 4 cameras",
            "operator": "OP-02",
        },
        {
            "status": "ok",
            "confidence": "high",
            "strides_left": 6,
            "strides_right": 6,
            "keypoint_confidence": 0.91,
            "calib_residual_px": 0.4,
            "notes": [],
        },
        {
            "gait": task([
                metric("gait_speed", 1.05, "m/s"),
                metric("cadence", 146, "steps/min"),
                metric("heel_first_share", 22, "% of strides", "left"),
                metric("heel_first_share", 28, "% of strides", "right"),
            ], curves=True),
            "tug": task([metric("tug_time", 8.4, "s")]),
            "sts5": task([metric("sts5_time", 9.1, "s")]),
            "sls": task([
                metric("sls_time", 7.5, "s", "left"),
                metric("sls_time", 6.8, "s", "right"),
            ]),
            "tandem": task([metric("tandem_steps", 8, "steps of 10")]),
            "hop": task([
                metric("hop_count", 6, "hops", "left"),
                metric("hop_count", 5, "hops", "right"),
            ]),
        },
        [{"visit_id": "V0", "date": "2025-11-10", "metrics": {"gait_speed": 1.02}}],
    ),
    shell(
        {
            "pid": "SYN-A-0102",
            "display_name": "Adult 70",
            "group": "adult",
            "age_y": 70,
            "age_band": "65-74",
            "sex": "M",
            "height_m": 1.72,
            "segment": {"site": "PHC-1", "nationality_group": "Non-national"},
            "consent": {"type": "adult", "date": "2026-11-14", "language": "en"},
        },
        {
            "visit_id": "V1",
            "date": "2026-11-14",
            "site": "PHC-1",
            "kit": "M1, 4 cameras",
            "operator": "OP-02",
        },
        {
            "status": "insufficient",
            "confidence": "low",
            "strides_left": 2,
            "strides_right": 1,
            "keypoint_confidence": 0.42,
            "calib_residual_px": 1.8,
            "notes": ["Too few strides to report."],
        },
        {
            "gait": task([
                metric("gait_speed", 0.9, "m/s"),
                metric("cadence", 104, "steps/min"),
            ], curves=True),
            "tug": task([metric("tug_time", 13.2, "s")]),
            "sts5": task([metric("sts5_time", 14.0, "s")]),
            "sls": task([metric("sls_time", 3.1, "s", "left")]),
        },
        [],
    ),
]


def build_all() -> list[dict]:
    return [flags.apply(copy.deepcopy(raw)) for raw in RAW]


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for session in build_all():
        pid = session["participant"]["pid"]
        path = SAMPLES / f"{pid}.json"
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
