"""Runs the reporting queries against the registry and writes the outputs.

The SQL lives in sql/reporting_queries.sql, not in code, so a reviewer can
read it on its own. Everything here is SQL against the SQLite tables:
monthly new diagnoses, reports and acceptance by provider, and county
counts. The outputs are a Markdown report, a JSON report, three CSVs that
can feed a dashboard, and a self-contained HTML dashboard.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

from .ingest import STAGING_TABLE
from .integrate import PATIENTS_TABLE, REPORTS_TABLE

QUERIES_PATH = Path(__file__).resolve().parent.parent / "sql" / "reporting_queries.sql"


def _load_queries() -> dict[str, str]:
    """Parse sql/reporting_queries.sql into {name: sql} by its markers."""
    text = QUERIES_PATH.read_text(encoding="utf-8")
    parts = re.split(r"-- query:\s*(\w+)\s*\n", text)
    queries: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        name, body = parts[i], parts[i + 1]
        queries[name] = body.strip().rstrip(";")
    return queries


def build_report(
    db_path: str | Path,
    validation: dict,
    integrated: dict,
    out_dir: str | Path,
) -> dict:
    """Run the reporting queries and write every output file."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    queries = _load_queries()
    with sqlite3.connect(db_path) as conn:
        monthly = pd.read_sql(queries["monthly"], conn)
        by_provider = pd.read_sql(queries["by_provider"], conn)
        staged_by_provider = pd.read_sql(queries["staged_by_provider"], conn)
        counties = pd.read_sql(queries["counties"], conn)
        codes = pd.read_sql(queries["codes"], conn)

    acceptance = staged_by_provider.merge(by_provider, on="provider", how="left")
    acceptance["reports_accepted"] = acceptance["reports_accepted"].fillna(0).astype(int)
    acceptance["acceptance_rate_pct"] = (
        acceptance["reports_accepted"] / acceptance["reports_received"] * 100
    ).round(1)

    summary = {
        "patients_in_registry": integrated["patients"],
        "reports_accepted": integrated["reports"],
        "patients_reported_twice": integrated["patients_reported_twice"],
        "rows_received": validation["rows_in"],
        "rows_excluded": validation["excluded_rows"],
        "exclusion_reasons": validation["exclusion_reasons"],
        "standardized_values": validation["standardized_values"],
        "monthly_new_patients": monthly.to_dict("records"),
        "by_provider": acceptance.to_dict("records"),
        "county_counts": counties.to_dict("records"),
        "diagnosis_codes": codes.to_dict("records"),
    }

    (out / "registry_report.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    monthly.to_csv(out / "monthly_counts.csv", index=False)
    acceptance.to_csv(out / "provider_completeness.csv", index=False)
    counties.to_csv(out / "county_counts.csv", index=False)
    _write_markdown(summary, out / "registry_report.md")
    _write_dashboard(summary, out / "registry_dashboard.html")
    return summary


def _write_markdown(summary: dict, path: Path) -> None:
    lines = [
        "# Sunshine Registry: monthly report (synthetic data)",
        "",
        f"- Patients in registry: **{summary['patients_in_registry']}**",
        f"- Reports accepted: **{summary['reports_accepted']}**",
        f"- Rows received: **{summary['rows_received']}**",
        f"- Rows excluded: **{summary['rows_excluded']}**",
        f"- Patients reported by two providers: **{summary['patients_reported_twice']}**",
        "",
        "## Exclusion reasons",
        "",
    ]
    if summary["exclusion_reasons"]:
        for reason, count in sorted(summary["exclusion_reasons"].items()):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- none")
    lines += ["", "## Acceptance by provider", ""]
    for row in summary["by_provider"]:
        lines.append(
            f"- {row['provider']}: {row['reports_accepted']} of "
            f"{row['reports_received']} accepted ({row['acceptance_rate_pct']}%)"
        )
    lines += ["", "## New patients by month", ""]
    for row in summary["monthly_new_patients"]:
        lines.append(f"- {row['month']}: {row['new_patients']}")
    lines += ["", "## Patients by county", ""]
    for row in summary["county_counts"]:
        lines.append(f"- {row['county']}: {row['patients']}")
    lines += ["", "## Diagnosis codes", ""]
    for row in summary["diagnosis_codes"]:
        lines.append(f"- {row['diagnosis_code']}: {row['patients']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _bar_chart(monthly: list[dict]) -> str:
    """Inline SVG bar chart of new patients by month. No JavaScript."""
    width, height, pad = 720, 220, 30
    values = [row["new_patients"] for row in monthly]
    labels = [row["month"] for row in monthly]
    peak = max(values) if values else 1
    n = len(values)
    bar_w = (width - 2 * pad) / n
    parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
    for i, (label, value) in enumerate(zip(labels, values)):
        bar_h = value / peak * (height - 2 * pad)
        x = pad + i * bar_w + 1
        y = height - pad - bar_h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 2:.1f}" '
            f'height="{bar_h:.1f}" fill="#1F4E79"><title>{label}: {value}</title></rect>'
        )
    for i, label in enumerate(labels):
        if i % 6 == 0:
            x = pad + i * bar_w + bar_w / 2
            parts.append(
                f'<text x="{x:.1f}" y="{height - 8}" font-size="10" '
                f'text-anchor="middle" fill="#555">{label}</text>'
            )
    parts.append(
        f'<text x="{pad}" y="14" font-size="11" fill="#555">New patients by month (peak {peak})</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _table(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _write_dashboard(summary: dict, path: Path) -> None:
    """Self-contained HTML dashboard. No JavaScript, no external files."""
    total = summary["rows_received"]
    accepted = summary["reports_accepted"]
    rate = round(accepted / total * 100, 1) if total else 0.0
    months = summary["monthly_new_patients"]
    first_month = months[0]["month"] if months else ""
    last_month = months[-1]["month"] if months else ""

    provider_rows = [
        [r["provider"], r["reports_received"], r["reports_accepted"], f"{r['acceptance_rate_pct']}%"]
        for r in summary["by_provider"]
    ]
    exclusion_rows = [
        [reason, count] for reason, count in sorted(summary["exclusion_reasons"].items())
    ]
    county_rows = [[r["county"], r["patients"]] for r in summary["county_counts"]]
    code_rows = [[r["diagnosis_code"], r["patients"]] for r in summary["diagnosis_codes"]]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sunshine Registry: dashboard (synthetic data)</title>
<style>
body {{ font-family: Calibri, Arial, sans-serif; margin: 24px; color: #1A1A1A; }}
h1 {{ color: #1F4E79; font-size: 22px; margin-bottom: 2px; }}
h2 {{ color: #1F4E79; font-size: 16px; border-bottom: 1px solid #1F4E79; padding-bottom: 2px; }}
p.note {{ color: #555; font-size: 13px; }}
.kpis {{ display: flex; gap: 12px; margin: 16px 0; }}
.kpi {{ border: 1px solid #CCC; padding: 10px 14px; min-width: 130px; }}
.kpi .value {{ font-size: 24px; font-weight: bold; color: #1F4E79; }}
.kpi .label {{ font-size: 12px; color: #555; }}
table {{ border-collapse: collapse; margin: 8px 0 20px 0; }}
th, td {{ border: 1px solid #CCC; padding: 5px 10px; text-align: left; font-size: 14px; }}
th {{ background: #E8EEF4; color: #1F4E79; }}
</style>
</head>
<body>
<h1>Sunshine Registry: dashboard</h1>
<p class="note">Florida Parkinson's Disease Registry. Synthetic data only. New patients {first_month} to {last_month}. Generated by the registry pipeline.</p>
<div class="kpis">
<div class="kpi"><div class="value">{summary["patients_in_registry"]}</div><div class="label">Patients in registry</div></div>
<div class="kpi"><div class="value">{accepted}</div><div class="label">Reports accepted</div></div>
<div class="kpi"><div class="value">{rate}%</div><div class="label">Acceptance rate</div></div>
<div class="kpi"><div class="value">{summary["rows_excluded"]}</div><div class="label">Rows excluded</div></div>
</div>
<h2>New patients by month</h2>
{_bar_chart(months)}
<h2>Acceptance by provider</h2>
{_table(["Provider", "Reports received", "Reports accepted", "Acceptance"], provider_rows)}
<h2>Exclusion reasons</h2>
{_table(["Reason", "Rows"], exclusion_rows)}
<h2>Patients by county</h2>
{_table(["County", "Patients"], county_rows)}
<h2>Diagnosis codes</h2>
{_table(["Code", "Patients"], code_rows)}
<p class="note">Every record in this dashboard is fake, generated with a fixed seed. This is an independent portfolio project, not affiliated with the University of South Florida.</p>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
