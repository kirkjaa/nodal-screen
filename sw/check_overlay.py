"""Check image: the solved 3D skeleton projected back onto each camera's video.

Green lines are the 3D skeleton reprojected through the solved cameras; small
orange dots are the raw 2D detections. If the green sits on the body in all
three views, the cameras and the 3D are right.

    python -m sw.check_overlay <take_dir> <pose_dir> <recon_dir> <out.png> [--at 0.5]
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from sw.recon3d import CAMS, frame_times

BONES = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
         (11, 13), (13, 15), (12, 14), (14, 16), (0, 5), (0, 6),
         (15, 17), (15, 19), (16, 20), (16, 22),
         (91, 100), (112, 121)]   # wrist to middle-finger base, both hands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("take_dir", type=Path)
    ap.add_argument("pose_dir", type=Path)
    ap.add_argument("recon_dir", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--at", type=float, default=0.5, help="position in the take, 0 to 1")
    a = ap.parse_args()
    take = a.take_dir.name

    rec = np.load(a.recon_dir / "skeleton3d.npz")
    cams = json.loads((a.recon_dir / "cameras.json").read_text())
    X, grid = rec["X"], rec["t"]
    f = int(round(a.at * (len(grid) - 1)))
    while f < len(grid) - 1 and np.isnan(X[f, 5, 0]):
        f += 1
    t = grid[f]

    tiles = []
    for cam, c in zip(CAMS, cams):
        times = frame_times(a.take_dir / f"{take}_{cam}.jsonl")
        i = int(np.argmin(np.abs(times - t)))
        cap = cv2.VideoCapture(str(a.take_dir / f"{take}_{cam}.mp4"))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, img = cap.read()
        cap.release()
        if not ok:
            img = np.zeros((1080, 1920, 3), np.uint8)
        raw = np.load(a.pose_dir / f"pose2d_{cam}.npz")
        if i < len(raw["keypoints"]):
            for (u, v), s in zip(raw["keypoints"][i][:23], raw["scores"][i][:23]):
                if s > 0.3 and not np.isnan(u):
                    cv2.circle(img, (int(u), int(v)), 5, (0, 140, 255), -1)
        rvec = cv2.Rodrigues(np.array(c["R"]))[0]
        pts = X[f].astype(np.float64)
        good = ~np.isnan(pts[:, 0])
        uv = np.full((len(pts), 2), np.nan)
        if good.any():
            uv[good] = cv2.projectPoints(pts[good], rvec, np.array(c["t_m"]),
                                         np.array(c["K"]), np.array(c["dist"]))[0].reshape(-1, 2)
        for a_, b_ in BONES:
            if not (np.isnan(uv[a_, 0]) or np.isnan(uv[b_, 0])):
                cv2.line(img, tuple(int(x) for x in uv[a_]), tuple(int(x) for x in uv[b_]),
                         (60, 220, 60), 4, cv2.LINE_AA)
        cv2.putText(img, f"{cam}  frame {i}  t={t:.2f}s", (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 3, cv2.LINE_AA)
        tiles.append(cv2.resize(img, (960, 540)))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(a.out), np.hstack(tiles))
    print(f"wrote {a.out} at t={t:.2f}s (grid frame {f})")


if __name__ == "__main__":
    main()
