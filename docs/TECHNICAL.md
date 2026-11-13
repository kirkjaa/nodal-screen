# NODAL Strain Watch: technical documentation

Prototype submitted to the Future Health Digital Innovation Challenge, challenge statement "[Population Health] Population and Workforce Health Early Warning". Version 0.1, November 2026. NODAL Vision Systems Pte. Ltd., Singapore.

## 1. Purpose and scope

Strain Watch screens a manual workstation for posture risk. Three NODAL M1 cameras film a worker doing a repetitive task; the software builds a 3D skeleton from the video, computes joint angles, scores every frame with two standard ergonomic methods (RULA and REBA), rolls the scores up per task cycle, and tracks them by job role over time. When a role's risk rises, or a worker's daily exposure passes a set limit, an occupational health lead gets a flag that names the joint, the angle and the moment in the recording.

It is a screening tool. It does not diagnose, treat or predict injury in an individual. A qualified occupational health professional reviews every flag and decides what, if anything, changes at the station. Scores are never used to rate a worker's output.

## 2. System overview

```
 3 x NODAL M1 cameras          laptop or server (NODAL, Singapore)                       site
 on tripods, one radio  --->  1 capture ----> 2 2D pose ----> 3 3D skeleton ----> 4 joint angles
 trigger, worker opted in        |              RTMW per view    three views        trunk, neck, arms,
                                 |                               triangulated       wrists, legs
                                 |                                                       |
                                 v                                                       v
                             video deleted  <--- 6 privacy step  <--- 5 RULA and REBA per frame,
                             skeleton kept                            rolled up per cycle
                                                                              |
                                                                              v
                                               8 review by the health lead <--- 7 early warning:
                                                 joint, angle, clip time          trend by role, daily exposure
```

Code: `sw/pose2d.py` (step 2), `sw/recon3d.py` (step 3, with `sw/check_overlay.py` for a visual check), `sw/ergo.py` (steps 4 and 5), `sw/report_data.py` (steps 5 to 7), `web/report.html` (step 8). `sw/synth.py` generates a synthetic worker so the chain from step 3 onward can be run without footage.

## 3. Method

### 3.1 Capture

Three M1 cameras stand on tripods 2.5 to 3.5 m from the workstation, 60 to 90 degrees apart, each seeing the worker head to feet. One 2.4 GHz radio pulse from the controller starts all three recordings. Each camera writes an MP4 and a sidecar file with the trigger edge and every frame's monotonic timestamp; `sw/recon3d.py:frame_times` turns those into seconds from the trigger, which is how the three streams are aligned (`resample` interpolates each view onto one time grid). The cameras' shutters are not locked to each other, so frames from different cameras can be up to one frame apart (33 ms at 30 fps); whole-frame offsets are corrected, sub-frame offsets are not.

### 3.2 2D pose (`sw/pose2d.py`)

Each view runs through RTMW, OpenMMLab's whole-body 2D pose model, via the `rtmlib` library (`PoseTracker(Wholebody, ..., backend="onnxruntime", device="cpu")`). RTMW outputs 133 COCO-WholeBody keypoints per person per frame (body, feet, face, hands) with a confidence score each. The largest detected person is kept per frame (`best_person`). Output per view: keypoints (frames x 133 x 2) and scores (frames x 133). Throughput on the NODAL server CPU is about 3 frames per second per 1080p view.

### 3.3 3D skeleton (`sw/recon3d.py`)

The lenses are known from NODAL's factory calibration (`load_intrinsics`, camera matrix and distortion per camera); keypoints are undistorted first (`undistort`). Where the cameras stand is solved from the worker's own body, with no calibration object:

1. For the best pair of views, body-joint correspondences with confidence above `MIN_SCORE` (0.35) give an essential matrix and a relative pose (`pair_pose`).
2. The third camera is placed by RANSAC PnP against points triangulated from the first pair (`cv2.solvePnPRansac`, 8 px reprojection threshold).
3. A bundle adjustment refines all three camera poses and the points together (`bundle_adjust`, `scipy.optimize.least_squares` with a Huber loss).
4. Every frame is then triangulated by weighted DLT (`triangulate`, `triangulate_all`); a point is dropped when its reprojection error exceeds 15 px or it is seen by fewer than two views.
5. The world frame (`world_frame`) takes "up" as the direction perpendicular to every camera's x axis, which assumes level tripod heads; a body-based estimate is computed as a check and the angle between the two is reported as floor tilt. Scale is set from a nominal upper-arm length of 0.31 m, so distances are approximate; joint angles do not depend on scale.

