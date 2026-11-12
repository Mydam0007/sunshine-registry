# Sunshine Registry: monthly registry load (SOP)

Run this once a month, after the providers send their files.

## 1. Collect the files

Put the three provider files in `data/raw/`, named `provider_tampa_neurology.csv`,
`provider_gulf_coast.csv`, and `provider_central_florida.csv`. Check that each
file has the expected columns (see DATA_DICTIONARY.md). If a provider changes
its columns or date format, update the mapping in `pipeline/ingest.py` first.

## 2. Run the pipeline

```bash
python run_pipeline.py --regenerate
```

`--regenerate` rebuilds the synthetic raw files for a test run. For a real
monthly load, place the real provider files in `data/raw/` and run without
`--regenerate`. Pass the hash salt with `--salt` or the `PIPELINE_SALT`
environment variable. Never use the default salt for real data.

## 3. Read the report

Open `outputs/registry_report.md`. Check:

- Rows received against rows expected from each provider.
- Rows excluded and the reasons. Any reason that jumps from last month needs
  a look before the registry is published.
- Acceptance by provider. A provider under 95% usually means its file
  changed shape; check with them before re-running.

## 4. Check the verification

```bash
python verify_outputs.py
```

All checks must pass. If any check fails, do not publish the registry
outputs. Find the failing check, fix the cause, and re-run.

## 5. Publish and archive

- Copy `outputs/registry_report.md`, the three CSVs, and `outputs/registry_dashboard.html` to the dashboard
  folder.
- Keep `outputs/registry.db` and `outputs/audit_log.jsonl` with the month's
  records. The audit log is the record of what happened to every row.
- Archive the raw provider files as received. Never edit them in place.
