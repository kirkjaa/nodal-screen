"""Synthetic walks and screening tests, built footstep first.

Lab frame, millimetres: x forward along the walkway, y left, z up, floor at 0.
Joints are the 17 COCO body points, then left big toe, left small toe, left heel,
right big toe, right small toe, right heel.

Segment lengths are fractions of body height. Thigh 0.245, shank 0.246 and foot
0.152 are the length/height values in the Winter anthropometry table quoted by
the ME/BIOE 281 homework (Winter 1990). In the 4th edition, Table 4.1 is mass,
center of mass and radius of gyration; the length figure is Figure 4.1 (Drillis
and Contini, 1966). Upper arm 0.186, forearm 0.146 and the 0.039 ankle-height
label are read from that figure as reprinted in the WPI RBE 595 notes. Hip
breadth 0.191 and trunk 0.288 (0.818 shoulder label minus 0.530 hip label) use
the same figure; those two labels were not named in the text layer.

Heights below, when a preset does not set one, are rough demo values, not a
growth chart. Speeds, cadences and hold times on the presets are demo inputs,
not published norms.

    python -m screen.gaitsynth --preset child-typical-6 --out data/raw/child-typical-6/
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

FPS = 60

NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SH, R_SH, L_EL, R_EL, L_WR, R_WR = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_KN, R_KN, L_AN, R_AN = 11, 12, 13, 14, 15, 16
L_BTOE, L_STOE, L_HEEL = 17, 18, 19
R_BTOE, R_STOE, R_HEEL = 20, 21, 22

# Pairs whose length is fixed by construction. Tests use the same list.
BONES = (
    (L_HIP, L_KN), (L_KN, L_AN), (R_HIP, R_KN), (R_KN, R_AN),
    (L_SH, L_EL), (L_EL, L_WR), (R_SH, R_EL), (R_EL, R_WR),
    (L_HEEL, L_BTOE), (R_HEEL, R_BTOE),
    (L_AN, L_HEEL), (L_AN, L_BTOE), (L_AN, L_STOE),
    (R_AN, R_HEEL), (R_AN, R_BTOE), (R_AN, R_STOE),
    (L_HIP, R_HIP), (L_SH, R_SH),
    (L_SH, L_HIP), (R_SH, R_HIP),
    (NOSE, L_EYE), (NOSE, R_EYE), (NOSE, L_EAR), (NOSE, R_EAR),
    (L_SH, NOSE), (R_SH, NOSE),
)


def rough_height(age_y: float, sex: str) -> float:
    """Rough demo height in metres. Not transcribed from a growth chart."""
    if age_y < 12:
        return 1.05 + 0.035 * max(age_y - 5, 0) + (0.02 if sex == "M" else 0.0)
    return 1.76 if sex == "M" else 1.62


@dataclass
class Person:
    age_y: float
    sex: str
    height_m: float | None = None
    speed_m_s: float = 1.25
    cadence_spm: float = 112.0
    step_length_asym_pct: float = 0.0
    step_time_asym_pct: float = 0.0
    step_time_cv_pct: float = 0.0
    toe_walk: float | bool = 0.0
    reduced_knee_flexion_deg: float = 0.0
    reduced_knee_side: str = "R"
    arm_swing_scale: float = 1.0
    noise_mm: float = 0.0
    dropout: float = 0.0
    seed: int = 0

    def __post_init__(self):
        if isinstance(self.toe_walk, bool):
            self.toe_walk = 1.0 if self.toe_walk else 0.0
        else:
            self.toe_walk = float(self.toe_walk)
        if self.height_m is None:
            self.height_m = rough_height(self.age_y, self.sex)
        self.reduced_knee_side = "L" if self.reduced_knee_side in ("L", "left") else "R"


@dataclass
class Body:
    H: float
    thigh: float
    shank: float
    foot: float
    ankle_h: float
    heel_to_ankle: float
    toe_w: float
    upper_arm: float
    forearm: float
    hip_w: float
    shoulder_w: float
    trunk: float
    head: float

    @classmethod
    def from_height(cls, height_m: float) -> "Body":
        h = height_m * 1000.0
        foot = 0.152 * h
        return cls(
            H=h,
            thigh=0.245 * h,
            shank=0.246 * h,
            foot=foot,
            ankle_h=0.039 * h,
            heel_to_ankle=0.25 * foot,  # rough; not a Table 4.1 cell
            toe_w=0.025 * h,  # rough
            upper_arm=0.186 * h,
            forearm=0.146 * h,
            hip_w=0.191 * h,
            shoulder_w=0.22 * h,  # rough; the figure label was not clear
            trunk=0.288 * h,
            head=0.13 * h,  # rough
        )

    @property
    def leg(self) -> float:
        return self.thigh + self.shank


def _fwd_lat(yaw: float):
    fwd = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    lat = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    return fwd, lat


def _pitch_xz(back: float, up: float, pitch: float):
    """Rotate a foot point about the toe. Positive pitch lifts the heel."""
    c, s = math.cos(pitch), math.sin(pitch)
    x_s = -back
    return c * x_s + s * up, -s * x_s + c * up


def foot_points(toe, yaw: float, pitch: float, side: str, body: Body):
    fwd, lat = _fwd_lat(yaw)
    if side == "R":
        lat = -lat

    def place(back, lateral, up):
        x2, z2 = _pitch_xz(back, up, pitch)
        return toe + fwd * x2 + lat * lateral + np.array([0.0, 0.0, z2])

    heel = place(body.foot, 0.0, 0.0)
    big = place(0.0, 0.0, 0.0)
    small = place(0.0, body.toe_w, 0.0)
    ankle = place(body.foot - body.heel_to_ankle, 0.0, body.ankle_h)
    return heel, ankle, big, small


def knee_position(hip, ankle, body: Body, forward):
    hip = np.asarray(hip, float)
    ankle = np.asarray(ankle, float)
    delta = ankle - hip
    dist = float(np.linalg.norm(delta))
    max_d = body.leg - 0.5
    min_d = abs(body.thigh - body.shank) + 0.5
    if dist < min_d or dist > max_d:
        raise RuntimeError(f"leg not in reach: {dist:.1f} mm")
    u = delta / dist
    a = (body.thigh ** 2 - body.shank ** 2 + dist ** 2) / (2.0 * dist)
    h = math.sqrt(max(body.thigh ** 2 - a * a, 0.0))
    f = forward - u * float(np.dot(forward, u))
    n = float(np.linalg.norm(f))
    if n < 1e-8:
        up = np.array([0.0, 0.0, 1.0])
        f = up - u * float(np.dot(up, u))
        n = float(np.linalg.norm(f))
    f = f / n
    if float(np.dot(f, forward)) < 0:
        f = -f
    knee = hip + u * a + f * h
    return knee


def _hips(pelvis, yaw, body: Body):
    _, lat = _fwd_lat(yaw)
    half = body.hip_w / 2.0
    return pelvis + lat * half, pelvis - lat * half


def _limit_z(pelvis, ankles, yaw, body: Body):
    """Lower the pelvis so both ankles stay inside the leg length.

    Hip x and y are left as they are, so the forward speed does not change.
    One pass is enough: those x and y do not depend on height.
    """
    pelvis = np.array(pelvis, float)
    left, right = _hips(pelvis, yaw, body)
    max_h = body.leg - 3.0
    for hip, ankle in ((left, ankles[0]), (right, ankles[1])):
        horiz = math.hypot(float(hip[0] - ankle[0]), float(hip[1] - ankle[1]))
        if horiz >= max_h:
            continue
        room = math.sqrt(max_h * max_h - horiz * horiz)
        pelvis[2] = min(float(pelvis[2]), float(ankle[2]) + room)
    return pelvis


def _arm(shoulder, yaw, swing, bend, body: Body, side: str):
    fwd, lat = _fwd_lat(yaw)
    if side == "R":
        lat = -lat
    c, s = math.cos(swing), math.sin(swing)
    direction = -np.array([0.0, 0.0, 1.0]) * c + fwd * s
    direction = direction / np.linalg.norm(direction)
    elbow = shoulder + direction * body.upper_arm
    cb, sb = math.cos(bend), math.sin(bend)
    fdir = direction * cb + (-fwd) * sb + lat * 0.2
    fdir = fdir / np.linalg.norm(fdir)
    wrist = elbow + fdir * body.forearm
    return elbow, wrist


def _head(mid, yaw, body: Body):
    fwd, lat = _fwd_lat(yaw)
    up = np.array([0.0, 0.0, 1.0])
    nose = mid + up * (body.head * 0.85) + fwd * (body.head * 0.12)
    eye_l = nose + lat * (0.03 * body.H) + up * (0.015 * body.H) - fwd * (0.02 * body.H)
    eye_r = nose - lat * (0.03 * body.H) + up * (0.015 * body.H) - fwd * (0.02 * body.H)
    ear_l = nose + lat * (0.07 * body.H) - fwd * (0.05 * body.H)
    ear_r = nose - lat * (0.07 * body.H) - fwd * (0.05 * body.H)
    return nose, eye_l, eye_r, ear_l, ear_r


def _pull_airborne(toe, pitch, side, hip, yaw, body: Body):
    """Keep a swinging foot inside the leg length. Planted feet are not moved."""
    toe = np.array(toe, float)
    max_d = body.leg - 8.0
    for _ in range(4):
        heel, ankle, big, _small = foot_points(toe, yaw, pitch, side, body)
        if min(float(heel[2]), float(big[2])) <= 5.0:
            return toe
        delta = ankle[:2] - hip[:2]
        horiz = float(np.hypot(delta[0], delta[1]))
        allow = math.sqrt(max(max_d ** 2 - (body.leg * 0.55) ** 2, 1.0))
        if horiz <= allow:
            return toe
        toe = toe.copy()
        toe[:2] = toe[:2] - delta / horiz * (horiz - allow)
    return toe


def skeleton(left_toe, right_toe, left_pitch, right_pitch, pelvis, yaw, swings, bends, body: Body):
    """One pose. Segment lengths come from `body`, not from the joint angles."""
    hip_l, hip_r = _hips(pelvis, yaw, body)
    left_toe = _pull_airborne(left_toe, left_pitch, "L", hip_l, yaw, body)
    right_toe = _pull_airborne(right_toe, right_pitch, "R", hip_r, yaw, body)
    heel_l, ank_l, big_l, small_l = foot_points(left_toe, yaw, left_pitch, "L", body)
    heel_r, ank_r, big_r, small_r = foot_points(right_toe, yaw, right_pitch, "R", body)
    pelvis = _limit_z(pelvis, (ank_l, ank_r), yaw, body)
    hip_l, hip_r = _hips(pelvis, yaw, body)
    forward, _ = _fwd_lat(yaw)
    mid = (hip_l + hip_r) / 2.0
    knee_l = knee_position(hip_l, ank_l, body, forward)
    knee_r = knee_position(hip_r, ank_r, body, forward)

    _, lat = _fwd_lat(yaw)
    trunk_top = mid + np.array([0.0, 0.0, body.trunk]) + forward * (0.04 * body.trunk)
    sh_l = trunk_top + lat * (body.shoulder_w / 2.0)
    sh_r = trunk_top - lat * (body.shoulder_w / 2.0)
    el_l, wr_l = _arm(sh_l, yaw, swings[0], bends[0], body, "L")
    el_r, wr_r = _arm(sh_r, yaw, swings[1], bends[1], body, "R")
    nose, eye_l, eye_r, ear_l, ear_r = _head(trunk_top, yaw, body)

    row = np.zeros((23, 3))
    for idx, point in (
        (NOSE, nose), (L_EYE, eye_l), (R_EYE, eye_r), (L_EAR, ear_l), (R_EAR, ear_r),
        (L_SH, sh_l), (R_SH, sh_r), (L_EL, el_l), (R_EL, el_r), (L_WR, wr_l), (R_WR, wr_r),
        (L_HIP, hip_l), (R_HIP, hip_r), (L_KN, knee_l), (R_KN, knee_r), (L_AN, ank_l), (R_AN, ank_r),
        (L_BTOE, big_l), (L_STOE, small_l), (L_HEEL, heel_l),
        (R_BTOE, big_r), (R_STOE, small_r), (R_HEEL, heel_r),
    ):
        row[idx] = point
    return row


def _toe_stride(index: int, share: float) -> bool:
    if share <= 0:
        return False
    if share >= 1:
        return True
    return (index % 5) < int(round(share * 5))


def _step_lengths(person: Person):
    mean_t = 60.0 / person.cadence_spm
    mean_l = person.speed_m_s * mean_t
    half_l = 0.5 * (person.step_length_asym_pct / 100.0) * mean_l
    half_t = 0.5 * (person.step_time_asym_pct / 100.0) * mean_t
    # Right is the shorter step when asymmetry is positive. The reduced-knee
    # preset uses the right leg.
    lengths = {"L": mean_l + half_l, "R": mean_l - half_l}
    times = {"L": mean_t + half_t, "R": mean_t - half_t}
    return lengths, times, mean_t


def _schedule(person: Person, distance_m: float, zone: bool):
    lengths, times, mean_t = _step_lengths(person)
    x = 0.0
    side = "L"
    count = 0
    while x < distance_m - 1e-9:
        x += lengths[side]
        side = "R" if side == "L" else "L"
        count += 1
    factors = np.ones(count)
    if person.step_time_cv_pct > 0 and count:
        rng = np.random.default_rng(person.seed)
        # Variability is applied on the steady steps only, then recentered.
        steady = []
        x = 0.0
        side = "L"
        for i in range(count):
            if not zone or (2.0 <= x < max(distance_m - 2.0, 2.0) and distance_m >= 10):
                steady.append(i)
            x += lengths[side]
            side = "R" if side == "L" else "L"
        if steady:
            noise = rng.normal(0.0, person.step_time_cv_pct / 100.0, len(steady))
            noise -= noise.mean()
            for i, value in zip(steady, noise):
                factors[i] = max(0.5, 1.0 + float(value))

    steps = []
    x = 0.0
    t = 0.0
    side = "L"
    for i in range(count):
        slow = zone and distance_m >= 10 and (x < 2.0 or x >= distance_m - 2.0)
        scale = 1.6 if slow else 1.0
        duration = times[side] * scale * float(factors[i])
        steps.append({
            "side": side,
            "along_m": x,
            "length_m": lengths[side],
            "time_s": duration,
            "hs_time": t,
            "toe_walk": _toe_stride(i, person.toe_walk),
            "steady": not slow,
        })
        x += lengths[side]
        t += duration
        side = "R" if side == "L" else "L"
    # Trailing foot already down at the start, from a step that began earlier.
    pre_side = "R"
    steps.insert(0, {
        "side": pre_side,
        "along_m": -lengths[pre_side],
        "length_m": lengths[pre_side],
        "time_s": times[pre_side],
        "hs_time": -times[pre_side],
        "toe_walk": False,
        "steady": False,
        "phantom": True,
    })
    stride_t = times["L"] + times["R"]
    speed = person.speed_m_s
    stance_frac = float(np.clip(0.60 + 0.08 * (1.25 - speed), 0.55, 0.70))
    for i, step in enumerate(steps):
        nxt = next((steps[j] for j in range(i + 1, len(steps)) if steps[j]["side"] == step["side"]), None)
        if nxt is None:
            # Stay planted through the end of the clip. There is no next landing.
            step["to_time"] = step["hs_time"] + 1.0e4
            step["next_hs"] = None
        else:
            stride = nxt["hs_time"] - step["hs_time"]
            step["to_time"] = step["hs_time"] + min(stance_frac * stride, stride * 0.85)
            step["next_hs"] = nxt["hs_time"]
    return steps, lengths, times, stride_t


def _scale_schedule(steps, duration_s: float):
    finite = [step for step in steps if step["to_time"] < step["hs_time"] + 1000]
    end = max(step["hs_time"] + step["time_s"] for step in steps)
    if finite:
        end = max(end, max(step["to_time"] for step in finite))
    if end <= 0:
        return
    scale = duration_s / end
    for step in steps:
        step["hs_time"] *= scale
        step["to_time"] *= scale
        step["time_s"] *= scale
        if step["next_hs"] is not None:
            step["next_hs"] *= scale


def _frames(steps, n: int):
    def frame(t):
        return int(round(t * FPS))

    for step in steps:
        step["hs"] = frame(step["hs_time"])
        step["to"] = frame(step["to_time"])
        step["next_hs_frame"] = frame(step["next_hs"]) if step["next_hs"] is not None else None
        if step["next_hs_frame"] is not None and step["to"] >= step["next_hs_frame"]:
            step["to"] = step["next_hs_frame"] - 1
        if step["to"] <= step["hs"]:
            step["to"] = step["hs"] + 1
    return n


def _pelvis_keys(steps, body: Body, yaw: float, origin):
    """Pelvis samples at mid-stance, in seconds, so speed is not frame-rounded."""
    fwd, lat = _fwd_lat(yaw)
    keys = []
    for step in steps:
        if step["to_time"] > step["hs_time"] + 1000:
            mid_t = step["hs_time"]
        else:
            mid_t = (step["hs_time"] + step["to_time"]) / 2.0
        sign = 1.0 if step["side"] == "L" else -1.0
        heel = origin + fwd * (step["along_m"] * 1000.0) + lat * (sign * body.hip_w / 2.0)
        ankle_along = heel + fwd * body.heel_to_ankle
        keys.append((mid_t, float(ankle_along[0]), float(ankle_along[1])))
    keys.sort()
    cleaned = []
    for time, x, y in keys:
        if cleaned and time <= cleaned[-1][0]:
            time = cleaned[-1][0] + 1e-4
        cleaned.append((time, x, y))
    return cleaned


def _interp(time_s: float, keys):
    # Hold the end positions. Extrapolating walks the pelvis away from the
    # planted feet after the last step.
    if time_s <= keys[0][0]:
        return keys[0][1], keys[0][2]
    if time_s >= keys[-1][0]:
        return keys[-1][1], keys[-1][2]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= time_s <= b[0]:
            t0, x0, _y0 = a
            t1, x1, _y1 = b
            span = t1 - t0 if t1 != t0 else 1e-6
            w = (time_s - t0) / span
            return x0 + (x1 - x0) * w, 0.0
    return keys[-1][1], keys[-1][2]


def _heel_pose(step, yaw, origin, body: Body):
    fwd, lat = _fwd_lat(yaw)
    sign = 1.0 if step["side"] == "L" else -1.0
    heel = origin + fwd * (step["along_m"] * 1000.0) + lat * (sign * body.hip_w / 2.0)
    heel = np.array([heel[0], heel[1], 0.0])
    # Toe is one foot length ahead of the heel. foot_points places the toe
    # and rotates the heel back, so pass the toe position.
    toe = heel + fwd * body.foot
    toe[2] = 0.0
    return toe


def _pitch_for(step, frame: int, body: Body, swing: bool, person: Person, side: str, s: float):
    reduced = person.reduced_knee_flexion_deg > 0 and side == person.reduced_knee_side
    if step["toe_walk"]:
        # Heel stays about 35 mm up. Short feet stay under a 5 mm horizontal slide.
        rise = min(35.0, body.foot * 0.22)
        pitch = math.asin(rise / body.foot)
    else:
        pitch = 0.0
        if not swing:
            span = max(step["to"] - step["hs"], 1)
            prog = (frame - step["hs"]) / span
            if prog > 0.8:
                rise = min(20.0, body.foot * 0.12)
                pitch = math.asin(rise / body.foot) * (prog - 0.8) / 0.2
        else:
            land = -0.25 if not step["toe_walk"] else math.asin(min(35.0, body.foot * 0.22) / body.foot)
            start = math.asin(min(20.0, body.foot * 0.12) / body.foot)
            pitch = start + (land - start) * s
    return pitch, reduced


def _render_gait(person: Person, distance_m: float, zone: bool, yaw: float, origin, n_frames: int | None, duration_s: float | None, task: str):
    body = Body.from_height(person.height_m)
    steps, lengths, times, stride_t = _schedule(person, distance_m, zone)
    if duration_s is not None:
        _scale_schedule(steps, duration_s)
    finite_to = [step["to_time"] for step in steps if step["to_time"] < step["hs_time"] + 1000]
    end_t = max(finite_to + [step["hs_time"] for step in steps]) + 0.05
    if n_frames is None:
        n_frames = int(round(end_t * FPS)) + 1
    _frames(steps, n_frames)
    keys = _pelvis_keys(steps, body, yaw, origin)
    forward, _ = _fwd_lat(yaw)
    kp = np.zeros((n_frames, 23, 3))
    stride_frames = max(int(round(stride_t * FPS)), 4)

    def covering(frame, side):
        chosen = None
        for step in steps:
            if step["side"] != side:
                continue
            nxt = step["next_hs_frame"]
            if nxt is None or frame < nxt:
                if step["hs"] <= frame or chosen is None:
                    chosen = step
                    if step["hs"] <= frame and (nxt is None or frame < nxt):
                        return step
        return chosen

    for frame in range(n_frames):
        toes = {}
        pitches = {}
        for side in ("L", "R"):
            step = covering(frame, side)
            planted = _heel_pose(step, yaw, origin, body)
            swing = step["hs"] <= frame and frame >= step["to"] and (
                step["next_hs_frame"] is None or frame < step["next_hs_frame"]
            )
            # Before this step's heel strike, if it is the first one, stay planted
            # only when the phantom step says so. `covering` returns the step
            # whose window contains the frame.
            if frame < step["hs"]:
                swing = False
            if swing and step["next_hs_frame"] is not None and frame < step["next_hs_frame"]:
                span = max(step["next_hs_frame"] - step["to"], 1)
                s = (frame - step["to"]) / span
                s = min(max(s, 0.0), 0.999)
                u = 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5
                nxt = next(item for item in steps if item["side"] == side and item["hs"] == step["next_hs_frame"])
                dest = _heel_pose(nxt, yaw, origin, body)
                toe = planted * (1 - u) + dest * u
                pitch, reduced = _pitch_for(step, frame, body, True, person, side, s)
                peak = 12.0 if reduced else 20.0
                clearance = 12.0 + (peak - 12.0) * math.sin(math.pi * s)
                if reduced:
                    outward = 60.0 * math.sin(math.pi * s)
                    _, lat = _fwd_lat(yaw)
                    if side == "R":
                        lat = -lat
                    toe = toe + lat * outward
                heel, ankle, big, small = foot_points(toe, yaw, pitch, side, body)
                low = min(heel[2], big[2], small[2])
                lift = clearance - low
                toe = toe + np.array([0.0, 0.0, lift])
            else:
                toe = planted
                pitch, _ = _pitch_for(step, frame, body, False, person, side, 0.0)
            toes[side] = toe
            pitches[side] = pitch

        px, _along_y = _interp(frame / FPS, keys)
        wave = 15.0 * math.sin(2.0 * math.pi * frame / stride_frames)
        sway = 20.0 * math.sin(2.0 * math.pi * frame / max(stride_frames / 2.0, 1))
        base_z = body.ankle_h + body.leg * math.cos(math.radians(8))
        pelvis = np.array([px, sway, base_z + wave])
        phase = 2.0 * math.pi * frame / stride_frames
        amp = 0.45 * person.arm_swing_scale
        swings = (-amp * math.sin(phase), amp * math.sin(phase))
        bends = (0.35, 0.35)
        kp[frame] = skeleton(toes["L"], toes["R"], pitches["L"], pitches["R"], pelvis, yaw, swings, bends, body)

    events = {"left": [], "right": []}
    for step in steps:
        if step.get("phantom") and not (0 <= step["to"] < n_frames):
            continue
        name = "left" if step["side"] == "L" else "right"
        entry = {"toe_walk": bool(step["toe_walk"])}
        if not step.get("phantom") and 0 <= step["hs"] < n_frames:
            entry["hs"] = int(step["hs"])
        if 0 <= step["to"] < n_frames:
            entry["to"] = int(step["to"])
        if "hs" in entry or "to" in entry:
            events[name].append(entry)
    truth = _truth(person, task, n_frames, events, lengths, extra={
        "distance_m": distance_m,
        "yaw": yaw,
    })
    return _finish(kp, person, truth, task)


def _truth(person: Person, task: str, n_frames: int, events, lengths, extra=None):
    truth = {
        "task": task,
        "fps": FPS,
        "params": asdict(person),
        "step_length_m": {"left": lengths["L"], "right": lengths["R"]},
        "events": events,
        "task_start_frame": 0,
        "task_end_frame": n_frames - 1,
        "duration_s": (n_frames - 1) / FPS,
    }
    if extra:
        truth.update(extra)
    return truth


def _finish(kp, person: Person, truth, task: str):
    conf = np.full((kp.shape[0], 23), 0.95)
    if person.noise_mm or person.dropout:
        rng = np.random.default_rng(person.seed + {"walk10": 1, "tug": 2, "sts5": 3, "sls": 4}.get(task, 5))
        if person.noise_mm:
            kp = kp + rng.normal(0.0, person.noise_mm, kp.shape)
        if person.dropout:
            target = person.dropout * kp.shape[0] * 23
            got = 0
            guard = 0
            while got < target - 0.01 * kp.shape[0] * 23 and guard < 20000:
                guard += 1
                joint = int(rng.integers(0, 23))
                length = int(rng.integers(8, 28))
                start = int(rng.integers(0, kp.shape[0]))
                end = min(kp.shape[0], start + length)
                room = target + 0.015 * kp.shape[0] * 23 - got
                end = min(end, start + max(1, int(room)))
                free = np.isfinite(kp[start:end, joint, 0]).sum()
                kp[start:end, joint, :] = np.nan
                got += int(free)
            missing = np.isnan(kp).any(axis=2)
            conf = conf.copy()
            conf[missing] = 0.15
    return {"kp": kp, "conf": conf, "fps": float(FPS), "truth": truth}


def walk10(person: Person):
    """10 m steady walk, plus about 2 m to speed up and 2 m to slow down."""
    origin = np.zeros(3)
    return _render_gait(person, 14.0, True, 0.0, origin, None, None, "walk10")


def _paste_phase(person, dest, start, count, builder):
    piece = builder(count)
    n = min(count, len(piece["kp"]), dest.shape[0] - start)
    dest[start:start + n] = piece["kp"][:n]
    return piece, n


def tug(person: Person, total_s: float):
    """Sit, stand, walk 3 m, turn, walk back, turn, sit. Duration is total_s."""
    n = int(round(total_s * FPS)) + 1
    t_stand = min(1.2, total_s * 0.12)
    t_turn = min(1.0, total_s * 0.08)
    t_sit = t_stand
    t_walk = max(0.4, (total_s - 2 * t_stand - 2 * t_turn) / 2.0)
    parts = [t_stand, t_walk, t_turn, t_walk, t_turn, t_sit]
    counts = [max(2, int(round(t / total_s * n))) for t in parts]
    while sum(counts) > n:
        counts[counts.index(max(counts))] -= 1
    while sum(counts) < n:
        counts[counts.index(max(counts))] += 1
    kp = np.zeros((n, 23, 3))
    cursor = 0
    events = {"left": [], "right": []}
    # Stand up at the origin, then walk out along +x.
    stand = _sit_stand_clip(person, counts[0], rising=True)
    kp[0:counts[0]] = stand["kp"]
    cursor = counts[0]
    out = _render_gait(person, 3.0, False, 0.0, np.zeros(3), counts[1], counts[1] / FPS, "walk10")
    kp[cursor:cursor + counts[1]] = out["kp"][:counts[1]]
    _shift_events(events, out["truth"]["events"], cursor)
    cursor += counts[1]
    kp[cursor:cursor + counts[2]] = _turn_clip(kp[cursor - 1], counts[2], 0.0, math.pi, person)
    cursor += counts[2]
    back_origin = np.array([3000.0, 0.0, 0.0])
    back = _render_gait(person, 3.0, False, math.pi, back_origin, counts[3], counts[3] / FPS, "walk10")
    kp[cursor:cursor + counts[3]] = back["kp"][:counts[3]]
    _shift_events(events, back["truth"]["events"], cursor)
    cursor += counts[3]
    kp[cursor:cursor + counts[4]] = _turn_clip(kp[cursor - 1], counts[4], math.pi, 2 * math.pi, person)
    cursor += counts[4]
    sit = _sit_stand_clip(person, counts[5], rising=False)
    kp[cursor:cursor + counts[5]] = sit["kp"]
    lengths, _, _ = _step_lengths(person)
    truth = _truth(person, "tug", n, events, lengths, extra={"total_s": total_s, "chair_m": 0.45})
    return _finish(kp, person, truth, "tug")


def _shift_events(into, events, offset):
    for side in ("left", "right"):
        for event in events[side]:
            shifted = {"toe_walk": event["toe_walk"]}
            if "hs" in event:
                shifted["hs"] = int(event["hs"] + offset)
            if "to" in event:
                shifted["to"] = int(event["to"] + offset)
            into[side].append(shifted)


def _planted_toes(body: Body, yaw: float, origin):
    fwd, lat = _fwd_lat(yaw)
    toes = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        heel = origin + lat * (sign * body.hip_w / 2.0)
        toe = heel + fwd * body.foot
        toe = np.array([toe[0], toe[1], 0.0])
        toes[side] = toe
    return toes


def _sit_stand_clip(person: Person, n: int, rising: bool):
    body = Body.from_height(person.height_m)
    origin = np.zeros(3)
    toes = _planted_toes(body, 0.0, origin)
    # Hip x: behind the ankles when sitting, over them when standing.
    stand_z = body.ankle_h + body.leg * math.cos(math.radians(8))
    sit_z = 450.0
    sit_x = -body.thigh * 0.85
    stand_x = body.heel_to_ankle
    kp = np.zeros((n, 23, 3))
    bends = (1.15, 1.15)
    swings = (0.9, 0.9)
    for i in range(n):
        u = i / max(n - 1, 1)
        if not rising:
            u = 1.0 - u
        # Smooth rise: 0 sit, 1 stand.
        w = 0.5 - 0.5 * math.cos(math.pi * u)
        pelvis = np.array([
            sit_x + (stand_x - sit_x) * w,
            0.0,
            sit_z + (stand_z - sit_z) * w,
        ])
        kp[i] = skeleton(toes["L"], toes["R"], 0.0, 0.0, pelvis, 0.0, swings, bends, body)
    return {"kp": kp}


def _turn_clip(last_row, n: int, yaw0: float, yaw1: float, person: Person):
    """Pivot. Feet stay at the last frame's toe positions. Yaw changes."""
    body = Body.from_height(person.height_m)
    # Recover a planted toe from the last heel/toe by keeping those xy and z=0.
    left_toe = np.array([last_row[L_BTOE, 0], last_row[L_BTOE, 1], 0.0])
    right_toe = np.array([last_row[R_BTOE, 0], last_row[R_BTOE, 1], 0.0])
    pelvis_xy = 0.5 * (last_row[L_HIP, :2] + last_row[R_HIP, :2])
    stand_z = body.ankle_h + body.leg * math.cos(math.radians(8))
    kp = np.zeros((n, 23, 3))
    for i in range(n):
        w = i / max(n - 1, 1)
        yaw = yaw0 + (yaw1 - yaw0) * w
        pelvis = np.array([pelvis_xy[0], pelvis_xy[1], stand_z])
        kp[i] = skeleton(left_toe, right_toe, 0.0, 0.0, pelvis, yaw, (0.2, 0.2), (0.35, 0.35), body)
    return kp


