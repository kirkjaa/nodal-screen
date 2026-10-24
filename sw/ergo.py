"""Joint angles and RULA / REBA posture scores from the 3D skeleton.

Input is skeleton3d.npz from sw.recon3d: X (frames x 133 x 3), world frame,
metres, z up. Output is per-frame angles, the component scores and the final
RULA (1-7) and REBA (1-15) scores for each side.

Methods:
  RULA: McAtamney L, Corlett EN. RULA: a survey method for the investigation of
        work-related upper limb disorders. Applied Ergonomics 1993;24(2):91-99.
  REBA: Hignett S, McAtamney L. Rapid Entire Body Assessment (REBA).
        Applied Ergonomics 2000;31(2):201-205.
The lookup tables below are transcribed from those papers and must be checked
against the published worksheets before results are shown to anyone.

What video cannot see is a parameter, not a guess: the load or force on the
hands, the coupling (grip) quality, and wrist twist. Defaults are stated in
TaskInputs and shown in the report next to the scores.

Thresholds marked HEURISTIC (shoulder raised, abduction, twist, side bend, neck
twist) are judgement calls the methods leave to the observer; they are set
here as constants so they can be reviewed.
"""

from dataclasses import dataclass

import numpy as np

# COCO-WholeBody indices
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SH, R_SH, L_EL, R_EL, L_WR, R_WR = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_KN, R_KN, L_AN, R_AN = 11, 12, 13, 14, 15, 16
L_HAND = {"wrist": 91, "index": 96, "middle": 100, "pinky": 108}
R_HAND = {"wrist": 112, "index": 117, "middle": 121, "pinky": 129}

# HEURISTIC thresholds (degrees unless stated)
ABDUCTION_DEG = 30.0
TRUNK_TWIST_DEG = 20.0
TRUNK_SIDE_DEG = 10.0
NECK_TWIST_DEG = 20.0
NECK_SIDE_DEG = 10.0
WRIST_DEVIATION_DEG = 15.0
SHOULDER_RAISE_RATIO = 0.80   # ear-to-shoulder height below 80% of the take's median
NECK_EXTENSION_TOL = 5.0      # backward tilt smaller than this counts as level, not extension


@dataclass
class TaskInputs:
    """What the cameras cannot measure. Set per task or role."""
    load_kg: float = 1.0             # load handled; kitting parts are light
    shock_or_rapid_force: bool = False
    repeated_over_4_per_min: bool = True    # RULA muscle use / REBA activity
    static_over_1_min: bool = False
    coupling: int = 0                # REBA: 0 good, 1 fair, 2 poor, 3 unacceptable
    wrist_twist_end_range: bool = False      # RULA wrist twist; not visible on video
    arm_supported: bool = False


# ---------------------------------------------------------------- tables

