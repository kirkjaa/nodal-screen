"""Load reference values and cut-offs.

`norm_for` and `cutoffs_for` read the CSV files. A row with no mean, or a
cut-off with no threshold, is kept in the file and ignored by the lookups.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMS_PATH = ROOT / "data" / "norms.csv"
CUTOFFS_PATH = ROOT / "data" / "cutoffs.csv"


@dataclass(frozen=True)
class NormRow:
    source_id: str
    metric: str
    sex: str
    age_min: float | None
    age_max: float | None
    condition: str
    mean: float | None
    sd: float | None
    n: float | None
    table_ref: str
    status: str


@dataclass(frozen=True)
class CutoffRow:
    source_id: str
    metric: str
    group: str
    op: str
    threshold: float | None
    unit: str
    meaning: str
    table_ref: str
    status: str


@dataclass(frozen=True)
class Tables:
    norms: tuple[NormRow, ...]
    cutoffs: tuple[CutoffRow, ...]


def _blank(value: str) -> str:
    return (value or "").strip()


def _num(value: str) -> float | None:
    text = _blank(value)
    if text == "":
        return None
    return float(text)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load(norms_path: Path | None = None, cutoffs_path: Path | None = None) -> Tables:
    norms_path = Path(norms_path) if norms_path else NORMS_PATH
    cutoffs_path = Path(cutoffs_path) if cutoffs_path else CUTOFFS_PATH
    norms = tuple(
        NormRow(
            source_id=_blank(row["source_id"]),
            metric=_blank(row["metric"]),
            sex=_blank(row["sex"]) or "all",
            age_min=_num(row["age_min"]),
            age_max=_num(row["age_max"]),
            condition=_blank(row["condition"]),
            mean=_num(row["mean"]),
            sd=_num(row["sd"]),
            n=_num(row["n"]),
            table_ref=_blank(row["table_ref"]),
            status=_blank(row["status"]),
        )
        for row in _read_csv(norms_path)
    )
    cutoffs = tuple(
        CutoffRow(
            source_id=_blank(row["source_id"]),
            metric=_blank(row["metric"]),
            group=_blank(row["group"]) or "all",
            op=_blank(row["op"]),
            threshold=_num(row["threshold"]),
            unit=_blank(row["unit"]),
            meaning=_blank(row["meaning"]),
            table_ref=_blank(row["table_ref"]),
            status=_blank(row["status"]),
        )
        for row in _read_csv(cutoffs_path)
    )
    return Tables(norms, cutoffs)


def _age_span(row: NormRow) -> float:
    if row.age_min is None or row.age_max is None:
        return 1e9
    return row.age_max - row.age_min


def norm_for(metric: str, sex: str, age_y: float, group: str, tables: Tables | None = None):
    """Return mean, sd, source_id and status, or None.

    `group` is accepted so callers can pass the participant group. Matching
    uses metric, sex and age. A sex-specific row beats `all`, then the
    narrower age span wins, then a transcribed row beats a placeholder.
    Rows without a mean are not returned.
    """
    del group  # age bands already separate children from adult decades
    tables = tables if tables is not None else load()
    matches = []
    for row in tables.norms:
        if row.metric != metric or row.mean is None:
            continue
        if row.sex not in (sex, "all"):
            continue
        if row.age_min is None or row.age_max is None:
            continue
        if not (row.age_min <= age_y <= row.age_max):
            continue
        matches.append(row)
    if not matches:
        return None
    status_rank = {"verified": 0, "transcribed": 1, "placeholder": 2}

    def sort_key(row: NormRow):
        sex_rank = 0 if row.sex == sex else 1
        return (sex_rank, _age_span(row), status_rank.get(row.status, 9))

    chosen = sorted(matches, key=sort_key)[0]
    return {
        "mean": chosen.mean,
        "sd": chosen.sd,
        "source_id": chosen.source_id,
        "status": chosen.status,
    }


def cutoffs_for(metric: str, group: str, cutoff_set: str = "ewgsop2", tables: Tables | None = None):
    """Active value cut-offs for one metric.

    Includes the selected set, NODAL screening rules, and STEADI for TUG
    whatever the selected set is. Perera rows are change bands, not value
    cut-offs, so they are left out here.
    """
    tables = tables if tables is not None else load()
    found = []
    for row in tables.cutoffs:
        if row.metric != metric or row.threshold is None:
            continue
        if row.group not in (group, "all"):
            continue
        if row.source_id == "perera2006":
            continue
        use = row.source_id == cutoff_set or row.source_id == "nodal-rule"
        if metric == "tug_time" and row.source_id == "steadi":
            use = True
        if use:
            found.append(row)
    return found
