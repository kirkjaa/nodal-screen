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
        # Speed up over the first 2 m and slow down over the last 2 m gradually
        # (step time 1.6x at the ends, 1.0x in the timing zone).
        if slow and x < 2.0:
            scale = 1.0 + 0.6 * (1.0 - x / 2.0)
        elif slow:
            scale = 1.0 + 0.6 * min((x - (distance_m - 2.0)) / 2.0, 1.0)
        else:
            scale = 1.0
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
    if person.age_y < 13:
        # Rough demo value: children spend less of the cycle in double support
        # (about 16 to 18 % in Voss 2020, Table 2), so stance is shorter.
        stance_frac = 0.585
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


# ---------------------------------------------------------------------------
# Walking
#
# One planned motion, no corrections afterwards:
#   * the pelvis moves forward smoothly through the footstep plan; its height is
#     planned so it is lowest at each heel strike (landing leg nearly straight)
#     and highest at mid-stance;
#   * a stance foot rolls over the heel, lies flat, then rises on the toe;
#   * a swing ankle follows a planned forward path. A knee angle k fixes the
#     hip-to-ankle distance R(k), so the ankle sits on the circle of radius R(k)
#     around the hip; the knee follows its own curve (stance value at toe-off,
#     peak at 30 % of the swing, near straight at landing). The swing therefore
#     ends exactly on the next footfall.
# Angles and shares below are rough demo values chosen to look like ordinary
# walking. They are not transcribed norms.

PITCH_LAND = math.radians(-14.0)   # toes up at heel strike
PITCH_OFF = math.radians(22.0)     # foot pitch at toe-off (heel raised); less on a stiff-knee side
TOE_WALK_RISE = 40.0               # heel height (mm) held through a toe-walking stance
KNEE_LAND = 6.0                    # knee flexion at heel strike, deg
KNEE_MID = 10.0                    # stance knee used for the mid-stance pelvis height, deg
KNEE_PEAK = 60.0                   # swing peak, deg
PEAK_AT = 0.30                     # share of the swing at which the knee peaks
FOOT_FLAT = 0.17                   # share of stance spent rolling over the heel
HEEL_OFF = 0.55                    # share of stance at which the heel starts to rise
CLEARANCE = 12.0                   # mm, lowest foot point above the floor in mid-swing
HS_LAG = 0.60                      # pelvis behind the landing ankle at heel strike, share of the step
SWING_LEVEL_AT = 0.60             # share of the swing by which the foot reaches its landing pitch


def _reach(body: Body, knee_deg: float) -> float:
    """Hip-to-ankle distance for a knee flexion angle."""
    k = math.radians(knee_deg)
    return math.sqrt(body.thigh ** 2 + body.shank ** 2 + 2.0 * body.thigh * body.shank * math.cos(k))


