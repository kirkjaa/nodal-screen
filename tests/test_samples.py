"""Sample sessions stay a fixed point of the flag rules, with catalogue units."""

import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from screen import flags

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
FIXTURES = ROOT / "tests" / "fixtures"
CATALOGUE_UNITS = {
    "gait_speed": "m/s",
    "cadence": "steps/min",
    "stride_length": "m",
    "stride_length_h": "stride / height",
    "step_time_cv": "%",
    "double_support": "% of cycle",
    "step_length_si": "%",
    "step_time_si": "%",
    "knee_rom": "deg",
    "heel_first_share": "% of strides",
    "tug_time": "s",
    "sts5_time": "s",
    "sls_time": "s",
    "tandem_steps": "steps of 10",
    "hop_count": "hops",
}


def session_paths(folder):
    return [path for path in sorted(folder.glob("*.json")) if path.name != "index.json"]


def sample_paths():
    return session_paths(SAMPLES) + session_paths(FIXTURES)


def test_both_folders_hold_sessions():
    assert session_paths(SAMPLES)
    assert (FIXTURES / "SYN-C-0007.json").is_file()
    assert (FIXTURES / "SYN-A-0102.json").is_file()
    assert not (SAMPLES / "SYN-C-0007.json").exists()
    assert not (SAMPLES / "SYN-A-0102.json").exists()


def metrics_of(session):
    rows = []
    for task in session["tasks"].values():
        rows.extend(task["metrics"])
    return rows


def load_verify():
    path = ROOT / "scripts" / "verify.py"
    spec = importlib.util.spec_from_file_location("screen_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sample_units_follow_the_catalogue():
    assert set(CATALOGUE_UNITS) == {
        "gait_speed", "cadence", "stride_length", "stride_length_h", "step_time_cv",
        "double_support", "step_length_si", "step_time_si", "knee_rom", "heel_first_share",
        "tug_time", "sts5_time", "sls_time", "tandem_steps", "hop_count",
    }
    for path in sample_paths():
        session = json.loads(path.read_text(encoding="utf-8"))
        for metric in metrics_of(session):
            assert metric["unit"] == CATALOGUE_UNITS[metric["id"]], (path.name, metric["id"])


def test_samples_match_apply():
    assert sample_paths()
    for path in sample_paths():
        session = json.loads(path.read_text(encoding="utf-8"))
        result = flags.apply(session)
        assert metrics_of(result) == metrics_of(session)
        assert result["flags"] == session["flags"]
        assert result["suggested_pathway"] == session["suggested_pathway"]


def test_schema_rejects_a_metric_without_cutoff():
    schema = json.loads((ROOT / "docs" / "session.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for path in sample_paths():
        session = json.loads(path.read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(session))
        assert errors == [], (path.name, [(list(err.path), err.message) for err in errors])
    session = json.loads(sample_paths()[0].read_text(encoding="utf-8"))
    del session["tasks"]["gait"]["metrics"][0]["cutoff"]
    errors = list(validator.iter_errors(session))
    assert any(err.validator == "required" and "cutoff" in err.message for err in errors)


def test_honesty_allows_citation_titles_not_the_word():
    verify = load_verify()

    def flagged(text):
        cleaned = verify._scrub(text)
        return any(pattern.search(cleaned) for pattern in verify.PATTERNS)

    ewgsop = "Sarcopenia: revised European consensus on definition and diagnosis"
    awgs = "Asian Working Group for Sarcopenia: 2019 Consensus Update on Sarcopenia Diagnosis and Treatment"
    assert flagged("fda")
    assert flagged("FDA")
    assert flagged("diagnosis")
    assert not flagged(ewgsop)
    assert not flagged(awgs)
    assert not flagged(f"See {ewgsop}.")
    assert flagged("revised European consensus on definition and diagnosis")