Quality numbers written with each take: bundle-adjustment median reprojection error, body-point median reprojection error, share of body points placed in 3D, floor tilt. `sw/check_overlay.py` draws the triangulated skeleton back onto all three views at a chosen moment so a person can see whether the solve is right.

### 3.4 Joint angles (`sw/ergo.py:angles`)

From the 3D skeleton per frame: a pelvis-facing body frame (`body_frame`), then trunk flexion, side bend and twist; neck flexion, side bend and twist; for each arm, upper-arm flexion and abduction relative to the trunk, elbow flexion, wrist flexion and deviation from the hand keypoints, whether the wrist crosses the midline or is out to the side, and whether the shoulder is raised (ear-to-shoulder distance along the trunk axis below 80 percent of the take's median); knee flexion for each leg and whether one foot is raised. Degrees throughout.

### 3.5 RULA and REBA (`sw/ergo.py:rula`, `reba`, `score_take`)

RULA (McAtamney and Corlett, 1993) and REBA (Hignett and McAtamney, 2000) are scored per frame for each side of the body, following the published worksheets: body-part scores from the angles, table A and table B lookups, then table C for the final score (RULA 1 to 7, REBA 1 to 15). The lookup tables are transcribed from the two papers and spot-checked in `tests/test_ergo.py`; a full check against the official worksheets is still to be done (section 5).

What the cameras cannot see is a parameter, not a guess (`TaskInputs`): the load on the hands, shock or rapid force, whether the task repeats more than four times a minute or is held static over a minute, grip (coupling) quality, wrist twist at end of range, and arm support. The health lead sets these per task; the defaults (1 kg, repeated, good grip) are shown on the report beside the scores. Thresholds the methods leave to the observer (abduction, twist, side bend, shoulder raise) are named constants at the top of `ergo.py` so they can be reviewed.

Frames with any required joint missing are marked invalid and excluded from every summary. The session score per frame is the higher of the two sides.

### 3.6 Cycles, summaries and findings (`sw/report_data.py`)

- Cycle detection (`detect_cycles`): a repetitive task shows up as a periodic trunk-flexion signal. The cycle length is the dominant period of that signal by autocorrelation (searched between 3 s and 60 s); cycle starts are the most upright moments, one per period. This assumes one repeated task per take.
- Time in RULA action level: the share of valid frames at RULA 1 to 2 (acceptable), 3 to 4 (investigate) and 5 to 7 (change), per the method's action levels.
- Findings: rules over the angles with their thresholds stated in `FINDING_RULES`. Upper arm above 90 degrees (RULA upper-arm score 4) in at least two cycles; neck above 20 degrees (RULA neck score 3) for at least 40 percent of the session; wrist deviation above 15 degrees for at least 25 percent of the cycle; trunk above 45 degrees for at least 10 percent of the cycle. The trunk threshold sits inside RULA's 20 to 60 degree band and is a review threshold chosen so that deep stoops stand out from ordinary leaning, not a score boundary.
- Risk-factor cards and left/right balance: peaks, medians and shares per joint, and the share of time each side spends at an elevated joint score.

### 3.7 Early warning (`sw/report_data.py`)

Two rules, both with named parameters:

1. Rising role: the average RULA of this role across the trend window (earlier sessions plus this one) rises by `RISING_DELTA` (0.5) or more from first to last.
2. Daily exposure: hours in the day at RULA `EXPOSURE_RULA` (5) or above pass `EXPOSURE_LIMIT_H` (2.0 hours).

Earlier sessions and hours already worked today come from a history file; without one, the report says it is the first session for the role and that the trend needs earlier sessions to compare against. Storing history across sessions and workers at a site is planned; the prototype reads it from a file.

### 3.8 The report (`web/report.html`)

A single page in the NODAL Design System that renders entirely from a data file (`report-data.js`, written by `sw/report_data.py`). Tabs: Health lead (peaks, time in action levels, cycle time, findings, a skeleton replay with the per-frame RULA strip, an exposure clock showing RULA around the average cycle, the role trend, early warnings), Risk factors, Load balance, Role card (average RULA, suggested review items derived from the findings), Source. The header badge states the kind of data on every tab: sample, synthetic, or measured; measured styling is never shown for anything else.

## 4. Data handling and privacy

| Item | Handling |
|---|---|
| Consent | Workers opt in; written consent on camera before any clip is used. Worker consultation before filming at a site. |
| Video | Processed, then deleted. Nothing in the report links to video. |
| Kept | 3D skeleton (joint positions over time), joint angles, scores, session metadata. No faces, no images. |
| Identity | Pseudonymous worker IDs; reports are by role and station, not name. |
| Use | Scores are never used to rate a worker's output; written into the site agreement. |
| Where | Processing on NODAL's server in Singapore for the prototype; at a pilot, on a laptop at the site or a server in the site's chosen region. |
| Retention | Skeleton data kept for the trend window the site agrees (planned default 12 months), then deleted. |
| Health records | None used. No data from the organizers. |

## 5. Assumptions

- Three cameras, 2.5 to 3.5 m from the station, 60 to 90 degrees apart, level tripod heads, each view showing the whole body; even light; nothing between a camera and the worker.
- Factory lens calibration is valid (recalibrate after a lens or focus change).
- One worker in frame, doing one repetitive task per take; cycle detection relies on the trunk moving with the task.
- 1080p at 30 fps; the pose model runs on CPU at about 3 fps per view, so processing takes longer than the recording.
- RULA and REBA lookup tables transcribed from the 1993 and 2000 papers, spot-checked against values from the worksheets, full check pending.
- Observer-judgment thresholds (abduction, twist, side bend, shoulder raise) are fixed constants, documented in `ergo.py`.
- Task inputs (load, repetition, grip) are set by the health lead and apply to the whole take.
- The prototype's report data comes from a synthetic worker (`sw/synth.py`); no numbers in the submission are measurements of a person.

## 6. Limitations and known failure modes

- Markerless accuracy for these tasks is not yet validated against a marker-based laboratory system by NODAL. Published multi-camera systems report mean joint-angle errors of 3 to 4.5 degrees against marker-based capture (Uhlrich et al., 2023; Pagnon et al., 2022); the same accuracy for M1 and this pipeline is a target, not a result.
- Inter-camera timing: frames can be up to one frame apart (33 ms at 30 fps); fast movements add error.
- Occlusion, loose clothing, a hand behind the body or a worker turned away lower keypoint confidence; those frames are dropped, which can bias summaries toward easier postures.
- Pose models are trained on public datasets and can be less accurate for some body sizes and clothing; validation across workers is part of the pilot plan.
- RULA and REBA were designed for human observers rating a posture; applying them per frame is an adaptation, and the action levels were not derived for continuous scoring. Human raters themselves agree only moderately (Kee, 2022).
- A single-camera commercial AI tool has shown poor agreement with an expert (Balogh et al., 2025); that is why three views are used and why validation comes before any pilot.
- Camera moved, calibration drift or poor light raise the reprojection error; the quality numbers are shown so a reviewer can distrust a take.
- Not a medical device; no regulatory clearance anywhere.

## 7. Validation plan

Before any pilot:
1. Joint angles against a marker-based laboratory reference on the three task types: target mean absolute error under 5 degrees for trunk and upper arm.
2. RULA and REBA against two trained assessors on the same recordings: target weighted kappa of 0.6 or more.
3. Repeatability: the same task filmed twice gives the same flags.
4. The RULA and REBA tables checked line by line against the official worksheets.

At the pilot (one or two sites, six months): setup time under 15 minutes per station, share of shifts processed without manual fixes, review time per week, worker opt-in rate, share of flagged tasks changed, minutes of high-risk posture per worker per shift before and after, and musculoskeletal complaints, first-aid visits and lost-time cases against the year before.

## 8. Evidence and references

- World Health Organization. Musculoskeletal health, fact sheet, 14 July 2022. 1.71 billion people live with musculoskeletal conditions, the leading contributor to disability worldwide.
- EU-OSHA. Healthy Workplaces campaign 2020 to 2022, musculoskeletal disorders. About three in five EU workers report MSD complaints; MSDs are Europe's most common work-related health problem.
- US Bureau of Labor Statistics. Musculoskeletal disorders fact sheet, 2018 data. MSDs were 30 percent of days-away-from-work cases; 38 to 40 percent for laborers, material movers and order fillers.
- Anwar W, et al. Work-related musculoskeletal disorders and quality of life among construction workers in the UAE. F1000Research 2025;14:80.
- McAtamney L, Corlett EN. RULA: a survey method for the investigation of work-related upper limb disorders. Applied Ergonomics 1993;24(2):91-99.
- Hignett S, McAtamney L. Rapid Entire Body Assessment (REBA). Applied Ergonomics 2000;31(2):201-205.
- Kee D. Systematic comparison of OWAS, RULA, and REBA based on a literature review. IJERPH 2022;19(1):595.
- Uhlrich SD, et al. OpenCap: human movement dynamics from smartphone videos. PLOS Computational Biology 2023;19(10):e1011462. Mean absolute joint-angle error 4.5 degrees against marker-based capture.
- Pagnon D, Domalain M, Reveret L. Pose2Sim, part 2: accuracy. Sensors 2022;22(7):2712. Mean joint-angle errors 3.0 to 4.1 degrees.
- Scataglini S, et al. A systematic review of the accuracy, validity, and reliability of markerless versus marker camera-based 3D motion capture for industrial ergonomic risk analysis. Sensors 2025;25(17):5513. Agreement on RULA and REBA kappa 0.46 to 0.87 across 20 studies.
- Balogh D, et al. Reliability and agreement during the Rapid Entire Body Assessment: comparing rater expertise and artificial intelligence. PLoS One 2025;20(5):e0323262.
- Tompa E, et al. A systematic review of workplace ergonomic interventions with economic analyses. Journal of Occupational Rehabilitation 2010;20(2):220-234.
- Jiang T, et al. RTMPose: real-time multi-person pose estimation based on MMPose. arXiv:2303.07399, 2023. Jiang T, Xie X, Li Y. RTMW: real-time multi-person 2D and 3D whole-body pose estimation. arXiv:2407.08634, 2024.

## 9. How to run it

```
pip install -r requirements.txt            # rtmlib, opencv-python, numpy, scipy, onnxruntime
pip install -r requirements-dev.txt        # pytest
python -m pytest -q                        # 9 tests

# A recorded take (three MP4s and sidecars from the M1 cameras, factory intrinsics in calib/):
python -m sw.pose2d <take_dir>/rx-cam1.mp4 <pose_dir>/rx-cam1 --mode balanced   # one call per camera
python -m sw.recon3d <take_dir> <pose_dir> <calib_dir> <recon_dir>               # skeleton3d.npz + quality JSON
python -m sw.check_overlay <take_dir> <pose_dir> <recon_dir> check.png --at 0.5  # visual check
python -m sw.report_data <recon_dir> web --station K-2 --role picker --load-kg 1.0 [--history history.json]
# then open web/report.html

# Without footage, the synthetic worker:
python -m sw.synth out/synth --cycles 9 --fps 30
python -m sw.report_data out/synth web --history out/synth/history.json
```

`recon3d` expects a `meta.json` next to its output with `data_kind: "measured"` and the quality numbers; `synth` writes one with `data_kind: "synthetic"`. There is no single command that runs the whole chain yet; each step is a module with a command line.

## 10. Third-party components and licenses

| Component | Version on the NODAL server | License | Use |
|---|---|---|---|
| rtmlib | 0.0.16 | Apache 2.0 | runs the pose model |
| RTMW / RTMPose model weights (OpenMMLab) | as downloaded by rtmlib | Released with MMPose under Apache 2.0 | 2D whole-body pose |
| onnxruntime | 1.23.2 | MIT | model inference |
| opencv-python-headless | 5.0.0.93 | Apache 2.0 | undistortion, PnP, triangulation |
| NumPy | 2.2.6 | BSD 3-Clause | arrays |
| SciPy | 1.15.3 | BSD 3-Clause | bundle adjustment |
| RULA, REBA | published methods | cited; worksheets not reproduced | scoring |
| Space Grotesk, IBM Plex Mono (fonts, via Google Fonts) | | SIL Open Font License | the report page |

No GPL or AGPL components. NODAL's own pose software (NODAL Pose) is not used. NODAL's M1 hardware, firmware, capture and calibration software are pre-existing and are used as tools; they are not part of the submitted materials.
