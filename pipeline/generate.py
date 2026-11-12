"""Makes up the raw provider files. All records are fake, made with a fixed seed
so every run with the same seed gives the same files.

Three providers report the same kind of data in slightly different shapes,
on purpose: different column names, different date formats, an extra column.
About a quarter of the patients show up in two providers' files, so the
pipeline has to spot the same person twice. A few bad rows get mixed in
(missing values, bad codes, future dates, duplicate report IDs) so the
validation step has something to catch.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

FIRST_NAMES = [
    "Ava", "Liam", "Maya", "Noah", "Zoe", "Ethan", "Ruby", "Owen",
    "Isla", "Lucas", "Nora", "Mason", "Ella", "Logan", "Ivy", "James",
    "Luna", "Henry", "Chloe", "Leo", "Mia", "Jack", "Amara", "Eli",
    "Sofia", "Caleb", "Priya", "Omar", "Tara", "Felix", "Nina", "Hugo",
    "Lena", "Marcus", "Aisha", "Diego", "Kira", "Sam", "Rosa", "Ivan",
    "Mei", "Jonas", "Farah", "Tomas", "Elif", "Ravi", "Greta", "Yusuf",
    "Clara", "Dante",
]

LAST_NAMES = [
    "Anderson", "Patel", "Kim", "Garcia", "Nguyen", "Smith", "Chen",
    "Okafor", "Rossi", "Khan", "Muller", "Santos", "Haddad", "Novak",
    "Tanaka", "Ali", "Brooks", "Fischer", "Dubois", "Costa", "Reyes",
    "Ahmed", "Larsen", "Moreau", "Silva", "Petrov", "Osei", "Lindqvist",
    "Marino", "Kaur", "Weber", "Nakamura", "Ferrara", "Dube", "Kowalski",
    "Vargas", "Barros", "Singh", "Keller", "Adeyemi", "Berg", "Rahman",
    "Park",
]

# Real Florida counties. Anything outside this list is a data error.
COUNTIES = [
    "Broward", "Miami-Dade", "Hillsborough", "Orange", "Duval",
    "Palm Beach", "Pinellas", "Lee", "Polk", "Brevard", "Volusia",
    "Pasco", "Sarasota", "Collier", "Leon",
]

# ICD-10 codes the registry accepts. G20 is Parkinson disease; the rest
# are atypical parkinsonism, which the registry also tracks.
VALID_CODES = ["G20", "G21.0", "G21.1", "G23.1", "G23.2", "G23.8"]

PROVIDERS = {
    "tampa_neurology": "Tampa Neurology Associates",
    "gulf_coast": "Gulf Coast Movement Disorders",
    "central_florida": "Central Florida Neurology Group",
}

CANONICAL_COLUMNS = [
    "report_id",
    "full_name",
    "date_of_birth",
    "sex",
    "diagnosis_date",
    "diagnosis_code",
    "county",
    "provider",
    "report_date",
]

# Provider B uses its own column names and US date format.
PROVIDER_B_COLUMNS = {
    "report_id": "ReportID",
    "full_name": "PatientName",
    "date_of_birth": "DOB",
    "sex": "Sex",
    "diagnosis_date": "DxDate",
    "diagnosis_code": "DxCode",
    "county": "County",
    "provider": "Provider",
    "report_date": "ReportDate",
}

DX_END = date(2026, 10, 31)


def _random_date(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=rng.randrange(span + 1))


def _diagnosis_date(rng: random.Random, dob: date) -> date:
    # Diagnoses fall in the recent reporting window, so the monthly
    # report covers about three years instead of seventy.
    earliest = max(dob + timedelta(days=20 * 365), date(2024, 1, 1))
    return _random_date(rng, earliest, DX_END)


def generate(n_patients: int = 900, seed: int = 42) -> dict[str, pd.DataFrame]:
    """Generate one raw file per provider and return them as dataframes."""
    rng = random.Random(seed)
    patients = []
    for _ in range(n_patients):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        dob = _random_date(rng, date(1930, 1, 1), date(2005, 12, 31))
        patients.append(
            {
                "full_name": f"{first} {last}",
                "date_of_birth": dob,
                "sex": rng.choice(["F", "M"]),
                "county": rng.choice(COUNTIES),
            }
        )

    rows: dict[str, list[dict]] = {k: [] for k in PROVIDERS}
    report_no = 100001
    for p in patients:
        # A quarter of patients are reported by two providers.
        n_reports = 2 if rng.random() < 0.25 else 1
        providers = rng.sample(list(PROVIDERS), k=n_reports)
        for key in providers:
            dx = _diagnosis_date(rng, p["date_of_birth"])
            report_date = min(dx + timedelta(days=rng.randrange(61)), DX_END)
            code = "G20" if rng.random() < 0.85 else rng.choice(VALID_CODES[1:])
            rows[key].append(
                {
                    "report_id": f"R-{report_no}",
                    "full_name": p["full_name"],
                    "date_of_birth": p["date_of_birth"].isoformat(),
                    "sex": p["sex"],
                    "diagnosis_date": dx.isoformat(),
                    "diagnosis_code": code,
                    "county": p["county"],
                    "provider": PROVIDERS[key],
                    "report_date": report_date.isoformat(),
                }
            )
            report_no += 1

    frames: dict[str, pd.DataFrame] = {}
    for key, recs in rows.items():
        df = pd.DataFrame(recs, columns=CANONICAL_COLUMNS)
        frames[key] = _inject_defects(df, rng)
    return frames


def _inject_defects(df: pd.DataFrame, rng: random.Random) -> pd.DataFrame:
    """Mix in a small, known set of bad rows. Same seed, same bad rows.
    Counts scale with file size so the defect rate stays about the same."""
    df = df.copy()
    idx = list(df.index)
    n = len(df)
    scale = max(1, round(n / 370))

    def pick(k: int) -> list:
        return rng.sample(idx, k=min(k * scale, n))

    for j in pick(2):
        df.at[j, "full_name"] = ""
    for j in pick(2):
        df.at[j, "report_id"] = df.at[rng.choice(idx), "report_id"]
    for j in pick(3):
        df.at[j, "diagnosis_date"] = ""
    for j in pick(2):
        df.at[j, "diagnosis_date"] = "2027-03-15"
    for j in pick(4):
        df.at[j, "diagnosis_code"] = rng.choice(["X99", "G99", ""])
    for j in pick(3):
        df.at[j, "county"] = rng.choice(["Nowhere", "Unknown County", ""])
    for j in pick(2):
        df.at[j, "date_of_birth"] = rng.choice(["not-a-date", "2010-05-01"])
    for j in pick(2):
        df.at[j, "sex"] = rng.choice(["X", ""])
    # County written in a non-standard form; the pipeline standardizes it.
    for j in pick(15):
        c = df.at[j, "county"]
        df.at[j, "county"] = f"{c} County" if rng.random() < 0.5 else c.lower()
    return df


def write_raw(
    n_patients: int = 900,
    seed: int = 42,
    raw_dir: str | Path = "data/raw",
) -> dict[str, Path]:
    """Generate the three provider files and return their paths."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    frames = generate(n_patients=n_patients, seed=seed)
    paths: dict[str, Path] = {}
    for key, df in frames.items():
        out = df.copy()
        if key == "gulf_coast":
            # Provider B's own column names and US dates.
            out = out.rename(columns=PROVIDER_B_COLUMNS)
            for col in ["DOB", "DxDate", "ReportDate"]:
                out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%m/%d/%Y")
                out[col] = out[col].fillna("")
        if key == "central_florida":
            # Provider C adds a free-text notes column the pipeline ignores.
            out["notes"] = ""
        path = raw_dir / f"provider_{key}.csv"
        out.to_csv(path, index=False)
        paths[key] = path
    return paths
