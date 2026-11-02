# NODAL Strain Watch: technical summary

Future Health Digital Innovation Challenge, "[Population Health] Population and Workforce Health Early Warning". NODAL Vision Systems Pte. Ltd., Singapore. Version 0.1, November 2026. The full documentation is `TECHNICAL.md`.

## What it does

Three NODAL M1 cameras film a worker at a station. The software builds a 3D skeleton from the three views, computes joint angles, scores every frame with RULA and REBA, rolls the scores up per task cycle, and tracks them by job role over time. When a role's average risk rises, or a worker's daily time at RULA 5 or above passes a set limit, the occupational health lead gets a flag naming the joint, the angle and the moment. It screens; it does not diagnose. A qualified professional reviews every flag.

## How it works

| Step | What | Where in the code |
|---|---|---|
| 1 Capture | 3 M1 cameras, one radio trigger; worker has opted in | M1 hardware (pre-existing) |
| 2 2D pose | RTMW whole-body model (133 keypoints) on each view, via rtmlib, CPU | `sw/pose2d.py` |
| 3 3D skeleton | Camera positions solved from the worker's joints (essential matrix, PnP, bundle adjustment), then weighted triangulation; reprojection error as the quality check | `sw/recon3d.py`, `sw/check_overlay.py` |
| 4 Joint angles | Trunk, neck, upper arm, elbow, wrist, knee, per frame | `sw/ergo.py:angles` |
| 5 Scores | RULA (1 to 7) and REBA (1 to 15) per frame and side; load, repetition and grip set by the health lead | `sw/ergo.py:rula`, `reba` |
| 6 Privacy | Video deleted after processing; skeleton and scores kept; pseudonymous IDs; reports by role | pipeline outputs, site agreement |
| 7 Early warning | Cycles by autocorrelation; time in action levels; findings from stated thresholds; rising-role and daily-exposure rules | `sw/report_data.py` |
| 8 Review | One-page report: findings, skeleton replay, exposure clock, trend, warnings, role card | `web/report.html` |

## Assumptions

Cameras 2.5 to 3.5 m from the station, 60 to 90 degrees apart, level tripod heads, whole body in every view, even light. Factory lens calibration valid. One worker doing one repetitive task per take. 1080p at 30 fps. RULA and REBA tables transcribed from the 1993 and 2000 papers, spot-checked, full worksheet check pending. Task inputs the camera cannot see (load, repetition, grip) set by the health lead.

## Limitations

- Accuracy for these tasks not yet validated against a marker-based laboratory; published multi-camera systems reach 3 to 4.5 degrees mean joint-angle error, which is our target, not our result.
- Frames from different cameras can be up to one frame apart (33 ms at 30 fps).
- Occlusion, loose clothing and poor light drop frames and can bias summaries.
- RULA and REBA were designed for human observers; per-frame scoring is an adaptation. Human raters agree only moderately with each other.
- The submitted report runs on a synthetic worker, labelled as such on every screen; no number in it is a measurement of a person.
- Not a medical device.

## Validation before any pilot

Joint angles against marker-based capture, target under 5 degrees mean error; RULA and REBA against two trained assessors, target weighted kappa 0.6 or more; repeatability of flags; tables checked against the official worksheets. Then a six-month pilot at one or two sites measuring setup time, processed shifts, review time, opt-in, tasks changed, high-risk minutes per shift, and complaints and lost-time cases against the year before.

## Data

Consented test footage only; no health records; no third-party worker data; no data from the organizers. Video deleted after processing. Pilot data under a site data agreement and local data-protection law.

## Third-party components

rtmlib 0.0.16 (Apache 2.0); RTMW / RTMPose weights released with MMPose (Apache 2.0); onnxruntime 1.23.2 (MIT); opencv-python-headless 5.0 (Apache 2.0); NumPy 2.2 and SciPy 1.15 (BSD 3-Clause). No GPL or AGPL. NODAL's own pose software is not used; M1 hardware and its software are pre-existing tools, not submitted materials.

## Running it

`pip install -r requirements.txt`, then `python -m sw.pose2d`, `sw.recon3d`, `sw.report_data` on a take, or `python -m sw.synth` for the synthetic worker; open `web/report.html`. Tests: `python -m pytest -q` (9 tests).
