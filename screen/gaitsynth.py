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
    foot_off: float
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
            hip_w=0.10 * h,  # rough demo: hip-joint spacing, not the 0.191 outline breadth
            foot_off=0.032 * h,  # rough demo: feet land toward the midline
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


def _elbow_between(shoulder, wrist, upper: float, fore: float, outward):
    """Elbow that keeps both arm lengths. Wrist is moved along the same line if needed."""
    shoulder = np.asarray(shoulder, float)
    wrist = np.asarray(wrist, float)
    delta = wrist - shoulder
    dist = float(np.linalg.norm(delta))
    if dist < 1e-6:
        delta = np.array([1.0, 0.0, 0.0])
        dist = 1.0
    max_d = upper + fore - 1.0
    min_d = abs(upper - fore) + 1.0
    use = min(max(dist, min_d), max_d)
    if abs(use - dist) > 1e-6:
        wrist = shoulder + delta / dist * use
        delta = wrist - shoulder
        dist = use
    along = delta / dist
    a = (upper ** 2 - fore ** 2 + dist ** 2) / (2.0 * dist)
    h = math.sqrt(max(upper ** 2 - a * a, 0.0))
    mid = shoulder + along * a
    axis = np.cross(along, outward)
    n = float(np.linalg.norm(axis))
    if n < 1e-8:
        axis = np.cross(along, np.array([0.0, 0.0, 1.0]))
        n = float(np.linalg.norm(axis))
    axis = axis / n
    elbow = mid + axis * h
    if elbow[2] > mid[2]:
        elbow = mid - axis * h
    return elbow, wrist


def _crossed_arms(sh_l, sh_r, body: Body, yaw: float):
    """Each wrist stays in front of the opposite shoulder, within 150 mm."""
    fwd, lat = _fwd_lat(yaw)
    up = np.array([0.0, 0.0, 1.0])
    # 90 mm forward and 40 mm down: about 98 mm from the opposite shoulder.
    wrist_l = sh_r + fwd * 90.0 - up * 40.0
    wrist_r = sh_l + fwd * 90.0 - up * 40.0
    elbow_l, wrist_l = _elbow_between(sh_l, wrist_l, body.upper_arm, body.forearm, lat)
    elbow_r, wrist_r = _elbow_between(sh_r, wrist_r, body.upper_arm, body.forearm, -lat)
    return elbow_l, wrist_l, elbow_r, wrist_r


def skeleton(left_toe, right_toe, left_pitch, right_pitch, pelvis, yaw, swings, bends, body: Body, crossed: bool = False):
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
    if crossed:
        el_l, wr_l, el_r, wr_r = _crossed_arms(sh_l, sh_r, body, yaw)
    else:
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
    stance_frac = float(np.clip(0.605 + 0.06 * (1.25 - speed), 0.58, 0.62))
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
        heel = origin + fwd * (step["along_m"] * 1000.0) + lat * (sign * body.foot_off)
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
    heel = origin + fwd * (step["along_m"] * 1000.0) + lat * (sign * body.foot_off)
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
            if prog < 0.10:
                # Heel is down. A small angle keeps the toe's floorward travel under 5 mm.
                pitch = -0.12 * (1.0 - prog / 0.10)
            elif prog > 0.8:
                rise = min(20.0, body.foot * 0.12)
                pitch = math.asin(rise / body.foot) * (prog - 0.8) / 0.2
        else:
            land = -0.25 if not step["toe_walk"] else math.asin(min(35.0, body.foot * 0.22) / body.foot)
            start = math.asin(min(20.0, body.foot * 0.12) / body.foot)
            pitch = start + (land - start) * s
    return pitch, reduced


def _rod(v, axis, ang: float):
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(axis, v) * s + axis * float(np.dot(axis, v)) * (1.0 - c)


def _foot_from_ankle(ankle, yaw: float, pitch: float, side: str, body: Body):
    """Foot with the same bone lengths as foot_points, ankle kept."""
    fwd, _lat = _fwd_lat(yaw)
    back = body.foot - body.heel_to_ankle
    x2, z2 = _pitch_xz(back, body.ankle_h, pitch)
    toe = np.asarray(ankle, float) - fwd * x2 - np.array([0.0, 0.0, z2])
    return foot_points(toe, yaw, pitch, side, body)