def sts5(person: Person, total_s: float):
    """Five rises from a 0.45 m chair, arms crossed. Duration is total_s."""
    n = int(round(total_s * FPS)) + 1
    body = Body.from_height(person.height_m)
    toes = _planted_toes(body, 0.0, np.zeros(3))
    stand_z = body.ankle_h + body.leg * math.cos(math.radians(8))
    sit_z = 450.0
    sit_x = -body.thigh * 0.85
    stand_x = body.heel_to_ankle
    kp = np.zeros((n, 23, 3))
    for i in range(n):
        cycle = (i / max(n - 1, 1)) * 5.0
        w = 0.5 - 0.5 * math.cos(2.0 * math.pi * cycle)  # 0 sit, 1 stand, 0 sit
        # The cosine form above is 0 at the start of the cycle and 0 at the end,
        # and 1 at the middle. That is one rise and one return.
        pelvis = np.array([
            sit_x + (stand_x - sit_x) * w,
            0.0,
            sit_z + (stand_z - sit_z) * w,
        ])
        kp[i] = skeleton(toes["L"], toes["R"], 0.0, 0.0, pelvis, 0.0, (0.9, 0.9), (1.15, 1.15), body)
    lengths, _, _ = _step_lengths(person)
    truth = _truth(person, "sts5", n, {"left": [], "right": []}, lengths, extra={"total_s": total_s, "chair_m": 0.45})
    return _finish(kp, person, truth, "sts5")


