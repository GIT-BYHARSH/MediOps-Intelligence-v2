-- Analysis 04: recovery priority list
-- Assumptions (simplified, to be refined with ML later):
--   win chance:   Incomplete Documents 70%, Coding Error 60%, Medical Necessity Not Met 35%
--   effort hours: Incomplete Documents 1,   Coding Error 2,   Medical Necessity Not Met 5

WITH recoverable AS (
    -- Step 1: every claim that is rejected/cut for a fixable reason
    SELECT
        c.claim_id,
        h.hospital_name,
        i.insurer_name,
        c.rejection_reason,
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
    FROM fact_claim   AS c
    JOIN fact_visit   AS v ON v.visit_id    = c.visit_id
    JOIN dim_hospital AS h ON h.hospital_id = v.hospital_id
    JOIN dim_insurer  AS i ON i.insurer_id  = c.insurer_id
    WHERE c.claim_status IN ('Rejected', 'Partially Approved')
      AND c.rejection_reason IN ('Incomplete Documents', 'Coding Error', 'Medical Necessity Not Met')
),
scored AS (
    -- Step 2: expected recovery and priority score, then rank everything
    SELECT
        *,
        recoverable_amount * win_chance                          AS expected_recovery,
        recoverable_amount * win_chance / effort_hours           AS priority_score,
        RANK() OVER (ORDER BY recoverable_amount * win_chance / effort_hours DESC) AS priority_rank
    FROM recoverable
)

-- Step 3a: the top 10 claims to chase first
SELECT
    priority_rank,
    claim_id,
    hospital_name,
    insurer_name,
    rejection_reason,
    ROUND(recoverable_amount)   AS recoverable_inr,
    ROUND(expected_recovery)    AS expected_recovery_inr,
    effort_hours
FROM scored
ORDER BY priority_rank
LIMIT 10;
-- Step 3b: what do we win if we only work the top 10% / 25% / 50% of the list?
WITH recoverable AS (
    SELECT
        c.claim_amount - c.approved_amount AS recoverable_amount,
        CASE c.rejection_reason
            WHEN 'Incomplete Documents' THEN 0.70
            WHEN 'Coding Error' THEN 0.60
            WHEN 'Medical Necessity Not Met' THEN 0.35 END AS win_chance,
        CASE c.rejection_reason
            WHEN 'Incomplete Documents' THEN 1
            WHEN 'Coding Error' THEN 2
            WHEN 'Medical Necessity Not Met' THEN 5 END AS effort_hours
    FROM fact_claim AS c
    WHERE c.claim_status IN ('Rejected', 'Partially Approved')
      AND c.rejection_reason IN ('Incomplete Documents', 'Coding Error', 'Medical Necessity Not Met')
),
scored AS (
    SELECT
        *,
        recoverable_amount * win_chance AS expected_recovery,
        NTILE(10) OVER (ORDER BY recoverable_amount * win_chance / effort_hours DESC) AS decile
    FROM recoverable
)
SELECT
    decile,
    COUNT(*)                                          AS claims,
    ROUND(SUM(expected_recovery) / 10000000.0, 2)     AS expected_recovery_crore,
    SUM(effort_hours)                                 AS total_effort_hours,
    ROUND(SUM(expected_recovery) / SUM(effort_hours)) AS inr_per_effort_hour
FROM scored
GROUP BY decile
ORDER BY decile;