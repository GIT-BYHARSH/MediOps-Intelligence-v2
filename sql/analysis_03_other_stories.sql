-- Analysis 03: stories 4, 5, 6 and 7
-- Reporting date for the simulation: 31 Dec 2025

-- ---------- Story 5: pending claims older than 90 days, by hospital ----------
SELECT
    h.hospital_name,
    COUNT(*)                                                         AS pending_claims,
    COUNT(*) FILTER (WHERE DATE '2025-12-31' - c.claim_date > 90)    AS pending_over_90_days,
    ROUND(SUM(c.claim_amount)
          FILTER (WHERE DATE '2025-12-31' - c.claim_date > 90) / 10000000.0, 2) AS stuck_crore
FROM fact_claim AS c
JOIN fact_visit   AS v ON v.visit_id    = c.visit_id
JOIN dim_hospital AS h ON h.hospital_id = v.hospital_id
WHERE c.claim_status = 'Pending'
GROUP BY h.hospital_name
ORDER BY pending_over_90_days DESC
LIMIT 5;


-- ---------- Story 6: denial rate by bill size ----------
SELECT
    CASE
        WHEN b.total_amount <  10000  THEN '1. Under 10,000'
        WHEN b.total_amount <  50000  THEN '2. 10,000 to 50,000'
        WHEN b.total_amount <= 200000 THEN '3. 50,000 to 2,00,000'
        ELSE                               '4. Above 2,00,000'
    END                                                              AS bill_size_band,
    COUNT(*) FILTER (WHERE c.claim_status <> 'Pending')              AS decided_claims,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
          / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending'), 1)  AS denial_rate_pct,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected'
                                     AND c.rejection_reason = 'Medical Necessity Not Met')
          / COUNT(*) FILTER (WHERE c.claim_status = 'Rejected'), 0)  AS medical_necessity_share_pct
FROM fact_claim AS c
JOIN fact_bill  AS b ON b.bill_id = c.bill_id
GROUP BY 1
ORDER BY 1;


-- ---------- Story 7: partial approvals by treatment type ----------
SELECT
    v.treatment_type,
    COUNT(*) FILTER (WHERE c.claim_status <> 'Pending')              AS decided_claims,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Partially Approved')
          / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending'), 1)  AS partial_approval_rate_pct,

    ROUND(SUM(c.claim_amount - c.approved_amount)
          FILTER (WHERE c.claim_status <> 'Pending') / 10000000.0, 2) AS claim_gap_crore
FROM fact_claim AS c
JOIN fact_visit AS v ON v.visit_id = c.visit_id
GROUP BY v.treatment_type
ORDER BY partial_approval_rate_pct DESC;


-- ---------- Story 4a: visits and waiting time by month of the year ----------
SELECT
    EXTRACT(MONTH FROM visit_date)::int   AS month_number,
    COUNT(*)                              AS visits,
    ROUND(AVG(waiting_minutes), 1)        AS avg_wait_minutes
FROM fact_visit
GROUP BY 1
ORDER BY 1;


-- ---------- Story 4b: denial rate by month of the visit ----------
SELECT
    EXTRACT(MONTH FROM v.visit_date)::int AS month_number,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
          / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending'), 1) AS denial_rate_pct
FROM fact_claim AS c
JOIN fact_visit AS v ON v.visit_id = c.visit_id
GROUP BY 1
ORDER BY 1;