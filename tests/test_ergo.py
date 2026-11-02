"""Scoring sanity checks on synthetic skeletons.

The table spot checks repeat values from the published RULA and REBA worksheets;
the posture checks confirm the angles move the scores the right way.
"""

import numpy as np

from sw import ergo
from sw.ergo import TaskInputs


def standing(frames=1):
    """Upright person facing +y, arms hanging, elbows bent 80 degrees forward."""
    X = np.full((frames, 133, 3), np.nan)
    p = {
        ergo.NOSE: (0, 0.10, 1.62), ergo.L_EAR: (-0.07, 0.0, 1.62), ergo.R_EAR: (0.07, 0.0, 1.62),
        ergo.L_EYE: (-0.03, 0.08, 1.65), ergo.R_EYE: (0.03, 0.08, 1.65),
        ergo.L_SH: (-0.20, 0, 1.45), ergo.R_SH: (0.20, 0, 1.45),
        ergo.L_EL: (-0.20, 0, 1.15), ergo.R_EL: (0.20, 0, 1.15),
        ergo.L_HIP: (-0.10, 0, 0.95), ergo.R_HIP: (0.10, 0, 0.95),
        ergo.L_KN: (-0.10, 0, 0.50), ergo.R_KN: (0.10, 0, 0.50),
        ergo.L_AN: (-0.10, 0, 0.08), ergo.R_AN: (0.10, 0, 0.08),
    }
    for side, el, hand in (("l", ergo.L_EL, ergo.L_HAND), ("r", ergo.R_EL, ergo.R_HAND)):
        x = p[el][0]
        # forearm 80 degrees forward of straight down, 0.26 m long
        a = np.radians(80)
        wrist = (x, 0.26 * np.sin(a), 1.15 - 0.26 * np.cos(a))
        p[{"l": ergo.L_WR, "r": ergo.R_WR}[side]] = wrist
        fore = np.array([0, np.sin(a), -np.cos(a)])
        w = np.array(wrist)
        p[hand["wrist"]] = tuple(w)
        p[hand["middle"]] = tuple(w + 0.08 * fore)
        p[hand["index"]] = tuple(w + 0.08 * fore + np.array([0.02, 0, 0]))
        p[hand["pinky"]] = tuple(w + 0.07 * fore + np.array([-0.02, 0, 0]))
    for j, xyz in p.items():
        X[:, j] = xyz
    return X


def bend_trunk(X, deg):
    """Rotate everything above the hips forward about the hip axis."""
    Y = X.copy()
    hip = (X[0, ergo.L_HIP] + X[0, ergo.R_HIP]) / 2
    a = np.radians(deg)
    R = np.array([[1, 0, 0], [0, np.cos(a), np.sin(a)], [0, -np.sin(a), np.cos(a)]])
    upper = [j for j in range(133) if not np.isnan(X[0, j, 0])
             and j not in (ergo.L_HIP, ergo.R_HIP, ergo.L_KN, ergo.R_KN, ergo.L_AN, ergo.R_AN)]
    Y[:, upper] = (X[:, upper] - hip) @ R.T + hip
    return Y


def test_table_spot_checks():
    assert ergo.RULA_A.shape == (6, 3, 4, 2)
    assert ergo.RULA_B.shape == (6, 6, 2)
    assert ergo.RULA_C.shape == (8, 7)
    assert ergo.REBA_A.shape == (3, 5, 4)
    assert ergo.REBA_B.shape == (2, 6, 3)
    assert ergo.REBA_C.shape == (12, 12)
    assert ergo.RULA_A[0, 0, 0, 0] == 1 and ergo.RULA_A[5, 2, 3, 1] == 9
    assert ergo.RULA_C[0, 0] == 1 and ergo.RULA_C[7, 6] == 7
    assert ergo.REBA_C[0, 0] == 1 and ergo.REBA_C[11, 11] == 12


def test_upright_angles_are_neutral():
    a = ergo.angles(standing())
    assert abs(a["trunk_flexion"][0]) < 1
    assert abs(a["left_upper_arm_flexion"][0]) < 1
    assert 79 < a["left_elbow_flexion"][0] < 81
    assert a["left_wrist_flexion"][0] < 1


def test_upright_scores_low():
    s = ergo.score_take(standing(), TaskInputs(repeated_over_4_per_min=False))
    assert s["valid"][0]
    assert s["rula_left"]["score"][0] <= 2
    assert s["reba_left"]["score"][0] <= 3


def test_bending_raises_scores():
    calm = TaskInputs(repeated_over_4_per_min=False)
    base = ergo.score_take(standing(), calm)
    bent = ergo.score_take(bend_trunk(standing(), 70), calm)
    assert 69 < ergo.angles(bend_trunk(standing(), 70))["trunk_flexion"][0] < 71
    assert bent["rula_left"]["trunk"][0] == 4
    assert bent["reba_left"]["trunk"][0] == 4
    assert bent["rula_left"]["score"][0] > base["rula_left"]["score"][0]
    assert bent["reba_left"]["score"][0] > base["reba_left"]["score"][0]


def test_load_raises_force_score():
    light = ergo.score_take(standing(), TaskInputs(load_kg=1, repeated_over_4_per_min=False))
    heavy = ergo.score_take(standing(), TaskInputs(load_kg=12, repeated_over_4_per_min=True))
    assert heavy["rula_left"]["score_a"][0] >= light["rula_left"]["score_a"][0] + 3


def test_bending_the_trunk_does_not_raise_the_shoulder():
    """A take that mixes upright and bent frames: the shoulder flag must not follow the trunk."""
    X = np.concatenate([standing(30), bend_trunk(standing(30), 60)])
    a = ergo.angles(X)
    assert not a["right_shoulder_raised"].any()
    assert not a["left_shoulder_raised"].any()