def _knee_for(body: Body, dist: float) -> float:
    c = (dist * dist - body.thigh ** 2 - body.shank ** 2) / (2.0 * body.thigh * body.shank)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def _ease(w: float) -> float:
    w = min(max(w, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * w)


def _hermite(p0: float, m0: float, p1: float, m1: float, w: float) -> float:
    w2, w3 = w * w, w * w * w
    return (2 * w3 - 3 * w2 + 1) * p0 + (w3 - 2 * w2 + w) * m0 + (-2 * w3 + 3 * w2) * p1 + (w3 - w2) * m1


def _pchip(xs, ys):
    """Monotone cubic through (xs, ys); holds the end values outside the range."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    n = len(xs)
    if n == 1:
        return lambda x: np.full_like(np.asarray(x, float), ys[0])
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros(n)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        x = np.clip(np.asarray(x, float), xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, x, side="right") - 1, 0, n - 2)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
                + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


_GRID = np.linspace(0.0, 1.0, 2001)
_PROG = np.concatenate([[0.0], np.cumsum(np.sqrt(np.sin(np.pi * 0.5 * (_GRID[1:] + _GRID[:-1]))) * np.diff(_GRID))])
_PROG /= _PROG[-1]


def _progress(s: float) -> float:
    """Forward progress of the swing ankle: speed ~ sqrt(sin(pi*s)), steep at both ends."""
    return float(np.interp(s, _GRID, _PROG))


def _toe_from_ankle(ankle, yaw: float, pitch: float, body: Body):
    fwd, _ = _fwd_lat(yaw)
    x2, z2 = _pitch_xz(body.foot - body.heel_to_ankle, body.ankle_h, pitch)
    return np.asarray(ankle, float) - fwd * x2 - np.array([0.0, 0.0, z2])


def _toe_from_heel(heel, yaw: float, pitch: float, body: Body):
    fwd, _ = _fwd_lat(yaw)
    return np.asarray(heel, float) + fwd * (body.foot * math.cos(pitch)) - np.array([0.0, 0.0, body.foot * math.sin(pitch)])


def _stance_foot(step, u: float, yaw: float, origin, body: Body):
    """Toe and pitch of a planted foot at stance progress u (0 heel strike, 1 last stance frame)."""
    heel0 = _heel_pose(step, yaw, origin, body) - _fwd_lat(yaw)[0] * body.foot   # planned heel on the floor
    toe0 = heel0 + _fwd_lat(yaw)[0] * body.foot
    off = step.get("pitch_off", PITCH_OFF)
    if step["toe_walk"]:
        tw = math.asin(TOE_WALK_RISE / body.foot)
        if u <= HEEL_OFF:
            return toe0, tw
        w = (u - HEEL_OFF) / (1.0 - HEEL_OFF)
        return toe0, tw + (max(off, tw) - tw) * w * w
    if u < FOOT_FLAT:
        pitch = PITCH_LAND * (1.0 - _ease(u / FOOT_FLAT))
        return _toe_from_heel(heel0, yaw, pitch, body), pitch
    if u <= HEEL_OFF:
        return toe0, 0.0
    w = (u - HEEL_OFF) / (1.0 - HEEL_OFF)
    return toe0, off * w * w



def _assemble(pelvis, yaw, body: Body, legs, swings, bends):
    """Build the 23-point row from the pelvis and each leg's (ankle, toe, pitch)."""
    fwd, lat = _fwd_lat(yaw)
    hip_l, hip_r = _hips(pelvis, yaw, body)
    feet = {}
    for side, hip in (("L", hip_l), ("R", hip_r)):
        toe, pitch = legs[side]
        heel, ank, big, small = foot_points(toe, yaw, pitch, side, body)
        knee = knee_position(hip, ank, body, fwd)
        feet[side] = (knee, ank, heel, big, small)
    mid = (hip_l + hip_r) / 2.0
    trunk_top = mid + np.array([0.0, 0.0, body.trunk]) + fwd * (0.04 * body.trunk)
    sh_l = trunk_top + lat * (body.shoulder_w / 2.0)
    sh_r = trunk_top - lat * (body.shoulder_w / 2.0)
    el_l, wr_l = _arm(sh_l, yaw, swings[0], bends[0], body, "L")
    el_r, wr_r = _arm(sh_r, yaw, swings[1], bends[1], body, "R")
    nose, eye_l, eye_r, ear_l, ear_r = _head(trunk_top, yaw, body)
    row = np.zeros((23, 3))
    kl, al, hl, bl, sl = feet["L"]
    kr, ar, hr, br, sr = feet["R"]
    for idx, point in (
        (NOSE, nose), (L_EYE, eye_l), (R_EYE, eye_r), (L_EAR, ear_l), (R_EAR, ear_r),
        (L_SH, sh_l), (R_SH, sh_r), (L_EL, el_l), (R_EL, el_r), (L_WR, wr_l), (R_WR, wr_r),
        (L_HIP, hip_l), (R_HIP, hip_r), (L_KN, kl), (R_KN, kr), (L_AN, al), (R_AN, ar),
        (L_BTOE, bl), (L_STOE, sl), (L_HEEL, hl), (R_BTOE, br), (R_STOE, sr), (R_HEEL, hr),
    ):
        row[idx] = point
    return row


def _render_gait(person: Person, distance_m: float, zone: bool, yaw: float, origin, n_frames: int | None, duration_s: float | None, task: str, start_standing: bool = False):
    body = Body.from_height(person.height_m)
    steps, lengths, times, stride_t = _schedule(person, distance_m, zone)
    real = [st for st in steps if not st.get("phantom")]
    if len(real) >= 3:
        # Closing step: the last foot lands beside the other one, so the walk ends standing.
        real[-1]["along_m"] = real[-2]["along_m"]
        real[-1]["length_m"] = 0.0
    if person.reduced_knee_flexion_deg > 0:
        for st in steps:
            if st["side"] == person.reduced_knee_side:
                # A stiff knee also bends less before toe-off: less heel rise on that side.
                st["pitch_off"] = PITCH_OFF - math.radians(0.4 * person.reduced_knee_flexion_deg)
    ph = steps[0] if steps and steps[0].get("phantom") else None
    if ph is not None and len(real) >= 2:
        # The foot already down at the start belongs to a step as slow as the first one.
        same = next((st for st in real if st["side"] == ph["side"]), None)
        first = real[0]
        if same is not None and first.get("next_hs") is not None:
            frac = (first["to_time"] - first["hs_time"]) / (first["next_hs"] - first["hs_time"])
            ph["time_s"] = first["time_s"]
            ph["hs_time"] = -first["time_s"]
            ph["to_time"] = ph["hs_time"] + frac * (same["hs_time"] - ph["hs_time"])
    if duration_s is not None:
        _scale_schedule(steps, duration_s)
    if start_standing and ph is not None and len(real) >= 3:
        # Start from standing, feet side by side: the trailing foot leaves first
        # and lands one step ahead; the other foot is already flat.
        first = real[0]
        same = next(st for st in real if st["side"] == ph["side"])
        after = next((st for st in real[1:] if st["side"] == first["side"]), None)
        step_t = same["hs_time"]
        ph["along_m"] = first["along_m"]
        ph["to_time"] = max(step_t * 0.2, 0.05)
        # Flat at t = 0, heel rising from there (stance progress HEEL_OFF at frame 0).
        ph["hs_time"] = -(HEEL_OFF / (1.0 - HEEL_OFF)) * (ph["to_time"] - 1.0 / FPS)
        first["hs_time"] = -0.5
        if after is not None:
            first["to_time"] = after["hs_time"] - 0.8 * step_t
    finite_to = [step["to_time"] for step in steps if step["to_time"] < step["hs_time"] + 1000]
    end_t = max(finite_to + [step["hs_time"] for step in steps]) + 0.05
    if n_frames is None:
        n_frames = int(round(end_t * FPS)) + 1
    _frames(steps, n_frames)
    origin = np.asarray(origin, float)
    fwd, lat = _fwd_lat(yaw)
    up = np.array([0.0, 0.0, 1.0])
    along = lambda p: float(np.dot(np.asarray(p, float) - origin, fwd))
    across = lambda p: float(np.dot(np.asarray(p, float) - origin, lat))

    by_side = {s: sorted([st for st in steps if st["side"] == s], key=lambda st: st["hs"]) for s in "LR"}
    for s in "LR":
        for a, b in zip(by_side[s], by_side[s][1:]):
            a["next"] = b
        by_side[s][-1]["next"] = None
    finite = [st["to"] - st["hs"] for st in steps if st["next"] is not None]
    nominal = int(np.median(finite)) if finite else 30

    def n_stance(step):
        return max((step["to"] - 1 - step["hs"]) if step["next"] is not None else nominal, 1)

    def stance_u(step, frame):
        u = (frame - step["hs"]) / n_stance(step)
        if step["next"] is None:
            u = min(u, HEEL_OFF)          # last footfall: the foot stays flat
        return u

    def ankle_of(toe, pitch):
        return foot_points(toe, yaw, pitch, "L", body)[1]

    def ankle_of_static(toe):
        return ankle_of(toe, 0.0)

    # Pelvis: over each stance ankle at mid-stance, sway toward the stance foot,
    # and at the end over both feet after the closing step.
    sway_amp = min(0.012 * body.H, 0.8 * body.foot_off)
    last = max(steps, key=lambda st: st["hs_time"])
    ordered = sorted(steps, key=lambda st: st["hs_time"])
    keys, sway = [], []
    for prev, st in zip([None] + ordered[:-1], ordered):
        toe0, _p = _stance_foot(st, 0.4, yaw, origin, body)
        a_ank = along(ankle_of_static(toe0))
        sign = 1.0 if st["side"] == "L" else -1.0
        if st is last:
            keys.append([st["hs_time"] + 0.35, a_ank])
            sway.append([st["hs_time"] + 0.35, 0.0])
            continue
        # At heel strike the pelvis trails the landing ankle by HS_LAG of the step.
        step_mm = st["length_m"] * 1000.0 if prev is None else a_ank - along(ankle_of_static(_stance_foot(prev, 0.4, yaw, origin, body)[0]))
        keys.append([st["hs_time"], a_ank - HS_LAG * step_mm])
        if st["to_time"] < st["hs_time"] + 1000:
            sway.append([(st["hs_time"] + st["to_time"]) / 2.0, sign * sway_amp])
    for seq in (keys, sway):
        seq.sort()
        for a, b in zip(seq, seq[1:]):
            if b[0] <= a[0]:
                b[0] = a[0] + 1e-4
    if start_standing:
        # Standing at t = 0 over both feet, then away.
        base = along(ankle_of_static(_stance_foot(steps[0], 0.4, yaw, origin, body)[0]))
        keys = [k for k in keys if k[0] > 0.05] + [[0.0, base]]
        sway = [k for k in sway if k[0] > 0.05] + [[0.0, 0.0]]
        keys.sort()
        sway.sort()
    a_of_t = _pchip([k[0] for k in keys], [k[1] for k in keys])
    l_of_t = _pchip([k[0] for k in sway], [k[1] for k in sway])
    frames_t = np.arange(n_frames) / FPS
    p_along = a_of_t(frames_t)
    p_lat = l_of_t(frames_t)

    def hip_xy(frame, side):
        sign = 1.0 if side == "L" else -1.0
        return p_along[frame], p_lat[frame] + sign * body.hip_w / 2.0

    # Pelvis height keys: lowest at heel strike, highest at mid-stance.
    z_keys = []
    for st in steps:
        hs = st["hs"]
        if st.get("phantom") or not (0 <= hs < n_frames):
            continue
        toe, pitch = _stance_foot(st, 0.0, yaw, origin, body)
        ank = ankle_of(toe, pitch)
        ha, hl = hip_xy(hs, st["side"])
        dh2 = (ha - along(ank)) ** 2 + (hl - across(ank)) ** 2
        z_keys.append((hs, float(ank[2]) + math.sqrt(max(_reach(body, KNEE_LAND) ** 2 - dh2, 1.0))))
        if st["next"] is None and st is not last:
            continue                      # second-to-last foot: no mid-stance of its own
        mid = hs + (n_stance(st) * 0.5 if st["next"] is not None else 0.35 * FPS)
        mid_f = int(round(min(mid, n_frames - 1)))
        toe, pitch = _stance_foot(st, 0.4, yaw, origin, body)
        ank = ankle_of(toe, pitch)
        ha, hl = hip_xy(mid_f, st["side"])
        dh2 = (ha - along(ank)) ** 2 + (hl - across(ank)) ** 2
        z_keys.append((mid, float(ank[2]) + math.sqrt(max(_reach(body, KNEE_MID) ** 2 - dh2, 1.0))))
    if start_standing:
        toe0, pitch0 = _stance_foot(steps[0], 0.4, yaw, origin, body)
        z_keys = [k for k in z_keys if k[0] > 3] + [(0.0, float(ankle_of(toe0, pitch0)[2]) + _reach(body, KNEE_MID))]
    z_keys.sort()
    z_of_f = _pchip([k[0] for k in z_keys], [k[1] for k in z_keys])
    p_z = z_of_f(np.arange(n_frames, dtype=float))

    def phase(frame, side):
        """('stance', step, u) or ('swing', step, None) for this side at this frame."""
        chosen = by_side[side][0]
        for st in by_side[side]:
            if st["hs"] <= frame:
                chosen = st
        if frame < chosen["to"] or chosen["next"] is None:
            return "stance", chosen, stance_u(chosen, frame)
        return "swing", chosen, None

    # Stance legs cap the pelvis height so the leg always reaches the planted ankle.
    max_d = body.leg - 3.0
    for frame in range(n_frames):
        for side in "LR":
            kind, st, u = phase(frame, side)
            if kind != "stance":
                continue
            toe, pitch = _stance_foot(st, u, yaw, origin, body)
            ank = ankle_of(toe, pitch)
            ha, hl = hip_xy(frame, side)
            dh2 = (ha - along(ank)) ** 2 + (hl - across(ank)) ** 2
            cap = float(ank[2]) + math.sqrt(max(max_d ** 2 - dh2, 1.0))
            p_z[frame] = min(p_z[frame], cap)
    # A cap may only lower the pelvis; let it sink into and rise out of a cap at a
    # limited rate so releasing a leg never makes the pelvis jump.
    rate = 10.0                   # mm per frame (0.6 m/s), above the plan's own slopes
    for i in range(1, n_frames):
        p_z[i] = min(p_z[i], p_z[i - 1] + rate)
    for i in range(n_frames - 2, -1, -1):
        p_z[i] = min(p_z[i], p_z[i + 1] + rate)

    def pelvis_at(frame):
        return origin + fwd * p_along[frame] + lat * p_lat[frame] + up * p_z[frame]

    def hip_at(frame, side):
        hl, hr = _hips(pelvis_at(frame), yaw, body)
        return hl if side == "L" else hr

    def knee_angle(hip, ank):
        return _knee_for(body, float(np.linalg.norm(np.asarray(ank) - np.asarray(hip))))

    reduced = person.reduced_knee_flexion_deg if person.reduced_knee_flexion_deg > 0 else 0.0

    def swing_pose(st, frame, side):
        f0, f1 = st["to"] - 1, st["next"]["hs"]
        n = max(f1 - f0, 2)
        s = (frame - f0) / n
        toe0, pitch0 = _stance_foot(st, 1.0, yaw, origin, body)
        ank0 = ankle_of(toe0, pitch0)
        toe1, pitch1 = _stance_foot(st["next"], 0.0, yaw, origin, body)
        ank1 = ankle_of(toe1, pitch1)
        k0 = knee_angle(hip_at(f0, side), ank0)
        k1 = knee_angle(hip_at(f1, side), ank1)
        # knee rate at the end of stance, per unit of swing progress
        if f0 - 1 >= st["hs"]:
            tprev, pprev = _stance_foot(st, stance_u(st, f0 - 1), yaw, origin, body)
            m0 = (k0 - knee_angle(hip_at(f0 - 1, side), ankle_of(tprev, pprev))) * n
        else:
            m0 = 0.0
        peak = KNEE_PEAK - (reduced if side == person.reduced_knee_side else 0.0)
        peak = max(peak, k0 + 5.0)
        m0 = min(max(m0, 0.0), 2.5 * (peak - k0) / PEAK_AT)
        if s <= PEAK_AT:
            k = _hermite(k0, m0 * PEAK_AT, peak, 0.0, s / PEAK_AT)
        else:
            # Still extending at contact (cosine quarter), so the heel keeps descending.
            k = k1 + (peak - k1) * math.cos(0.5 * math.pi * (s - PEAK_AT) / (1.0 - PEAK_AT))
        # The foot levels out by mid-swing (toes up for the landing), so the toe clears.
        w = min(s / SWING_LEVEL_AT, 1.0)
        pitch = pitch1 + (pitch0 - pitch1) * (1.0 - w) ** 1.7   # starts toes-up at once, levels smoothly
        a = along(ank0) + (along(ank1) - along(ank0)) * _progress(s)
        sign = 1.0 if side == "L" else -1.0
        circ = (0.02 * body.H if side == person.reduced_knee_side and reduced > 0 else 0.0) * math.sin(math.pi * s)
        l = across(ank0) + (across(ank1) - across(ank0)) * _ease(s) + sign * circ
        hip = hip_at(frame, side)
        da, dl = a - along(hip), l - across(hip)
        # Clearance guard: if the lowest foot point would come within CLEARANCE of
        # the floor in mid-swing, bend the knee just enough to hold it there.
        heel_p, ank_p, big_p, _s = foot_points(np.zeros(3), yaw, pitch, side, body)
        below = float(ank_p[2] - min(heel_p[2], big_p[2]))      # lowest point under the ankle
        need = below + CLEARANCE * min(1.0, s * n / 2.0, (1.0 - s) * n / 2.0)   # ramps over 2 frames
        top = float(hip[2]) - need
        k_min = _knee_for(body, math.sqrt(da * da + dl * dl + max(top, 1.0) ** 2))
        k = max(k, k_min)
        r = _reach(body, k)
        vert = math.sqrt(max(r * r - da * da - dl * dl, 1.0))
        ank = hip + fwd * da + lat * dl - up * vert
        return _toe_from_ankle(ank, yaw, pitch, body), pitch

    kp = np.zeros((n_frames, 23, 3))
    for frame in range(n_frames):
        legs = {}
        for side in "LR":
            kind, st, u = phase(frame, side)
            if kind == "stance":
                legs[side] = _stance_foot(st, u, yaw, origin, body)
            else:
                legs[side] = swing_pose(st, frame, side)
        pelvis = pelvis_at(frame)
        hip_l, hip_r = _hips(pelvis, yaw, body)
        thigh = {}
        for side, hip in (("L", hip_l), ("R", hip_r)):
            ank = foot_points(legs[side][0], yaw, legs[side][1], side, body)[1]
            d = ank - hip
            thigh[side] = math.atan2(float(np.dot(d, fwd)), float(-d[2]))
        scale = 0.5 * person.arm_swing_scale
        swings = (scale * thigh["R"], scale * thigh["L"])
        bends = (0.35 + 0.15 * max(swings[0], 0.0), 0.35 + 0.15 * max(swings[1], 0.0))
        kp[frame] = _assemble(pelvis, yaw, body, legs, swings, bends)

    events = {"left": [], "right": []}
    for step in steps:
        if step.get("phantom") and not (0 <= step["to"] < n_frames):
            continue
        name = "left" if step["side"] == "L" else "right"
        entry = {"toe_walk": bool(step["toe_walk"])}
        if not step.get("phantom") and 0 <= step["hs"] < n_frames:
            entry["hs"] = int(step["hs"])
            heel = _heel_pose(step, yaw, origin, body) - fwd * body.foot
            entry["heel_mm"] = [round(float(heel[0]), 1), round(float(heel[1]), 1)]
        if step["next"] is not None and 0 <= step["to"] < n_frames:
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
    out = _render_gait(person, 3.0, False, 0.0, np.zeros(3), counts[1], counts[1] / FPS, "walk10", start_standing=True)
    kp[cursor:cursor + counts[1]] = out["kp"][:counts[1]]
    _shift_events(events, out["truth"]["events"], cursor)
    cursor += counts[1]
    kp[cursor:cursor + counts[2]] = _turn_clip(kp[cursor - 1], counts[2], 0.0, math.pi, person)
    cursor += counts[2]
    # The walk back starts from the turned pose: its heels are the new origin.
    last = kp[cursor - 1]
    heel_xy = 0.5 * (last[L_HEEL, :2] + last[R_HEEL, :2])
    back_origin = np.array([float(heel_xy[0]), 0.0, 0.0])
    back = _render_gait(person, 3.0, False, math.pi, back_origin, counts[3], counts[3] / FPS, "walk10", start_standing=True)
    kp[cursor:cursor + counts[3]] = back["kp"][:counts[3]]
    _shift_events(events, back["truth"]["events"], cursor)
    cursor += counts[3]
    kp[cursor:cursor + counts[4]] = _turn_clip(kp[cursor - 1], counts[4], math.pi, 2 * math.pi, person)
    cursor += counts[4]
    sit = _sit_stand_clip(person, counts[5], rising=False)
    shift = 0.5 * (kp[cursor - 1, L_HIP, :2] + kp[cursor - 1, R_HIP, :2]) - 0.5 * (sit["kp"][0, L_HIP, :2] + sit["kp"][0, R_HIP, :2])
    sit_kp = sit["kp"].copy()
    sit_kp[:, :, :2] += shift
    kp[cursor:cursor + counts[5]] = sit_kp
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
        # Arms forward while seated, hanging once upright, so the walk takes over smoothly.
        arm = (0.9 * (1.0 - w), 0.9 * (1.0 - w))
        bend = (1.15 * (1.0 - w) + 0.35 * w, 1.15 * (1.0 - w) + 0.35 * w)
        kp[i] = skeleton(toes["L"], toes["R"], 0.0, 0.0, pelvis, 0.0, arm, bend, body)
    return {"kp": kp}


def _turn_clip(last_row, n: int, yaw0: float, yaw1: float, person: Person):
    """Turn on the spot: the standing pose rotates about the pelvis' vertical axis."""
    centre = 0.5 * (last_row[L_HIP, :2] + last_row[R_HIP, :2])
    kp = np.zeros((n, 23, 3))
    for i in range(n):
        w = 0.5 - 0.5 * math.cos(math.pi * i / max(n - 1, 1))
        a = (yaw1 - yaw0) * w
        c, s_ = math.cos(a), math.sin(a)
        row = last_row.copy()
        dx = row[:, 0] - centre[0]
        dy = row[:, 1] - centre[1]
        row[:, 0] = centre[0] + c * dx - s_ * dy
        row[:, 1] = centre[1] + s_ * dx + c * dy
        kp[i] = row
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
