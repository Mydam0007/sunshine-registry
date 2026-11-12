# Sunshine Registry

A Florida Parkinson's Disease Registry pipeline.

I built this to show how I handle registry data: take in reports from three different providers, each in its own shape, clean them up, match the same person across providers, and build one registry with a report on top.

Everything here is synthetic. All 5,000 patients are made up by a seeded generator, so there are no real people and no real patient data anywhere in this project. I made it as an independent portfolio project. It is not connected to USF in any way.

## What it does

1. **Generate** three provider files (about 6,300 reports for 5,000 patients). Each provider sends the same kind of data differently: different column names, different date formats, an extra notes column. About a quarter of the patients show up in two providers' files. A few bad rows are mixed in on purpose.
2. **Ingest** the files into a staging table in SQLite, mapping each provider's columns onto one shared schema. Nothing is cleaned at this step.
3. **Validate** the staged rows. Rows with no patient name, a date of birth that does not parse, a missing or future diagnosis date, a diagnosis code the registry does not accept, or an age at diagnosis outside 20 to 100 get dropped. Duplicate report IDs keep the first occurrence. County spellings get standardized (323 fixed) and bad sex values become "Unknown" (36 fixed). Everything is counted.
4. **Integrate** the clean rows into the registry. Patients are matched on a salted hash of name plus date of birth, so no raw identifiers land in the registry tables. Each patient gets one record: the earliest diagnosis date, the code and county from that report, and how many providers reported them. Two tables result: one row per patient, one row per accepted report.
5. **Report** with SQL queries against the registry: new patients by month, acceptance by provider, patients by county, and diagnosis code counts. The queries live in `sql/reporting_queries.sql`, not in code, so they can be read on their own. The outputs are a report (JSON and Markdown), three CSVs, and a self-contained HTML dashboard with the monthly chart and the quality numbers, plus an audit log with one event per stage.

## How to run

```bash
pip install -r requirements.txt
python run_pipeline.py
```

Or as a module:

```bash
python -m pipeline
```

Options:

```bash
python run_pipeline.py --patients 5000 --seed 42 --salt my-secret-salt --regenerate
```

`--patients` and `--seed` control the fake data. `--salt` (or the `PIPELINE_SALT` environment variable) sets the hash salt. Without one it falls back to a dev default and the run gets flagged in the audit log. In real use the salt would live in a secrets store, not in the code.

With Docker:

```bash
docker build -t sunshine-registry .
docker run --rm -v "$PWD/outputs:/app/outputs" sunshine-registry
```

## What came out

Ran with seed 42 on Python 3.12, pandas 2.1.4. Pipeline time 1.01 s. Same seed gives identical reports, dashboard included.

- Rows received: 6,271 from three providers. Rows excluded: 268. Reports accepted: 6,003.
- Patients in the registry: 4,845. Of those, 1,158 were reported by two providers and matched into one record.
- Excluded (268): 36 missing patient name, 36 duplicate report ID, 18 dates of birth that did not parse, 53 missing diagnosis date, 34 diagnosis dates in the future, 72 invalid diagnosis codes, 19 age at diagnosis outside 20 to 100.
- Acceptance by provider: Tampa Neurology Associates 95.7% (1,985 of 2,074), Gulf Coast Movement Disorders 95.9% (2,066 of 2,155), Central Florida Neurology Group 95.6% (1,952 of 2,042).
- Diagnosis codes: G20 Parkinson disease 4,140, G21.1 157, G21.0 147, G23.8 139, G23.2 139, G23.1 123.
- New patients by month: 34 months, January 2024 to October 2026.

`verify_outputs.py` checks the outputs on its own: all output files exist, the three SQLite tables exist, patient hashes are 64-character hex and unique, no raw names or dates of birth in any output file, row counts add up, codes and counties are valid, ages are 20 to 100, the monthly counts add up to the patient total, the dashboard is self-contained HTML with a monthly bar chart, and the audit log parses as JSONL with 5 events in order. All 28 checks pass.

```bash
python verify_outputs.py
```

After a run, `outputs/` has the registry database (`registry.db`), the registry report, the three CSVs, the dashboard (`registry_dashboard.html`), and the audit log. The raw provider files live in `data/raw/` and never get written to `outputs/`. Both folders are git-ignored: the raw files look like real patient data even though every record is fake, and the outputs can be rebuilt from the seed.

## Stack

Python 3.12, pandas, SQLite, Docker. Nothing else.

## A few things worth knowing

- The data is fake and the default salt is for development only. Neither would do for real patient data.
- Hashing with a salt is pseudonymization, not anonymization. With the salt and the source data the hashes can be reversed, which is why the raw files are still treated as sensitive.
- The registry covers January 2024 to October 2026. Florida's statewide Parkinson's registry starts mandatory provider reporting in January 2027; this project models the same kind of load with earlier synthetic data.
- This shows the technique. It is not a compliance certification and does not claim to be one.
