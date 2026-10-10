-- Analysis 01: overall KPIs and insurer comparison
-- Definitions follow docs/kpi_dictionary.md
-- Decided claims = Approved + Partially Approved + Rejected (Pending is excluded from rates)

-- ---------- Query 1: headline KPIs ----------
SELECT
    COUNT(*)                                                        AS total_claims,
    COUNT(*) FILTER (WHERE claim_status <> 'Pending')               AS decided_claims,

    ROUND(100.0 * COUNT(*) FILTER (WHERE claim_status = 'Rejected')
          / COUNT(*) FILTER (WHERE claim_status <> 'Pending'), 1)   AS denial_rate_pct,

    ROUND(100.0 * COUNT(*) FILTER (WHERE claim_status = 'Approved')
          / COUNT(*) FILTER (WHERE claim_status <> 'Pending'), 1)   AS approval_rate_pct,

    ROUND(SUM(claim_amount - approved_amount)
          FILTER (WHERE claim_status <> 'Pending') / 10000000.0, 2) AS claim_gap_crore,

    ROUND(SUM(claim_amount - approved_amount)
          FILTER (WHERE claim_status IN ('Rejected', 'Partially Approved')
                    AND rejection_reason IN ('Incomplete Documents',
                                             'Coding Error',
                                             'Medical Necessity Not Met'))
          / 10000000.0, 2)                                          AS recoverable_crore,

    ROUND(AVG(settlement_date - claim_date), 1)                     AS avg_settlement_days
FROM fact_claim;


-- ---------- Query 2: the same KPIs for each insurer ----------
SELECT
    i.insurer_name,
    i.insurer_type,
    COUNT(*) FILTER (WHERE c.claim_status <> 'Pending')             AS decided_claims,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
          / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending'), 1) AS denial_rate_pct,

    ROUND(AVG(c.settlement_date - c.claim_date), 1)                 AS avg_settlement_days,

    ROUND(SUM(c.claim_amount - c.approved_amount)
          FILTER (WHERE c.claim_status <> 'Pending') / 10000000.0, 2) AS claim_gap_crore
FROM fact_claim AS c
JOIN dim_insurer AS i ON i.insurer_id = c.insurer_id
GROUP BY i.insurer_name, i.insurer_type
ORDER BY denial_rate_pct DESC;