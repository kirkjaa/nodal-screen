"""3D skeleton from three synchronized M1 views, without a calibration target.

The lenses are known (factory intrinsics per camera). Where the cameras stand is
solved from the worker's own body: the same joints seen in two views give an
essential matrix, the third camera is placed by PnP, and a bundle adjustment
refines all three poses together. Every frame is then triangulated.

Gravity comes from the cameras: on a level tripod head a camera's x axis is
horizontal, so "up" is perpendicular to every camera's x axis. A body-based
estimate is computed as a check. Scale is set from a nominal upper-arm length,
so distances are approximate; joint angles do not depend on scale.

    python -m sw.recon3d <take_dir> <pose_dir> <calib_dir> <out_dir>
"""

import argparse
import itertools
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

CAMS = ["rx-cam1", "rx-cam2", "rx-cam3"]
SOLVE_KPTS = list(range(0, 23))      # COCO body 17 + 6 foot points
MIN_SCORE = 0.35
UPPER_ARM_M = 0.31                    # nominal adult shoulder-to-elbow length
L_SH, R_SH, L_EL, R_EL, L_HIP, R_HIP = 5, 6, 7, 8, 11, 12


# ---------------------------------------------------------------- loading

def load_intrinsics(calib_dir, cam):
    d = json.loads((Path(calib_dir) / f"{cam}_intrinsics.json").read_text())
    return np.array(d["camera_matrix"], float), np.array(d["dist_coeffs"], float).ravel()


def frame_times(sidecar):
    """Seconds from the radio trigger edge for every recorded frame, in order."""
    lines = [json.loads(l) for l in Path(sidecar).read_text().splitlines() if l.strip()]
    edge = lines[0]["edge_mono_ns"]
    frames = sorted((l for l in lines[1:] if "seq" in l), key=lambda l: l["seq"])
    return np.array([(f["mono_ns"] - edge) / 1e9 for f in frames])


def undistort(kpts, K, dist):
    """Pixel keypoints to ideal-pinhole pixels (same K, no distortion)."""
    shp = kpts.shape
    flat = kpts.reshape(-1, 1, 2).astype(np.float64)
    ok = ~np.isnan(flat[:, 0, 0])
    out = np.full_like(flat, np.nan)
    if ok.any():
        out[ok] = cv2.undistortPoints(flat[ok], K, dist, P=K)
    return out.reshape(shp)


def resample(times, kpts, scores, grid):
    """Linear interpolation of keypoints onto a common time grid."""
    n = min(len(times), len(kpts))
    times, kpts, scores = times[:n], kpts[:n], scores[:n]
    idx = np.clip(np.searchsorted(times, grid) - 1, 0, n - 2)
    w = ((grid - times[idx]) / (times[idx + 1] - times[idx]))[:, None, None]
    k = (1 - w) * kpts[idx] + w * kpts[idx + 1]
    s = np.minimum(scores[idx], scores[idx + 1])
    return k, s


# ---------------------------------------------------------------- geometry

def project(X, R, t, K):
    x = (R @ X.T + t[:, None]).T
    uv = x[:, :2] / x[:, 2:3]
    return uv @ K[:2, :2].T + K[:2, 2], x[:, 2]


def triangulate(views):
    """Weighted DLT. views: list of (P 3x4, uv (2,), weight)."""
    A = []
    for P, uv, w in views:
        A.append(w * (uv[0] * P[2] - P[0]))
        A.append(w * (uv[1] * P[2] - P[1]))
    _, _, vt = np.linalg.svd(np.array(A))
    X = vt[-1]
    return X[:3] / X[3]


def pair_pose(ua, ub, K_a, K_b):
    """Relative pose b-from-a from matched undistorted pixels."""
    na = cv2.undistortPoints(ua.reshape(-1, 1, 2), K_a, None)
    nb = cv2.undistortPoints(ub.reshape(-1, 1, 2), K_b, None)
    E, mask = cv2.findEssentialMat(na, nb, np.eye(3), method=cv2.RANSAC,
                                   prob=0.999, threshold=2.0 / K_a[0, 0])
    n, R, t, mask2 = cv2.recoverPose(E, na, nb, np.eye(3), mask=mask)
    return R, t.ravel(), int(n)


