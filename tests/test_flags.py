"""Flag engine: thresholds, direction, pathways, and transcribed tables."""

import copy
import json

import pytest

from screen import flags, norms

HEADER_N = "source_id,metric,sex,age_min,age_max,condition,mean,sd,n,table_ref,status\n"
HEADER_C = "source_id,metric,group,op,threshold,unit,meaning,table_ref,status\n"
UNITS = {
    "gait_speed": "m/s",
    "cadence": "steps/min",
    "tug_time": "s",
    "sts5_time": "s",
    "sls_time": "s",
    "step_length_si": "%",
    "step_time_si": "%",
    "heel_first_share": "% of strides",
}


def session(group="adult", age=70, sex="M", rows=(), qc=None, history=None):
    tasks = {}
    for task, metric_id, value, side in rows:
        tasks.setdefault(task, {"metrics": []})
        tasks[task]["metrics"].append({
            "id": metric_id,
            "side": side,
            "value": value,
            "unit": UNITS.get(metric_id, ""),
            "ref": None,
            "status": "",
        })
    return {
        "schema": "nodal-screen/session@1",
        "provenance": "synthetic",
        "participant": {"pid": "SYN-T-0001", "group": group, "age_y": age, "sex": sex},
        "qc": qc or {"status": "ok", "confidence": "high"},
        "tasks": tasks,
        "flags": [],
        "history": history or [],
    }


def rules(result, rule):
    return [flag for flag in result["flags"] if flag["rule"] == rule]


def metric(result, metric_id, side=None):
    for task in result["tasks"].values():
        for item in task["metrics"]:
            if item["id"] == metric_id and item.get("side") == side:
                return item
    raise AssertionError(metric_id)


def load_pair(tmp_path, norms_body, cutoffs_body=""):
    norms_path = tmp_path / "norms.csv"
    cutoffs_path = tmp_path / "cutoffs.csv"
    norms_path.write_text(HEADER_N + norms_body, encoding="utf-8")
    cutoffs_path.write_text(HEADER_C + cutoffs_body, encoding="utf-8")
    return norms.load(norms_path, cutoffs_path)


def test_symmetry_index():
    assert flags.symmetry_index(1, 1) == 0
    assert flags.symmetry_index(1.1, 0.9) == pytest.approx(20)
    assert flags.symmetry_index(2, 1) == pytest.approx(100 * 1 / 1.5)
    assert flags.symmetry_index(0, 0) is None


def test_norm_lookup_uses_decade_sex_and_skips_blank_rows():
    tables = norms.load()
    men = norms.norm_for("gait_speed", "M", 45, "adult", tables)
    women = norms.norm_for("gait_speed", "F", 72, "adult", tables)
    assert men["source_id"] == "bohannon2011"
    assert men["mean"] == pytest.approx(1.434)
    assert men["sd"] is None
    assert men["status"] == "transcribed"
    assert women["mean"] == pytest.approx(1.132)
    assert norms.norm_for("gait_speed", "M", 29, "adult", tables)["mean"] == pytest.approx(1.358)
    assert norms.norm_for("gait_speed", "M", 30, "adult", tables)["mean"] == pytest.approx(1.433)
    assert norms.norm_for("gait_speed", "F", 99, "adult", tables)["mean"] == pytest.approx(0.943)
    assert norms.norm_for("gait_speed", "M", 100, "adult", tables) is None
    child = norms.norm_for("gait_speed", "F", 6, "child", tables)
    assert child["source_id"] == "voss2020"
    assert child["mean"] == pytest.approx(1.11)
    assert child["sd"] == pytest.approx(0.12)
    stand = norms.norm_for("sts5_time", "F", 72, "adult", tables)
    assert stand["source_id"] == "bohannon2010sts"
    assert stand["mean"] == pytest.approx(9.3)
    assert stand["sd"] == pytest.approx(2.1)
    tug = norms.norm_for("tug_time", "M", 75, "adult", tables)
    assert tug["mean"] == pytest.approx(9.2)
    assert tug["sd"] is None
    sls = norms.norm_for("sls_time", "F", 65, "adult", tables)
    assert sls["mean"] == pytest.approx(30.4)
    assert sls["sd"] is None


