-- Reporting queries for the Florida Parkinson's registry.
-- Each query is one section, marked by "-- query: <name>".
-- report.py loads this file and runs each query against the SQLite
-- registry database. Keep the queries here, not in code, so a reviewer
-- can read the SQL on its own.

-- query: monthly
SELECT substr(first_diagnosis_date, 1, 7) AS month,
       COUNT(*) AS new_patients
FROM registry_patients
GROUP BY month ORDER BY month;

-- query: by_provider
SELECT provider, COUNT(*) AS reports_accepted
FROM registry_reports
GROUP BY provider ORDER BY provider;

-- query: staged_by_provider
SELECT provider, COUNT(*) AS reports_received
FROM staging_reports
GROUP BY provider ORDER BY provider;

-- query: counties
SELECT county, COUNT(*) AS patients
FROM registry_patients
GROUP BY county ORDER BY patients DESC;

-- query: codes
SELECT diagnosis_code, COUNT(*) AS patients
FROM registry_patients
GROUP BY diagnosis_code ORDER BY patients DESC;
