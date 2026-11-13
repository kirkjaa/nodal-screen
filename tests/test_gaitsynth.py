"""Synthetic screening walks: bones, contacts, speed, and the nine presets."""

import json
from pathlib import Path

import numpy as np

from screen.gaitsynth import (
    BONES,
    FPS,
    L_BTOE,
    L_HEEL,
    L_HIP,
    PRESETS,
    R_BTOE,
    R_HEEL,
    R_HIP,
    Person,
    plot_file,
    save_npz,
    sls,
    sts5,
    tug,
    walk10,
    write_preset,
)


def clean(**over):
    data = dict(age_y=40, sex="M", height_m=1.75, speed_m_s=1.25, cadence_spm=112, seed=1)
    data.update(over)
    return Person(**data)


def bone_span(kp):
    worst = 0.0
    pair = None
    for a, b in BONES:
        dist = np.linalg.norm(kp[:, a] - kp[:, b], axis=1)
        span = float(dist.max() - dist.min())
        if span > worst:
            worst, pair = span, (a, b, float(dist.mean()))
    return worst, pair


def foot_height(kp, side):
    heel = L_HEEL if side == "left" else R_HEEL
    toe = L_BTOE if side == "left" else R_BTOE
    return np.minimum(kp[:, heel, 2], kp[:, toe, 2])


def crossings(z, level=10.0):
    down, up = [], []
    for i in range(1, len(z)):
        if z[i - 1] > level >= z[i]:
            down.append(i)
        if z[i - 1] <= level < z[i]:
            up.append(i)
    return down, up


def nearest(frame, hits):
    return min(abs(frame - hit) for hit in hits)


def test_bones_stay_fixed_without_noise():
    for maker in (walk10, lambda p: tug(p, 9.0), lambda p: sts5(p, 8.0), lambda p: sls(p, "L", 3.0)):
        out = maker(clean())
        assert np.isfinite(out["kp"]).all()
        worst, pair = bone_span(out["kp"])
        assert worst < 1.0, (maker, worst, pair)


def test_stance_foot_does_not_slide():
    out = walk10(clean())
    kp = out["kp"]
    for side, heel, toe in (("left", L_HEEL, L_BTOE), ("right", R_HEEL, R_BTOE)):
        small = toe + 1  # small toe follows the big toe in the joint list
        for event in out["truth"]["events"][side]:
            if "hs" not in event or "to" not in event:
                continue
            hs, to = event["hs"], event["to"]
            if to <= hs:
                continue
            for idx in (heel, toe, small):
                xy = kp[hs:to, idx, :2]
                drift = np.linalg.norm(xy - xy[0], axis=1).max()
                assert drift < 5.0, (side, idx, drift)


def test_speed_and_step_length():
    person = clean(speed_m_s=1.25, cadence_spm=112)
    out = walk10(person)
    kp = out["kp"]
    hip_x = 0.5 * (kp[:, L_HIP, 0] + kp[:, R_HIP, 0])
    i1 = int(np.argmax(hip_x >= 4000))
    i2 = int(np.argmax(hip_x >= 10000))
    assert i2 > i1
    speed = 6.0 / ((i2 - i1) / FPS)
    assert abs(speed - 1.25) / 1.25 < 0.02, speed

    for side, heel, key in (("left", L_HEEL, "left"), ("right", R_HEEL, "right")):
        order = []
        for event in out["truth"]["events"]["left"]:
            if "hs" in event:
                order.append(("left", event["hs"], kp[event["hs"], L_HEEL, 0]))
        for event in out["truth"]["events"]["right"]:
            if "hs" in event:
                order.append(("right", event["hs"], kp[event["hs"], R_HEEL, 0]))
        order.sort(key=lambda item: item[1])
        lengths = []
        for prev, cur in zip(order, order[1:]):
            if cur[0] == side and prev[0] != side and cur[2] > prev[2]:
                lengths.append((cur[2] - prev[2]) / 1000.0)
        assert lengths
        assert abs(np.mean(lengths) - out["truth"]["step_length_m"][key]) < 0.01


def test_events_match_foot_height_crossings():
    out = walk10(clean())
    kp = out["kp"]
    for side in ("left", "right"):
        down, up = crossings(foot_height(kp, side))
        assert down and up
        for event in out["truth"]["events"][side]:
            if event.get("hs", 0) > 0:
                assert nearest(event["hs"], down) <= 1, (side, event, down)
            if "to" in event:
                assert nearest(event["to"], up) <= 1, (side, event, up)
        hs_frames = [event["hs"] for event in out["truth"]["events"][side] if "hs" in event]
        to_frames = [event["to"] for event in out["truth"]["events"][side] if "to" in event]
        for hit in down:
            assert nearest(hit, hs_frames) <= 1, (side, hit, hs_frames)
        for hit in up:
            assert nearest(hit, to_frames) <= 1, (side, hit, to_frames)