def sls(person: Person, side: str, hold_s: float):
    """Stand, lift one foot about 10 cm, hold, and put it down.

    `hold_s` is the hold. Short lift and lower sit just outside it, so the
    clip is within 0.1 s of `hold_s` as well.
    """
    side = "L" if side in ("L", "left") else "R"
    trans = 0.04
    total = hold_s + 2 * trans
    n = int(round(total * FPS)) + 1
    body = Body.from_height(person.height_m)
    toes = _planted_toes(body, 0.0, np.zeros(3))
    stand_z = body.ankle_h + body.leg * math.cos(math.radians(6))
    # Pelvis over the stance foot.
    sign = 1.0 if side == "R" else -1.0  # shift toward the foot that stays down
    # If we lift the left foot, stand on the right: pelvis y negative.
    stance_sign = -1.0 if side == "L" else 1.0
    pelvis_y = stance_sign * body.hip_w / 2.0
    kp = np.zeros((n, 23, 3))
    for i in range(n):
        t = i / FPS
        if t < trans:
            lift = 100.0 * (t / trans)
        elif t > hold_s + trans:
            lift = 100.0 * max(0.0, 1.0 - (t - hold_s - trans) / trans)
        else:
            lift = 100.0
        left = toes["L"].copy()
        right = toes["R"].copy()
        if side == "L":
            left[2] = lift
        else:
            right[2] = lift
        pelvis = np.array([body.heel_to_ankle, pelvis_y, stand_z])
        kp[i] = skeleton(left, right, 0.0, 0.0, pelvis, 0.0, (0.4, 0.4), (0.5, 0.5), body)
    lengths, _, _ = _step_lengths(person)
    truth = _truth(person, "sls", n, {"left": [], "right": []}, lengths, extra={
        "hold_s": hold_s,
        "side": "left" if side == "L" else "right",
        "total_s": total,
    })
    # The reported duration for this task is the hold the caller asked for.
    truth["duration_s"] = (n - 1) / FPS
    truth["hold_s"] = hold_s
    return _finish(kp, person, truth, "sls")


