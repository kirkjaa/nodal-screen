"""Apply reference bands, cut-offs and pathway suggestions.

Pure function: the only file read is through `screen.norms`. Boundaries used
here, where the contract names a closed range and an open "beyond":

- bad-direction z above 2.0 is a flag; 1.5 through 2.0, including both ends, is a watch
- symmetry index at or above 15 is a flag; 10 up to but not including 15 is a watch
- heel-first share below 50 is a flag; 50 through 80 is a watch
"""

from __future__ import annotations

import copy

from screen import norms

# Direction that counts against the participant. From CONTRACT section 3.
BAD = {
    "gait_speed": "low",
    "cadence": "both",
    "stride_length": "low",
    "stride_length_h": "low",
    "step_time_cv": "high",
    "double_support": "high",
    "step_length_si": "high",
    "step_time_si": "high",
    "knee_rom": "low",
    "heel_first_share": "low",
    "tug_time": "high",
    "sts5_time": "high",
    "sls_time": "low",
    "tandem_steps": "low",
    "hop_count": "low",
}

LABEL = {
    "gait_speed": "Gait speed",
    "cadence": "Cadence",
    "stride_length": "Stride length",
    "stride_length_h": "Stride length over height",
    "step_time_cv": "Step-time variability",
    "double_support": "Double support",
    "step_length_si": "Step-length symmetry",
    "step_time_si": "Step-time symmetry",
    "knee_rom": "Knee range",
    "heel_first_share": "Heel-first contact",
    "tug_time": "Timed Up and Go",
    "sts5_time": "Five-time chair stand",
    "sls_time": "Single-leg stance",
    "tandem_steps": "Tandem steps",
    "hop_count": "Hop count",
}

SOURCE_NAME = {
    "ewgsop2": "EWGSOP2",
    "awgs2019": "AWGS 2019",
    "steadi": "STEADI",
    "perera2006": "Perera 2006",
    "nodal-rule": "NODAL screening rule",
    "bohannon2011": "Bohannon 2011",
}

TASK_ORDER = ("gait", "tug", "sts5", "sls", "tandem", "hop")
RANK = {"no_reference": 0, "in_range": 1, "borderline": 2, "out_of_range": 3}


def symmetry_index(left: float, right: float) -> float | None:
    """SI = 100 * |L - R| / (0.5 * (L + R))."""
    denom = 0.5 * (left + right)
    if denom == 0:
        return None
    return 100.0 * abs(left - right) / denom


def _meets(value: float, op: str, threshold: float) -> bool:
    if op == ">=":
        return value >= threshold
    if op == ">":
        return value > threshold
    if op == "<=":
        return value <= threshold
    if op == "<":
        return value < threshold
    raise ValueError(f"unknown op {op}")


def _worse(current: str | None, new: str) -> str:
    if current is None or RANK[new] >= RANK[current]:
        return new
    return current


def _num(value: float) -> str:
    return f"{value:.4g}"


def _side_suffix(metric: dict) -> str:
    side = metric.get("side")
    if side in ("left", "right"):
        return f" on the {side}"
    return ""


def _iter_metrics(session: dict):
    tasks = session.get("tasks") or {}
    keys = [key for key in TASK_ORDER if key in tasks]
    keys += [key for key in tasks if key not in TASK_ORDER]
    for key in keys:
        for metric in tasks[key].get("metrics") or []:
            yield metric


def _bad_magnitude(metric_id: str, z: float) -> float:
    direction = BAD.get(metric_id, "both")
    if direction == "low":
        return max(-z, 0.0)
    if direction == "high":
        return max(z, 0.0)
    return abs(z)


def _band_rows(tables: norms.Tables, metric_id: str, group: str):
    rows = norms.cutoffs_for(metric_id, group, "ewgsop2", tables)
    flag_row = watch_row = None
    for row in rows:
        if row.source_id != "nodal-rule":
            continue
        text = row.meaning.lower()
        if text.startswith("flag"):
            flag_row = row
        elif text.startswith("watch"):
            watch_row = row
    return flag_row, watch_row