# ---------------------------------------------------------------- solve

def correspondences(U, S, a, b, frames):
    ua, ub, ref = [], [], []
    for f in frames:
        for j in SOLVE_KPTS:
            if S[a][f, j] > MIN_SCORE and S[b][f, j] > MIN_SCORE \
                    and not np.isnan(U[a][f, j, 0]) and not np.isnan(U[b][f, j, 0]):
                ua.append(U[a][f, j]); ub.append(U[b][f, j]); ref.append((f, j))
    return np.array(ua), np.array(ub), ref


def bundle_adjust(Ks, poses, U, S, frames):
    """Refine cameras 1..n-1 (camera 0 fixed) and the 3D points jointly."""
    nc = len(Ks)
    Ps = [Ks[c] @ np.hstack([poses[c][0], poses[c][1][:, None]]) for c in range(nc)]
    pts, obs = [], []
    for f in frames:
        for j in SOLVE_KPTS:
            vis = [c for c in range(nc) if S[c][f, j] > MIN_SCORE and not np.isnan(U[c][f, j, 0])]
            if len(vis) < 2:
                continue
            X = triangulate([(Ps[c], U[c][f, j], S[c][f, j]) for c in vis])
            pid = len(pts)
            pts.append(X)
            for c in vis:
                obs.append((pid, c, U[c][f, j], S[c][f, j]))
    pts = np.array(pts)
    scale0 = np.linalg.norm(poses[1][1])

    def pack(poses, pts):
        cam = [np.r_[cv2.Rodrigues(poses[c][0])[0].ravel(), poses[c][1]] for c in range(1, nc)]
        return np.r_[np.concatenate(cam), pts.ravel()]

    def unpack(x):
        cams = [poses[0]]
        for c in range(1, nc):
            r = x[(c - 1) * 6:(c - 1) * 6 + 3]
            cams.append((cv2.Rodrigues(r)[0], x[(c - 1) * 6 + 3:(c - 1) * 6 + 6]))
        return cams, x[(nc - 1) * 6:].reshape(-1, 3)

    o_pid = np.array([o[0] for o in obs]); o_cam = np.array([o[1] for o in obs])
    o_uv = np.array([o[2] for o in obs]); o_w = np.sqrt(np.array([o[3] for o in obs]))

    def residuals(x):
        cams, P3 = unpack(x)
        res = np.empty((len(obs), 2))
        for c in range(nc):
            m = o_cam == c
            uv, _ = project(P3[o_pid[m]], cams[c][0], cams[c][1], Ks[c])
            res[m] = (uv - o_uv[m]) * o_w[m, None]
        gauge = 100.0 * (np.linalg.norm(cams[1][1]) - scale0)
        return np.r_[res.ravel(), gauge]

    n_cam = (nc - 1) * 6
    A = lil_matrix((len(obs) * 2 + 1, n_cam + len(pts) * 3), dtype=int)
    for i, (pid, c) in enumerate(zip(o_pid, o_cam)):
        if c > 0:
            A[2 * i:2 * i + 2, (c - 1) * 6:(c - 1) * 6 + 6] = 1
        A[2 * i:2 * i + 2, n_cam + pid * 3:n_cam + pid * 3 + 3] = 1
    A[-1, 3:6] = 1
    r = least_squares(residuals, pack(poses, pts), jac_sparsity=A, loss="huber",
                      f_scale=3.0, x_scale="jac", method="trf", max_nfev=60, verbose=0)
    cams, _ = unpack(r.x)
    raw = r.fun[:-1].reshape(-1, 2) / o_w[:, None]
    return cams, float(np.sqrt(np.median((raw ** 2).sum(1)))), len(pts)