def _swing_chain(hip, yaw, side, hip_flex_deg, knee_flex_deg, abduct_deg, foot_pitch, body: Body):
    """Knee and foot from hip and knee angles. Lengths come from `body`."""
    fwd, lat = _fwd_lat(yaw)
    up = np.array([0.0, 0.0, 1.0])
    outward = lat if side == "L" else -lat
    axis = lat / max(float(np.linalg.norm(lat)), 1e-8)
    hf = math.radians(hip_flex_deg)
    kf = math.radians(knee_flex_deg)
    ab = math.radians(abduct_deg)
    thigh = -up * math.cos(hf) + fwd * math.sin(hf)
    thigh = thigh * math.cos(ab) + outward * math.sin(ab)
    thigh = thigh / max(float(np.linalg.norm(thigh)), 1e-8)
    knee = np.asarray(hip, float) + thigh * body.thigh
    # Flex about an axis perpendicular to the thigh so the bend equals kf
    # even when the thigh is hiked out to the side.
    flex_axis = axis - thigh * float(np.dot(axis, thigh))
    n_axis = float(np.linalg.norm(flex_axis))
    if n_axis < 1e-8:
        flex_axis = axis
    else:
        flex_axis = flex_axis / n_axis
    shank = _rod(thigh, flex_axis, kf)
    shank = shank / max(float(np.linalg.norm(shank)), 1e-8)
    ankle = knee + shank * body.shank
    heel, ankle, big, small = _foot_from_ankle(ankle, yaw, foot_pitch, side, body)
    return knee, ankle, heel, big, small


def _swing_curve(g: float, stance_frac: float, knee_peak: float):
    """Knee peaks near 70% of the stride. Slopes stay non-zero at both ends of swing.

    A smoothstep would park the foot, and a speed threshold would then call
    contact early. The thigh is still flexing at heel strike, near 27 degrees.
    """
    stance_frac = min(max(stance_frac, 0.4), 0.68)
    span = max(1.0 - stance_frac, 1e-3)
    u = min(max((g - stance_frac) / span, 0.0), 1.0)
    u_peak = min(max((0.70 - stance_frac) / span, 0.18), 0.55)
    if u <= u_peak:
        t = u / u_peak
        knee = 40.0 + (knee_peak - 40.0) * math.sin(0.5 * math.pi * t)
    else:
        t = (u - u_peak) / (1.0 - u_peak)
        knee = knee_peak + (12.0 - knee_peak) * (t ** 0.8)
    hip = -12.0 + 39.0 * (u ** 0.75)
    abduct = math.sin(math.pi * u)
    return knee, hip, abduct, u


def _translate_upper(row, delta):
    """Move the trunk, head, arms and both hips together. Feet stay put."""
    row[:13] = row[:13] + np.asarray(delta, float)


def _plant_knee(row, side: str, body: Body, yaw: float) -> bool:
    hip_i = L_HIP if side == "L" else R_HIP
    an_i = L_AN if side == "L" else R_AN
    kn_i = L_KN if side == "L" else R_KN
    fwd, _lat = _fwd_lat(yaw)
    try:
        row[kn_i] = knee_position(row[hip_i], row[an_i], body, fwd)
    except RuntimeError:
        return False
    return True


def _try_shift(row, delta, stance_sides, body: Body, yaw: float) -> bool:
    saved_upper = row[:13].copy()
    saved_knees = row[[L_KN, R_KN]].copy()
    _translate_upper(row, delta)
    if all(_plant_knee(row, side, body, yaw) for side in stance_sides):
        return True
    row[:13] = saved_upper
    row[L_KN] = saved_knees[0]
    row[R_KN] = saved_knees[1]
    return False


def _write_leg(row, side, knee, ankle, heel, big, small):
    kn_i = L_KN if side == "L" else R_KN
    an_i = L_AN if side == "L" else R_AN
    he_i = L_HEEL if side == "L" else R_HEEL
    bt_i = L_BTOE if side == "L" else R_BTOE
    st_i = L_STOE if side == "L" else R_STOE
    row[kn_i] = knee
    row[an_i] = ankle
    row[he_i] = heel
    row[bt_i] = big
    row[st_i] = small


def _point_flex(hip, knee, ankle) -> float:
    v1 = np.asarray(hip, float) - np.asarray(knee, float)
    v2 = np.asarray(ankle, float) - np.asarray(knee, float)
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom < 1e-8:
        return 0.0
    c = float(np.dot(v1, v2) / denom)
    return 180.0 - math.degrees(math.acos(min(1.0, max(-1.0, c))))


