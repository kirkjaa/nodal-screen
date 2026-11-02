"""Build the report's data file from the pipeline's outputs.

Input: skeleton3d.npz (X: frames x 133 x 3, from sw.recon3d or sw.synth) and a
meta.json beside it (data_kind, fps, cameras, quality numbers when known).
Output: report-data.js, which sets window.REPORT_DATA for web/report.html, and
report-data.json with the same content.

What this file computes, and how:
- Cycles: a repetitive task shows up as a periodic trunk-flexion signal. The
  cycle length is the dominant period of that signal (autocorrelation, over 3 s
  to 60 s); cycle starts are the upright moments (local minima of trunk
  flexion) spaced about one period apart. Assumes the worker repeats one task.
- Time in RULA action level: share of valid frames at RULA 1-2 (acceptable),
  3-4 (investigate), 5-7 (change), per the RULA action levels.
- Findings: rules over the joint angles, each with its threshold from sw.ergo
  (trunk > 45 deg is RULA trunk score 3; upper arm > 90 is score 4; neck > 20
  is score 3; wrist deviation > WRIST_DEVIATION_DEG). A finding is raised when
  the share of the cycle, or the number of cycles, passes the stated minimum.
- Early warnings: (a) rising role, when the average RULA of this role over the
  last sessions rises by RISING_DELTA or more from first to last; (b) daily
  exposure, when hours at RULA 5 or above in the day pass EXPOSURE_LIMIT_H.
  History (earlier sessions, hours today) comes from history.json if present;
  without it only this session is known and the warnings say so.

    python -m sw.report_data <take_dir> <out_dir> [--station K-2] [--role picker] [--load-kg 1.0]
"""

import argparse
import json
from pathlib import Path

import numpy as np

from sw import ergo
from sw.ergo import TaskInputs

RISING_DELTA = 0.5          # average RULA rise across the trend window that raises a warning
EXPOSURE_LIMIT_H = 2.0      # hours a day at RULA 5 or above
EXPOSURE_RULA = 5
MIN_CYCLE_S, MAX_CYCLE_S = 3.0, 60.0

# Finding rules: (key, label, angle key, threshold deg, side-specific, minimum share of cycle, minimum cycles)
FINDING_RULES = [
    ("trunk", "Trunk", "trunk_flexion", 45.0, False, 0.10, 1),
    ("shoulder_right", "Right shoulder", "right_upper_arm_flexion", 90.0, True, 0.0, 2),
    ("shoulder_left", "Left shoulder", "left_upper_arm_flexion", 90.0, True, 0.0, 2),
    ("wrists", "Wrists", "wrist_deviation_max", ergo.WRIST_DEVIATION_DEG, False, 0.25, 1),
    ("neck", "Neck", "neck_flexion", 20.0, False, 0.40, 1),
]


def rula_level(score):
    return np.select([score <= 2, score <= 4], ["accept", "investigate"], "change")


# ---------------------------------------------------------------- cycles