RULA_A = np.array([  # [upper arm 1-6][lower arm 1-3][wrist 1-4][twist 1-2]
    [[[1, 2], [2, 2], [2, 3], [3, 3]], [[2, 2], [2, 2], [3, 3], [3, 3]], [[2, 3], [3, 3], [3, 3], [4, 4]]],
    [[[2, 3], [3, 3], [3, 3], [4, 4]], [[3, 3], [3, 3], [3, 4], [4, 4]], [[3, 4], [4, 4], [4, 4], [5, 5]]],
    [[[3, 3], [4, 4], [4, 4], [5, 5]], [[3, 4], [4, 4], [4, 4], [5, 5]], [[4, 4], [4, 4], [4, 5], [5, 5]]],
    [[[4, 4], [4, 4], [4, 5], [5, 5]], [[4, 4], [4, 4], [4, 5], [5, 5]], [[4, 4], [4, 5], [5, 5], [6, 6]]],
    [[[5, 5], [5, 5], [5, 6], [6, 7]], [[5, 6], [6, 6], [6, 7], [7, 7]], [[6, 6], [6, 7], [7, 7], [7, 8]]],
    [[[7, 7], [7, 7], [7, 8], [8, 9]], [[8, 8], [8, 8], [8, 9], [9, 9]], [[9, 9], [9, 9], [9, 9], [9, 9]]],
])
RULA_B = np.array([  # [neck 1-6][trunk 1-6][legs 1-2]
    [[1, 3], [2, 3], [3, 4], [5, 5], [6, 6], [7, 7]],
    [[2, 3], [2, 3], [4, 5], [5, 5], [6, 7], [7, 7]],
    [[3, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 7]],
    [[5, 5], [5, 6], [6, 7], [7, 7], [7, 7], [8, 8]],
    [[7, 7], [7, 7], [7, 8], [8, 8], [8, 8], [8, 8]],
    [[8, 8], [8, 8], [8, 8], [8, 9], [9, 9], [9, 9]],
])
RULA_C = np.array([  # [score A 1-8+][score B 1-7+]
    [1, 2, 3, 3, 4, 5, 5],
    [2, 2, 3, 4, 4, 5, 5],
    [3, 3, 3, 4, 4, 5, 6],
    [3, 3, 3, 4, 5, 6, 6],
    [4, 4, 4, 5, 6, 7, 7],
    [4, 4, 5, 6, 6, 7, 7],
    [5, 5, 6, 6, 7, 7, 7],
    [5, 5, 6, 7, 7, 7, 7],
])
REBA_A = np.array([  # [neck 1-3][trunk 1-5][legs 1-4]
    [[1, 2, 3, 4], [2, 3, 4, 5], [2, 4, 5, 6], [3, 5, 6, 7], [4, 6, 7, 8]],
    [[1, 2, 3, 4], [3, 4, 5, 6], [4, 5, 6, 7], [5, 6, 7, 8], [6, 7, 8, 9]],
    [[3, 3, 5, 6], [4, 5, 6, 7], [5, 6, 7, 8], [6, 7, 8, 9], [7, 8, 9, 9]],
])
REBA_B = np.array([  # [lower arm 1-2][upper arm 1-6][wrist 1-3]
    [[1, 2, 2], [1, 2, 3], [3, 4, 5], [4, 5, 5], [6, 7, 8], [7, 8, 8]],
    [[1, 2, 3], [2, 3, 4], [4, 5, 5], [5, 6, 7], [7, 8, 8], [8, 9, 9]],
])
REBA_C = np.array([  # [score A 1-12][score B 1-12]
    [1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 7, 7],
    [1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8],
    [2, 3, 3, 3, 4, 5, 6, 7, 7, 8, 8, 8],
    [3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9],
    [4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9, 9],
    [6, 6, 6, 7, 8, 8, 9, 9, 10, 10, 10, 10],
    [7, 7, 7, 8, 9, 9, 9, 10, 10, 11, 11, 11],
    [8, 8, 8, 9, 10, 10, 10, 10, 10, 11, 11, 11],
    [9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12],
    [10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12, 12],
    [11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12],
    [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12],
])

RULA_ACTION = {1: "acceptable", 2: "acceptable", 3: "investigate", 4: "investigate",
               5: "change soon", 6: "change soon", 7: "change now"}


def reba_risk(score):
    if score <= 1:
        return "negligible"
    if score <= 3:
        return "low"
    if score <= 7:
        return "medium"
    if score <= 10:
        return "high"
    return "very high"


# ---------------------------------------------------------------- vectors

def _unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return v / n


def _deg(y, x):
    return np.degrees(np.arctan2(y, x))


def _dot(a, b):
    return np.sum(a * b, axis=-1)


def body_frame(X):
    """Per-frame axes: up (world z), forward (pelvis facing), left (person's left)."""
    up = np.array([0.0, 0.0, 1.0])
    hips = X[:, L_HIP] - X[:, R_HIP]
    fwd = np.cross(hips, up)
    fwd[:, 2] = 0
    fwd = _unit(fwd)
    left = np.cross(up, fwd)
    return np.broadcast_to(up, fwd.shape), fwd, left


