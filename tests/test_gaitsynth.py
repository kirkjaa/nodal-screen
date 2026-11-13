"""Synthetic screening walks: bones, contacts, speed, and the nine presets."""

import json
from pathlib import Path

import numpy as np

from screen.gaitsynth import (
    BONES,
    FPS,
    L_AN,
    L_BTOE,
    L_HEEL,
    L_HIP,
    L_KN,
    L_SH,
    L_WR,
    PRESETS,
    R_AN,
    R_BTOE,
    R_HEEL,
    R_HIP,
    R_KN,
    R_SH,
    R_WR,
    Person,
    _knee_flex_deg,
    _person_from_spec,
    plot_file,
    plot_knee,
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
    # The foot rolls over the heel and onto the toe, so only the point that is on
    # the floor must stay put: no point slides while it is within 3 mm of the floor.
    out = walk10(clean())
    kp = out["kp"]
    for side, heel, toe in (("left", L_HEEL, L_BTOE), ("right", R_HEEL, R_BTOE)):
        small = toe + 1  # small toe follows the big toe in the joint list
        for event in out["truth"]["events"][side]:
            if "hs" not in event or "to" not in event:
                continue
            hs, to = event["hs"], event["to"]
            for idx in (heel, toe, small):
                down = np.flatnonzero(kp[hs:to, idx, 2] < 3.0)
                if down.size < 2:
                    continue
                xy = kp[hs + down, idx, :2]
                drift = np.linalg.norm(xy - xy[0], axis=1).max()
                assert drift < 5.0, (side, idx, hs, drift)


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
        if name in ("adult-typical-45", "adult-asym-64"):
            knee_png = plot_dir / f"knee-{name}.png"
            plot_knee(walk, knee_png, name)
            assert knee_png.stat().st_size > 1000
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


def _peaks(kp):
    left = float(np.max(_knee_flex_deg(kp[:, L_HIP], kp[:, L_KN], kp[:, L_AN])))
    right = float(np.max(_knee_flex_deg(kp[:, R_HIP], kp[:, R_KN], kp[:, R_AN])))
    return left, right


def _steady_peaks(out):
    kp = out["kp"]
    hip_x = 0.5 * (kp[:, L_HIP, 0] + kp[:, R_HIP, 0])
    zone = (hip_x >= 2000.0) & (hip_x <= 12000.0)
    left = float(np.max(_knee_flex_deg(kp[zone, L_HIP], kp[zone, L_KN], kp[zone, L_AN])))
    right = float(np.max(_knee_flex_deg(kp[zone, R_HIP], kp[zone, R_KN], kp[zone, R_AN])))
    return left, right


def test_knee_peaks_match_the_angle_curves():
    # Measured over the steady 10 m, the part a 10 m walk test times.
    typical = walk10(_person_from_spec(PRESETS["adult-typical-45"]))
    child = walk10(_person_from_spec(PRESETS["child-typical-6"]))
    for out in (typical, child):
        left, right = _steady_peaks(out)
        assert 55.0 <= left <= 65.0, left
        assert 55.0 <= right <= 65.0, right
    asym = walk10(_person_from_spec(PRESETS["adult-asym-64"]))
    left, right = _steady_peaks(asym)
    assert abs((left - right) - 20.0) <= 3.0, (left, right)


def test_heel_lands_and_the_toe_clears():
    for name in ("adult-typical-45", "child-typical-6", "adult-asym-64"):
        out = walk10(_person_from_spec(PRESETS[name]))
        kp = out["kp"]
        for side, heel, toe in (("left", L_HEEL, L_BTOE), ("right", R_HEEL, R_BTOE)):
            events = out["truth"]["events"][side]
            strikes = [event["hs"] for event in events if "hs" in event]
            for event in events:
                hs = event.get("hs")
                if hs is None or hs < 1 or event["toe_walk"]:
                    continue
                err = float(np.linalg.norm(kp[hs, heel, :2] - np.array(event["heel_mm"])))
                assert err < 5.0, (name, side, hs, err)
                assert abs(float(kp[hs, heel, 2])) < 1.0, (name, side, hs)
            for event in events:
                to = event.get("to")
                if to is None:
                    continue
                nxt = [hs for hs in strikes if hs > to]
                if not nxt:
                    continue
                swing = kp[to:nxt[0], toe, 2]
                assert swing.size
                assert float(np.min(swing)) >= 5.0, (name, side, to)


def test_sts_arms_stay_crossed():
    out = sts5(_person_from_spec(PRESETS["adult-typical-45"]), 8.5)
    kp = out["kp"]
    left = np.linalg.norm(kp[:, L_WR] - kp[:, R_SH], axis=1)
    right = np.linalg.norm(kp[:, R_WR] - kp[:, L_SH], axis=1)
    assert float(left.max()) < 150.0
    assert float(right.max()) < 150.0


def _horiz_speed(kp, heel, toe):
    heel_step = np.linalg.norm(np.diff(kp[:, heel, :2], axis=0), axis=1)
    toe_step = np.linalg.norm(np.diff(kp[:, toe, :2], axis=0), axis=1)
    slow = np.minimum(heel_step, toe_step)
    return np.concatenate([slow, slow[-1:]])


def test_swing_foot_does_not_ease_to_a_stop():
    # The slowed final stride sits in the timing zone and is not part of this check.
    for name in ("adult-typical-45", "child-typical-6"):
        out = walk10(_person_from_spec(PRESETS[name]))
        kp = out["kp"]
        for side, heel, toe in (("left", L_HEEL, L_BTOE), ("right", R_HEEL, R_BTOE)):
            events = out["truth"]["events"][side]
            strikes = [event["hs"] for event in events if "hs" in event]
            if len(strikes) < 2:
                continue
            last = strikes[-1]
            speed = _horiz_speed(kp, heel, toe)
            for event in events:
                to = event.get("to")
                if to is None:
                    continue
                nxt = [hs for hs in strikes if hs > to]
                if not nxt or nxt[0] == last or nxt[0] <= to + 2:
                    continue
                seg = speed[to:nxt[0]]
                peak = float(seg.max())
                assert peak > 0.0
                slow_after = 0
                for value in seg:
                    if value < 0.1 * peak:
                        slow_after += 1
                    else:
                        break
                slow_before = 0
                for value in seg[::-1]:
                    if value < 0.1 * peak:
                        slow_before += 1
                    else:
                        break
                assert slow_after <= 1, (name, side, to, slow_after)
                assert slow_before <= 1, (name, side, to, slow_before)


def test_stance_and_double_support_fractions():
    for name in ("adult-typical-45", "child-typical-6"):
        out = walk10(_person_from_spec(PRESETS[name]))
        fractions = []
        for side in ("left", "right"):
            events = out["truth"]["events"][side]
            strikes = [event["hs"] for event in events if "hs" in event]
            for event in events:
                if "hs" not in event or "to" not in event:
                    continue
                nxt = [hs for hs in strikes if hs > event["hs"]]
                if not nxt:
                    continue
                cycle = nxt[0] - event["hs"]
                if cycle < 10:
                    continue
                fractions.append((event["to"] - event["hs"]) / cycle)
        assert fractions
        assert 0.58 <= float(np.mean(fractions)) <= 0.62

        def down(side, frame):
            for event in out["truth"]["events"][side]:
                hs = event.get("hs")
                to = event.get("to")
                if hs is not None and to is not None and hs <= frame < to:
                    return True
            return False

        n = len(out["kp"])
        both = total = 0
        for frame in range(120, n - 120):
            total += 1
            if down("left", frame) and down("right", frame):
                both += 1
        assert total
        low, high = (0.14, 0.20) if name.startswith("child") else (0.18, 0.24)
        assert low <= both / total <= high, (name, both / total)


def test_step_width_and_hip_spacing():
    for name in ("adult-typical-45", "child-typical-6"):
        out = walk10(_person_from_spec(PRESETS[name]))
        kp = out["kp"]
        height = PRESETS[name]["height_m"] * 1000.0
        gap = np.abs(kp[:, L_HIP, 1] - kp[:, R_HIP, 1])
        assert abs(float(np.median(gap)) - 0.10 * height) < 8.0
        order = []
        for side, ankle in (("left", L_AN), ("right", R_AN)):
            for event in out["truth"]["events"][side]:
                if "hs" in event and event["hs"] > 30:
                    order.append((event["hs"], float(kp[event["hs"], ankle, 1])))
        order.sort()
        widths = [abs(a[1] - b[1]) for a, b in zip(order, order[1:])]
        assert widths
        for width in widths[:-1]:
            assert 0.05 * height <= width <= 0.08 * height




CONTINUITY_PRESETS = ("adult-typical-45", "child-typical-6", "adult-asym-64", "child-toewalk-7")
FOOT = (L_AN, R_AN, L_HEEL, R_HEEL, L_BTOE, R_BTOE, L_BTOE + 1, R_BTOE + 1)


def _swings(out, side):
    events = out["truth"]["events"][side]
    strikes = [event["hs"] for event in events if "hs" in event]
    for event in events:
        to = event.get("to")
        nxt = [hs for hs in strikes if to is not None and hs > to]
        if to is not None and nxt:
            yield to, nxt[0]


def test_no_jumps():
    # Fix 2: nothing teleports. Every joint moves at most 4x walking speed per
    # frame, and foot points change height by at most 25 mm a frame.
    for name in CONTINUITY_PRESETS:
        spec = PRESETS[name]
        out = walk10(_person_from_spec(spec))
        kp = out["kp"]
        limit = 4.0 * spec["speed_m_s"] * 1000.0 / FPS
        step = np.linalg.norm(np.diff(kp, axis=0), axis=2)
        assert float(step.max()) <= limit, (name, float(step.max()), np.unravel_index(step.argmax(), step.shape))
        dz = np.abs(np.diff(kp[:, FOOT, 2], axis=0))
        assert float(dz.max()) <= 25.0, (name, float(dz.max()))


def test_swing_ankle_moves_forward_only():
    for name in CONTINUITY_PRESETS:
        out = walk10(_person_from_spec(PRESETS[name]))
        kp = out["kp"]
        for side, ankle in (("left", L_AN), ("right", R_AN)):
            for to, hs in _swings(out, side):
                x = kp[to - 1:hs + 1, ankle, 0]
                assert float(np.diff(x).min()) >= -1.0, (name, side, to)


def test_one_speed_peak_per_swing():
    for name in CONTINUITY_PRESETS:
        spec = PRESETS[name]
        out = walk10(_person_from_spec(spec))
        kp = out["kp"]
        for side, ankle in (("left", L_AN), ("right", R_AN)):
            for to, hs in _swings(out, side):
                v = np.linalg.norm(np.diff(kp[to - 1:hs + 1, ankle, :2], axis=0), axis=1) * FPS / 1000.0
                if v.size < 5:
                    continue
                peak = float(v.max())
                assert peak <= 3.5 * spec["speed_m_s"], (name, side, to, peak)
                tops = [i for i in range(1, v.size - 1) if v[i] >= v[i - 1] and v[i] > v[i + 1] and v[i] > 0.5 * peak]
                assert len(tops) == 1, (name, side, to, tops)


def _detect(kp, heel, toe):
    """Plain velocity-threshold events on the slower of heel and toe."""
    speed = np.minimum(np.linalg.norm(np.gradient(kp[:, heel, :2], axis=0), axis=1),
                       np.linalg.norm(np.gradient(kp[:, toe, :2], axis=0), axis=1))
    peak = float(np.percentile(speed, 98))
    contact, hs, to = speed[0] < 0.1 * peak, [], []
    for i in range(1, len(speed)):
        if contact and speed[i] > 0.2 * peak:
            contact = False
            to.append(i)
        elif not contact and speed[i] < 0.1 * peak:
            contact = True
            hs.append(i)
    return hs, to


def test_events_are_recoverable():
    for name in CONTINUITY_PRESETS:
        out = walk10(_person_from_spec(PRESETS[name]))
        kp = out["kp"]
        hip_x = 0.5 * (kp[:, L_HIP, 0] + kp[:, R_HIP, 0])
        for side, heel, toe in (("left", L_HEEL, L_BTOE), ("right", R_HEEL, R_BTOE)):
            hs_found, to_found = _detect(kp, heel, toe)
            for event in out["truth"]["events"][side]:
                for key, found in (("hs", hs_found), ("to", to_found)):
                    frame = event.get(key)
                    if frame is None or not (2000.0 <= hip_x[frame] <= 12000.0):
                        continue
                    assert found and nearest(frame, found) <= 2, (name, side, key, frame)
