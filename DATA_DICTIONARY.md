# Sunshine Registry: data dictionary

All data is synthetic. Column names below are the canonical names used after
ingest. Provider B sends its own names (ReportID, PatientName, DOB, DxDate,
DxCode) and US dates; ingest maps them back. Provider C adds a notes column
that the pipeline ignores.

## Staging table: staging_reports

One row per provider report as received, after column mapping. Raw values
only; no cleaning happens here.

| Column | What it is |
|---|---|
| report_id | Provider's report ID, e.g. R-100001 |
| full_name | Patient name as reported (raw; never leaves staging) |
| date_of_birth | Patient date of birth as reported, YYYY-MM-DD |
| sex | F, M, or anything the provider sent |
| diagnosis_date | Date of Parkinson's diagnosis as reported |
| diagnosis_code | ICD-10 code as reported |
| county | Florida county as reported |
| provider | Reporting provider name |
| report_date | Date the provider sent the report |
| source_file | Which provider file the row came from |

## Registry table: registry_patients

One row per person. No raw identifiers: patients are keyed by a salted
SHA-256 hash of name plus date of birth.

| Column | What it is |
|---|---|
| patient_hash | Salted hash of lowercase name + date of birth |
| birth_year | Year of birth |
| sex | F, M, or Unknown |
| first_diagnosis_date | Earliest diagnosis date across the patient's reports |
| diagnosis_code | ICD-10 code from the earliest report |
| county | Florida county, or Unknown |
| providers_reporting | How many distinct providers reported this patient |
| reports_received | How many accepted reports this patient has |

## Registry table: registry_reports

One row per accepted provider report.

| Column | What it is |
|---|---|
| report_id | Provider's report ID |
| patient_hash | Same hash as registry_patients |
| provider | Reporting provider name |
| report_date | Date the provider sent the report |
| diagnosis_date | Date of diagnosis on this report |
| diagnosis_code | ICD-10 code on this report |
| county | Florida county, or Unknown |

## Diagnosis codes accepted

| Code | Meaning |
|---|---|
| G20 | Parkinson disease |
| G21.0 | Malignant neuroleptic syndrome |
| G21.1 | Other drug-induced secondary parkinsonism |
| G23.1 | Progressive supranuclear ophthalmoplegia |
| G23.2 | Multiple system atrophy, parkinsonian type |
| G23.8 | Other specified degenerative diseases of basal ganglia |

Anything else is rejected at validation and counted.

## Counties

Broward, Miami-Dade, Hillsborough, Orange, Duval, Palm Beach, Pinellas,
Lee, Polk, Brevard, Volusia, Pasco, Sarasota, Collier, Leon. Anything else
becomes "Unknown" at validation and is counted.