def test_toe_walk_heel_stays_up():
    out = walk10(clean(toe_walk=1.0, seed=2))
    kp = out["kp"]
    for side, heel in (("left", L_HEEL), ("right", R_HEEL)):
        for event in out["truth"]["events"][side]:
            if "hs" not in event or not event["toe_walk"]:
                continue
            assert kp[event["hs"], heel, 2] > 30.0

    mixed = walk10(clean(toe_walk=0.8, seed=3))
    flagged = []
    for side, heel in (("left", L_HEEL), ("right", R_HEEL)):
        for event in mixed["truth"]["events"][side]:
            if "hs" not in event:
                continue
            up = mixed["kp"][event["hs"], heel, 2] > 30.0
            flagged.append(up)
            if event["toe_walk"]:
                assert up
    assert abs(np.mean(flagged) - 0.8) < 0.15


def test_task_durations():
    held = sls(clean(), "R", 4.0)
    assert abs(held["truth"]["duration_s"] - 4.0) <= 0.1 or abs(held["truth"]["hold_s"] - 4.0) <= 0.1
    z = foot_height(held["kp"], "right")
    up = np.flatnonzero(z >= 90.0)
    assert abs((up[-1] - up[0]) / FPS - 4.0) <= 0.1

    for total, maker in ((13.5, lambda p: tug(p, 13.5)), (16.0, lambda p: sts5(p, 16.0))):
        out = maker(clean())
        clip = (len(out["kp"]) - 1) / out["fps"]
        assert abs(clip - total) <= 0.1
        assert abs(out["truth"]["duration_s"] - total) <= 0.1


def test_noise_and_dropout_shape():
    out = walk10(clean(noise_mm=25, dropout=0.4, seed=4))
    assert out["kp"].shape[1:] == (23, 3)
    assert out["conf"].shape == out["kp"].shape[:2]
    share = float(np.isnan(out["kp"]).mean())
    assert abs(share - 0.4) < 0.02, share
    missing = np.isnan(out["kp"]).any(axis=2)
    assert out["conf"][missing].max() <= 0.2
    assert out["conf"][~missing].min() >= 0.9


def test_asymmetry_inputs_are_in_the_steps():
    person = clean(step_length_asym_pct=18, reduced_knee_flexion_deg=20, reduced_knee_side="R")
    out = walk10(person)
    left = out["truth"]["step_length_m"]["left"]
    right = out["truth"]["step_length_m"]["right"]
    mean = 0.5 * (left + right)
    si = 100.0 * abs(left - right) / mean
    assert abs(si - 18) < 0.1
    assert right < left


def test_presets_write_and_plots(tmp_path):
    plot_dir = Path(__file__).resolve().parents[1] / "out" / "gaitsynth"
    plot_dir.mkdir(parents=True, exist_ok=True)
    assert len(PRESETS) == 9
    for name in PRESETS:
        dest = tmp_path / name
        write_preset(name, dest)
        walk_name = "v1.npz" if "speeds" in PRESETS[name] else "walk10.npz"
        walk = dest / walk_name
        assert walk.exists()
        assert (dest / "tug.npz").exists()
        assert (dest / "sts5.npz").exists()
        assert (dest / "sls.npz").exists()
        data = np.load(walk)
        truth = json.loads(str(data["truth"].item()))
        assert data["kp"].shape[1:] == (23, 3)
        assert truth["task_start_frame"] == 0
        png = plot_dir / f"{name}.png"
        plot_file(walk, png, name)
        assert png.stat().st_size > 1000
    decline = np.load(tmp_path / "adult-decline-69" / "v3.npz")
    assert abs(json.loads(str(decline["truth"].item()))["params"]["speed_m_s"] - 0.94) < 1e-9
    low = np.load(tmp_path / "child-lowdata-5" / "walk10.npz")
    assert abs(float(np.isnan(low["kp"]).mean()) - 0.4) < 0.02


def test_npz_truth_is_json(tmp_path):
    path = tmp_path / "walk.npz"
    save_npz(path, walk10(clean(toe_walk=True)))
    data = np.load(path)
    truth = json.loads(str(data["truth"].item()))
    assert truth["params"]["toe_walk"] == 1.0
    assert truth["fps"] == FPS
