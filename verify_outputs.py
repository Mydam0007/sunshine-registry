#!/usr/bin/env python3
"""Checks the registry outputs after a run: no patient identifiers left in
any output file, hashes look right, row counts add up, and the reporting
CSVs match the database.

Run it from the project root, after a run: python verify_outputs.py
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
DB = OUT / "registry.db"
REPORT = OUT / "registry_report.json"
AUDIT = OUT / "audit_log.jsonl"

fails: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def main() -> int:
    for name in [
        "registry.db",
        "registry_report.json",
        "registry_report.md",
        "monthly_counts.csv",
        "provider_completeness.csv",
        "county_counts.csv",
        "registry_dashboard.html",
        "audit_log.jsonl",
    ]:
        check(f"output exists: {name}", (OUT / name).exists())

    dashboard = (OUT / "registry_dashboard.html").read_text(encoding="utf-8")
    report = json.loads(REPORT.read_text())
    check("dashboard is self-contained HTML", dashboard.startswith("<!DOCTYPE html>"))
    check("dashboard has a monthly bar chart", "<svg" in dashboard and "<rect" in dashboard)
    check(
        "dashboard shows the patient total",
        str(report["patients_in_registry"]) in dashboard,
    )

    with sqlite3.connect(DB) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        check(
            "tables exist: staging, patients, reports",
            {"staging_reports", "registry_patients", "registry_reports"} <= tables,
        )
        patients = pd.read_sql("SELECT * FROM registry_patients", conn)
        reports = pd.read_sql("SELECT * FROM registry_reports", conn)
        staged = pd.read_sql("SELECT * FROM staging_reports", conn)

    # 1. Patient hashes are 64-char hex and unique.
    hexre = re.compile(r"^[0-9a-f]{64}$")
    check("patient_hash all 64-hex", patients["patient_hash"].astype(str).str.match(hexre).all())
    check("patient_hash unique", patients["patient_hash"].is_unique)
    check("report patient_hash all in registry", set(reports["patient_hash"]) <= set(patients["patient_hash"]))

    # 2. No raw name or date of birth in any output file.
    raw_text = ""
    for path in RAW_DIR.glob("provider_*.csv"):
        raw_text += path.read_text(encoding="utf-8")
    outputs_text = "".join(
        (OUT / p).read_text(encoding="utf-8", errors="ignore")
        for p in ["registry_report.json", "registry_report.md", "monthly_counts.csv",
                  "provider_completeness.csv", "county_counts.csv",
                  "registry_dashboard.html", "audit_log.jsonl"]
    )
    leaked = []
    raw = pd.concat(
        [pd.read_csv(p, dtype=str, keep_default_na=False) for p in RAW_DIR.glob("provider_*.csv")],
        ignore_index=True,
    )
    name_col = "full_name" if "full_name" in raw.columns else "PatientName"
    dob_col = "date_of_birth" if "date_of_birth" in raw.columns else "DOB"
    for col in [name_col, dob_col]:
        for v in raw[col].dropna().astype(str).unique():
            if len(v) >= 4 and v in outputs_text:
                leaked.append((col, v))
    check("no raw name or DOB in any output", not leaked)
    if leaked:
        print("  leaked sample:", leaked[:5])

    # 3. Counts reconcile.
    check("staged == excluded + accepted", len(staged) == report["rows_excluded"] + len(reports))
    check("reports accepted == registry reports", report["reports_accepted"] == len(reports))
    check("patients <= reports", len(patients) <= len(reports))
    check("patients == report total", report["patients_in_registry"] == len(patients))

    # 4. Codes, counties, ages valid.
    check(
        "diagnosis codes valid",
        set(patients["diagnosis_code"]) <= {"G20", "G21.0", "G21.1", "G23.1", "G23.2", "G23.8"},
    )
    florida = {"Broward", "Miami-Dade", "Hillsborough", "Orange", "Duval", "Palm Beach",
               "Pinellas", "Lee", "Polk", "Brevard", "Volusia", "Pasco", "Sarasota",
               "Collier", "Leon", "Unknown"}
    check("counties valid or Unknown", set(patients["county"]) <= florida)
    ages = (pd.to_datetime(patients["first_diagnosis_date"]).dt.year - patients["birth_year"])
    check("age at diagnosis 20..100", bool(((ages >= 20) & (ages <= 100)).all()))

    # 5. Monthly counts sum to patients; provider file sums to staged.
    monthly = pd.read_csv(OUT / "monthly_counts.csv")
    check("monthly counts sum to patients", int(monthly["new_patients"].sum()) == len(patients))
    completeness = pd.read_csv(OUT / "provider_completeness.csv")
    check(
        "provider received sums to staged",
        int(completeness["reports_received"].sum()) == len(staged),
    )
    check(
        "provider accepted sums to reports",
        int(completeness["reports_accepted"].sum()) == len(reports),
    )

    # 6. Audit log parses as JSONL, 5 events in order.
    events = [json.loads(line) for line in AUDIT.read_text().splitlines()]
    check("audit log parses as JSONL, 5 events", len(events) == 5)
    check(
        "audit stages in order",
        [e["stage"] for e in events]
        == ["generate", "ingest", "validate", "integrate", "report"],
    )

    print("\nRESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