def solve_cameras(Ks, U, S, n_frames):
    frames = list(range(0, n_frames, 3))
    best = None
    for a, b in itertools.combinations(range(3), 2):
        ua, ub, _ = correspondences(U, S, a, b, frames)
        if len(ua) < 50:
            continue
        R, t, n = pair_pose(ua, ub, Ks[a], Ks[b])
        if best is None or n > best[0]:
            best = (n, a, b, R, t)
    if best is None:
        raise SystemExit("not enough shared body points to place the cameras")
    _, a, b, R_ab, t_ab = best
    c = 3 - a - b
    poses = {a: (np.eye(3), np.zeros(3)), b: (R_ab, t_ab)}
    # Place the third camera by PnP against points from the first pair.
    Pa = Ks[a] @ np.hstack([np.eye(3), np.zeros((3, 1))])
    Pb = Ks[b] @ np.hstack([R_ab, t_ab[:, None]])
    obj, img = [], []
    for f in frames:
        for j in SOLVE_KPTS:
            if all(S[k][f, j] > MIN_SCORE and not np.isnan(U[k][f, j, 0]) for k in (a, b, c)):
                obj.append(triangulate([(Pa, U[a][f, j], 1.0), (Pb, U[b][f, j], 1.0)]))
                img.append(U[c][f, j])
    ok, rvec, tvec, inl = cv2.solvePnPRansac(np.array(obj), np.array(img), Ks[c], None,
                                             reprojectionError=8.0, iterationsCount=500)
    if not ok:
        raise SystemExit("could not place the third camera")
    poses[c] = (cv2.Rodrigues(rvec)[0], tvec.ravel())
    order = [a, b, c]
    cams, rms, npts = bundle_adjust([Ks[k] for k in order], [poses[k] for k in order],
                                    [U[k] for k in order], [S[k] for k in order], frames)
    solved = {order[i]: cams[i] for i in range(3)}
    return [solved[k] for k in range(3)], rms, npts, (CAMS[a], CAMS[b])


KEEP_KPTS = list(range(0, 23)) + list(range(91, 133))   # body, feet, both hands (no face)


def triangulate_all(Ks, cams, U, S, n_kpts, max_err=15.0):
    Ps = [Ks[c] @ np.hstack([cams[c][0], cams[c][1][:, None]]) for c in range(3)]
    T = U[0].shape[0]
    X = np.full((T, n_kpts, 3), np.nan)
    err = np.full((T, n_kpts), np.nan)
    nviews = np.zeros((T, n_kpts), dtype=np.int8)
    for f in range(T):
        for j in KEEP_KPTS:
            vis = [c for c in range(3) if S[c][f, j] > 0.3 and not np.isnan(U[c][f, j, 0])]
            while len(vis) >= 2:
                Xj = triangulate([(Ps[c], U[c][f, j], S[c][f, j]) for c in vis])
                e = [np.linalg.norm(project(Xj[None], *cams[c], Ks[c])[0][0] - U[c][f, j]) for c in vis]
                if max(e) <= max_err or len(vis) == 2:
                    if max(e) <= max_err:
                        X[f, j], err[f, j], nviews[f, j] = Xj, float(np.mean(e)), len(vis)
                    break
                vis.pop(int(np.argmax(e)))
    return X, err, nviews


