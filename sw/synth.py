"""A synthetic worker doing a kitting cycle, in the pipeline's own skeleton format.

The output is what sw.recon3d would produce for a real take: X of shape
(frames, 133, 3), world frame, metres, z up, COCO-WholeBody indices. It exists so
the rest of the pipeline (sw.ergo, sw.report_data, the report page) can be run
and shown end to end before real footage is recorded. Every number that comes
out of it is synthetic and is labelled so downstream.

The cycle: stand at the bench, reach forward to the tray, stoop to a bin at floor
level, stand, reach up to a shelf, stand. Posture is driven by a few parameters
per phase (trunk bend, arm raise, neck bend); the body is built from the upright
pose used in tests/test_ergo.py and rotated about the hips, shoulders and neck.
Small random variation is added per cycle so cycles differ, as real ones do.

    python -m sw.synth <out_dir> [--cycles 9] [--fps 30] [--seed 7]
"""

import argparse
import json
from pathlib import Path

import numpy as np

from sw import ergo

# Phases of one cycle: (name, seconds, trunk flexion deg, right arm flexion deg,
# left arm flexion deg, neck flexion deg). Arms are raised forward of the trunk.
PHASES = [
    ("stand", 1.6, 3, 22, 22, 10),
    ("reach tray", 1.4, 14, 55, 45, 24),
    ("hold tray", 1.2, 12, 50, 45, 26),
    ("stand", 1.4, 4, 22, 22, 10),
    ("stoop to bin", 1.2, 58, 45, 40, 8),
    ("lift from bin", 1.0, 50, 40, 38, 8),
    ("stand", 1.2, 5, 25, 24, 12),
    ("reach shelf", 1.0, -3, 98, 32, -6),
    ("place on shelf", 0.6, -2, 95, 32, -8),
    ("stand", 1.0, 3, 22, 22, 10),
]
CYCLE_S = sum(p[1] for p in PHASES)  # 11.6 s

# Other stations, same parameters per phase. "kitting" is PHASES above. Each is a
# plausible cycle for the station named, chosen so the reports differ in the way
# real ones would: packing is mostly waist-height work with one lift, assembly is
# a still trunk with the head down over the part, restock alternates overhead
# and low-shelf reaches.
PROFILES = {
    "kitting": PHASES,
    "packing": [
        ("stand", 1.2, 4, 24, 24, 12),
        ("reach carton", 1.0, 10, 48, 46, 22),
        ("pack", 2.4, 14, 42, 44, 30),
        ("tape", 1.2, 12, 40, 36, 28),
        ("lift to pallet", 1.0, 32, 52, 50, 10),
        ("place on pallet", 0.8, 38, 46, 44, 10),
        ("stand", 1.0, 4, 24, 24, 12),
    ],
    "assembly": [
        ("stand", 1.0, 6, 28, 28, 18),
        ("pick part", 0.8, 10, 40, 36, 30),
        ("fit", 2.6, 12, 38, 38, 36),
        ("inspect", 1.2, 8, 34, 34, 42),
        ("set aside", 0.8, 10, 36, 30, 24),
    ],
    "restock": [
        ("stand", 1.0, 4, 22, 22, 10),
        ("take from trolley", 1.0, 16, 44, 44, 20),
        ("reach high shelf", 1.2, -4, 110, 96, -10),
        ("place high", 0.8, -4, 105, 92, -12),
        ("stand", 0.8, 4, 24, 22, 8),
        ("take from trolley", 1.0, 16, 44, 44, 20),
        ("lower shelf", 1.2, 48, 40, 40, 14),
        ("place low", 0.8, 44, 38, 38, 14),
        ("stand", 1.0, 4, 22, 22, 10),
    ],
}
# wrist deviation per profile: (base deg, amplitude deg) over the cycle
WRIST = {"kitting": (8, 9), "packing": (10, 10), "assembly": (14, 12), "restock": (6, 8)}


def _rot_x(deg):
    a = np.radians(deg)
    return np.array([[1, 0, 0], [0, np.cos(a), np.sin(a)], [0, -np.sin(a), np.cos(a)]])


def upright():
    """Upright person facing +y: the test pose, one frame, 133 x 3."""
    X = np.full((133, 3), np.nan)
    p = {
        ergo.NOSE: (0, 0.10, 1.62), ergo.L_EAR: (-0.07, 0.0, 1.62), ergo.R_EAR: (0.07, 0.0, 1.62),
        ergo.L_EYE: (-0.03, 0.08, 1.65), ergo.R_EYE: (0.03, 0.08, 1.65),
        ergo.L_SH: (-0.20, 0, 1.45), ergo.R_SH: (0.20, 0, 1.45),
        ergo.L_HIP: (-0.10, 0, 0.95), ergo.R_HIP: (0.10, 0, 0.95),
        ergo.L_KN: (-0.10, 0, 0.50), ergo.R_KN: (0.10, 0, 0.50),
        ergo.L_AN: (-0.10, 0, 0.08), ergo.R_AN: (0.10, 0, 0.08),
    }
    for j, xyz in p.items():
        X[j] = xyz
    return X


