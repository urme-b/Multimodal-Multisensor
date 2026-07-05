"""Statistics for a small within-subject design: ICC with CIs, FDR-corrected correlations."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def icc1(data) -> dict:
    """ICC(1,1) one-way random-effects reliability with a 95% CI.

    ``data`` has shape (n_subjects, k_ratings) — here participants × sessions.
    Returns ``icc``, ``ci95``, ``n``, ``k``, ``F`` (Shrout & Fleiss 1979).
    """
    x = np.asarray(data, dtype=float)
    x = x[~np.isnan(x).any(axis=1)]
    n, k = x.shape
    grand = x.mean()
    ms_between = k * ((x.mean(axis=1) - grand) ** 2).sum() / (n - 1)
    ms_within = ((x - x.mean(axis=1, keepdims=True)) ** 2).sum() / (n * (k - 1))
    denom = ms_between + (k - 1) * ms_within
    icc = (ms_between - ms_within) / denom if denom else float("nan")

    # CI is undefined without within-subject variance (perfect agreement).
    if ms_within == 0:
        return {"icc": float(icc), "ci95": (float("nan"), float("nan")),
                "n": int(n), "k": int(k), "F": float("inf")}

    f = ms_between / ms_within
    f_lo = f / stats.f.ppf(0.975, n - 1, n * (k - 1))
    f_hi = f * stats.f.ppf(0.975, n * (k - 1), n - 1)
    lower = (f_lo - 1) / (f_lo + (k - 1))
    upper = (f_hi - 1) / (f_hi + (k - 1))
    return {"icc": float(icc), "ci95": (float(lower), float(upper)),
            "n": int(n), "k": int(k), "F": float(f)}


def benjamini_hochberg(pvals) -> np.ndarray:
    """Benjamini-Hochberg FDR-adjusted p-values, in the input order."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    adj = p[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(adj, 0, 1)
    return out


def corr_matrix_fdr(df: pd.DataFrame) -> dict:
    """Pearson correlation matrix with raw and FDR-adjusted p-values.

    Returns ``{'r', 'p_raw', 'p_fdr', 'n_tests'}``. Judge significance across the
    whole matrix on ``p_fdr``, not ``p_raw``.
    """
    cols = list(df.columns)
    n = len(cols)
    r = np.eye(n)
    p_raw = np.ones((n, n))
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = df[cols[i]], df[cols[j]]
            mask = a.notna() & b.notna()
            rr, pp = (stats.pearsonr(a[mask], b[mask]) if mask.sum() >= 3
                      else (np.nan, 1.0))
            r[i, j] = r[j, i] = rr
            p_raw[i, j] = p_raw[j, i] = pp
            pairs.append((i, j, pp))

    p_fdr = np.ones((n, n))
    for (i, j, _), pa in zip(pairs, benjamini_hochberg([p for *_, p in pairs])):
        p_fdr[i, j] = p_fdr[j, i] = pa

    frame = lambda m: pd.DataFrame(m, index=cols, columns=cols)
    return {"r": frame(r), "p_raw": frame(p_raw), "p_fdr": frame(p_fdr),
            "n_tests": len(pairs)}
