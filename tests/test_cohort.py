"""Cohort generator and the small-cell rule."""

import json
from datetime import date
from pathlib import Path

from screen import cohort, flags

ROOT = Path(__file__).resolve().parents[1]
COHORT_PATH = ROOT / "data" / "cohort.json"
METRICS = {
    "gait_speed", "cadence", "stride_length", "stride_length_h", "step_time_cv",
    "double_support", "step_length_si", "step_time_si", "knee_rom", "heel_first_share",
    "tug_time", "sts5_time", "sls_time",
}
PATHWAYS = {
    "RECAPTURE", "WCV_DEV_REVIEW", "FALLS_PREVENTION", "ADULT_SARCOPENIA",
    "CLINICIAN_SPECIALIST", "ADULT_EARLY_REVIEW", "ROUTINE",
}
KEYS = [
    "cohort.generated", "cohort.reach", "cohort.reachLead", "cohort.invited",
    "cohort.screened", "cohort.flags", "cohort.flagsLead", "cohort.flagged",
    "cohort.pathways", "cohort.pathwaysLead", "cohort.completion",
    "cohort.completionLead", "cohort.within30", "cohort.within60", "cohort.median",
    "cohort.byNationality", "cohort.byAge", "cohort.total", "cohort.suppressed",
    "cohort.noComplement", "cohort.percent", "cohort.days", "cohort.loadError",
    "nat.UAE national", "nat.Non-national", "site.PHC-1", "site.SCH-1", "site.MAJ-1",
    "metric.double_support", "metric.step_length_si", "metric.step_time_si",
]
PERSON_KEYS = {
    "pid", "group", "age_band", "sex", "nationality_group", "site", "invited",
    "screened", "flags", "pathway", "flag_date", "attended_date",
}


def load():
    return json.loads(COHORT_PATH.read_text(encoding="utf-8"))


def cell(people, site, key, value):
    return sum(1 for person in people if person["site"] == site and person[key] == value)


def test_under_ten_is_suppressed_and_not_plotted():
    assert cohort.cell_count(9) == "<10"
    assert cohort.cell_count(0) == "<10"
    assert cohort.cell_rate(9, 0.4) == "<10"
    assert cohort.cell_plotted(9) is False


def test_ten_or_more_shows_the_number_and_may_be_plotted():
    assert cohort.cell_count(10) == 10
    assert cohort.cell_count(140) == 140
    assert cohort.cell_rate(10, 0.4) == 0.4
    assert cohort.cell_plotted(10) is True


def test_total_shows_the_true_count_when_every_part_is_suppressed():
    parts = [3, 4, 2]
    assert [cohort.cell_count(part) for part in parts] == ["<10", "<10", "<10"]
    assert cohort.cell_count(sum(parts), total=True) == 9
    assert cohort.cell_count(0, total=True) == 0


def test_no_complementary_suppression():
    assert cohort.cell_count(4) == "<10"
    assert cohort.cell_count(96) == 96
    assert cohort.cell_count(100, total=True) == 100


def test_named_cells_cover_both_sides():
    people = load()["people"]
    small_nat = cell(people, "SCH-1", "nationality_group", "Non-national")
    large_nat = cell(people, "PHC-1", "nationality_group", "UAE national")
    small_age = cell(people, "PHC-1", "age_band", "80-99")
    large_age = cell(people, "PHC-1", "age_band", "40-59")
    assert small_nat == 7
    assert large_nat == 140
    assert small_age == 6
    assert large_age == 45
    assert cohort.cell_count(small_nat) == "<10"
    assert cohort.cell_count(large_nat) == 140
    assert cohort.cell_count(small_age) == "<10"
    assert cohort.cell_count(large_age) == 45
    assert cohort.cell_count(small_nat, total=True) == 7


def test_pathway_code_uses_the_flag_engine():
    watches = cohort.flag_specs((
        ("heel_first_share", "toe_walk", "watch"),
        ("gait_speed", "norm_z", "watch"),
    ))
    assert cohort.pathway_code("child", watches) == flags._pathway("child", watches)["code"]
    assert cohort.pathway_code("child", watches) == "WCV_DEV_REVIEW"
    tug = cohort.flag_specs((("tug_time", "cutoff", "flag"),))
    assert cohort.pathway_code("adult", tug) == "FALLS_PREVENTION"
    chair = cohort.flag_specs((("sts5_time", "cutoff", "flag"),))
    assert cohort.pathway_code("adult", chair) == "ADULT_SARCOPENIA"
    asymmetry = cohort.flag_specs((("step_length_si", "asymmetry", "flag"),))
    assert cohort.pathway_code("adult", asymmetry) == "CLINICIAN_SPECIALIST"
    change = cohort.flag_specs((("gait_speed", "change", "flag"),))
    assert cohort.pathway_code("adult", change) == "ADULT_EARLY_REVIEW"
    assert cohort.pathway_code("adult", []) == "ROUTINE"
    assert cohort.pathway_code("child", []) == "ROUTINE"