def _py(value):
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def save_npz(path, packed):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        kp=packed["kp"],
        conf=packed["conf"],
        fps=np.float64(packed["fps"]),
        truth=np.array(json.dumps(_py(packed["truth"]))),
    )


PRESETS = {
    "child-typical-6": dict(age_y=6, sex="F", height_m=1.15, speed_m_s=1.10, cadence_spm=146, tug_s=8.0, sts_s=8.0, sls_s=8.0),
    "child-toewalk-7": dict(age_y=7, sex="F", height_m=1.22, speed_m_s=1.05, cadence_spm=148, toe_walk=0.8, tug_s=8.0, sts_s=8.0, sls_s=8.0),
    "child-coord-8": dict(age_y=8, sex="M", height_m=1.28, speed_m_s=1.08, cadence_spm=142, step_time_cv_pct=9.0, tug_s=8.0, sts_s=9.0, sls_s=2.0),
    "child-lowdata-5": dict(age_y=5, sex="M", height_m=1.10, speed_m_s=1.00, cadence_spm=150, noise_mm=25.0, dropout=0.40, tug_s=8.0, sts_s=8.0, sls_s=6.0),
    "adult-typical-45": dict(age_y=45, sex="M", height_m=1.76, speed_m_s=1.30, cadence_spm=112, tug_s=8.0, sts_s=8.5, sls_s=20.0),
    "adult-falls-72": dict(age_y=72, sex="F", height_m=1.60, speed_m_s=0.85, cadence_spm=100, arm_swing_scale=0.7, tug_s=13.5, sts_s=12.0, sls_s=4.0),
    "adult-sarco-78": dict(age_y=78, sex="M", height_m=1.72, speed_m_s=0.75, cadence_spm=96, tug_s=14.0, sts_s=16.0, sls_s=5.0),
    "adult-asym-64": dict(age_y=64, sex="M", height_m=1.74, speed_m_s=1.05, cadence_spm=104, step_length_asym_pct=18.0, reduced_knee_flexion_deg=20.0, reduced_knee_side="R", tug_s=11.0, sts_s=12.0, sls_s=8.0),
    "adult-decline-69": dict(age_y=69, sex="F", height_m=1.62, speed_m_s=0.94, cadence_spm=108, tug_s=11.0, sts_s=12.0, sls_s=8.0, speeds=(1.15, 1.05, 0.94)),
}


