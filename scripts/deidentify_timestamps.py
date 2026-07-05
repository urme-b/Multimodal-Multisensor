#!/usr/bin/env python3
"""Shift absolute timestamps to relative session time (privacy hardening).

Absolute appointment date + start time is a re-identification vector for an n=10
cohort. This anchors each session at ``2000-01-01T00:00:00``, removing the
wall-clock date/time while preserving relative timings.

- **Dry-run by default**; ``--apply`` writes in place, ``--apply --out DIR`` writes copies.
- **Alignment-preserving**: files sharing a (folder, session) shift by one offset,
  so cross-stream joins still line up.
- **Format-preserving**: slash or ISO-8601 output as in the source.

Scope: per-session streams + psychometric originals. Aggregates (``QQ*``) and
``*_modified`` files are left alone.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = pd.Timestamp("2000-01-01T00:00:00")

# column -> ("slash" | "iso") output format
TIME_COLUMNS = {
    "datetime": "slash",
    "Question Start Time": "iso",
    "Question Answer Time": "iso",
}
SLASH_FMT = "%Y/%m/%d %H:%M:%S.%f"


def session_key(path: Path) -> str:
    """Group files that must share a time origin: (folder, session suffix)."""
    folder = path.relative_to(ROOT).parts[1]  # case-study | individual
    m = re.search(r"_(\d{2})(?:_modified)?\.csv$", path.name)
    sess = m.group(1) if m else "baseline"
    return f"{folder}/{sess}"


def _parse(series: pd.Series, fmt: str) -> pd.Series:
    return pd.to_datetime(series, format=SLASH_FMT if fmt == "slash" else None,
                          utc=(fmt == "iso"), errors="coerce")


def _emit(ts: pd.Series, fmt: str) -> pd.Series:
    if fmt == "slash":
        return ts.dt.strftime(SLASH_FMT).str.slice(0, -2)  # trim to .ffff (4 dp)
    return ts.dt.strftime("%Y-%m-%dT%H:%M:%S.") + \
        (ts.dt.microsecond // 1000).astype(str).str.zfill(3) + "Z"


def collect() -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for path in sorted(ROOT.glob("data/*/**/*.csv")):
        if "_modified" in path.name or path.name.startswith("QQ"):
            continue
        cols = pd.read_csv(path, nrows=0).columns
        if any(c in TIME_COLUMNS for c in cols):
            groups.setdefault(session_key(path), []).append(path)
    return groups


def group_offset(paths: list[Path]) -> pd.Timedelta:
    mins = []
    for p in paths:
        df = pd.read_csv(p)
        for col, fmt in TIME_COLUMNS.items():
            if col in df.columns:
                t = _parse(df[col], fmt)
                if t.notna().any():
                    mins.append(t.min().tz_localize(None) if t.dt.tz else t.min())
    return min(mins) - ANCHOR if mins else pd.Timedelta(0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--out", type=Path, help="write copies under this dir instead of in place")
    args = ap.parse_args()

    groups = collect()
    total = sum(len(v) for v in groups.values())
    print(f"{'APPLY' if args.apply else 'DRY-RUN'}: {total} files across "
          f"{len(groups)} (folder, session) groups\n")

    for key, paths in groups.items():
        offset = group_offset(paths)
        print(f"[{key}] shift -{offset}  ({len(paths)} files)")
        if not args.apply:
            continue
        for p in paths:
            df = pd.read_csv(p)
            for col, fmt in TIME_COLUMNS.items():
                if col in df.columns:
                    shifted = _parse(df[col], fmt)
                    shifted = (shifted.dt.tz_localize(None) if fmt == "iso" else shifted) - offset
                    df[col] = _emit(shifted, fmt)
            dest = (args.out / p.relative_to(ROOT)) if args.out else p
            dest.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(dest, index=False)

    if not args.apply:
        print("\nNo files written. Re-run with --apply to shift timestamps in place,")
        print("or --apply --out data_deid/ to write de-identified copies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
