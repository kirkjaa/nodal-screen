# T03: synthetic movement generator

Branch `t03-gaitsynth`. Read `AGENTS.md` first. Look at `sw/synth.py` for the house style (it makes a synthetic worker for Strain Watch); this is the same idea for walking and the screening tests.

The output must be believable to a gait engine: feet that stay planted in stance, clean heel strikes and toe-offs, constant bone lengths. Build it footstep-first, not angle-first.

## Output format

`screen/gaitsynth.py` writes one `.npz` per task with:

- `kp` (T, 23, 3) float, millimetres, lab frame: x forward along the walkway, y left, z up, floor at z = 0. Joints in COCO-WholeBody order: the 17 COCO body points (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles), then left big toe, left small toe, left heel, right big toe, right small toe, right heel.
- `conf` (T, 23) keypoint confidence; `fps` (60 by default); `truth`: a JSON string with every parameter used and the true events (heel strike and toe-off frame per side, step lengths, task start and end frames).

## Parameters (dataclass `Person` plus a task)

age_y, sex, height_m (if not given, a plausible height for age and sex; say in a comment where the numbers come from or mark them as rough), speed_m_s, cadence_spm, step_length asymmetry (%), step-time asymmetry (%), step-time variability CV (%), toe_walk (bool or share of strides), reduced knee flexion on one side (deg), arm swing scale, noise_mm, dropout share (NaN runs).

Segment lengths from height with Winter's anthropometric ratios (Winter, Biomechanics and Motor Control of Human Movement, 4th ed., table 4.1); cite them in a comment.

## Method

1. **Footsteps first.** Lay out alternating foot placements along x with the step lengths and step times (asymmetry and variability applied), plus about 2 m to speed up and 2 m to slow down around a 10 m walk.
2. **Stance foot fixed** on the floor between heel strike and toe-off (heel and toes in contact, then the heel rises before toe-off). Stance about 60 % of the cycle at normal speed, falling slightly as speed rises.
3. **Swing foot** follows a minimum-jerk path with a toe-clearance peak of about 1 to 2 cm; heel first at contact, unless `toe_walk` makes that stride land toe first with the heel staying 3 to 6 cm up through stance.
4. **Pelvis** moves forward at the step-driven speed, with about 2 to 5 cm vertical and a little lateral sway at step frequency. Hips from the pelvis and hip width.
5. **Knees** by two-link inverse kinematics from hip to ankle with fixed thigh and shank lengths, knee bending forward. Reduced knee flexion on one side shortens that side's swing clearance and adds circumduction.
6. **Trunk, arms and head** follow the pelvis with arm swing opposite to the legs.
7. Then add Gaussian noise and the NaN dropout runs, and lower `conf` where there is dropout.

## Tasks

`walk10(person)`, `tug(person, total_s)` (sit on a 0.45 m chair, stand, walk 3 m, turn 180 degrees, walk back, turn, sit), `sts5(person, total_s)` (five full rises from the chair, arms crossed), `sls(person, side, hold_s)` (stand, lift one foot about 10 cm, hold, put it down). A command line: `python -m screen.gaitsynth --preset <name> --out data/raw/<name>/` writing one `.npz` per task.

Presets (the featured synthetic participants; all values are inputs for the demo, not claims about real people):

| Preset | Person | Shape of the movement |
|---|---|---|
| `child-typical-6` | 6 y, F | typical for age |
| `child-toewalk-7` | 7 y, F | 80 % of strides toe first, both sides |
| `child-coord-8` | 8 y, M | step-time CV about 9 %, single-leg stance short |
| `child-lowdata-5` | 5 y, M | dropout 40 %, noise 25 mm |
| `adult-typical-45` | 45 y, M | typical |
| `adult-falls-72` | 72 y, F | 0.85 m/s, TUG about 13.5 s, single-leg stance about 4 s |
| `adult-sarco-78` | 78 y, M | 0.75 m/s, five sit-to-stands about 16 s |
| `adult-asym-64` | 64 y, M | step-length asymmetry about 18 %, reduced right knee flexion 20 degrees |
| `adult-decline-69` | 69 y, F | three yearly visits: 1.15, 1.05, 0.94 m/s (three walk files: `v1`, `v2`, `v3`) |

## Tests `tests/test_gaitsynth.py`

Without noise: bone lengths constant within 1 mm; stance foot moves under 5 mm between heel strike and toe-off; walking speed over the middle 6 m within 2 % of the input; mean step length within 1 cm of the input per side; true events in `truth` agree with foot height crossing 1 cm within one frame; toe-walk strides have the heel above 3 cm at contact; TUG, sit-to-stand and single-leg durations within 0.1 s of the input. With noise and dropout: the shapes and NaN share are as asked. Runs in under 30 s.

## Done when

Tests pass, the nine presets write without error, and the done note includes a small side-view plot per preset (`out/gaitsynth/<preset>.png`, matplotlib allowed) of foot heights over time with the true events marked.