def detect_cycles(trunk_flexion, fps):
    """Cycle start frames from the periodicity of trunk flexion. Returns (starts, period_s)."""
    x = np.nan_to_num(trunk_flexion - np.nanmean(trunk_flexion))
    n = len(x)
    if n < int(2 * MIN_CYCLE_S * fps):
        return np.array([0]), n / fps
    ac = np.correlate(x, x, mode="full")[n - 1:]
    ac /= ac[0] if ac[0] else 1
    lo, hi = int(MIN_CYCLE_S * fps), min(int(MAX_CYCLE_S * fps), n - 1)
    lag = lo + int(np.argmax(ac[lo:hi]))
    period = lag / fps
    # cycle starts: the most upright frame in each window of one period
    win = max(3, int(0.25 * fps))
    smooth = np.convolve(np.nan_to_num(trunk_flexion), np.ones(win) / win, mode="same")
    starts = [int(np.argmin(smooth[: min(lag, n)]))]
    if starts[0] > lag // 3:   # the take began mid-cycle: count the lead-in as the first cycle
        starts = [0] + starts
    while starts[-1] + lag < n:
        c = starts[-1] + lag
        a, b = max(0, c - lag // 4), min(n, c + lag // 4)
        starts.append(a + int(np.argmin(smooth[a:b])))
    return np.array(starts), period


# ---------------------------------------------------------------- summaries

def _share(mask, valid):
    v = valid.sum()
    return float(mask[valid].sum() / v) if v else 0.0


def build(take_dir, station="K-2", role="picker", task=TaskInputs(), history=None, stride=3):
    take_dir = Path(take_dir)
    d = np.load(take_dir / "skeleton3d.npz")
    X = d["X"]
    meta = json.loads((take_dir / "meta.json").read_text(encoding="utf-8")) if (take_dir / "meta.json").exists() else {}
    fps = float(meta.get("fps", d["fps"] if "fps" in d else 30))
    kind = meta.get("data_kind", "measured")
    s = ergo.score_take(X, task)
    a, valid = s["angles"], s["valid"]
    n = len(X)
    rula = np.maximum(s["rula_left"]["score"], s["rula_right"]["score"])
    reba = np.maximum(s["reba_left"]["score"], s["reba_right"]["score"])
    starts, period = detect_cycles(a["trunk_flexion"], fps)
    bounds = list(zip(starts, list(starts[1:]) + [n]))
    cycles = len(bounds)
    a["wrist_deviation_max"] = np.maximum(a["left_wrist_deviation"], a["right_wrist_deviation"])

    lv = rula_level(rula)
    levels = {k: round(_share(lv == k, valid), 3) for k in ("accept", "investigate", "change")}

    def per_cycle(key, thr):
        out = []
        for b0, b1 in bounds:
            m = valid[b0:b1]
            out.append(float(((a[key][b0:b1] > thr) & m).sum() / max(1, m.sum())))
        return np.array(out)

    findings = []
    for key, label, akey, thr, sided, min_share, min_cycles in FINDING_RULES:
        shares = per_cycle(akey, thr)
        n_cyc = int((shares > 0.02).sum())
        share = float(np.mean(shares))
        if share >= min_share and n_cyc >= min_cycles and n_cyc > 0:
            sec = share * period
            if key == "trunk":
                text = f"Trunk bent past {thr:.0f}° for {sec:.1f} s per cycle."
                when = "every cycle" if n_cyc == cycles else f"{n_cyc} of {cycles} cycles"
            elif key.startswith("shoulder"):
                text = f"Upper arm above {thr:.0f}° while reaching up."
                when = f"{n_cyc} of {cycles} cycles"
            elif key == "wrists":
                text = f"Wrist bent past {thr:.0f}° sideways."
                when = f"{share * 100:.0f}% of the cycle"
            else:
                text = f"Neck bent past {thr:.0f}° looking down."
                when = f"{share * 100:.0f}% of the session"
            severity = "red" if (key in ("trunk",) or key.startswith("shoulder")) else "amber"
            findings.append({"key": key, "label": label, "when": when, "text": text, "severity": severity,
                             "share": round(share, 3), "cycles": n_cyc})

    def stat(key, how):
        v = a[key][valid]
        return float(np.nanmax(v)) if how == "peak" else float(np.nanmedian(v))

    def share_over(key, thr):
        return round(_share(a[key] > thr, valid), 3)

    rr, rl = s["rula_right"], s["rula_left"]
    factors = [
        {"name": "Trunk flexion", "score": f"REBA {int(np.max(s['reba_right']['trunk'][valid]))}", "value": round(stat("trunk_flexion", "peak")), "unit": "deg peak", "share_text": f">45° {share_over('trunk_flexion', 45) * 100:.0f}% of cycle", "ref": "Ref <20°", "grade": "r" if share_over("trunk_flexion", 45) > 0.1 else "a"},
        {"name": "Trunk twist", "score": "+1" if share_over("trunk_twist", ergo.TRUNK_TWIST_DEG) > 0.05 else "0", "value": round(stat("trunk_twist", "peak")), "unit": "deg peak", "share_text": f">{ergo.TRUNK_TWIST_DEG:.0f}° {share_over('trunk_twist', ergo.TRUNK_TWIST_DEG) * 100:.0f}% of cycle", "ref": f"Ref <{ergo.TRUNK_TWIST_DEG:.0f}°", "grade": "a" if share_over("trunk_twist", ergo.TRUNK_TWIST_DEG) > 0.05 else "g"},
        {"name": "Neck flexion", "score": f"RULA {int(np.median(rr['neck'][valid]))}", "value": round(stat("neck_flexion", "median")), "unit": "deg median", "share_text": f">20° {share_over('neck_flexion', 20) * 100:.0f}%", "ref": "Ref <10°", "grade": "a" if share_over("neck_flexion", 20) > 0.3 else "g"},
        {"name": "Legs", "score": f"REBA {int(np.median(s['reba_right']['legs'][valid]))}", "value": round(stat("right_knee_flexion", "median")), "unit": "deg knee", "share_text": f"Both feet down {(1 - _share(a['one_foot_raised'], valid)) * 100:.0f}%", "ref": "Ref", "grade": "g"},
        {"name": "Upper arm · right", "score": f"RULA {int(np.max(rr['upper_arm'][valid]))}", "value": round(stat("right_upper_arm_flexion", "peak")), "unit": "deg peak", "share_text": f">90° {int((per_cycle('right_upper_arm_flexion', 90) > 0.02).sum())} of {cycles} cycles", "ref": "Ref <20°", "grade": "r" if share_over("right_upper_arm_flexion", 90) > 0.03 else "a"},
        {"name": "Upper arm · left", "score": f"RULA {int(np.max(rl['upper_arm'][valid]))}", "value": round(stat("left_upper_arm_flexion", "peak")), "unit": "deg peak", "share_text": f">45° {share_over('left_upper_arm_flexion', 45) * 100:.0f}%", "ref": "Ref <20°", "grade": "a" if share_over("left_upper_arm_flexion", 45) > 0.1 else "g"},
        {"name": "Lower arm · both", "score": f"RULA {int(np.median(rr['lower_arm'][valid]))}", "value": round(stat("right_elbow_flexion", "median")), "unit": "deg median", "share_text": f"60-100° {_share((a['right_elbow_flexion'] >= 60) & (a['right_elbow_flexion'] <= 100), valid) * 100:.0f}%", "ref": "Ref 60-100°", "grade": "g"},
        {"name": "Wrist · right", "score": f"RULA {int(np.max(rr['wrist'][valid]))}", "value": round(stat("right_wrist_deviation", "peak")), "unit": "deg peak", "share_text": f">{ergo.WRIST_DEVIATION_DEG:.0f}° {share_over('right_wrist_deviation', ergo.WRIST_DEVIATION_DEG) * 100:.0f}%", "ref": f"Ref <{ergo.WRIST_DEVIATION_DEG:.0f}°", "grade": "a" if share_over("right_wrist_deviation", ergo.WRIST_DEVIATION_DEG) > 0.2 else "g"},
    ]

    # left / right balance: share of time each side is in RULA 3+ for that joint score
    def side_share(side, part, thr):
        return round(_share(s[f"rula_{side}"][part] >= thr, valid), 3)
    balance = [
        {"joint": "Shoulder", "left": side_share("left", "upper_arm", 3), "right": side_share("right", "upper_arm", 3)},
        {"joint": "Wrist", "left": side_share("left", "wrist", 3), "right": side_share("right", "wrist", 3)},
        {"joint": "Elbow", "left": side_share("left", "lower_arm", 2), "right": side_share("right", "lower_arm", 2)},
    ]
    tot_l = sum(b["left"] for b in balance) or 1e-9
    tot_r = sum(b["right"] for b in balance)
    ratio = tot_r / tot_l if tot_l > 1e-6 else 0.0
    heavier = "right" if tot_r >= tot_l else "left"

    # history: earlier sessions of this role and hours today, if known
    hist = history or {}
    sessions = hist.get("role_sessions", [])  # [{"label": "Mon", "avg_rula": 3.9}, ...]
    this_avg = float(np.mean(rula[valid])) if valid.any() else 0.0
    trend = sessions + [{"label": hist.get("today_label", "Today"), "avg_rula": round(this_avg, 2)}]
    hours_today = float(hist.get("hours_today_at_or_above", 0.0)) + _share(rula >= EXPOSURE_RULA, valid) * n / fps / 3600
    warnings = []
    if len(trend) >= 3 and trend[-1]["avg_rula"] - trend[0]["avg_rula"] >= RISING_DELTA:
        warnings.append({"kind": "rising", "severity": "red",
                         "text": f"Average RULA for this role rose from {trend[0]['avg_rula']:.1f} to {trend[-1]['avg_rula']:.1f} over the last {len(trend)} sessions."})
    if hours_today >= EXPOSURE_LIMIT_H:
        warnings.append({"kind": "exposure", "severity": "amber",
                         "text": f"{hours_today:.1f} h at RULA {EXPOSURE_RULA} or above today, against a site limit of {EXPOSURE_LIMIT_H:g} h."})
    if not sessions:
        warnings.append({"kind": "note", "severity": "muted",
                         "text": "First session for this role: the trend and daily exposure need earlier sessions to compare against."})

    # per-frame series for the page, thinned
    idx = np.arange(0, n, stride)
    kp = {"head": (ergo.L_EAR, ergo.R_EAR), "neck": (ergo.L_SH, ergo.R_SH), "hip": (ergo.L_HIP, ergo.R_HIP),
          "kn": (ergo.L_KN, ergo.R_KN), "an": (ergo.L_AN, ergo.R_AN), "el": (ergo.R_EL,), "wr": (ergo.R_WR,),
          "hd": (ergo.R_HAND["middle"],), "el2": (ergo.L_EL,), "wr2": (ergo.L_WR,)}

    def side_xy(j):  # side view: forward (y) and up (z), metres
        P = np.nanmean(X[idx][:, list(j)], axis=1)
        return np.round(P[:, [1, 2]], 3).tolist()
    frames = {"fps": fps / stride, "t": np.round(idx / fps, 2).tolist(), "rula": rula[idx].astype(int).tolist(),
              "trunk_flexion": np.round(np.nan_to_num(a["trunk_flexion"][idx]), 1).tolist(),
              "right_upper_arm_flexion": np.round(np.nan_to_num(a["right_upper_arm_flexion"][idx]), 1).tolist(),
              "keypoints": {k: side_xy(v) for k, v in kp.items()}}

    quality = meta.get("quality", {})
    return {
        "data_kind": kind,
        "session": {"station": station, "role": role, "cameras": meta.get("cameras", 3), "frames": n, "fps": fps,
                    "duration_s": round(n / fps, 1), "cycles": cycles, "cycle_s": round(period, 1),
                    "detected_share": quality.get("detected_share"), "reproj_px": quality.get("reproj_px"),
                    "floor_tilt_deg": quality.get("floor_tilt_deg"), "source": meta.get("source", "sw.recon3d")},
        "task_inputs": {"load_kg": task.load_kg, "repeated_over_4_per_min": task.repeated_over_4_per_min,
                        "coupling": task.coupling, "wrist_twist_end_range": task.wrist_twist_end_range},
        "peaks": {"rula": int(rula[valid].max()), "reba": int(reba[valid].max()),
                  "rula_action": ergo.RULA_ACTION[int(rula[valid].max())], "reba_risk": ergo.reba_risk(int(reba[valid].max()))},
        "levels": levels,
        "findings": findings,
        "factors": factors,
        "balance": {"rows": balance, "ratio": round(ratio, 1), "heavier": heavier},
        "trend": trend,
        "warnings": warnings,
        "role_card": {"avg_rula": round(this_avg, 1), "sessions": len(trend), "workers": hist.get("workers_in_role", 1)},
        "frames": frames,
        "cycle_starts_s": np.round(starts / fps, 2).tolist(),
    }


def write(data, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    js = json.dumps(data, separators=(",", ":"))
    (out / "report-data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    (out / "report-data.js").write_text("window.REPORT_DATA = " + js + ";\n", encoding="utf-8")
    return out / "report-data.js"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("take_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--station", default="K-2")
    ap.add_argument("--role", default="picker")
    ap.add_argument("--load-kg", type=float, default=1.0)
    ap.add_argument("--history", default=None, help="history.json with role_sessions, hours_today_at_or_above, workers_in_role")
    a = ap.parse_args()
    hist = json.loads(Path(a.history).read_text(encoding="utf-8")) if a.history else None
    data = build(a.take_dir, a.station, a.role, TaskInputs(load_kg=a.load_kg), hist)
    p = write(data, a.out_dir)
    s = data["session"]
    print(f"{data['data_kind']}: {s['cycles']} cycles of {s['cycle_s']} s, RULA peak {data['peaks']['rula']}, "
          f"REBA peak {data['peaks']['reba']}, levels {data['levels']}, {len(data['findings'])} findings, "
          f"{len(data['warnings'])} warnings -> {p}")


if __name__ == "__main__":
    main()