def test_norm_for_prefers_sex_then_narrower_age(tmp_path):
    tables = load_pair(
        tmp_path,
        "fixture,gait_speed,all,0,120,test,1.0,0.2,10,wide,transcribed\n"
        "fixture,gait_speed,F,40,49,test,1.2,0.2,10,narrow,transcribed\n"
        "fixture,gait_speed,F,0,120,test,9.0,0.2,10,wide-sex,placeholder\n",
    )
    chosen = norms.norm_for("gait_speed", "F", 45, "adult", tables)
    assert chosen["mean"] == pytest.approx(1.2)
    assert chosen["status"] == "transcribed"


def test_unread_sources_and_catalog():
    tables = norms.load()
    catalog = json.loads((norms.ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    expected = {
        "bohannon2011", "voss2020", "bohannon2006tug", "bohannon2010sts",
        "springer2007", "steadi", "ewgsop2", "awgs2019", "perera2006", "nodal-rule",
    }
    assert set(catalog) == expected
    assert all(item["verified"] is False for item in catalog.values())
    pending = [row for row in tables.norms if row.status == "placeholder"]
    assert len(pending) == 1
    assert pending[0].metric == "stride_length"
    assert all(row.mean is None and row.source_id == "voss2020" for row in pending)
    assert all(row.sd is None for row in tables.norms if row.source_id in {"bohannon2011", "bohannon2006tug", "springer2007"})
    assert all(row.status != "verified" for row in tables.norms + tables.cutoffs)


def test_z_edges_and_direction(tmp_path):
    tables = load_pair(
        tmp_path,
        "fixture,gait_speed,all,0,120,test,1.0,0.1,10,fixture,transcribed\n"
        "fixture,cadence,all,0,120,test,100,10,10,fixture,transcribed\n",
    )

    def one(metric_id, value):
        result = flags.apply(session("child", 8, "F", [("gait", metric_id, value, None)]), tables=tables)
        return metric(result, metric_id), rules(result, "norm_z")

    gait, gait_flags = one("gait_speed", 0.85)
    assert gait["status"] == "borderline"
    assert gait["ref"]["z"] == pytest.approx(-1.5)
    assert gait_flags[0]["severity"] == "watch"

    gait, gait_flags = one("gait_speed", 0.8)
    assert gait["ref"]["z"] == pytest.approx(-2.0)
    assert gait_flags[0]["severity"] == "watch"

    gait, gait_flags = one("gait_speed", 0.799)
    assert gait["status"] == "out_of_range"
    assert gait_flags[0]["severity"] == "flag"

    gait, gait_flags = one("gait_speed", 0.851)
    assert gait["status"] == "in_range"
    assert gait_flags == []

    gait, gait_flags = one("gait_speed", 1.3)
    assert gait["ref"]["z"] == pytest.approx(3.0)
    assert gait["status"] == "in_range"
    assert gait_flags == []

    for value, severity in ((115, "watch"), (120, "watch"), (120.1, "flag"), (85, "watch"), (80, "watch"), (79.9, "flag")):
        cadence, cadence_flags = one("cadence", value)
        assert cadence_flags[0]["severity"] == severity


def test_norm_stays_beside_the_cutoff():
    quiet = flags.apply(session(rows=[("gait", "gait_speed", 1.20, None)]))
    item = metric(quiet, "gait_speed")
    assert item["ref"]["kind"] == "norm"
    assert item["ref"]["source_id"] == "bohannon2011"
    assert item["ref"]["mean"] == pytest.approx(1.262)
    assert item["ref"]["sd"] is None
    assert item["ref"]["z"] is None
    assert item["cutoff"] == {"source_id": "ewgsop2", "threshold": 0.8, "op": "<=", "met": False}
    assert item["status"] == "in_range"
    assert quiet["flags"] == []

    slow = flags.apply(session(rows=[("gait", "gait_speed", 0.70, None)]))
    item = metric(slow, "gait_speed")
    assert item["ref"]["mean"] == pytest.approx(1.262)
    assert item["ref"]["z"] is None
    assert item["cutoff"]["met"] is True
    assert item["cutoff"]["source_id"] == "ewgsop2"
    assert item["status"] == "out_of_range"
    assert [flag["rule"] for flag in slow["flags"]] == ["cutoff"]

    awgs = flags.apply(session(rows=[("gait", "gait_speed", 0.95, None)]), cutoff_set="awgs2019")
    ewgsop = flags.apply(session(rows=[("gait", "gait_speed", 0.95, None)]), cutoff_set="ewgsop2")
    assert metric(awgs, "gait_speed")["cutoff"]["met"] is True
    assert metric(awgs, "gait_speed")["cutoff"]["op"] == "<"
    assert metric(awgs, "gait_speed")["cutoff"]["threshold"] == pytest.approx(1.0)
    assert metric(ewgsop, "gait_speed")["cutoff"]["met"] is False

    bare = flags.apply(session(rows=[("gait", "cadence", 100, None)]))
    item = metric(bare, "cadence")
    assert item["ref"] is None
    assert item["cutoff"] is None
    assert item["status"] == "no_reference"
    assert bare["flags"] == []


def test_placeholder_norm_keeps_status(tmp_path):
    tables = load_pair(
        tmp_path,
        "fixture,gait_speed,all,0,120,test,1.0,0.2,10,fixture,placeholder\n",
    )
    result = flags.apply(session("child", 8, "F", [("gait", "gait_speed", 0.5, None)]), tables=tables)
    item = metric(result, "gait_speed")
    assert item["ref"]["status"] == "placeholder"
    assert item["ref"]["z"] == pytest.approx(-2.5)
    assert item["status"] == "out_of_range"
    assert rules(result, "norm_z")[0]["source_ids"] == ["fixture"]


def _edge(op, threshold, meets):
    step = 0.01
    if meets:
        return {">=": threshold, ">": threshold + step, "<=": threshold, "<": threshold - step}[op]
    return {">=": threshold - step, ">": threshold, "<=": threshold + step, "<": threshold}[op]


def test_each_value_cutoff_just_inside_and_outside():
    tables = norms.load()
    task_for = {"gait_speed": "gait", "sts5_time": "sts5", "tug_time": "tug"}
    for cutoff_set in ("ewgsop2", "awgs2019"):
        seen = []
        for row in tables.cutoffs:
            if row.threshold is None or row.source_id == "perera2006" or row.source_id == "nodal-rule":
                continue
            active = row.source_id == cutoff_set or (row.metric == "tug_time" and row.source_id == "steadi")
            if not active:
                continue
            seen.append(row)
            group = "adult"
            outside = flags.apply(
                session(group, 70, "M", [(task_for[row.metric], row.metric, _edge(row.op, row.threshold, True), None)]),
                cutoff_set=cutoff_set,
                tables=tables,
            )
            inside = flags.apply(
                session(group, 70, "M", [(task_for[row.metric], row.metric, _edge(row.op, row.threshold, False), None)]),
                cutoff_set=cutoff_set,
                tables=tables,
            )
            assert rules(outside, "cutoff"), (cutoff_set, row.source_id, row.metric, row.op, row.threshold)
            assert rules(inside, "cutoff") == [], (cutoff_set, row.source_id, row.metric)
        assert {row.source_id for row in seen} >= {cutoff_set, "steadi"}


def test_cutoff_set_switches_gait_and_chair_stand():
    slow_gait = [("gait", "gait_speed", 0.9, None)]
    ewgsop = flags.apply(session(rows=slow_gait), cutoff_set="ewgsop2")
    awgs = flags.apply(session(rows=slow_gait), cutoff_set="awgs2019")
    assert rules(ewgsop, "cutoff") == []
    assert rules(awgs, "cutoff")[0]["source_ids"] == ["awgs2019"]

    chair = [("sts5", "sts5_time", 13, None)]
    assert rules(flags.apply(session(rows=chair), cutoff_set="ewgsop2"), "cutoff") == []
    assert rules(flags.apply(session(rows=chair), cutoff_set="awgs2019"), "cutoff")[0]["source_ids"] == ["awgs2019"]

    exact = flags.apply(session(rows=[("sts5", "sts5_time", 15, None)]), cutoff_set="ewgsop2")
    over = flags.apply(session(rows=[("sts5", "sts5_time", 15.01, None)]), cutoff_set="ewgsop2")
    assert rules(exact, "cutoff") == []
    assert rules(over, "cutoff")


def test_nodal_bands_and_toe_walk_age():
    def kinds(group, age, metric_id, value, task):
        result = flags.apply(session(group, age, "F", [(task, metric_id, value, None)]))
        return result["flags"]

    assert kinds("adult", 64, "step_length_si", 9.9, "gait") == []
    watch = kinds("adult", 64, "step_length_si", 10, "gait")
    assert watch[0]["severity"] == "watch" and watch[0]["rule"] == "asymmetry"
    assert kinds("adult", 64, "step_length_si", 14.99, "gait")[0]["severity"] == "watch"
    assert kinds("adult", 64, "step_length_si", 15, "gait")[0]["severity"] == "flag"
    assert kinds("adult", 64, "step_time_si", 15, "gait")[0]["rule"] == "asymmetry"

    assert kinds("child", 7, "heel_first_share", 80.01, "gait") == []
    assert kinds("child", 7, "heel_first_share", 80, "gait")[0]["severity"] == "watch"
    assert kinds("child", 7, "heel_first_share", 50, "gait")[0]["severity"] == "watch"
    assert kinds("child", 7, "heel_first_share", 49.99, "gait")[0]["severity"] == "flag"
    assert kinds("child", 3, "heel_first_share", 40, "gait")[0]["rule"] == "toe_walk"
    assert kinds("child", 2, "heel_first_share", 10, "gait") == []
    assert kinds("adult", 70, "heel_first_share", 10, "gait") == []


def test_change_edges_use_the_table_and_the_earliest_visit():
    tables = norms.load()
    perera = sorted(
        row.threshold for row in tables.cutoffs
        if row.source_id == "perera2006" and row.threshold is not None
    )
    small, substantial = perera
    current = 1.2

    def changed(drop, history=None):
        if history is None:
            history = [{"date": "2024-01-01", "metrics": {"gait_speed": round(current + drop, 10)}}]
        result = flags.apply(session(rows=[("gait", "gait_speed", current, None)], history=history), tables=tables)
        return rules(result, "change")

    assert changed(small - 0.01) == []
    assert changed(small)[0]["severity"] == "watch"
    assert changed(substantial - 0.01)[0]["severity"] == "watch"
    assert changed(substantial)[0]["severity"] == "flag"
    dated = changed(0, [
        {"date": "2026-01-01", "metrics": {"gait_speed": 1.0}},
        {"date": "2020-01-01", "metrics": {"gait_speed": current + substantial}},
    ])
    assert dated[0]["severity"] == "flag"
    assert dated[0]["source_ids"] == ["perera2006"]


def test_insufficient_clears_flags_and_asks_for_recapture():
    raw = session(
        rows=[("tug", "tug_time", 30, None), ("gait", "gait_speed", 0.4, None)],
        qc={"status": "insufficient", "confidence": "low", "notes": ["too few strides"]},
    )
    before = copy.deepcopy(raw)
    result = flags.apply(raw)
    assert raw == before
    assert result["flags"] == []
    assert result["suggested_pathway"]["code"] == "RECAPTURE"
    assert metric(result, "tug_time")["status"] == "insufficient"
    assert metric(result, "gait_speed")["status"] == "insufficient"


def test_pathway_order_first_match_wins():
    both = flags.apply(session(rows=[("tug", "tug_time", 13, None), ("sts5", "sts5_time", 16, None)]))
    assert both["suggested_pathway"]["code"] == "FALLS_PREVENTION"
    assert any(flag["metric_ids"] == ["sts5_time"] for flag in both["flags"])

    gait_and_chair = flags.apply(session(rows=[("gait", "gait_speed", 0.7, None), ("sts5", "sts5_time", 20, None)]))
    assert gait_and_chair["suggested_pathway"]["code"] == "FALLS_PREVENTION"

    chair_only = flags.apply(session(rows=[("sts5", "sts5_time", 16, None), ("gait", "gait_speed", 1.2, None)]))
    assert chair_only["suggested_pathway"]["code"] == "ADULT_SARCOPENIA"

    asymmetry_and_change = flags.apply(session(
        rows=[("gait", "gait_speed", 1.2, None), ("gait", "step_length_si", 18, None)],
        history=[{"date": "2024-01-01", "metrics": {"gait_speed": 1.35}}],
    ))
    assert asymmetry_and_change["suggested_pathway"]["code"] == "CLINICIAN_SPECIALIST"

    change_only = flags.apply(session(
        rows=[("gait", "gait_speed", 1.2, None)],
        history=[{"date": "2024-01-01", "metrics": {"gait_speed": 1.32}}],
    ))
    assert change_only["suggested_pathway"]["code"] == "ADULT_EARLY_REVIEW"

    watch_only = flags.apply(session(rows=[("gait", "step_length_si", 12, None)]))
    assert watch_only["suggested_pathway"]["code"] == "ROUTINE"
    assert watch_only["flags"][0]["severity"] == "watch"

    assert flags.apply(session(rows=[("gait", "gait_speed", 1.2, None)]))["suggested_pathway"]["code"] == "ROUTINE"

    child_flag = flags.apply(session("child", 7, "F", [("gait", "heel_first_share", 40, "left")]))
    assert child_flag["suggested_pathway"]["code"] == "WCV_DEV_REVIEW"
    assert child_flag["flags"][0]["confidence"] == "high"

    two_watches = flags.apply(session("child", 8, "M", [
        ("gait", "step_length_si", 12, None),
        ("gait", "step_time_si", 11, None),
    ]))
    assert two_watches["suggested_pathway"]["code"] == "WCV_DEV_REVIEW"
    one_watch = flags.apply(session("child", 8, "M", [("gait", "step_length_si", 12, None)]))
    assert one_watch["suggested_pathway"]["code"] == "ROUTINE"

    child_slow = flags.apply(session("child", 6, "F", [("gait", "gait_speed", 0.5, None)]))
    assert rules(child_slow, "cutoff") == []


def test_sls_norm_flag_is_a_falls_pathway(tmp_path):
    tables = load_pair(
        tmp_path,
        "fixture,sls_time,all,60,80,eyes open,20,4,10,fixture,transcribed\n",
        "perera2006,gait_speed,all,>=,0.05,m/s,Small meaningful decrease,Table 5,transcribed\n"
        "perera2006,gait_speed,all,>=,0.10,m/s,Substantial meaningful decrease,Table 5,transcribed\n",
    )
    result = flags.apply(session(rows=[("sls", "sls_time", 10, "right")]), tables=tables)
    assert rules(result, "norm_z")[0]["severity"] == "flag"
    assert result["suggested_pathway"]["code"] == "FALLS_PREVENTION"
    assert "right" in rules(result, "norm_z")[0]["title"]


def test_nodal_rule_is_the_metric_cutoff():
    out = flags.apply(session("child", 7, "F", [
        ("gait", "heel_first_share", 22, "left"),
        ("gait", "heel_first_share", 65, "right"),
        ("gait", "step_length_si", 4.0, None),
    ]))
    by_side = {(m["id"], m["side"]): m for m in out["tasks"]["gait"]["metrics"]}
    left = by_side[("heel_first_share", "left")]
    assert left["cutoff"] == {"source_id": "nodal-rule", "threshold": 50.0, "op": "<", "met": True}
    assert left["status"] == "out_of_range"
    right = by_side[("heel_first_share", "right")]
    assert right["cutoff"]["met"] is False and right["status"] == "borderline"
    si = by_side[("step_length_si", None)]
    assert si["cutoff"] == {"source_id": "nodal-rule", "threshold": 15.0, "op": ">=", "met": False}
    assert si["status"] == "in_range"
    # Adults are not screened for toe walking: no rule, no cut-off.
    adult = flags.apply(session("adult", 40, "M", [("gait", "heel_first_share", 22, "left")]))
    assert adult["tasks"]["gait"]["metrics"][0]["cutoff"] is None