def _knee_reach(body: Body, knee_flex_deg: float) -> float:
    kf = math.radians(max(knee_flex_deg, 0.0))
    return math.sqrt(body.thigh ** 2 + body.shank ** 2 + 2.0 * body.thigh * body.shank * math.cos(kf))


def _ankle_for_heel(planned, yaw, pitch, side, body: Body):
    """Ankle that puts the heel on `planned` at this foot pitch."""
    heel0, ankle0, _big, _small = _foot_from_ankle(np.zeros(3), yaw, pitch, side, body)
    return np.asarray(planned, float) - (heel0 - ankle0)


def _approach(row, hip_i, target, distance, stance_sides, body: Body, yaw: float) -> bool:
    """Move the trunk so this hip is about `distance` mm from `target`."""
    for _ in range(24):
        hip = row[hip_i]
        gap = np.asarray(target, float) - hip
        dist = float(np.linalg.norm(gap))
        if dist <= distance + 1.0:
            return True
        step = min(12.0, dist - distance)
        delta = gap / dist * step
        if _try_shift(row, delta, stance_sides, body, yaw):
            continue
        if not _try_shift(row, delta * 0.35, stance_sides, body, yaw):
            return False
    return False


def _aim_foot(hip, planned, knee_flex, pitch, yaw, side, body: Body):
    """Hip and knee angles whose heel lands nearest `planned`.

    Prefer about 27 degrees of hip flexion when several poses land inside 5 mm.
    """
    best = None

    def consider(hf, ab):
        nonlocal best
        knee, ankle, heel, big, small = _swing_chain(hip, yaw, side, hf, knee_flex, ab, pitch, body)
        err = float(np.linalg.norm(heel - planned))
        if float(heel[2]) < -1.0:
            err += 500.0
        score = err + 0.3 * abs(hf - 27.0) + 0.05 * abs(ab) if err < 5.0 else 100.0 + err
        if best is None or score < best[0]:
            best = (score, err, hf, ab, knee, ankle, heel, big, small)

    for hf in range(0, 56, 4):
        for ab in range(-12, 13, 6):
            consider(float(hf), float(ab))
    _score, _err, hf0, ab0, *_rest = best
    for hf in np.linspace(hf0 - 2.0, hf0 + 2.0, 5):
        for ab in np.linspace(ab0 - 3.0, ab0 + 3.0, 5):
            consider(float(hf), float(ab))
    return best[1:]


