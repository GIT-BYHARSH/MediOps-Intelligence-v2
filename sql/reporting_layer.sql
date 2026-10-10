-- MediOps Intelligence v2: reporting layer for Power BI
-- Creates a calendar table and two views. Safe to run again at any time.
-- Definitions follow docs/kpi_dictionary.md. Reporting date of the simulation: 31 Dec 2025.

-- ---------- Calendar table ----------
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date AS
SELECT
    d::date                                  AS date_id,
    EXTRACT(YEAR    FROM d)::int             AS year,
    EXTRACT(QUARTER FROM d)::int             AS quarter,
    EXTRACT(MONTH   FROM d)::int             AS month_number,
    TO_CHAR(d, 'Mon')                        AS month_name,
    TO_CHAR(d, 'YYYY-MM')                    AS year_month,
    TO_CHAR(d, 'Dy')                         AS day_name,
    (EXTRACT(MONTH FROM d) IN (12, 1))       AS is_winter
FROM generate_series(DATE '2024-01-01', DATE '2025-12-31', INTERVAL '1 day') AS d;

ALTER TABLE dim_date ADD PRIMARY KEY (date_id);

-- ---------- Central fact view: one row per claim ----------
DROP VIEW IF EXISTS report_recovery_priority;
DROP VIEW IF EXISTS report_claim;

CREATE VIEW report_claim AS
SELECT
    c.claim_id,
    c.bill_id,
    c.visit_id,
    v.hospital_id,
    v.department_id,
    c.insurer_id,
    v.visit_date,
    c.claim_date,
    c.settlement_date,

    v.visit_type,
    v.treatment_type,
    v.diagnosis,
    p.gender,
    CASE
        WHEN p.age < 18 THEN '0-17'
        WHEN p.age < 41 THEN '18-40'
        WHEN p.age < 61 THEN '41-60'
        ELSE '61+'
    END                                                          AS age_group,

    c.claim_status,
    c.rejection_reason,
    (c.claim_status <> 'Pending')                                AS is_decided,
    (c.claim_status = 'Rejected')                                AS is_rejected,
    (c.claim_status = 'Approved')                                AS is_approved,

    b.total_amount                                               AS bill_amount,
    c.claim_amount,
    c.approved_amount,

    -- Claim Gap: money claimed but not paid (decided claims only)
    CASE WHEN c.claim_status <> 'Pending'
         THEN c.claim_amount - c.approved_amount END             AS claim_gap,

    -- Recoverable Amount: gap caused by fixable reasons
    CASE WHEN c.claim_status IN ('Rejected', 'Partially Approved')
              AND c.rejection_reason IN ('Incomplete Documents', 'Coding Error', 'Medical Necessity Not Met')
         THEN c.claim_amount - c.approved_amount END             AS recoverable_amount,

    -- Preventable denial: 1 = preventable reason, 0 = not, empty = no denial reason
    CASE
        WHEN c.rejection_reason IS NULL THEN NULL
        WHEN c.rejection_reason IN ('Incomplete Documents', 'Coding Error', 'Duplicate Claim') THEN 1
        ELSE 0
    END                                                          AS is_preventable,

    -- Settlement days (decided claims) and claim age (pending claims)
    (c.settlement_date - c.claim_date)                           AS settlement_days,
    CASE WHEN c.claim_status = 'Pending'
         THEN DATE '2025-12-31' - c.claim_date END               AS pending_age_days,
    CASE
        WHEN c.claim_status <> 'Pending'                         THEN NULL
        WHEN DATE '2025-12-31' - c.claim_date <= 30              THEN '0-30 days'
        WHEN DATE '2025-12-31' - c.claim_date <= 60              THEN '31-60 days'
        WHEN DATE '2025-12-31' - c.claim_date <= 90              THEN '61-90 days'
        ELSE '90+ days'
    END                                                          AS aging_bucket
FROM fact_claim   AS c
JOIN fact_bill    AS b ON b.bill_id    = c.bill_id
JOIN fact_visit   AS v ON v.visit_id   = c.visit_id
JOIN dim_patient  AS p ON p.patient_id = v.patient_id;

-- ---------- Recovery priority view (same logic as sql/analysis_04) ----------
-- Win chance and effort hours are documented assumptions, not measured values.
CREATE VIEW report_recovery_priority AS
WITH recoverable AS (
    SELECT
        c.claim_id,
        c.claim_amount - c.approved_amount AS recoverable_amount,
        CASE c.rejection_reason
            WHEN 'Incomplete Documents'      THEN 0.70
            WHEN 'Coding Error'              THEN 0.60
            WHEN 'Medical Necessity Not Met' THEN 0.35
        END AS win_chance,
        CASE c.rejection_reason
            WHEN 'Incomplete Documents'      THEN 1
            WHEN 'Coding Error'              THEN 2
            WHEN 'Medical Necessity Not Met' THEN 5
        END AS effort_hours
    FROM fact_claim AS c
    WHERE c.claim_status IN ('Rejected', 'Partially Approved')
      AND c.rejection_reason IN ('Incomplete Documents', 'Coding Error', 'Medical Necessity Not Met')
),
scored AS (
    SELECT
        *,
        recoverable_amount * win_chance                 AS expected_recovery,
        recoverable_amount * win_chance / effort_hours  AS priority_score
    FROM recoverable
)
SELECT
    claim_id,
    recoverable_amount,
    win_chance,
    effort_hours,
    expected_recovery,
    priority_score,
    RANK()    OVER (ORDER BY priority_score DESC) AS priority_rank,
    NTILE(10) OVER (ORDER BY priority_score DESC) AS priority_decile
FROM scored;

-- ---------- Check ----------
SELECT 'dim_date' AS object, COUNT(*) AS row_count FROM dim_date
UNION ALL SELECT 'report_claim', COUNT(*) FROM report_claim
UNION ALL SELECT 'report_recovery_priority', COUNT(*) FROM report_recovery_priority;
