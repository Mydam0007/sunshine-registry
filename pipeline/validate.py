"""Checks the staged rows before anything goes into the registry.

Rows that fail a critical check get dropped: no patient name, a date of
birth that does not parse, a diagnosis date that is missing, unparseable,
or in the future, a diagnosis code the registry does not accept, or an
age at diagnosis outside 20-100. Duplicate report IDs keep the first
occurrence and drop the rest.

Two soft fixes: a county that is not a Florida county becomes "Unknown",
and a sex value outside F/M becomes "Unknown". Both get counted, and the
row stays in.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .generate import COUNTIES, VALID_CODES
from .ingest import STAGING_TABLE

FLORIDA_COUNTIES = set(COUNTIES)


def _standardize_county(value: str) -> str:
    """Turn "hillsborough county" or "Hillsborough County" into Hillsborough."""
    clean = value.strip().removesuffix(" County").removesuffix(" county").strip()
    for county in FLORIDA_COUNTIES:
        if clean.lower() == county.lower():
            return county
    return "Unknown"


def validate(db_path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Validate the staging table. Returns (clean_df, report)."""
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(f"SELECT * FROM {STAGING_TABLE}", conn, dtype=str).fillna("")

    report: dict = {
        "rows_in": int(len(df)),
        "excluded_rows": 0,
        "exclusion_reasons": {},
        "standardized_values": {},
        "null_counts_before": {},
    }
    work = df.copy()
    excluded = pd.Series(False, index=work.index)

    def exclude(mask: pd.Series, reason: str) -> None:
        nonlocal excluded
        new = mask & ~excluded
        count = int(new.sum())
        if count:
            report["exclusion_reasons"][reason] = count
            excluded = excluded | new

    # --- Critical checks: row-level exclusion ---
    exclude(work["full_name"].str.strip() == "", "missing_patient_name")

    dup = work["report_id"].duplicated(keep="first") & (work["report_id"] != "")
    exclude(dup, "duplicate_report_id")

    dob = pd.to_datetime(work["date_of_birth"], errors="coerce")
    exclude(dob.isna(), "unparseable_date_of_birth")

    dx = pd.to_datetime(work["diagnosis_date"], errors="coerce")
    exclude(work["diagnosis_date"].str.strip() == "", "missing_diagnosis_date")
    exclude(dx.isna() & (work["diagnosis_date"].str.strip() != ""), "unparseable_diagnosis_date")
    exclude(dx > pd.Timestamp("2026-10-31"), "diagnosis_date_in_future")

    bad_code = ~work["diagnosis_code"].isin(VALID_CODES)
    exclude(bad_code, "invalid_diagnosis_code")

    age_years = (dx - dob).dt.days / 365.25
    bad_age = (age_years < 20) | (age_years > 100)
    exclude(bad_age.fillna(False), "age_at_diagnosis_outside_20_100")

    # --- Soft fixes: standardize the value, keep the row ---
    standardized = work["county"].map(_standardize_county)
    changed = int((standardized != work["county"]).sum())
    if changed:
        report["standardized_values"]["county"] = changed
    work["county"] = standardized

    bad_sex = ~work["sex"].isin(["F", "M"])
    fixed_sex = int((bad_sex & ~excluded).sum())
    if fixed_sex:
        report["standardized_values"]["sex_to_unknown"] = fixed_sex
    work.loc[bad_sex, "sex"] = "Unknown"

    clean = work.loc[~excluded].copy()
    report["excluded_rows"] = int(excluded.sum())
    report["rows_out"] = int(len(clean))
    return clean, report
