"""Turn the findings into a sized action plan: what to do, how much money is at stake, effort, KPI to track.

Every figure is computed from the database. Where a figure depends on the ASSUMED win chances and effort
hours (docs/sensitivity_report.md), it is labelled "expected". Actions overlap, so values are NOT additive.
Output: docs/action_plan.md      Run from the project root:  python python/action_plan.py
"""
import pandas as pd

from db import PROJECT_ROOT, get_engine

OUT_PATH = PROJECT_ROOT / "docs" / "action_plan.md"
engine = get_engine()
YEARS = 2  # the simulation covers Jan 2024 - Dec 2025

JOINS = """FROM report_recovery_priority p
JOIN report_claim c ON c.claim_id = p.claim_id
JOIN dim_hospital h ON h.hospital_id = c.hospital_id
JOIN dim_insurer i ON i.insurer_id = c.insurer_id
JOIN dim_department d ON d.department_id = c.department_id"""


def recovery_segment(where):
    """Recoverable claims in a segment: count, recoverable Rs crore, expected recovery Rs crore, hours."""
    row = pd.read_sql(f"""SELECT COUNT(*) AS claims, SUM(p.recoverable_amount) / 1e7 AS recoverable_cr,
        SUM(p.expected_recovery) / 1e7 AS expected_cr, SUM(p.effort_hours) AS hours {JOINS} WHERE {where}""",
                      engine).iloc[0]
    return {k: float(v) for k, v in row.items()}


def scalar(sql):
    return float(pd.read_sql(sql, engine).iloc[0, 0])


# ---------------------------------------------------------------- 1. Aegis documentation problem
aegis = recovery_segment("i.insurer_name = 'Aegis Health Cover' AND h.hospital_name IN "
                         "('Coastal Care Hospital', 'Banyan Tree Hospital')")
aegis_rate = pd.read_sql("""SELECT 100.0 * COUNT(*) FILTER (WHERE c.is_rejected)
        / COUNT(*) FILTER (WHERE c.is_decided) AS r
        FROM report_claim c JOIN dim_hospital h ON h.hospital_id = c.hospital_id
        JOIN dim_insurer i ON i.insurer_id = c.insurer_id
        WHERE i.insurer_name = 'Aegis Health Cover' AND h.hospital_name IN ('Coastal Care Hospital', 'Banyan Tree Hospital')""",
                         engine).iloc[0, 0]
aegis_other = pd.read_sql("""SELECT 100.0 * COUNT(*) FILTER (WHERE c.is_rejected)
        / COUNT(*) FILTER (WHERE c.is_decided) AS r
        FROM report_claim c JOIN dim_hospital h ON h.hospital_id = c.hospital_id
        JOIN dim_insurer i ON i.insurer_id = c.insurer_id
        WHERE i.insurer_name = 'Aegis Health Cover' AND h.hospital_name NOT IN ('Coastal Care Hospital', 'Banyan Tree Hospital')""",
                          engine).iloc[0, 0]

# ---------------------------------------------------------------- 2. Cardiology coding errors
cardio = recovery_segment("h.hospital_name = 'Meridian Heart and Research Centre' AND d.department_name = 'Cardiology'")
cardio_rate = pd.read_sql("""SELECT 100.0 * COUNT(*) FILTER (WHERE c.is_rejected) / COUNT(*) FILTER (WHERE c.is_decided) AS r
        FROM report_claim c JOIN dim_hospital h ON h.hospital_id = c.hospital_id
        JOIN dim_department d ON d.department_id = c.department_id
        WHERE h.hospital_name = 'Meridian Heart and Research Centre' AND d.department_name = 'Cardiology'""", engine).iloc[0, 0]
cardio_other = pd.read_sql("""SELECT 100.0 * COUNT(*) FILTER (WHERE c.is_rejected) / COUNT(*) FILTER (WHERE c.is_decided) AS r
        FROM report_claim c JOIN dim_hospital h ON h.hospital_id = c.hospital_id
        JOIN dim_department d ON d.department_id = c.department_id
        WHERE h.hospital_name = 'Meridian Heart and Research Centre' AND d.department_name <> 'Cardiology'""", engine).iloc[0, 0]

