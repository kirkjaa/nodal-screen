"""Synthetic cohort for the program view.

The seed is fixed. Pathway codes are not restated here: each person is
passed through ``screen.flags._pathway``. Age bands are the display bands
from the T04 card (the contract's ``65-74`` figure is only an example).

A count or a rate whose cell has fewer than 10 people is ``<10`` and is
not plotted. Totals keep the true count. Complementary suppression is not
applied.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from screen.flags import _pathway

SEED = 20261113
MIN_CELL = 10
SUPPRESSED = "<10"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "cohort.json"

SITES = (
    {"id": "PHC-1", "type": "Primary care centre"},
    {"id": "SCH-1", "type": "School"},
    {"id": "MAJ-1", "type": "Community majlis"},
)
CHILD_BANDS = ("3-4", "5-6", "7-8", "9-12")
ADULT_BANDS = ("18-39", "40-59", "60-69", "70-79", "80-99")

# site, nationality, group, age band, people. Sums to 600.
# SCH-1 x Non-national is 7. PHC-1 x 80-99 is 6. Large cells sit beside them.
QUOTAS = (
    ("SCH-1", "UAE national", "child", "3-4", 36),
    ("SCH-1", "UAE national", "child", "5-6", 40),
    ("SCH-1", "UAE national", "child", "7-8", 40),
    ("SCH-1", "UAE national", "child", "9-12", 34),
    ("SCH-1", "Non-national", "child", "3-4", 3),
    ("SCH-1", "Non-national", "child", "5-6", 2),
    ("SCH-1", "Non-national", "child", "7-8", 2),
    ("PHC-1", "UAE national", "child", "3-4", 15),
    ("PHC-1", "UAE national", "child", "5-6", 15),
    ("PHC-1", "UAE national", "child", "7-8", 15),
    ("PHC-1", "UAE national", "child", "9-12", 15),
    ("PHC-1", "UAE national", "adult", "18-39", 20),
    ("PHC-1", "UAE national", "adult", "40-59", 25),
    ("PHC-1", "UAE national", "adult", "60-69", 20),
    ("PHC-1", "UAE national", "adult", "70-79", 12),
    ("PHC-1", "UAE national", "adult", "80-99", 3),
    ("PHC-1", "Non-national", "child", "3-4", 12),
    ("PHC-1", "Non-national", "child", "5-6", 12),
    ("PHC-1", "Non-national", "child", "7-8", 12),
    ("PHC-1", "Non-national", "child", "9-12", 12),
    ("PHC-1", "Non-national", "adult", "18-39", 20),
    ("PHC-1", "Non-national", "adult", "40-59", 20),
    ("PHC-1", "Non-national", "adult", "60-69", 16),
    ("PHC-1", "Non-national", "adult", "70-79", 13),
    ("PHC-1", "Non-national", "adult", "80-99", 3),
    ("MAJ-1", "UAE national", "adult", "18-39", 25),
    ("MAJ-1", "UAE national", "adult", "40-59", 30),
    ("MAJ-1", "UAE national", "adult", "60-69", 25),
    ("MAJ-1", "UAE national", "adult", "70-79", 16),
    ("MAJ-1", "UAE national", "adult", "80-99", 4),
    ("MAJ-1", "Non-national", "adult", "18-39", 20),
    ("MAJ-1", "Non-national", "adult", "40-59", 25),
    ("MAJ-1", "Non-national", "adult", "60-69", 20),
    ("MAJ-1", "Non-national", "adult", "70-79", 14),
    ("MAJ-1", "Non-national", "adult", "80-99", 4),
)

# (metric id, rule, severity). Chosen so _pathway sees real rule names.
CHILD_CASES = (
    (),
    (),
    (),
    (),
    (("heel_first_share", "toe_walk", "flag"),),
    (("heel_first_share", "toe_walk", "flag"),),
    (("gait_speed", "norm_z", "flag"),),
    (("cadence", "norm_z", "flag"), ("double_support", "norm_z", "flag")),
    (("heel_first_share", "toe_walk", "watch"), ("gait_speed", "norm_z", "watch")),
)
ADULT_CASES = (
    (),
    (),
    (),
    (),
    (("tug_time", "cutoff", "flag"),),
    (("tug_time", "cutoff", "flag"),),
    (("sls_time", "norm_z", "flag"),),
    (("gait_speed", "cutoff", "flag"),),
    (("sts5_time", "cutoff", "flag"),),
    (("step_length_si", "asymmetry", "flag"),),
    (("step_time_si", "asymmetry", "flag"),),
    (("gait_speed", "change", "flag"),),
)

SCREENED_P = 0.84
ATTEND_P = 0.78
FLAG_ORIGIN = date(2026, 5, 4)
SKIP_PID = {"child": {7}, "adult": {102}}


def cell_count(count: int, *, total: bool = False) -> int | str:
    """Show ``<10`` under 10 people. A total always keeps the true count."""
    if total or count >= MIN_CELL:
        return count
    return SUPPRESSED


def cell_rate(count: int, rate: float) -> float | str:
    """Suppress a rate when its cell has fewer than 10 people."""
    if count < MIN_CELL:
        return SUPPRESSED
    return rate


def cell_plotted(count: int) -> bool:
    """A suppressed cell is not plotted. Ten or more may be plotted."""
    return count >= MIN_CELL


def flag_specs(triples: tuple[tuple[str, str, str], ...] | list) -> list[dict]:
    specs = []
    for index, (metric_id, rule, severity) in enumerate(triples, start=1):
        specs.append({
            "id": f"F{index}",
            "rule": rule,
            "severity": severity,
            "metric_ids": [metric_id],
        })
    return specs


def pathway_code(group: str, specs: list[dict]) -> str:
    return _pathway(group, specs)["code"]


def _stored_flags(triples, code: str) -> list[str]:
    hard = [metric_id for metric_id, _rule, severity in triples if severity == "flag"]
    if hard:
        return hard
    if code != "ROUTINE":
        return [metric_id for metric_id, _rule, _severity in triples]
    return []


def _slots() -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for site, nationality, group, band, count in QUOTAS:
        rows.extend((site, nationality, group, band) for _ in range(count))
    if len(rows) != 600:
        raise RuntimeError(f"quota sum is {len(rows)}, expected 600")
    return rows


def _pid(group: str, number: int) -> str:
    letter = "C" if group == "child" else "A"
    return f"SYN-{letter}-{number:04d}"


def generate(seed: int = SEED, today: date | None = None) -> dict:
    """Build the cohort document. Does not write a file."""
    today = today or date.today()
    rng = random.Random(seed)
    counters = {"child": 0, "adult": 0}
    people = []
    for site, nationality, group, band in _slots():
        expected = CHILD_BANDS if group == "child" else ADULT_BANDS
        if band not in expected:
            raise ValueError(f"{group} has no band {band}")
        counters[group] += 1
        while counters[group] in SKIP_PID[group]:
            counters[group] += 1
        screened = rng.random() < SCREENED_P
        triples = rng.choice(CHILD_CASES if group == "child" else ADULT_CASES) if screened else ()
        specs = flag_specs(triples)
        code = pathway_code(group, specs)
        flags = _stored_flags(triples, code)
        flag_date = ""
        attended_date = ""
        if flags:
            flag_day = FLAG_ORIGIN + timedelta(days=rng.randrange(0, 120))
            flag_date = flag_day.isoformat()
            if rng.random() < ATTEND_P:
                attended_date = (flag_day + timedelta(days=rng.randrange(3, 91))).isoformat()
        people.append({
            "pid": _pid(group, counters[group]),
            "group": group,
            "age_band": band,
            "sex": rng.choice(("F", "M")),
            "nationality_group": nationality,
            "site": site,
            "invited": True,
            "screened": screened,
            "flags": flags,
            "pathway": code,
            "flag_date": flag_date,
            "attended_date": attended_date,
        })
    people.sort(key=lambda person: person["pid"])
    return {
        "schema": "nodal-screen/cohort@1",
        "provenance": "synthetic",
        "generated": today.isoformat(),
        "sites": [dict(site) for site in SITES],
        "people": people,
    }


def write_cohort(path: Path | None = None, seed: int = SEED, today: date | None = None) -> dict:
    """Write ``data/cohort.json`` only. Does not touch ``data/samples/``."""
    path = Path(path) if path is not None else DEFAULT_PATH
    payload = generate(seed, today or date.today())
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return payload


def main() -> None:
    write_cohort(DEFAULT_PATH)


if __name__ == "__main__":
    main()