def _lift_double_support(row, body: Body, yaw: float, person: Person | None = None):
    """Stand the pelvis up when both feet are down and a knee has folded."""
    cap_l = cap_r = 55.0
    if person is not None and person.reduced_knee_flexion_deg > 0:
        if person.reduced_knee_side == "L":
            cap_l = 36.0
        elif person.reduced_knee_side == "R":
            cap_r = 36.0
    for _ in range(8):
        flex_l = _point_flex(row[L_HIP], row[L_KN], row[L_AN])
        flex_r = _point_flex(row[R_HIP], row[R_KN], row[R_AN])
        if flex_l <= cap_l and flex_r <= cap_r:
            return
        pull = 0.5 * (
            (row[L_AN, :2] - row[L_HIP, :2]) + (row[R_AN, :2] - row[R_HIP, :2])
        )
        if float(np.linalg.norm(pull)) > 3.0:
            if not _try_shift(row, np.array([pull[0] * 0.5, pull[1] * 0.5, 0.0]), ("L", "R"), body, yaw):
                pull = np.zeros(2)
        z_cap = 1.0e9
        for hip_i, an_i in ((L_HIP, L_AN), (R_HIP, R_AN)):
            horiz = math.hypot(float(row[hip_i, 0] - row[an_i, 0]), float(row[hip_i, 1] - row[an_i, 1]))
            max_h = body.leg - 4.0
            if horiz >= max_h:
                return
            room = math.sqrt(max_h * max_h - horiz * horiz)
            z_cap = min(z_cap, float(row[an_i, 2]) + room)
        lift = z_cap - float(row[L_HIP, 2]) - 2.0
        if lift > 2.0:
            if not _try_shift(row, np.array([0.0, 0.0, lift]), ("L", "R"), body, yaw):
                return
        elif float(np.linalg.norm(pull)) <= 3.0:
            return


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
        jobs = []
        px, _along_y = _interp(frame / FPS, keys)
        wave = 15.0 * math.sin(2.0 * math.pi * frame / stride_frames)
        sway = 20.0 * math.sin(2.0 * math.pi * frame / max(stride_frames / 2.0, 1))
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
                # Stand-in foot under the hip so the two-link solve can reach.
                # The swing leg is replaced from hip and knee angles below.
                fwd, lat = _fwd_lat(yaw)
                sign = 1.0 if side == "L" else -1.0
                under = np.array([px, sway + sign * body.hip_w / 2.0, 0.0])
                toe = under + fwd * body.foot
                pitch = 0.0
            else:
                toe = np.array(planted, float)
                pitch = _pitch_for(step, frame, body, False, person, side, 0.0)[0]
                if pitch < 0.0 and not step["toe_walk"]:
                    # Rotate about the toe. Raise the toe so the heel stays on the floor.
                    toe[2] = -math.sin(pitch) * body.foot
                swing = False
            toes[side] = toe
            pitches[side] = pitch
            if swing:
                jobs.append(side)

        px, _along_y = _interp(frame / FPS, keys)
        base_z = body.ankle_h + body.leg * math.cos(math.radians(8))
        pelvis = np.array([px, sway, base_z + wave])
        phase = 2.0 * math.pi * frame / stride_frames
        amp = 0.45 * person.arm_swing_scale
        swings = (-amp * math.sin(phase), amp * math.sin(phase))
        bends = (0.35, 0.35)
        row = skeleton(toes["L"], toes["R"], pitches["L"], pitches["R"], pelvis, yaw, swings, bends, body)
        stance_sides = tuple(side for side in ("L", "R") if side not in jobs)
        for _raise in range(5):
            raised = False
            for side in stance_sides:
                hip_i = L_HIP if side == "L" else R_HIP
                kn_i = L_KN if side == "L" else R_KN
                an_i = L_AN if side == "L" else R_AN
                cap = 36.0 if person.reduced_knee_flexion_deg > 0 and side == person.reduced_knee_side else 55.0
                if _point_flex(row[hip_i], row[kn_i], row[an_i]) > cap:
                    if _try_shift(row, np.array([0.0, 0.0, 8.0]), stance_sides, body, yaw):
                        raised = True
            if not raised:
                break
        posed = {}
        for side in jobs:
            step = covering(frame, side)
            nxt = next(item for item in steps if item["side"] == side and item["hs"] == step["next_hs_frame"])
            span = max(step["next_hs_frame"] - step["hs"], 1)
            g = (frame - step["hs"]) / span
            stance_frac = (step["to"] - step["hs"]) / span
            reduced = person.reduced_knee_flexion_deg > 0 and side == person.reduced_knee_side
            peak = 60.0 - (person.reduced_knee_flexion_deg if reduced else 0.0)
            knee_flex, hip_flex, abduct_u, u = _swing_curve(g, stance_frac, peak)
            abduct = (28.0 if reduced else 0.0) * abduct_u
            last = frame + 1 == step["next_hs_frame"]
            if step["toe_walk"]:
                pitch = math.asin(min(35.0, body.foot * 0.22) / body.foot)
            elif last:
                pitch = -0.12
            else:
                pitch = 0.18 * (1.0 - u)
            fwd, _lat = _fwd_lat(yaw)
            dest_toe = np.array(_heel_pose(nxt, yaw, origin, body), float)
            if last and not step["toe_walk"]:
                dest_toe[2] = -math.sin(pitch) * body.foot
            if step["toe_walk"] or (last and pitch < 0.0):
                planned = foot_points(dest_toe, yaw, pitch, side, body)[0]
            else:
                planned = dest_toe - fwd * body.foot
                planned[2] = 0.0
            hip_i = L_HIP if side == "L" else R_HIP
            if stance_sides:
                st0 = stance_sides[0]
                sai = L_AN if st0 == "L" else R_AN
                shi = L_HIP if st0 == "L" else R_HIP
                ahead = float(np.dot(row[shi] - row[sai], fwd))
                if ahead > 450.0:
                    _try_shift(row, fwd * (450.0 - ahead), stance_sides, body, yaw)
                    horiz = math.hypot(
                        float(row[shi, 0] - row[sai, 0]),
                        float(row[shi, 1] - row[sai, 1]),
                    )
                    max_h = body.leg - 6.0
                    if horiz < max_h:
                        room = math.sqrt(max_h * max_h - horiz * horiz)
                        lift = float(row[sai, 2]) + room - float(row[shi, 2]) - 4.0
                        if lift > 4.0:
                            _try_shift(row, np.array([0.0, 0.0, lift]), stance_sides, body, yaw)
            if last:
                target_ankle = _ankle_for_heel(planned, yaw, pitch, side, body)
                reach = _knee_reach(body, knee_flex) - 2.0
                if stance_sides:
                    st = stance_sides[0]
                    sai = L_AN if st == "L" else R_AN
                    stance_ank = row[sai]
                else:
                    stance_ank = target_ankle
                ahead = float(np.dot(target_ankle - stance_ank, fwd))
                half = min(max(ahead * 0.5, 30.0), reach * 0.62)
                hf_rad = math.asin(half / reach)
                desired = np.array(target_ankle - fwd * (reach * math.sin(hf_rad)), float)
                desired[1] = float(row[hip_i, 1])
                desired[2] = float(target_ankle[2]) + reach * math.cos(hf_rad)
                hop = desired - row[hip_i]
                for scale in (1.0, 0.8, 0.55, 0.3):
                    if _try_shift(row, hop * scale, stance_sides, body, yaw):
                        break
                hip = row[hip_i].copy()
                _err, hf, ab, knee, ankle, heel, big, small = _aim_foot(
                    hip, planned, knee_flex, pitch, yaw, side, body
                )
                nudge = np.asarray(planned, float) - heel
                if float(np.linalg.norm(nudge)) > 0.8:
                    for scale in (1.0, 0.7, 0.4):
                        if _try_shift(row, nudge * scale, stance_sides, body, yaw):
                            hip = row[hip_i].copy()
                            knee, ankle, heel, big, small = _swing_chain(
                                hip, yaw, side, hf, knee_flex, ab, pitch, body
                            )
                            break
            else:
                if reduced:
                    _try_shift(row, np.array([0.0, 0.0, 18.0]), stance_sides, body, yaw)
                hip = row[hip_i].copy()
                knee = ankle = heel = big = small = None
                for _lift in range(14):
                    knee, ankle, heel, big, small = _swing_chain(
                        hip, yaw, side, hip_flex, knee_flex, abduct, pitch, body
                    )
                    toe_z = min(float(big[2]), float(small[2]))
                    heel_z = float(heel[2])
                    if toe_z >= 5.0 and heel_z >= 12.0:
                        break
                    if heel_z < 12.0:
                        if not _try_shift(row, np.array([0.0, 0.0, max(8.0, 12.0 - heel_z)]), stance_sides, body, yaw):
                            hip_flex += 3.0
                        else:
                            hip = row[hip_i].copy()
                    else:
                        hip_flex += 3.0
                if float(heel[2]) < 12.0 or min(float(big[2]), float(small[2])) < 5.0:
                    best_z = min(float(heel[2]), float(big[2]), float(small[2]))
                    best_pose = (knee, ankle, heel, big, small)
                    best_hf = hip_flex
                    forward_now = float(np.dot(heel, fwd))
                    for trial in range(-15, 85, 5):
                        tk, ta, th, tb, ts = _swing_chain(
                            hip, yaw, side, float(trial), knee_flex, abduct, pitch, body
                        )
                        if float(np.dot(th, fwd)) < forward_now - 40.0:
                            continue
                        if float(np.dot(th - np.asarray(planned, float), fwd)) > 70.0:
                            continue
                        z = min(float(th[2]), float(tb[2]), float(ts[2]))
                        if z > best_z:
                            best_z = z
                            best_hf = float(trial)
                            best_pose = (tk, ta, th, tb, ts)
                    hip_flex = best_hf
                    knee, ankle, heel, big, small = best_pose
                for _clear in range(4):
                    if min(float(heel[2]), float(big[2]), float(small[2])) >= 12.0:
                        break
                    if not _try_shift(row, np.array([0.0, 0.0, 8.0]), stance_sides, body, yaw):
                        break
                    hip = row[hip_i].copy()
                    knee, ankle, heel, big, small = _swing_chain(
                        hip, yaw, side, hip_flex, knee_flex, abduct, pitch, body
                    )
                while (
                    not reduced
                    and min(float(heel[2]), float(big[2]), float(small[2])) < 12.0
                    and knee_flex < peak - 0.5
                ):
                    knee_flex += 4.0
                    knee, ankle, heel, big, small = _swing_chain(
                        hip, yaw, side, hip_flex, knee_flex, abduct, pitch, body
                    )
                if u > 0.35:
                    gap = float(np.dot(np.asarray(planned, float) - heel, fwd))
                    if gap > 30.0:
                        step = min(36.0, gap * 0.2)
                        if not _try_shift(row, fwd * step, stance_sides, body, yaw):
                            step *= 0.5
                            _try_shift(row, fwd * step, stance_sides, body, yaw)
                        hip = row[hip_i].copy()
                        knee, ankle, heel, big, small = _swing_chain(
                            hip, yaw, side, hip_flex, knee_flex, abduct, pitch, body
                        )
                pulled = 0.0
                for _pullback in range(4):
                    over = float(np.dot(heel - np.asarray(planned, float), fwd))
                    if over <= 40.0 or pulled >= 8.0:
                        break
                    hip_flex -= 2.0
                    pulled += 2.0
                    knee, ankle, heel, big, small = _swing_chain(
                        hip, yaw, side, hip_flex, knee_flex, abduct, pitch, body
                    )
            if not last:
                low = min(float(heel[2]), float(big[2]), float(small[2]))
                if low < 12.0:
                    best_z = low
                    best_pose = (knee, ankle, heel, big, small)
                    best_hf = hip_flex
                    for trial in range(-20, 80, 4):
                        tk, ta, th, tb, ts = _swing_chain(
                            hip, yaw, side, float(trial), knee_flex, abduct, pitch, body
                        )
                        z = min(float(th[2]), float(tb[2]), float(ts[2]))
                        if z > best_z:
                            best_z = z
                            best_hf = float(trial)
                            best_pose = (tk, ta, th, tb, ts)
                    hip_flex = best_hf
                    knee, ankle, heel, big, small = best_pose
            posed[side] = (hf if last else hip_flex, knee_flex, ab if last else abduct, pitch)
            _write_leg(row, side, knee, ankle, heel, big, small)
        for side, (use_hf, use_knee, use_ab, use_pitch) in posed.items():
            hip_i = L_HIP if side == "L" else R_HIP
            kn_i = L_KN if side == "L" else R_KN
            an_i = L_AN if side == "L" else R_AN
            if abs(float(np.linalg.norm(row[hip_i] - row[kn_i])) - body.thigh) <= 1.5:
                continue
            fwd_now, _lat_now = _fwd_lat(yaw)
            try:
                row[kn_i] = knee_position(row[hip_i], row[an_i], body, fwd_now)
            except RuntimeError:
                knee, ankle, heel, big, small = _swing_chain(
                    row[hip_i], yaw, side, use_hf, use_knee, use_ab, use_pitch, body
                )
                _write_leg(row, side, knee, ankle, heel, big, small)
        if not jobs:
            _lift_double_support(row, body, yaw, person)
        kp[frame] = row

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
        heel = origin + lat * (sign * body.foot_off)
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
        kp[i] = skeleton(toes["L"], toes["R"], 0.0, 0.0, pelvis, 0.0, (0.9, 0.9), (1.15, 1.15), body, crossed=True)
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
    pelvis_y = stance_sign * body.foot_off
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