# ---------------------------------------------------------------- 3. Lakeview pending backlog
lake = pd.read_sql("""SELECT COUNT(*) AS claims, SUM(c.claim_amount) / 1e7 AS value_cr
        FROM report_claim c JOIN dim_hospital h ON h.hospital_id = c.hospital_id
        WHERE c.pending_age_days > 90 AND h.hospital_name = 'Lakeview General Hospital'""", engine).iloc[0]

# ---------------------------------------------------------------- 4. Unity slow settlement (cash tied up)
unity = pd.read_sql("""SELECT AVG(c.settlement_days) FILTER (WHERE i.insurer_name = 'Unity General Insurance') AS unity_days,
        AVG(c.settlement_days) FILTER (WHERE i.insurer_name <> 'Unity General Insurance') AS other_days,
        SUM(c.claim_amount) FILTER (WHERE i.insurer_name = 'Unity General Insurance'
                                    AND c.settlement_days IS NOT NULL) AS unity_claimed
        FROM report_claim c JOIN dim_insurer i ON i.insurer_id = c.insurer_id""", engine).iloc[0]
unity_daily = float(unity["unity_claimed"]) / (365 * YEARS)
unity_extra_days = float(unity["unity_days"]) - float(unity["other_days"])
unity_locked_cr = unity_daily * unity_extra_days / 1e7  # Little's law: receivables = daily flow x days waiting

# ---------------------------------------------------------------- 5. Winter denial spike
winter = pd.read_sql("""SELECT
    COUNT(*) FILTER (WHERE c.is_decided AND EXTRACT(MONTH FROM c.visit_date) IN (12, 1)) AS w_decided,
    100.0 * COUNT(*) FILTER (WHERE c.is_rejected AND EXTRACT(MONTH FROM c.visit_date) IN (12, 1))
          / NULLIF(COUNT(*) FILTER (WHERE c.is_decided AND EXTRACT(MONTH FROM c.visit_date) IN (12, 1)), 0) AS w_rate,
    100.0 * COUNT(*) FILTER (WHERE c.is_rejected AND EXTRACT(MONTH FROM c.visit_date) NOT IN (12, 1))
          / NULLIF(COUNT(*) FILTER (WHERE c.is_decided AND EXTRACT(MONTH FROM c.visit_date) NOT IN (12, 1)), 0) AS n_rate,
    AVG(c.claim_amount) FILTER (WHERE c.is_rejected AND EXTRACT(MONTH FROM c.visit_date) IN (12, 1)) AS avg_rejected
    FROM report_claim c""", engine).iloc[0]
winter_excess = float(winter["w_decided"]) * (float(winter["w_rate"]) - float(winter["n_rate"])) / 100
winter_value_cr = winter_excess * float(winter["avg_rejected"]) / 1e7

# ---------------------------------------------------------------- 6. Surgery partial approvals
surg = pd.read_sql("""SELECT SUM(c.claim_gap) FILTER (WHERE c.treatment_type = 'Surgery') / 1e7 AS surgery_gap_cr,
        SUM(c.claim_gap) / 1e7 AS total_gap_cr,
        COUNT(*) FILTER (WHERE c.treatment_type = 'Surgery') * 100.0 / COUNT(*) AS surgery_claim_share,
        100.0 * COUNT(*) FILTER (WHERE c.treatment_type = 'Surgery' AND c.claim_status = 'Partially Approved')
          / NULLIF(COUNT(*) FILTER (WHERE c.treatment_type = 'Surgery' AND c.is_decided), 0) AS surgery_partial_rate,
        100.0 * COUNT(*) FILTER (WHERE c.treatment_type <> 'Surgery' AND c.claim_status = 'Partially Approved')
          / NULLIF(COUNT(*) FILTER (WHERE c.treatment_type <> 'Surgery' AND c.is_decided), 0) AS other_partial_rate
        FROM report_claim c""", engine).iloc[0]
surg_rec = pd.read_sql("""SELECT SUM(p.recoverable_amount) / 1e7 AS rec, SUM(p.expected_recovery) / 1e7 AS exp
        FROM report_recovery_priority p JOIN report_claim c ON c.claim_id = p.claim_id
        WHERE c.treatment_type = 'Surgery'""", engine).iloc[0]

total_expected = scalar("SELECT SUM(expected_recovery) / 1e7 FROM report_recovery_priority")


def lakh(x_cr):
    return f"Rs {x_cr * 100:,.0f} lakh" if x_cr < 1 else f"Rs {x_cr:,.2f} crore"