def build_frame(trunk_deg, arm_r_deg, arm_l_deg, neck_deg, wrist_dev_deg=0.0):
    """One frame from the posture parameters. Arms hang from the shoulders and are
    raised forward by arm_*_deg relative to the trunk; elbows bent 80 degrees."""
    X = upright()
    hip = (X[ergo.L_HIP] + X[ergo.R_HIP]) / 2
    # arms in the upright trunk frame, then everything above the hips bends forward
    for sh, el, wr, hand, arm_deg in ((ergo.L_SH, ergo.L_EL, ergo.L_WR, ergo.L_HAND, arm_l_deg),
                                      (ergo.R_SH, ergo.R_EL, ergo.R_WR, ergo.R_HAND, arm_r_deg)):
        a = np.radians(arm_deg)
        upper = np.array([0, np.sin(a), -np.cos(a)]) * 0.30
        X[el] = X[sh] + upper
        b = np.radians(arm_deg + 80)  # forearm 80 degrees more flexed than the upper arm
        fore = np.array([0, np.sin(b), -np.cos(b)])
        X[wr] = X[el] + fore * 0.26
        w = X[wr]
        side = np.array([1.0, 0, 0]) if sh == ergo.R_SH else np.array([-1.0, 0, 0])
        dev = np.radians(wrist_dev_deg)
        m = fore * np.cos(dev) + side * np.sin(dev)
        X[hand["wrist"]] = w
        X[hand["middle"]] = w + 0.08 * m
        X[hand["index"]] = w + 0.08 * m + side * 0.02
        X[hand["pinky"]] = w + 0.07 * m - side * 0.02
    # neck: rotate the head about the shoulder midpoint
    mid_sh = (X[ergo.L_SH] + X[ergo.R_SH]) / 2
    for j in (ergo.NOSE, ergo.L_EAR, ergo.R_EAR, ergo.L_EYE, ergo.R_EYE):
        X[j] = (X[j] - mid_sh) @ _rot_x(neck_deg).T + mid_sh
    # trunk: rotate everything above the hips about the hip axis
    upper = [j for j in range(133) if not np.isnan(X[j, 0]) and j not in
             (ergo.L_HIP, ergo.R_HIP, ergo.L_KN, ergo.R_KN, ergo.L_AN, ergo.R_AN)]
    X[upper] = (X[upper] - hip) @ _rot_x(trunk_deg).T + hip
    # a slight knee bend when stooping, so the figure looks right and REBA legs can move
    if trunk_deg > 40:
        kb = (trunk_deg - 40) / 30 * 0.06
        X[[ergo.L_KN, ergo.R_KN], 1] += kb
        X[[ergo.L_KN, ergo.R_KN], 2] -= kb * 0.4
    return X


def cycle_params(t, rng, var, phases=PHASES):
    """Interpolated posture parameters at time t within a cycle, with per-cycle variation."""
    cycle_s = sum(p[1] for p in phases)
    t = t % cycle_s
    edges = np.cumsum([0] + [p[1] for p in phases])
    i = int(np.searchsorted(edges, t, side="right") - 1)
    i = min(i, len(phases) - 1)
    nxt = min(i + 1, len(phases) - 1)
    u = (t - edges[i]) / phases[i][1]
    u = u * u * (3 - 2 * u)  # smooth step between phases
    cur, after = np.array(phases[i][2:], float), np.array(phases[nxt][2:], float)
    return (cur + (after - cur) * u) * (1 + var)


def generate(cycles=9, fps=30, seed=7, profile="kitting"):
    phases = PROFILES[profile]
    cycle_s = sum(p[1] for p in phases)
    w_base, w_amp = WRIST[profile]
    rng = np.random.default_rng(seed)
    n = int(round(cycles * cycle_s * fps))
    X = np.full((n, 133, 3), np.nan)
    var = np.zeros(4)
    last_cycle = -1
    for f in range(n):
        t = f / fps
        c = int(t // cycle_s)
        if c != last_cycle:
            var = rng.normal(0, 0.06, 4)  # each cycle a little different
            last_cycle = c
        trunk, arm_r, arm_l, neck = cycle_params(t, rng, var, phases)
        X[f] = build_frame(trunk, arm_r, arm_l, neck, wrist_dev_deg=w_base + w_amp * np.sin(2 * np.pi * t / cycle_s))
    # measurement noise, a few millimetres, as triangulation gives; joints the model never places stay NaN
    placed = ~np.isnan(build_frame(0, 25, 25, 10)[:, 0])
    X[:, placed] += rng.normal(0, 0.004, (n, int(placed.sum()), 3))
    X[:, ~placed] = np.nan
    return X


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("--cycles", type=int, default=9)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="kitting", help="station cycle to simulate")
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    X = generate(a.cycles, a.fps, a.seed, a.profile)
    cycle_s = sum(p[1] for p in PROFILES[a.profile])
    np.savez_compressed(out / "skeleton3d.npz", X=X, fps=a.fps)
    meta = {"data_kind": "synthetic", "source": "sw.synth", "profile": a.profile, "cycles": a.cycles, "fps": a.fps,
            "seed": a.seed, "frames": int(X.shape[0]), "duration_s": round(X.shape[0] / a.fps, 1), "cycle_s": cycle_s,
            "note": "Synthetic worker: posture parameters per phase, not a recording. For pipeline testing and layout."}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {out / 'skeleton3d.npz'}: {a.profile}, {X.shape[0]} frames, {a.cycles} cycles, {meta['duration_s']} s")


if __name__ == "__main__":
    main()