def _change_bands(tables: norms.Tables):
    rows = [
        row for row in tables.cutoffs
        if row.source_id == "perera2006" and row.metric == "gait_speed" and row.threshold is not None
    ]
    if len(rows) < 2:
        return None, None
    ordered = sorted(rows, key=lambda row: row.threshold)
    return ordered[0].threshold, ordered[1].threshold


def _pathway(group: str, flags: list[dict]) -> dict:
    hard = [flag for flag in flags if flag["severity"] == "flag"]
    watches = [flag for flag in flags if flag["severity"] == "watch"]

    def ids(chosen: list[dict]) -> list[str]:
        return [flag["id"] for flag in chosen]

    if group == "child" and (hard or len(watches) >= 2):
        return {"code": "WCV_DEV_REVIEW", "reason_flag_ids": ids(hard or watches)}

    falls = []
    for flag in hard:
        metrics = set(flag["metric_ids"])
        if "tug_time" in metrics or "sls_time" in metrics:
            falls.append(flag)
        elif "gait_speed" in metrics and flag["rule"] in ("cutoff", "norm_z"):
            falls.append(flag)
    if group == "adult" and falls:
        return {"code": "FALLS_PREVENTION", "reason_flag_ids": ids(falls)}

    sarco = [
        flag for flag in hard
        if flag["rule"] == "cutoff" and set(flag["metric_ids"]) & {"sts5_time", "gait_speed"}
    ]
    if group == "adult" and sarco:
        return {"code": "ADULT_SARCOPENIA", "reason_flag_ids": ids(sarco)}

    asymmetry = [flag for flag in hard if flag["rule"] == "asymmetry"]
    if group == "adult" and asymmetry:
        return {"code": "CLINICIAN_SPECIALIST", "reason_flag_ids": ids(asymmetry)}

    change = [flag for flag in hard if flag["rule"] == "change"]
    if group == "adult" and change:
        return {"code": "ADULT_EARLY_REVIEW", "reason_flag_ids": ids(change)}

    return {"code": "ROUTINE", "reason_flag_ids": []}


