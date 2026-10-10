-- Analysis 05: recovery simulation under a fixed time budget
-- The team has 10,000 hours. Each strategy works its list from the top until the hours run out.
-- Win chances and effort hours are the same documented assumptions as analysis_04.

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
with_value AS (
    SELECT *, recoverable_amount * win_chance AS expected_recovery
    FROM recoverable
),
running AS (
    -- For each strategy: the running total of hours as we go down its list
    SELECT
        expected_recovery,
        effort_hours,
        SUM(effort_hours) OVER (ORDER BY md5(claim_id::text)
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS hours_random,
        SUM(effort_hours) OVER (ORDER BY recoverable_amount DESC, claim_id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS hours_largest,
        SUM(effort_hours) OVER (ORDER BY effort_hours ASC, recoverable_amount DESC, claim_id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS hours_quickest,
        SUM(effort_hours) OVER (ORDER BY expected_recovery / effort_hours DESC, claim_id
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS hours_priority
    FROM with_value
),
results AS (
    SELECT 'Random order'          AS strategy, COUNT(*) AS claims_worked,
           SUM(effort_hours) AS hours_used, SUM(expected_recovery) AS recovered
    FROM running WHERE hours_random <= 10000
    UNION ALL
    SELECT 'Largest amount first', COUNT(*), SUM(effort_hours), SUM(expected_recovery)
    FROM running WHERE hours_largest <= 10000
    UNION ALL
    SELECT 'Quickest first',       COUNT(*), SUM(effort_hours), SUM(expected_recovery)
    FROM running WHERE hours_quickest <= 10000
    UNION ALL
    SELECT 'Priority score',       COUNT(*), SUM(effort_hours), SUM(expected_recovery)
    FROM running WHERE hours_priority <= 10000
)
SELECT
    strategy,
    claims_worked,
    hours_used,
    ROUND(recovered / 10000000.0, 2) AS expected_recovery_crore,
    ROUND(recovered / MAX(recovered) FILTER (WHERE strategy = 'Random order') OVER (), 1)
                                     AS times_better_than_random
FROM results
ORDER BY recovered DESC;