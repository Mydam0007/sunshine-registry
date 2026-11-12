"""Runs the whole pipeline: generate, ingest, validate, integrate, report.

    python run_pipeline.py
    python run_pipeline.py --patients 5000 --seed 42
    python -m pipeline --patients 5000 --seed 42

Outputs go to outputs/: the SQLite registry database, the registry report
(JSON and Markdown), three CSVs for dashboards, and the audit log. The
raw provider files live in data/raw/ and are made on the first run (or
with --regenerate). They never get written to outputs/.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from .audit import AuditLog
from .generate import write_raw
from .ingest import STAGING_TABLE, ingest
from .integrate import get_salt, integrate
from .report import build_report
from .validate import validate

DEFAULT_PATIENTS = 5000
DEFAULT_SEED = 42


def _count_raw_rows(raw_dir: Path) -> int:
    total = 0
    for path in raw_dir.glob("provider_*.csv"):
        total += sum(1 for _ in open(path, encoding="utf-8")) - 1
    return total


def run(
    patients: int = DEFAULT_PATIENTS,
    seed: int = DEFAULT_SEED,
    salt: str | None = None,
    raw_dir: str = "data/raw",
    out_dir: str = "outputs",
    regenerate: bool = False,
) -> dict:
    """Run the full pipeline and return a summary dict."""
    started = time.perf_counter()
    raw = Path(raw_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    db_path = out / "registry.db"
    audit_path = out / "audit_log.jsonl"
    if audit_path.exists():
        audit_path.unlink()  # one log per run; never append across runs
    audit = AuditLog(audit_path)
    salt_value, used_default_salt = get_salt(salt)

    existing = sorted(raw.glob("provider_*.csv"))
    if regenerate or not existing:
        paths = write_raw(n_patients=patients, seed=seed, raw_dir=raw)
        rows_generated = _count_raw_rows(raw)
        audit.event("generate", rows_in=0, rows_out=rows_generated, seed=seed, regenerated=True)
    else:
        rows_generated = _count_raw_rows(raw)
        audit.event("generate", rows_in=0, rows_out=rows_generated, seed=seed, regenerated=False)

    counts = ingest(raw, db_path)
    total_in = sum(counts.values())
    audit.event("ingest", rows_in=total_in, rows_out=total_in, files=counts)

    clean, validation = validate(db_path)
    audit.event(
        "validate",
        rows_in=validation["rows_in"],
        rows_out=validation["rows_out"],
        excluded_rows=validation["excluded_rows"],
        exclusion_reasons=validation["exclusion_reasons"],
        standardized_values=validation["standardized_values"],
    )

    integrated = integrate(clean, salt_value, db_path)
    audit.event(
        "integrate",
        rows_in=validation["rows_out"],
        rows_out=integrated["reports"],
        patients=integrated["patients"],
        patients_reported_twice=integrated["patients_reported_twice"],
        used_default_salt=used_default_salt,
    )

    summary = build_report(db_path, validation, integrated, out)
    audit.event(
        "report",
        rows_in=integrated["patients"],
        rows_out=integrated["patients"],
        outputs=[
            "registry.db",
            "registry_report.json",
            "registry_report.md",
            "monthly_counts.csv",
            "provider_completeness.csv",
            "county_counts.csv",
            "registry_dashboard.html",
            "audit_log.jsonl",
        ],
    )

    elapsed = time.perf_counter() - started
    summary["run_id"] = audit.run_id
    summary["elapsed_seconds"] = round(elapsed, 2)
    summary["used_default_salt"] = used_default_salt
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sunshine Registry (synthetic data).")
    parser.add_argument("--patients", type=int, default=DEFAULT_PATIENTS, help="synthetic patients to generate")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed (reproducible runs)")
    parser.add_argument("--salt", type=str, default=None, help="hash salt (or PIPELINE_SALT env var)")
    parser.add_argument("--raw-dir", type=str, default="data/raw")
    parser.add_argument("--out-dir", type=str, default="outputs")
    parser.add_argument("--regenerate", action="store_true", help="regenerate the raw provider files")
    args = parser.parse_args(argv)

    summary = run(
        patients=args.patients,
        seed=args.seed,
        salt=args.salt,
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        regenerate=args.regenerate,
    )
    print(f"run_id:            {summary['run_id']}")
    print(f"rows received:     {summary['rows_received']}")
    print(f"rows excluded:     {summary['rows_excluded']}")
    print(f"reports accepted:  {summary['reports_accepted']}")
    print(f"patients:          {summary['patients_in_registry']}")
    print(f"reported twice:    {summary['patients_reported_twice']}")
    print(f"exclusions:        {summary['exclusion_reasons']}")
    print(f"elapsed:           {summary['elapsed_seconds']}s")
    if summary["used_default_salt"]:
        print("warning: using the default development salt. Pass --salt or PIPELINE_SALT")


if __name__ == "__main__":
    main()