def apply(session: dict, cutoff_set: str = "ewgsop2", tables: norms.Tables | None = None) -> dict:
    """Fill ref, status, flags and suggested_pathway. Does not mutate `session`."""
    tables = tables if tables is not None else norms.load()
    session = copy.deepcopy(session)
    qc = session.get("qc") or {}
    confidence = qc.get("confidence") or ""
    participant = session.get("participant") or {}
    group = participant.get("group") or ""
    age_y = participant.get("age_y")

    if qc.get("status") == "insufficient":
        for metric in _iter_metrics(session):
            metric["status"] = "insufficient"
            metric["ref"] = None
        session["flags"] = []
        session["suggested_pathway"] = {"code": "RECAPTURE", "reason_flag_ids": []}
        return session

    flags: list[dict] = []

    def add(rule: str, severity: str, title: str, metric: dict, evidence: str, source_ids: list[str]):
        flags.append({
            "id": f"F{len(flags) + 1}",
            "rule": rule,
            "severity": severity,
            "title": title,
            "metric_ids": [metric["id"]],
            "evidence": evidence,
            "confidence": confidence,
            "source_ids": source_ids,
        })

    for metric in _iter_metrics(session):
        metric_id = metric.get("id")
        value = metric.get("value")
        metric["ref"] = None
        metric["status"] = None
        if value is None:
            metric["status"] = "no_reference"
            continue
        value = float(value)

        norm = norms.norm_for(metric_id, participant.get("sex") or "", age_y or 0, group, tables)
        if norm is not None:
            z = None
            if norm["sd"] not in (None, 0):
                z = (value - norm["mean"]) / norm["sd"]
            metric["ref"] = {
                "kind": "norm",
                "source_id": norm["source_id"],
                "mean": norm["mean"],
                "sd": norm["sd"],
                "z": z,
                "status": norm["status"],
            }
            if z is not None:
                magnitude = _bad_magnitude(metric_id, z)
                label = LABEL.get(metric_id, metric_id) + _side_suffix(metric)
                if magnitude > 2.0:
                    metric["status"] = "out_of_range"
                    add("norm_z", "flag", f"{label} beyond the reference band", metric,
                        f"z {_num(z)}", [norm["source_id"]])
                elif magnitude >= 1.5:
                    metric["status"] = "borderline"
                    add("norm_z", "watch", f"{label} near the edge of the reference band", metric,
                        f"z {_num(z)}", [norm["source_id"]])
                else:
                    metric["status"] = "in_range"

        published = [
            row for row in norms.cutoffs_for(metric_id, group, cutoff_set, tables)
            if row.source_id != "nodal-rule"
        ]
        hit = next((row for row in published if _meets(value, row.op, row.threshold)), None)
        if hit is not None:
            name = SOURCE_NAME.get(hit.source_id, hit.source_id)
            label = LABEL.get(metric_id, metric_id) + _side_suffix(metric)
            metric["status"] = _worse(metric["status"], "out_of_range")
            if metric["ref"] is None:
                metric["ref"] = {
                    "kind": "cutoff",
                    "source_id": hit.source_id,
                    "threshold": hit.threshold,
                    "op": hit.op,
                    "status": hit.status,
                }
            unit = metric.get("unit") or hit.unit
            add("cutoff", "flag", f"{label} at the {name} cut-off", metric,
                f"{_num(value)} {unit}, cut-off {hit.op} {_num(hit.threshold)} {hit.unit}",
                [hit.source_id])
        elif published and metric["status"] is None:
            row = published[0]
            metric["ref"] = {
                "kind": "cutoff",
                "source_id": row.source_id,
                "threshold": row.threshold,
                "op": row.op,
                "status": row.status,
            }
            metric["status"] = "in_range"

        if metric_id in ("step_length_si", "step_time_si", "heel_first_share"):
            allowed = metric_id != "heel_first_share" or (group == "child" and age_y is not None and age_y >= 3)
            flag_row, watch_row = _band_rows(tables, metric_id, group)
            if allowed and flag_row is not None:
                severity = None
                row = None
                if _meets(value, flag_row.op, flag_row.threshold):
                    severity, row = "flag", flag_row
                elif watch_row is not None and _meets(value, watch_row.op, watch_row.threshold):
                    severity, row = "watch", watch_row
                label = LABEL.get(metric_id, metric_id) + _side_suffix(metric)
                rule = "toe_walk" if metric_id == "heel_first_share" else "asymmetry"
                if severity is not None and row is not None:
                    metric["status"] = _worse(metric["status"], "out_of_range" if severity == "flag" else "borderline")
                    if metric["ref"] is None:
                        metric["ref"] = {
                            "kind": "cutoff",
                            "source_id": "nodal-rule",
                            "threshold": row.threshold,
                            "op": row.op,
                            "status": row.status,
                        }
                    add(rule, severity, f"{label} at the NODAL screening rule", metric,
                        f"{_num(value)} {metric.get('unit') or row.unit}, NODAL screening rule {row.op} {_num(row.threshold)}",
                        ["nodal-rule"])
                elif metric["status"] is None:
                    metric["status"] = "in_range"
                    if metric["ref"] is None and flag_row is not None:
                        metric["ref"] = {
                            "kind": "cutoff",
                            "source_id": "nodal-rule",
                            "threshold": flag_row.threshold,
                            "op": flag_row.op,
                            "status": flag_row.status,
                        }

        if metric["status"] is None:
            metric["status"] = "no_reference"

    speed = next((m for m in _iter_metrics(session) if m.get("id") == "gait_speed" and m.get("value") is not None), None)
    small, substantial = _change_bands(tables)
    if speed is not None and small is not None and substantial is not None:
        dated = []
        for visit in session.get("history") or []:
            metrics = visit.get("metrics") or {}
            if metrics.get("gait_speed") is None:
                continue
            dated.append((visit.get("date") or "", float(metrics["gait_speed"])))
        if dated:
            earliest = sorted(dated, key=lambda item: item[0])[0][1]
            drop = round(earliest - float(speed["value"]), 10)
            if drop >= small:
                severity = "flag" if drop >= substantial else "watch"
                speed["status"] = _worse(speed["status"], "out_of_range" if severity == "flag" else "borderline")
                add("change", severity, "Gait speed fell from an earlier visit", speed,
                    f"fell {_num(drop)} m/s from {_num(earliest)} m/s", ["perera2006"])

    session["flags"] = flags
    session["suggested_pathway"] = _pathway(group, flags)
    return session
