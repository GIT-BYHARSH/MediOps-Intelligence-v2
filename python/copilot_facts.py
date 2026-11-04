"""The facts the AI features are allowed to use. Every number comes from the database,
never from the language model. Reporting date of the simulation: 31 Dec 2025."""
import pandas as pd

from db import get_engine

KPI_SQL = """
SELECT
    COUNT(*)                                                          AS claims,
    COUNT(*) FILTER (WHERE is_decided)                                AS decided_claims,
    100.0 * COUNT(*) FILTER (WHERE is_rejected)
          / NULLIF(COUNT(*) FILTER (WHERE is_decided), 0)             AS denial_rate_pct,
    100.0 * COUNT(*) FILTER (WHERE is_approved)
          / NULLIF(COUNT(*) FILTER (WHERE is_decided), 0)             AS approval_rate_pct,
    SUM(claim_gap) / 1e7                                              AS claim_gap_cr,
    SUM(recoverable_amount) / 1e7                                     AS recoverable_cr,
    COUNT(*) FILTER (WHERE pending_age_days > 90)                     AS pending_over_90_days,
    AVG(settlement_days)                                              AS avg_settlement_days
FROM report_claim
"""

TOP_CLAIMS_SQL = """
SELECT
    p.priority_rank, c.claim_id, h.hospital_name, h.city, i.insurer_name,
    c.treatment_type, c.diagnosis, c.claim_date, c.claim_amount, c.approved_amount,
    c.claim_status, c.rejection_reason,
    p.recoverable_amount, p.win_chance, p.effort_hours, p.expected_recovery
FROM report_recovery_priority p
JOIN report_claim   c ON c.claim_id    = p.claim_id
JOIN dim_hospital   h ON h.hospital_id = c.hospital_id
JOIN dim_insurer    i ON i.insurer_id  = c.insurer_id
ORDER BY p.priority_rank, c.claim_id
LIMIT {n}
"""


def inr(amount):
    """Format rupees the Indian way: Rs 2,14,000."""
    digits = f"{abs(float(amount)):.0f}"
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts) + "," + tail
    return f"Rs {digits}"


def get_kpis(engine=None):
    row = pd.read_sql(KPI_SQL, engine or get_engine()).iloc[0]
    return {key: float(value) for key, value in row.items()}


def get_strategies(engine=None):
    return pd.read_sql("SELECT * FROM report_strategy ORDER BY sort_order", engine or get_engine())


def get_alerts(n=9, engine=None):
    return pd.read_sql(
        f'SELECT alert_rank, "check", headline, detail, severity FROM report_alert ORDER BY alert_rank LIMIT {int(n)}',
        engine or get_engine(),
    )


def get_top_claims(n=5, engine=None):
    return pd.read_sql(TOP_CLAIMS_SQL.format(n=int(n)), engine or get_engine())


def get_expected_recovery_cr(engine=None):
    value = pd.read_sql(
        "SELECT SUM(expected_recovery) / 1e7 AS v FROM report_recovery_priority", engine or get_engine()
    ).iloc[0, 0]
    return float(value)


def facts_text(n_alerts=9, n_claims=5, engine=None):
    """All facts for the daily brief as plain text. Returns (text, parts)."""
    engine = engine or get_engine()
    kpis = get_kpis(engine)
    strategies = get_strategies(engine)
    alerts = get_alerts(n_alerts, engine)
    claims = get_top_claims(n_claims, engine)
    expected = get_expected_recovery_cr(engine)

    lines = ["DATA: simulated hospital claims, 25 fictional hospitals, 8 fictional insurers. Reporting date 31 Dec 2025.",
             "",
             "KPIs:",
             f"- Claims: {kpis['claims']:.0f} (decided: {kpis['decided_claims']:.0f})",
             f"- Denial rate: {kpis['denial_rate_pct']:.1f} percent",
             f"- Approval rate: {kpis['approval_rate_pct']:.1f} percent",
             f"- Claim gap (claimed minus approved): Rs {kpis['claim_gap_cr']:.2f} crore",
             f"- Recoverable amount: Rs {kpis['recoverable_cr']:.2f} crore",
             f"- Expected recovery if every recoverable claim is chased: Rs {expected:.2f} crore",
             f"- Claims pending over 90 days: {kpis['pending_over_90_days']:.0f}",
             f"- Average settlement time: {kpis['avg_settlement_days']:.2f} days",
             "",
             "Recovery strategies compared with the same 10,000 team hours:"]
    for _, s in strategies.iterrows():
        lines.append(f"- {s['strategy']}: Rs {s['expected_recovery_crore']:.2f} crore "
                     f"({s['times_better_than_random']:.1f} times random order)")
    lines += ["", "Automatic alerts (unusual behaviour):"]
    for _, a in alerts.iterrows():
        lines.append(f"- {a['alert_rank']}. {a['headline']} ({a['severity']}): {a['detail']}")
    lines += ["", "Top claims to chase first (highest expected recovery per hour of effort):"]
    for _, c in claims.iterrows():
        lines.append(f"- Rank {c['priority_rank']}: {c['hospital_name']} / {c['insurer_name']}, "
                     f"reason {c['rejection_reason']}, expected recovery Rs {c['expected_recovery'] / 1e5:.2f} lakh, "
                     f"{c['effort_hours']:.0f} hour(s) of effort")
    parts = {"kpis": kpis, "strategies": strategies, "alerts": alerts, "claims": claims, "expected": expected}
    return "\n".join(lines), parts
