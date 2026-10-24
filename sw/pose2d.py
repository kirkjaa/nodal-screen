"""2D whole-body keypoints for one camera view.

Runs RTMW (OpenMMLab, Apache 2.0) through rtmlib on every frame of a video and
keeps the most confident person. Output: an .npz with keypoints (frames x 133 x 2,
NaN where the person was not found), their scores, and a .json with run details.

    python -m sw.pose2d <video.mp4> <out_prefix> [--mode balanced] [--det-every 5]
"""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
from rtmlib import PoseTracker, Wholebody

N_KPTS = 133


def best_person(keypoints, scores):
    """Index of the most confident person in one frame, or None."""
    if keypoints is None or len(keypoints) == 0:
        return None
    return int(np.argmax(np.nanmean(scores, axis=1)))


def run(video, out_prefix, mode, det_every):
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    tracker = PoseTracker(Wholebody, det_frequency=det_every, to_openpose=False,
                          mode=mode, backend="onnxruntime", device="cpu",
                          tracking=False)

    kpts = np.full((n_frames, N_KPTS, 2), np.nan, dtype=np.float32)
    conf = np.zeros((n_frames, N_KPTS), dtype=np.float32)
    found = 0
    started = time.time()
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok or i >= n_frames:
            break
        keypoints, scores = tracker(frame)
        p = best_person(keypoints, scores)
        if p is not None:
            kpts[i] = keypoints[p]
            conf[i] = scores[p]
            found += 1
        i += 1
        if i % 100 == 0:
            rate = i / (time.time() - started)
            print(f"{video.name}: {i}/{n_frames} frames, {rate:.1f} fps", flush=True)
    cap.release()

    out_prefix = Path(out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(f"{out_prefix}.npz", keypoints=kpts[:i], scores=conf[:i])
    meta = {
        "video": video.name,
        "frames_read": i,
        "frames_with_person": found,
        "fps": fps,
        "width": width,
        "height": height,
        "model": f"rtmlib Wholebody (RTMDet + RTMW), mode={mode}",
        "detect_every_n_frames": det_every,
        "seconds": round(time.time() - started, 1),
    }
    Path(f"{out_prefix}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("out_prefix")
    ap.add_argument("--mode", default="balanced",
                    choices=["performance", "balanced", "lightweight"])
    ap.add_argument("--det-every", type=int, default=5)
    a = ap.parse_args()
    run(a.video, a.out_prefix, a.mode, a.det_every)


if __name__ == "__main__":
    main()
