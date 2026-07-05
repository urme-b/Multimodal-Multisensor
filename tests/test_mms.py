"""Unit tests for the shared analysis package `mms`.

Unlike the smoke tests (which only prove files parse), these check that the
metrics compute the *right numbers* — including regression guards for the two
bugs this package was created to fix (broadcast SDNN, uncorrected multiplicity)
and a reproduction check for the README's headline ICC values.
"""
import numpy as np
import pandas as pd
import pytest

import mms


def test_icc1_reproduces_readme_hrv_value():
    """mms.stats.icc1 reproduces the README's HRV ICC (~0.22) with a wide CI."""
    g = mms.io.load_group_summary("HRV_SDNN")
    mat = g[["Session 01", "Session 02", "Session 03"]].to_numpy(float)
    res = mms.stats.icc1(mat)
    assert res["icc"] == pytest.approx(0.22, abs=0.02)
    lo, hi = res["ci95"]
    assert lo < 0 < hi  # the interval crosses zero -> uninformative at n=10


def test_icc1_perfect_agreement_is_one():
    data = np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]])
    assert mms.stats.icc1(data)["icc"] == pytest.approx(1.0, abs=1e-9)


def test_sdnn_filters_artifacts_and_zeros():
    # zeros and out-of-range beats must be dropped before computing SD
    beats = pd.Series([800, 810, 0, 790, 5000, 805])
    expected = pd.Series([800, 810, 790, 805]).std(ddof=1)
    assert mms.hrv.sdnn(beats) == pytest.approx(expected)


def test_hrv_over_time_is_not_a_broadcast_scalar():
    """Regression guard for the original bug: SDNN must vary across windows."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "reltime": np.arange(0, 300, 0.8),
        "ibi": 800 + rng.normal(0, 40, len(np.arange(0, 300, 0.8))),
    })
    ts = mms.hrv.hrv_over_time(df, window_s=30)
    assert len(ts) > 1
    assert ts["sdnn"].nunique() > 1


def test_benjamini_hochberg_is_monotone_and_bounded():
    p = [0.001, 0.01, 0.04, 0.5, 0.9]
    adj = mms.stats.benjamini_hochberg(p)
    assert np.all(adj >= np.array(p) - 1e-12)      # adjusted >= raw
    assert np.all((adj >= 0) & (adj <= 1))
    assert np.all(np.diff(adj) >= -1e-12)          # preserves order


def test_corr_matrix_fdr_shrinks_significance():
    """FDR correction should not INCREASE the count of significant pairs."""
    g = pd.concat([
        mms.io.load_group_summary("HRV_SDNN").set_index("Participant").add_suffix("_HRV"),
        mms.io.load_group_summary("Pupil_Dilation_STD").set_index("Participant").add_suffix("_Pupil"),
    ], axis=1)
    res = mms.stats.corr_matrix_fdr(g)
    n = res["r"].shape[0]
    iu = np.triu_indices(n, k=1)
    sig_raw = int((res["p_raw"].values[iu] < 0.05).sum())
    sig_fdr = int((res["p_fdr"].values[iu] < 0.05).sum())
    assert sig_raw > 0  # guard is meaningful only if raw finds something to shrink
    assert sig_fdr <= sig_raw
