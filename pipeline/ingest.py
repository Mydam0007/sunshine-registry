"""Reads the three provider files, maps each one onto the same columns, and
loads everything into a staging table in SQLite. Nothing is cleaned here;
that comes later, in validation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .generate import CANONICAL_COLUMNS, PROVIDER_B_COLUMNS

STAGING_TABLE = "staging_reports"

# Provider B's file uses its own column names; map them back.
RENAME_B = {v: k for k, v in PROVIDER_B_COLUMNS.items()}


def ingest(raw_dir: str | Path, db_path: str | Path) -> dict[str, int]:
    """Load every provider file into staging. Returns rows per file."""
    raw_dir = Path(raw_dir)
    counts: dict[str, int] = {}
    frames = []
    for path in sorted(raw_dir.glob("provider_*.csv")):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        if "ReportID" in df.columns:
            # Provider B: rename columns, parse US dates back to ISO.
            df = df.rename(columns=RENAME_B)
            for col in ["date_of_birth", "diagnosis_date", "report_date"]:
                parsed = pd.to_datetime(df[col], format="%m/%d/%Y", errors="coerce")
                iso = parsed.dt.strftime("%Y-%m-%d")
                # Keep the original text when it does not parse, so
                # validation can see it and count it.
                df[col] = iso.where(parsed.notna(), df[col])
        df = df[[c for c in CANONICAL_COLUMNS if c in df.columns]]
        df["source_file"] = path.name
        frames.append(df)
        counts[path.name] = int(len(df))

    staged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        staged.to_sql(STAGING_TABLE, conn, if_exists="replace", index=False)
    return counts