def _knee_flex_deg(hip, knee, ankle):
    """180 minus the hip-knee-ankle angle, in degrees. One frame or a stack."""
    hip = np.asarray(hip, float)
    knee = np.asarray(knee, float)
    ankle = np.asarray(ankle, float)
    v1 = hip - knee
    v2 = ankle - knee
    if v1.ndim == 1:
        c = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        return 180.0 - math.degrees(math.acos(min(1.0, max(-1.0, c))))
    c = np.sum(v1 * v2, axis=1) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1))
    return 180.0 - np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def plot_knee(npz_path, png_path, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = np.load(npz_path, allow_pickle=False)
    kp = data["kp"]
    fps = float(data["fps"])
    time = np.arange(len(kp)) / fps
    left = _knee_flex_deg(kp[:, L_HIP], kp[:, L_KN], kp[:, L_AN])
    right = _knee_flex_deg(kp[:, R_HIP], kp[:, R_KN], kp[:, R_AN])
    fig, ax = plt.subplots(figsize=(8.0, 3.2))
    ax.plot(time, left, label="L knee", color="#3b5a7a", linewidth=1.0)
    ax.plot(time, right, label="R knee", color="#c8352b", linewidth=1.0)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Knee flexion (deg)")
    ax.set_title(f"{title} knee flexion, synthetic")
    ax.legend(loc="upper right", fontsize=8)
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