def angles(X):
    """All joint angles the scores need, per frame. Degrees."""
    up, fwd, left = body_frame(X)
    mid_hip = (X[:, L_HIP] + X[:, R_HIP]) / 2
    mid_sh = (X[:, L_SH] + X[:, R_SH]) / 2
    trunk = _unit(mid_sh - mid_hip)
    a = {}
    a["trunk_flexion"] = _deg(_dot(trunk, fwd), _dot(trunk, up))
    a["trunk_side_bend"] = np.abs(_deg(_dot(trunk, left), _dot(trunk, up)))
    sh_line = X[:, L_SH] - X[:, R_SH]
    hip_line = X[:, L_HIP] - X[:, R_HIP]
    sh_h, hip_h = sh_line.copy(), hip_line.copy()
    sh_h[:, 2] = 0
    hip_h[:, 2] = 0
    a["trunk_twist"] = np.degrees(np.arccos(np.clip(_dot(_unit(sh_h), _unit(hip_h)), -1, 1)))

    # Trunk-attached axes for the neck and arms.
    t_up = trunk
    t_fwd = _unit(fwd - _dot(fwd, t_up)[:, None] * t_up)
    t_left = np.cross(t_up, t_fwd)

    head = (X[:, L_EAR] + X[:, R_EAR]) / 2
    neck = _unit(head - mid_sh)
    a["neck_flexion"] = _deg(_dot(neck, t_fwd), _dot(neck, t_up))
    a["neck_side_bend"] = np.abs(_deg(_dot(neck, t_left), _dot(neck, t_up)))
    face = X[:, NOSE] - head
    face_h = face - _dot(face, t_up)[:, None] * t_up
    a["neck_twist"] = np.abs(_deg(_dot(_unit(face_h), t_left), _dot(_unit(face_h), t_fwd)))

    for side, sh, el, wr, hand, out in (("left", L_SH, L_EL, L_WR, L_HAND, 1.0),
                                        ("right", R_SH, R_EL, R_WR, R_HAND, -1.0)):
        upper = _unit(X[:, el] - X[:, sh])
        fore = _unit(X[:, wr] - X[:, el])
        down = -t_up
        a[f"{side}_upper_arm_flexion"] = _deg(_dot(upper, t_fwd), _dot(upper, down))
        a[f"{side}_upper_arm_abduction"] = _deg(out * _dot(upper, t_left), _dot(upper, down))
        a[f"{side}_elbow_flexion"] = np.degrees(np.arccos(np.clip(_dot(upper, fore), -1, 1)))
        lat = _dot(X[:, wr] - mid_sh, t_left) * out
        sh_lat = _dot(X[:, sh] - mid_sh, t_left) * out
        a[f"{side}_wrist_across_midline"] = lat < 0
        a[f"{side}_wrist_out_to_side"] = lat > sh_lat + 0.15
        m = _unit(X[:, hand["middle"]] - X[:, hand["wrist"]])
        palm = np.cross(X[:, hand["index"]] - X[:, hand["wrist"]],
                        X[:, hand["pinky"]] - X[:, hand["wrist"]])
        p = _unit(palm - _dot(palm, fore)[:, None] * fore)
        r = np.cross(fore, p)
        a[f"{side}_wrist_flexion"] = np.abs(_deg(_dot(m, p), _dot(m, fore)))
        a[f"{side}_wrist_deviation"] = np.abs(_deg(_dot(m, r), _dot(m, fore)))
        ear = L_EAR if side == "left" else R_EAR
        gap = X[:, ear, 2] - X[:, sh, 2]
        a[f"{side}_shoulder_raised"] = gap < SHOULDER_RAISE_RATIO * np.nanmedian(gap)

    for side, hip, kn, an in (("left", L_HIP, L_KN, L_AN), ("right", R_HIP, R_KN, R_AN)):
        th = _unit(X[:, kn] - X[:, hip])
        sh_ = _unit(X[:, an] - X[:, kn])
        a[f"{side}_knee_flexion"] = np.degrees(np.arccos(np.clip(_dot(th, sh_), -1, 1)))
    feet_z = X[:, [L_AN, R_AN], 2]
    a["one_foot_raised"] = np.abs(feet_z[:, 0] - feet_z[:, 1]) > 0.10
    return a


# ---------------------------------------------------------------- scoring

def _lookup(table, *idx):
    return table[tuple(np.asarray(i) - 1 for i in idx)]


def _upper_arm_score(flex, abducted, raised, supported):
    s = np.select([flex < -20, flex <= 20, flex <= 45, flex <= 90], [2, 1, 2, 3], 4)
    return np.clip(s + abducted + raised - int(supported), 1, 6)


