"""Lightweight data smoke test: every committed CSV must load and be non-trivial.

Catches corrupted, truncated, or empty data files before they silently break a
notebook. CSVs are discovered automatically, so newly committed data is covered
without touching this test.
"""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CSV_FILES = sorted(
    p for p in ROOT.rglob("*.csv") if ".ipynb_checkpoints" not in p.parts
)


def test_csv_files_present():
    assert CSV_FILES, "No CSV files found in the repository."


@pytest.mark.parametrize(
    "path", CSV_FILES, ids=[str(p.relative_to(ROOT)) for p in CSV_FILES]
)
def test_csv_loads_and_is_non_trivial(path):
    rel = path.relative_to(ROOT)
    assert path.stat().st_size > 0, f"{rel} is a zero-byte file"
    df = pd.read_csv(path)
    assert df.shape[0] >= 1, f"{rel} has no data rows"
    assert df.shape[1] >= 1, f"{rel} has no columns"


# --- Group-summary integrity ------------------------------------------------
# Exact byte-identical values across two sessions of a *continuous* physiological
# measure are a copy-paste red flag, not real data. One such case is already
# known and documented (see DATA_PROVENANCE.md); it is allow-listed so CI stays
# green, while any NEW, undocumented duplicate fails the build.
GROUP_SUMMARIES = sorted((ROOT / "data" / "group_results").glob("*.csv"))
KNOWN_SESSION_DUPLICATES = {
    ("HRV_SDNN.csv", "P01"),  # Session 02 == Session 03; source data not in repo
}


@pytest.mark.parametrize(
    "path", GROUP_SUMMARIES, ids=[p.name for p in GROUP_SUMMARIES]
)
def test_no_undocumented_session_duplicates(path):
    df = pd.read_csv(path)
    session_cols = [c for c in df.columns if c.lower().startswith("session")]
    if "Participant" not in df.columns or len(session_cols) < 2:
        pytest.skip("not a participant-by-session summary")

    offenders = []
    for _, row in df.iterrows():
        vals = [float(row[c]) for c in session_cols]
        allowed = (path.name, str(row["Participant"])) in KNOWN_SESSION_DUPLICATES
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                if vals[i] == vals[j] and not allowed:
                    offenders.append((row["Participant"], session_cols[i],
                                      session_cols[j], vals[i]))
    assert not offenders, (
        f"Undocumented exact session duplicates in {path.name}: {offenders}. "
        "If real, document in DATA_PROVENANCE.md and add to KNOWN_SESSION_DUPLICATES."
    )