def _person_from_spec(spec, **over):
    skip = {"tug_s", "sts_s", "sls_s", "speeds"}
    data = {k: v for k, v in spec.items() if k not in skip}
    data.update(over)
    return Person(**data)


def write_preset(name: str, out_dir):
    spec = PRESETS[name]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    person = _person_from_spec(spec)
    if "speeds" in spec:
        for label, speed in zip(("v1", "v2", "v3"), spec["speeds"]):
            save_npz(out / f"{label}.npz", walk10(_person_from_spec(spec, speed_m_s=speed)))
    else:
        save_npz(out / "walk10.npz", walk10(person))
    save_npz(out / "tug.npz", tug(person, spec["tug_s"]))
    save_npz(out / "sts5.npz", sts5(person, spec["sts_s"]))
    save_npz(out / "sls.npz", sls(person, "L", spec["sls_s"]))


def plot_file(npz_path, png_path, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = np.load(npz_path, allow_pickle=False)
    kp = data["kp"]
    truth = json.loads(str(data["truth"].item()))
    fps = float(data["fps"])
    time = np.arange(len(kp)) / fps
    fig, ax = plt.subplots(figsize=(8.0, 3.2))
    series = (
        ("L heel", L_HEEL, "#3b5a7a"),
        ("R heel", R_HEEL, "#c8352b"),
        ("L toe", L_BTOE, "#2f6f4f"),
        ("R toe", R_BTOE, "#8a6a1f"),
    )
    for label, idx, color in series:
        ax.plot(time, kp[:, idx, 2], label=label, color=color, linewidth=1.0)
    for side, color in (("left", "#3b5a7a"), ("right", "#c8352b")):
        for event in truth.get("events", {}).get(side, []):
            if "hs" in event:
                ax.axvline(event["hs"] / fps, color=color, alpha=0.35, linewidth=0.6)
            if "to" in event:
                ax.axvline(event["to"] / fps, color=color, alpha=0.35, linewidth=0.6, linestyle="--")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Foot height (mm)")
    ax.set_title(f"{title} foot height, synthetic")
    ax.legend(loc="upper right", fontsize=8, ncol=4)
    fig.tight_layout()
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=100)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write synthetic screening takes.")
    parser.add_argument("--preset", required=True, choices=sorted(PRESETS))
    parser.add_argument("--out", required=True)
    parser.add_argument("--plot", default="", help="Optional directory for a foot-height plot.")
    args = parser.parse_args(argv)
    write_preset(args.preset, args.out)
    if args.plot:
        walk = Path(args.out) / ("v1.npz" if "speeds" in PRESETS[args.preset] else "walk10.npz")
        plot_file(walk, Path(args.plot) / f"{args.preset}.png", args.preset)


if __name__ == "__main__":
    main()