def rula(a, side, task: TaskInputs):
    ua = _upper_arm_score(a[f"{side}_upper_arm_flexion"],
                          a[f"{side}_upper_arm_abduction"] > ABDUCTION_DEG,
                          a[f"{side}_shoulder_raised"], task.arm_supported)
    el = a[f"{side}_elbow_flexion"]
    la = np.where((el >= 60) & (el <= 100), 1, 2)
    la = np.clip(la + (a[f"{side}_wrist_across_midline"] | a[f"{side}_wrist_out_to_side"]), 1, 3)
    wf = a[f"{side}_wrist_flexion"]
    wr = np.select([wf < 5, wf <= 15], [1, 2], 3)
    wr = np.clip(wr + (a[f"{side}_wrist_deviation"] > WRIST_DEVIATION_DEG), 1, 4)
    tw = 2 if task.wrist_twist_end_range else 1
    sustained = task.repeated_over_4_per_min or task.static_over_1_min
    muscle = int(sustained)
    if task.shock_or_rapid_force:
        force = 3
    elif task.load_kg < 2:
        force = 0
    elif task.load_kg <= 10:
        force = 2 if sustained else 1
    else:
        force = 3 if sustained else 2
    score_a = _lookup(RULA_A, ua, la, wr, np.full_like(ua, tw)) + muscle + force

    nf = a["neck_flexion"]
    nk = np.select([nf < -NECK_EXTENSION_TOL, nf <= 10, nf <= 20], [4, 1, 2], 3)
    nk = np.clip(nk + (a["neck_twist"] > NECK_TWIST_DEG) + (a["neck_side_bend"] > NECK_SIDE_DEG), 1, 6)
    tf = np.abs(a["trunk_flexion"])
    tr = np.select([tf < 5, tf <= 20, tf <= 60], [1, 2, 3], 4)
    tr = np.clip(tr + (a["trunk_twist"] > TRUNK_TWIST_DEG) + (a["trunk_side_bend"] > TRUNK_SIDE_DEG), 1, 6)
    legs = np.where(a["one_foot_raised"], 2, 1)
    score_b = _lookup(RULA_B, nk, tr, legs) + muscle + force

    final = RULA_C[np.clip(score_a, 1, 8) - 1, np.clip(score_b, 1, 7) - 1]
    return {"upper_arm": ua, "lower_arm": la, "wrist": wr, "neck": nk, "trunk": tr,
            "legs": legs, "score_a": score_a, "score_b": score_b, "score": final}


def reba(a, side, task: TaskInputs):
    tf = a["trunk_flexion"]
    tr = np.select([np.abs(tf) < 5, np.abs(tf) <= 20, (tf <= 60) | (tf < -20)], [1, 2, 3], 4)
    tr = np.clip(tr + ((a["trunk_twist"] > TRUNK_TWIST_DEG) | (a["trunk_side_bend"] > TRUNK_SIDE_DEG)), 1, 5)
    nf = a["neck_flexion"]
    nk = np.where((nf >= -NECK_EXTENSION_TOL) & (nf <= 20), 1, 2)
    nk = np.clip(nk + ((a["neck_twist"] > NECK_TWIST_DEG) | (a["neck_side_bend"] > NECK_SIDE_DEG)), 1, 3)
    kf = np.maximum(a["left_knee_flexion"], a["right_knee_flexion"])
    legs = np.where(a["one_foot_raised"], 2, 1) + np.select([kf > 60, kf >= 30], [2, 1], 0)
    legs = np.clip(legs, 1, 4)
    load = 0 if task.load_kg < 5 else (1 if task.load_kg <= 10 else 2)
    load += int(task.shock_or_rapid_force)
    score_a = _lookup(REBA_A, nk, tr, legs) + load

    ua = _upper_arm_score(a[f"{side}_upper_arm_flexion"],
                          a[f"{side}_upper_arm_abduction"] > ABDUCTION_DEG,
                          a[f"{side}_shoulder_raised"], task.arm_supported)
    el = a[f"{side}_elbow_flexion"]
    la = np.where((el >= 60) & (el <= 100), 1, 2)
    wf = a[f"{side}_wrist_flexion"]
    wr = np.where(wf <= 15, 1, 2) + (a[f"{side}_wrist_deviation"] > WRIST_DEVIATION_DEG)
    wr = np.clip(wr, 1, 3)
    score_b = _lookup(REBA_B, la, ua, wr) + task.coupling

    c = REBA_C[np.clip(score_a, 1, 12) - 1, np.clip(score_b, 1, 12) - 1]
    activity = int(task.static_over_1_min) + int(task.repeated_over_4_per_min)
    final = c + activity
    return {"trunk": tr, "neck": nk, "legs": legs, "upper_arm": ua, "lower_arm": la,
            "wrist": wr, "score_a": score_a, "score_b": score_b, "score": final}


def score_take(X, task: TaskInputs = TaskInputs()):
    """Angles plus RULA and REBA for both sides; frames with missing joints are NaN."""
    a = angles(X)
    needed = [L_SH, R_SH, L_EL, R_EL, L_WR, R_WR, L_HIP, R_HIP, L_EAR, R_EAR, NOSE,
              L_HAND["middle"], R_HAND["middle"]]
    valid = ~np.isnan(X[:, needed, 0]).any(axis=1)
    out = {"valid": valid, "angles": a}
    for side in ("left", "right"):
        safe = {k: np.nan_to_num(v) if v.dtype.kind == "f" else v for k, v in a.items()}
        out[f"rula_{side}"] = rula(safe, side, task)
        out[f"reba_{side}"] = reba(safe, side, task)
    return out
