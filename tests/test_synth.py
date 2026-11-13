"""The synthetic worker: every station profile produces a usable skeleton and a report."""
import numpy as np

from sw import synth


def test_every_profile_generates_finite_skeletons():
    for name in synth.PROFILES:
        X = synth.generate(cycles=2, fps=10, seed=1, profile=name)
        placed = ~np.isnan(X[0, :, 0])
        assert X.shape[1:] == (133, 3)
        assert placed.sum() > 20, name
        assert np.isfinite(X[:, placed]).all(), name
        cycle_s = sum(p[1] for p in synth.PROFILES[name])
        assert X.shape[0] == round(2 * cycle_s * 10), name


def test_profiles_differ_in_posture():
    """Restock reaches overhead more than packing; assembly bends the neck more than kitting."""
    def peak_arm(name):
        return max(p[3] for p in synth.PROFILES[name])

    def mean_neck(name):
        ph = synth.PROFILES[name]
        return sum(p[1] * p[5] for p in ph) / sum(p[1] for p in ph)

    assert peak_arm("restock") > peak_arm("packing")
    assert mean_neck("assembly") > mean_neck("kitting")