def test_every_person_asks_the_imported_pathway(monkeypatch):
    seen = {"n": 0}
    real = cohort._pathway

    def wrapped(group, specs):
        seen["n"] += 1
        return real(group, specs)

    monkeypatch.setattr(cohort, "_pathway", wrapped)
    payload = cohort.generate(cohort.SEED, date(2026, 11, 13))
    assert seen["n"] == len(payload["people"]) == 600


def test_committed_file_matches_the_seed():
    committed = load()
    fresh = cohort.generate(cohort.SEED, date.fromisoformat(committed["generated"]))
    assert fresh == committed
    assert cohort.generate(cohort.SEED, date(2026, 11, 13)) == cohort.generate(cohort.SEED, date(2026, 11, 13))


def test_cohort_document_shape():
    payload = load()
    assert payload["schema"] == "nodal-screen/cohort@1"
    assert payload["provenance"] == "synthetic"
    assert date.fromisoformat(payload["generated"])
    assert payload["sites"] == [
        {"id": "PHC-1", "type": "Primary care centre"},
        {"id": "SCH-1", "type": "School"},
        {"id": "MAJ-1", "type": "Community majlis"},
    ]
    people = payload["people"]
    assert 580 <= len(people) <= 620
    pids = [person["pid"] for person in people]
    assert len(pids) == len(set(pids))
    assert "SYN-C-0007" not in pids
    assert "SYN-A-0102" not in pids
    flagged = []
    for person in people:
        assert set(person) == PERSON_KEYS
        assert person["pid"].startswith("SYN-")
        assert person["group"] in ("child", "adult")
        assert person["sex"] in ("F", "M")
        assert person["nationality_group"] in ("UAE national", "Non-national")
        assert person["site"] in ("PHC-1", "SCH-1", "MAJ-1")
        bands = cohort.CHILD_BANDS if person["group"] == "child" else cohort.ADULT_BANDS
        assert person["age_band"] in bands
        assert person["invited"] is True
        assert person["screened"] in (True, False)
        assert person["pathway"] in PATHWAYS
        assert set(person["flags"]) <= METRICS
        assert "tandem_steps" not in person["flags"]
        assert "hop_count" not in person["flags"]
        if not person["screened"]:
            assert person["flags"] == []
        if not person["flags"]:
            assert person["pathway"] == "ROUTINE"
            assert person["flag_date"] == ""
            assert person["attended_date"] == ""
        else:
            flagged.append(person)
            assert date.fromisoformat(person["flag_date"])
            if person["attended_date"]:
                gap = date.fromisoformat(person["attended_date"]) - date.fromisoformat(person["flag_date"])
                assert 3 <= gap.days <= 90
            else:
                assert person["attended_date"] == ""
    assert flagged
    assert any(person["attended_date"] == "" for person in flagged)
    assert any(person["attended_date"] for person in flagged)
    assert any(not person["screened"] for person in people)
    phc_nationals = [
        person for person in people
        if person["site"] == "PHC-1" and person["nationality_group"] == "UAE national" and person["flags"]
    ]
    school_non = [
        person for person in people
        if person["site"] == "SCH-1" and person["nationality_group"] == "Non-national" and person["flags"]
    ]
    assert len(phc_nationals) >= 10
    assert len(school_non) < 10


def test_write_cohort_does_not_create_a_samples_folder(tmp_path):
    dest = tmp_path / "cohort.json"
    cohort.write_cohort(dest, seed=cohort.SEED, today=date(2026, 11, 13))
    assert dest.is_file()
    assert [path.name for path in tmp_path.iterdir()] == ["cohort.json"]
    written = json.loads(dest.read_text(encoding="utf-8"))
    assert written["people"]
    assert "\r" not in dest.read_text(encoding="utf-8")


def test_new_strings_are_in_both_catalogs():
    en = json.loads((ROOT / "web" / "i18n" / "en.json").read_text(encoding="utf-8"))
    ar = json.loads((ROOT / "web" / "i18n" / "ar.json").read_text(encoding="utf-8"))
    same = {"cohort.suppressed", "cohort.percent"}
    for key in KEYS:
        assert en[key].strip()
        assert ar[key].strip()
        if key not in same:
            assert en[key] != ar[key]
    script = (ROOT / "web" / "routes" / "cohort.js").read_text(encoding="utf-8")
    assert "overview.step.program" in script
    assert "heading.cohort" not in script
    assert 'from "../lib/badge.js"' in script
    assert "data/cohort.json" in script
    assert "innerHTML" not in script
