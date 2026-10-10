-- Analysis 02: drill-down to find hidden problem areas

-- ---------- Query 1: insurer x hospital, highest denial rates ----------
SELECT
    i.insurer_name,
    h.hospital_name,
    COUNT(*) FILTER (WHERE c.claim_status <> 'Pending')               AS decided_claims,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
          / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending'), 1)   AS denial_rate_pct,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected'
                                     AND c.rejection_reason = 'Incomplete Documents')
          / COUNT(*) FILTER (WHERE c.claim_status = 'Rejected'), 0)   AS incomplete_docs_share_pct
FROM fact_claim AS c
JOIN fact_visit    AS v ON v.visit_id    = c.visit_id
JOIN dim_hospital  AS h ON h.hospital_id = v.hospital_id
JOIN dim_insurer   AS i ON i.insurer_id  = c.insurer_id
GROUP BY i.insurer_name, h.hospital_name
HAVING COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') >= 200
ORDER BY denial_rate_pct DESC
LIMIT 8;


-- ---------- Query 2: hospital x department, highest denial rates ----------
SELECT
    h.hospital_name,
    d.department_name,
    COUNT(*) FILTER (WHERE c.claim_status <> 'Pending')               AS decided_claims,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
          / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending'), 1)   AS denial_rate_pct,

    ROUND(100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected'
                                     AND c.rejection_reason = 'Coding Error')
          / COUNT(*) FILTER (WHERE c.claim_status = 'Rejected'), 0)   AS coding_error_share_pct
FROM fact_claim AS c
JOIN fact_visit      AS v ON v.visit_id      = c.visit_id
JOIN dim_hospital    AS h ON h.hospital_id   = v.hospital_id
JOIN dim_department  AS d ON d.department_id = v.department_id
GROUP BY h.hospital_name, d.department_name
HAVING COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') >= 200
ORDER BY denial_rate_pct DESC
LIMIT 8;