def world_frame(cams, X):
    """Rotation and origin putting z up, from camera x axes, with a body check."""
    xs = [c[0].T @ np.array([1.0, 0, 0]) for c in cams]
    ups = []
    for a, b in itertools.combinations(range(len(xs)), 2):
        u = np.cross(xs[a], xs[b])
        if np.linalg.norm(u) > 0.2:
            ups.append(u / np.linalg.norm(u))
    trunk = np.nanmedian((X[:, [L_SH, R_SH]].mean(1) - X[:, [L_HIP, R_HIP]].mean(1)), axis=0)
    trunk /= np.linalg.norm(trunk)
    if ups:
        ups = [u if u @ trunk > 0 else -u for u in ups]
        up = np.mean(ups, axis=0); up /= np.linalg.norm(up); source = "camera x axes"
    else:
        up, source = trunk, "median trunk direction"
    agree = float(np.degrees(np.arccos(np.clip(up @ trunk, -1, 1))))
    x = xs[0] - (xs[0] @ up) * up; x /= np.linalg.norm(x)
    y = np.cross(up, x)
    Rw = np.vstack([x, y, up])                      # world-from-cam0
    origin = np.nanmedian(X[:, [L_HIP, R_HIP]].mean(1), axis=0)
    return Rw, origin, source, agree


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("take_dir", type=Path)
    ap.add_argument("pose_dir", type=Path)
    ap.add_argument("calib_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    a = ap.parse_args()
    take = a.take_dir.name

    Ks, dists, times, raw = [], [], [], []
    for cam in CAMS:
        K, d = load_intrinsics(a.calib_dir, cam)
        p = np.load(a.pose_dir / f"pose2d_{cam}.npz")
        Ks.append(K); dists.append(d)
        times.append(frame_times(a.take_dir / f"{take}_{cam}.jsonl"))
        raw.append((p["keypoints"], p["scores"]))
    t0 = max(t[0] for t in times)
    t1 = min(t[min(len(t), len(k)) - 1] for t, (k, _) in zip(times, raw))
    grid = np.arange(t0, t1, 1 / 30.0)
    U, S = [], []
    for c in range(3):
        k, s = resample(times[c], raw[c][0], raw[c][1], grid)
        U.append(undistort(k, Ks[c], dists[c])); S.append(s)

    cams, ba_rms, ba_pts, ref_pair = solve_cameras(Ks, U, S, len(grid))
    n_kpts = U[0].shape[1]
    X, err, nviews = triangulate_all(Ks, cams, U, S, n_kpts)

    Rw, origin, up_source, up_agree = world_frame(cams, X)
    arm = np.nanmedian(np.r_[np.linalg.norm(X[:, L_SH] - X[:, L_EL], axis=1),
                             np.linalg.norm(X[:, R_SH] - X[:, R_EL], axis=1)])
    scale = UPPER_ARM_M / arm
    Xw = ((X - origin) @ Rw.T) * scale

    a.out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out_dir / "skeleton3d.npz", X=Xw.astype(np.float32),
                        reproj_px=err.astype(np.float32), n_views=nviews, t=grid)
    cams_w = []
    for c, cam in enumerate(CAMS):
        R, t = cams[c]
        Rcw = R @ Rw.T                                # cam-from-world
        tcw = (t + R @ origin) * scale
        cams_w.append({"node_id": cam, "K": Ks[c].tolist(), "dist": dists[c].tolist(),
                       "R": Rcw.tolist(), "t_m": tcw.tolist(),
                       "position_m": (-Rcw.T @ tcw).tolist()})
    body = list(range(17))
    summary = {
        "take": take,
        "frames": int(len(grid)),
        "duration_s": round(float(grid[-1] - grid[0]), 2),
        "reference_pair": ref_pair,
        "bundle_adjust_points": ba_pts,
        "bundle_adjust_median_reproj_px": round(ba_rms, 2),
        "triangulated_body_points_pct": round(float(100 * np.mean(~np.isnan(X[:, body, 0]))), 1),
        "body_median_reproj_px": round(float(np.nanmedian(err[:, body])), 2),
        "body_points_seen_by_3_cameras_pct": round(float(100 * np.mean(nviews[:, body] == 3)), 1),
        "up_from": up_source,
        "up_vs_trunk_deg": round(up_agree, 1),
        "scale": f"nominal upper arm {UPPER_ARM_M} m; distances approximate",
        "camera_positions_m": {c["node_id"]: [round(v, 2) for v in c["position_m"]] for c in cams_w},
    }
    (a.out_dir / "cameras.json").write_text(json.dumps(cams_w, indent=2))
    (a.out_dir / "recon3d.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