actions = f"""# Action Plan: what the finance team should do first

Generated by `python/action_plan.py` from the simulated database (Jan 2024 - Dec 2025). All data is simulated.
Figures marked **expected** use the assumed win chances and effort hours (70% / 60% / 35% and 1 / 2 / 5 hours;
see [sensitivity report](sensitivity_report.md)). The actions overlap, so the values are **not additive**.
For scale: working every recoverable claim has an expected recovery of Rs {total_expected:,.2f} crore.

| # | Action | Evidence | Money at stake | Effort | Owner | KPI to track |
|---|---|---|---|---|---|---|
| 1 | Fix document preparation for **Aegis at Coastal Care and Banyan Tree**, and resubmit the {aegis['claims']:,.0f} recoverable claims | Denial {aegis_rate:.1f}% vs {aegis_other:.1f}% for Aegis at other hospitals | Recoverable {lakh(aegis['recoverable_cr'])}; expected {lakh(aegis['expected_cr'])} | {aegis['hours']:,.0f} hours | Revenue cycle manager at each hospital | Aegis denial rate at both hospitals, target below 12% |
| 2 | **Audit coding in Meridian Cardiology**, retrain staff, resubmit the {cardio['claims']:,.0f} recoverable claims | Denial {cardio_rate:.1f}% vs {cardio_other:.1f}% for the rest of the hospital | Recoverable {lakh(cardio['recoverable_cr'])}; expected {lakh(cardio['expected_cr'])} | {cardio['hours']:,.0f} hours | Head of coding | Coding-error share of rejections |
| 3 | **Clear the Lakeview backlog**: follow up every claim older than 90 days, oldest and largest first | {lake['claims']:,.0f} claims over 90 days; no other hospital has any | Claim value {lakh(float(lake['value_cr']))} stuck | One owner, weekly review | Lakeview finance lead | Claims pending over 90 days, target 0 |
| 4 | **Escalate Unity General's payment time** and consider a payment-time clause | {unity['unity_days']:.1f} days vs {unity['other_days']:.1f} days for all other insurers, the same at every hospital | About {lakh(unity_locked_cr)} of extra cash tied up on average (daily claim flow x extra days) | Contract and relationship work | Insurer relationship owner | Average settlement days for Unity |
| 5 | **Staff up for December and January** (billing and documentation) | Denial {winter['w_rate']:.1f}% in winter vs {winter['n_rate']:.1f}% in other months | About {winter_excess:,.0f} extra rejected claims over {YEARS} years, roughly {lakh(winter_value_cr)} claimed | Temporary staff in 2 months a year | Revenue cycle head | Winter denial rate, target under 12% |
| 6 | **Add a pre-submission check for surgery claims** (package and documentation) | Surgery is {surg['surgery_claim_share']:.1f}% of claims but {lakh(float(surg['surgery_gap_cr']))} ({100 * surg['surgery_gap_cr'] / surg['total_gap_cr']:.0f}%) of the claim gap; partial approval {surg['surgery_partial_rate']:.1f}% vs {surg['other_partial_rate']:.1f}% for other treatments | Recoverable {lakh(float(surg_rec['rec']))}; expected {lakh(float(surg_rec['exp']))} | Process change plus review | Head of surgery billing | Surgery partial-approval rate |

## How to read this
- **Quick wins (1, 2, 3):** specific, fixable within weeks and cheap, but small in rupees. Start here to show results and build trust.
- **Biggest pool of money (6):** surgery holds most of the gap. Much of its recovery comes simply from working the priority worklist (`python/appeal_letters.py`, dashboard page 3). The pre-submission check stops the loss recurring, but it needs a process decision, so start the discussion early.
- **Action 4 is about cash flow, not lost revenue.** The money is paid, only late.
- **Action 5 is prevention.** It stops the same spike recurring every winter.
- **Order of work:** the priority worklist decides which individual claims to chase first; this plan decides which processes to fix.

## Limits
- Simulated data: the patterns were planted, so this shows the method, not real hospital performance.
- Expected recovery depends on assumed win chances and effort (tested in the sensitivity report).
- Action 4 uses an average-balance approximation (daily claim flow x extra days waiting), not a cash-flow model.
- Action 5 uses the average rejected claim value; the real loss is smaller if some rejected claims are later paid.
"""
OUT_PATH.write_text(actions, encoding="utf-8")
print(actions)
