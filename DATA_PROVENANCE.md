# Data Provenance & Reproducibility

This document states, honestly, **what in this repository can be regenerated
from committed data and what cannot** — the question a reviewer or reuser asks
first. It also documents the raw→processed→summary pipeline and known data
issues. It complements [DATA_ETHICS.md](DATA_ETHICS.md) (consent, GDPR,
de-identification).

## TL;DR reproducibility status

| Layer | Regenerable from this repo? | How |
|-------|-----------------------------|-----|
| Headline reliability numbers (ICC) | ✅ Yes | `mms.stats.icc1` on `data/group_results/*.csv` — reproduces the README's 0.22 / 0.45 / 0.61 **and** adds the 95% CIs |
| Case-study participant's summary row (= **P02**) | ✅ Yes, exactly | `python pipeline/build_group_summaries.py` |
| Group summary rows for the other 9 participants | ❌ No | Their raw streams were not released (privacy) — see below |
| Case-study per-session figures (HR, HRV, fixation, clustering) | ✅ Yes | Run the `case-study/` notebooks (data present) |

## The layers

```
data/case-study/raw/*.txt          # sensor exports (semicolon-delimited), one participant
        │  (parsing, column rename, derived fixation/duration columns)
        ▼
data/case-study/processed/*.csv    # tidy per-session streams: hr_0N, ibi_0N, sed_fix_0N
        │  (per-session summary statistics — see mms/)
        ▼
data/group_results/*.csv           # one row per participant, one column per session
```

- **raw → processed**: the raw `.txt` files are semicolon-delimited and use
  dotted names (`gazeDir.x`); the processed `.csv` files are comma-delimited,
  rename gaze columns, and add derived `fixation`, `fixation_id`, `duration`,
  and `gaze_diff` columns. Only the case-study participant's raw files are
  present, so only that participant's processed layer is regenerable end-to-end.
- **processed → summary**: `pipeline/build_group_summaries.py` computes SDNN,
  pupil-diameter STD and response-duration STD per session. It reproduces the
  committed **P02** row exactly (verified to < 1e-6; see
  `data/group_results/reconstructed/MANIFEST.json`).

## Why only one participant is regenerable

The case-study streams correspond to participant **P02** in the group tables.
This was verified, not assumed: the case-study IBI, pupil and duration data
reproduce the committed P02 row for all three metrics **exactly**. The raw
streams for P01 and P03–P10 were **not released** — a deliberate,
privacy-legitimate minimisation choice (only pseudonymised summaries are shared;
see DATA_ETHICS.md). Consequently their summary rows are provided *as released
values* and cannot be recomputed from this repository. `build_group_summaries.py`
does **not** invent them.

## Two recipes: original vs improved

`build_group_summaries.py` reports both, so the choice is explicit:

- **Original recipe** (reproduces the committed values): `ibi.std()` and
  `pupil.std()` with **no artifact filtering**. This is faithful to how the
  committed summaries were made, but it lets dropped beats and blink artifacts
  inflate variance — e.g. P02's Session-2 pupil STD of **1.12** is an artifact
  spike, ~4× the other sessions.
- **Improved recipe** (recommended going forward): `mms.hrv.sdnn` applies a
  300–2000 ms normal-to-normal filter; `mms.fixation.pupil_std` gates on the
  `pupilQ` quality flag. These are more defensible and remove the S2 spike.

## Known data-integrity issues

- **P01 HRV SDNN, Session 02 == Session 03 (both 65.39).** These two values are
  byte-identical, a suspected copy-paste artifact, and the archived technical
  report lists a different P01 Session-3 value. Because P01's raw data is not in
  the repo, **the correct value cannot be recovered here**, so it has been
  *flagged and left unmodified* rather than guessed. The data owner should
  restore it from the original source. `tests/test_data_integrity.py` now fails
  loudly if an undocumented duplicate like this appears in a group summary.

## `_modified` psychometric files

`data/case-study/psychometric/*_modified.csv` drop the `Type` column, add a
parsed `datetime` column, and reformat timestamps relative to the originals.
They are analysis conveniences derived from the canonical
`Psychometric_Test_Results_0N.csv` files; the originals are authoritative.
