"""Builds the registry from the validated rows.

The same person can be reported by two providers. Patients are matched on
a salted hash of name plus date of birth, so no raw identifiers land in
the registry tables. Each patient gets one registry record: the earliest
diagnosis date across their reports, the code and county from that
earliest report, and a count of how many providers reported them.

Two tables go into SQLite: registry_patients (one row per person) and
registry_reports (one row per accepted provider report).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_SALT = "dev-salt-change-me"

PATIENTS_TABLE = "registry_patients"
REPORTS_TABLE = "registry_reports"


def get_salt(explicit: str | None = None) -> tuple[str, bool]:
    """Return (salt, used_default)."""
    salt = explicit or os.environ.get("PIPELINE_SALT")
    if salt:
        return salt, False
    return DEFAULT_SALT, True


def _hash(value: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()


def integrate(clean: pd.DataFrame, salt: str, db_path: str | Path) -> dict:
    """Dedupe patients, build the registry tables, return counts."""
    work = clean.copy()
    key = (
        work["full_name"].str.strip().str.lower()
        + "|"
        + work["date_of_birth"].str.strip()
    )
    work["patient_hash"] = key.map(lambda v: _hash(v, salt))
    work["diagnosis_date"] = pd.to_datetime(work["diagnosis_date"])
    work["date_of_birth"] = pd.to_datetime(work["date_of_birth"])
    work["birth_year"] = work["date_of_birth"].dt.year
    work["age_at_diagnosis"] = ((work["diagnosis_date"] - work["date_of_birth"]).dt.days / 365.25).round(1)

    work = work.sort_values("diagnosis_date")
    first = work.groupby("patient_hash").first().reset_index()

    patients = pd.DataFrame(
        {
            "patient_hash": first["patient_hash"],
            "birth_year": first["birth_year"],
            "sex": first["sex"],
            "first_diagnosis_date": first["diagnosis_date"].dt.strftime("%Y-%m-%d"),
            "diagnosis_code": first["diagnosis_code"],
            "county": first["county"],
            "providers_reporting": work.groupby("patient_hash")["provider"].nunique().values,
            "reports_received": work.groupby("patient_hash").size().values,
        }
    )
    reports = pd.DataFrame(
        {
            "report_id": work["report_id"],
            "patient_hash": work["patient_hash"],
            "provider": work["provider"],
            "report_date": work["report_date"],
            "diagnosis_date": work["diagnosis_date"].dt.strftime("%Y-%m-%d"),
            "diagnosis_code": work["diagnosis_code"],
            "county": work["county"],
        }
    )

    with sqlite3.connect(db_path) as conn:
        patients.to_sql(PATIENTS_TABLE, conn, if_exists="replace", index=False)
        reports.to_sql(REPORTS_TABLE, conn, if_exists="replace", index=False)

    return {
        "patients": int(len(patients)),
        "reports": int(len(reports)),
        "patients_reported_twice": int((patients["providers_reporting"] > 1).sum()),
    }
