-- MediOps Intelligence v2: load CSV files into the tables
-- Run from the project root folder so the relative paths work.
-- Each \copy command must stay on ONE line.

\copy dim_hospital   FROM 'data/raw/hospitals.csv'    WITH (FORMAT csv, HEADER true)
\copy dim_department FROM 'data/raw/departments.csv'  WITH (FORMAT csv, HEADER true)
\copy dim_insurer    FROM 'data/raw/insurers.csv'     WITH (FORMAT csv, HEADER true)
\copy dim_patient    FROM 'data/raw/patients.csv'     WITH (FORMAT csv, HEADER true)
\copy fact_visit     FROM 'data/raw/visits.csv'       WITH (FORMAT csv, HEADER true)
\copy fact_bill      FROM 'data/raw/bills.csv'        WITH (FORMAT csv, HEADER true)
\copy fact_claim     FROM 'data/raw/claims.csv'       WITH (FORMAT csv, HEADER true)

-- Check: how many rows did each table get?
SELECT 'dim_hospital' AS table_name, COUNT(*) AS row_count FROM dim_hospital
UNION ALL SELECT 'dim_department', COUNT(*) FROM dim_department
UNION ALL SELECT 'dim_insurer',    COUNT(*) FROM dim_insurer
UNION ALL SELECT 'dim_patient',    COUNT(*) FROM dim_patient
UNION ALL SELECT 'fact_visit',     COUNT(*) FROM fact_visit
UNION ALL SELECT 'fact_bill',      COUNT(*) FROM fact_bill
UNION ALL SELECT 'fact_claim',     COUNT(*) FROM fact_claim;