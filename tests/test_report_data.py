"""The report builder on the synthetic worker: cycles, shares, findings and the two warning rules."""

import numpy as np

from sw import report_data, synth


def test_cycle_detection_finds_the_period():
    X = synth.generate(cycles=6, fps=30, seed=3)
    from sw import ergo
    a = ergo.angles(X)
    starts, period = report_data.detect_cycles(a["trunk_flexion"], 30)
    assert abs(period - synth.CYCLE_S) < 0.6
    assert 5 <= len(starts) <= 7


def test_build_on_synthetic(tmp_path):
    X = synth.generate(cycles=5, fps=30, seed=1)
    np.savez_compressed(tmp_path / "skeleton3d.npz", X=X, fps=30)
    (tmp_path / "meta.json").write_text('{"data_kind": "synthetic", "fps": 30}', encoding="utf-8")
    d = report_data.build(tmp_path)
    assert d["data_kind"] == "synthetic"
    assert abs(sum(d["levels"].values()) - 1.0) < 0.01
    assert 1 <= d["peaks"]["rula"] <= 7 and 1 <= d["peaks"]["reba"] <= 15
    keys = {f["key"] for f in d["findings"]}
    assert "trunk" in keys and "shoulder_right" in keys   # the stoop and the shelf reach
    assert any(w["kind"] == "note" for w in d["warnings"])  # no history: says so
    assert len(d["frames"]["rula"]) == len(d["frames"]["t"])


def test_warning_rules(tmp_path):
    X = synth.generate(cycles=4, fps=30, seed=2)
    np.savez_compressed(tmp_path / "skeleton3d.npz", X=X, fps=30)
    (tmp_path / "meta.json").write_text('{"data_kind": "synthetic", "fps": 30}', encoding="utf-8")
    flat = {"role_sessions": [{"label": "a", "avg_rula": 4.4}, {"label": "b", "avg_rula": 4.4}], "hours_today_at_or_above": 0.0}
    d = report_data.build(tmp_path, history=flat)
    assert not any(w["kind"] == "rising" for w in d["warnings"])
    assert not any(w["kind"] == "exposure" for w in d["warnings"])
    rising = {"role_sessions": [{"label": "a", "avg_rula": 3.0}, {"label": "b", "avg_rula": 3.5}], "hours_today_at_or_above": 2.0}
    d = report_data.build(tmp_path, history=rising)
    kinds = {w["kind"] for w in d["warnings"]}
    assert "rising" in kinds and "exposure" in kinds
