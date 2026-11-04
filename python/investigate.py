"""Alert investigator: pick an automatic alert and drill down into WHY it happened.

Step 1 (always the same, no AI): run fixed drill-down queries for that type of alert and collect facts
        (rates against peers, breakdown by denial reason, ageing, ...).
Step 2 (AI, optional): the language model writes a short explanation, likely cause and recommended action
        from those facts only. A grounding check flags any number that is not in the facts.
Without an LLM key a fixed template writes the explanation.

The alerts only say WHERE to look. The drill-down gives evidence; the cause is stated as a hypothesis.
"""
import pandas as pd
from sqlalchemy import text

from copilot_facts import get_alerts
from db import get_engine
from llm import ask_llm, model_label, unverified_numbers

BASE = """FROM report_claim c
JOIN dim_hospital  h ON h.hospital_id  = c.hospital_id
JOIN dim_insurer   i ON i.insurer_id   = c.insurer_id
JOIN dim_department d ON d.department_id = c.department_id"""

RATE = """COUNT(*) FILTER (WHERE c.is_decided) AS decided,
       100.0 * COUNT(*) FILTER (WHERE c.is_rejected) / NULLIF(COUNT(*) FILTER (WHERE c.is_decided), 0) AS rate"""

SYSTEM = (
    "You are a revenue-cycle analyst explaining an alert to a hospital finance manager. "
    "Use ONLY the facts provided; never invent a number. In at most 120 words give: "
    "1) what is happening, 2) the most likely cause, stated as a hypothesis to verify (not as proven), "
    "3) one concrete recommended action. The data is simulated."
)


def _row(engine, where, params):
    sql = f"SELECT {RATE} {BASE} WHERE {where}"
    row = pd.read_sql(text(sql), engine, params=params).iloc[0]
    return int(row["decided"]), (float(row["rate"]) if row["rate"] is not None and pd.notna(row["rate"]) else 0.0)


def _reasons(engine, where, params):
    sql = f"""SELECT c.rejection_reason AS reason, COUNT(*) AS claims,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
        {BASE} WHERE c.is_rejected AND c.rejection_reason IS NOT NULL AND {where}
        GROUP BY 1 ORDER BY claims DESC"""
    return pd.read_sql(text(sql), engine, params=params)


def _scalar(engine, sql, params):
    value = pd.read_sql(text(sql), engine, params=params).iloc[0, 0]
    return 0.0 if value is None or pd.isna(value) else float(value)


def investigate_pair(engine, insurer, hospital):
    p = {"i": insurer, "h": hospital}
    n, rate = _row(engine, "i.insurer_name = :i AND h.hospital_name = :h", p)
    _, elsewhere = _row(engine, "i.insurer_name = :i AND h.hospital_name <> :h", p)
    _, others_here = _row(engine, "i.insurer_name <> :i AND h.hospital_name = :h", p)
    table = _reasons(engine, "i.insurer_name = :i AND h.hospital_name = :h", p)
    lakh = _scalar(engine, f"SELECT SUM(c.recoverable_amount) / 1e5 {BASE} WHERE i.insurer_name = :i AND h.hospital_name = :h", p)
    facts = [f"{insurer} at {hospital}: denial rate {rate:.1f} percent on {n:,} decided claims",
             f"Same insurer at its other hospitals: {elsewhere:.1f} percent",
             f"Other insurers at this hospital: {others_here:.1f} percent",
             f"Recoverable amount in this pair: Rs {lakh:.1f} lakh"]
    if not table.empty:
        top = table.iloc[0]
        facts.append(f"Most common rejection reason here: {top['reason']} ({top['share_pct']:.1f} percent of rejections)")
    if rate > 1.5 * max(elsewhere, others_here):
        cause = "a problem specific to this insurer and hospital together, not to either one alone"
        action = ("Review how this hospital prepares documents for this insurer, and start resubmitting the "
                  "recoverable claims in priority order.")
    else:
        cause = "a broader problem with this insurer or this hospital (the pair is not unusual on its own)"
        action = "Look at the insurer's and the hospital's overall denial patterns before acting on this pair."
    return facts, table, cause, action


def investigate_department(engine, hospital, department):
    p = {"h": hospital, "d": department}
    n, rate = _row(engine, "h.hospital_name = :h AND d.department_name = :d", p)
    _, others = _row(engine, "h.hospital_name = :h AND d.department_name <> :d", p)
    table = _reasons(engine, "h.hospital_name = :h AND d.department_name = :d", p)
    facts = [f"{hospital} / {department}: denial rate {rate:.1f} percent on {n:,} decided claims",
             f"Other departments at the same hospital: {others:.1f} percent"]
    if not table.empty:
        top = table.iloc[0]
        facts.append(f"Most common rejection reason: {top['reason']} ({top['share_pct']:.1f} percent of rejections)")
    if rate > 1.5 * others:
        return (facts, table, "a process problem inside this department (the rest of the hospital is normal)",
                "Audit a sample of this department's rejected claims and retrain the coding or billing staff.")
    return (facts, table, "a hospital-wide issue (other departments are also high)",
            "Look at the hospital's overall billing process.")


def investigate_pending(engine, hospital):
    p = {"h": hospital}
    table = pd.read_sql(text(f"""SELECT c.aging_bucket AS age_bucket, COUNT(*) AS pending_claims,
        ROUND(SUM(c.claim_amount) / 1e7, 2) AS claim_value_cr {BASE}
        WHERE c.claim_status = 'Pending' AND h.hospital_name = :h GROUP BY 1 ORDER BY 1"""), engine, params=p)
    old_here = _scalar(engine, f"SELECT COUNT(*) {BASE} WHERE c.pending_age_days > 90 AND h.hospital_name = :h", p)
    old_elsewhere = _scalar(engine, f"SELECT COUNT(*) {BASE} WHERE c.pending_age_days > 90 AND h.hospital_name <> :h", p)
    value = _scalar(engine, f"SELECT SUM(c.claim_amount) / 1e7 {BASE} WHERE c.pending_age_days > 90 AND h.hospital_name = :h", p)
    facts = [f"{hospital}: {old_here:,.0f} claims pending over 90 days, worth Rs {value:.2f} crore",
             f"All other hospitals together: {old_elsewhere:,.0f} claims pending over 90 days"]
    if old_elsewhere < 0.1 * old_here:
        cause = "claims that were submitted and never followed up at this hospital (no other hospital has this problem)"
    else:
        cause = "a follow-up gap that also exists at other hospitals"
    return (facts, table, cause,
            "Assign someone to follow up on every claim older than 90 days at this hospital, oldest and largest first.")


def investigate_settlement(engine, insurer):
    p = {"i": insurer}
    mine = _scalar(engine, f"SELECT AVG(c.settlement_days) {BASE} WHERE i.insurer_name = :i", p)
    others = _scalar(engine, f"SELECT AVG(c.settlement_days) {BASE} WHERE i.insurer_name <> :i", p)
    claims = _scalar(engine, f"SELECT COUNT(*) {BASE} WHERE i.insurer_name = :i AND c.settlement_days IS NOT NULL", p)
    table = pd.read_sql(text(f"""SELECT h.hospital_name, ROUND(AVG(c.settlement_days), 1) AS avg_days {BASE}
        WHERE i.insurer_name = :i AND c.settlement_days IS NOT NULL GROUP BY 1 ORDER BY avg_days DESC LIMIT 5"""),
        engine, params=p)
    per_hospital = pd.read_sql(text(f"""SELECT AVG(c.settlement_days) AS a {BASE}
        WHERE i.insurer_name = :i AND c.settlement_days IS NOT NULL GROUP BY h.hospital_name"""), engine, params=p)["a"]
    low, high = float(per_hospital.min()), float(per_hospital.max())
    facts = [f"{insurer}: average settlement {mine:.1f} days on {claims:,.0f} settled claims",
             f"All other insurers: {others:.1f} days",
             f"Across hospitals this insurer's average ranges from {low:.1f} to {high:.1f} days"]
    if high - low < 15:
        cause = "a slow payer across the whole network (every hospital waits about the same)"
        action = "Escalate to the insurer relationship owner and consider a contract clause on payment time."
    else:
        cause = "slowness concentrated at some hospitals"
        action = "Compare the slow hospitals' submission process with the fast ones."
    return facts, table, cause, action


def investigate_month(engine, year_month):
    p = {"m": year_month}
    where_m = "TO_CHAR(c.visit_date, 'YYYY-MM') = :m"
    where_other = "TO_CHAR(c.visit_date, 'YYYY-MM') <> :m AND EXTRACT(MONTH FROM c.visit_date) NOT IN (12, 1)"
    n, rate = _row(engine, where_m, p)
    n_other, typical = _row(engine, where_other, p)
    table = pd.read_sql(text(f"""SELECT i.insurer_name,
        ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_rejected) / NULLIF(COUNT(*) FILTER (WHERE c.is_decided), 0), 1) AS denial_rate_pct
        {BASE} WHERE {where_m} GROUP BY 1 ORDER BY denial_rate_pct DESC"""), engine, params=p)
    low, high = float(table["denial_rate_pct"].min()), float(table["denial_rate_pct"].max())
    facts = [f"Month {year_month}: denial rate {rate:.1f} percent on {n:,} decided claims",
             f"Typical non-winter month: {typical:.1f} percent",
             f"Across insurers that month the denial rate ranges from {low:.1f} to {high:.1f} percent"]
    if n < 5000:
        cause = ("a month with few decided claims (many are still pending), so differences between insurers "
                 "may be noise rather than a real insurer problem")
        action = "Re-check this month after the pending claims are settled before acting on it."
    elif year_month[-2:] in ("12", "01") and high - low < 6:
        cause = "winter overload (December or January) that affects every insurer, not just one"
        action = "Plan extra billing and documentation staff for every December and January."
    elif high - low >= 6:
        cause = "a spike concentrated in one or two insurers"
        action = "Check which insurer drives the spike in the table and investigate that insurer."
    else:
        cause = "an unusual month with no single obvious driver"
        action = "Check whether the month had unusual volume or a process change."
    return facts, table, cause, action


def alert_table(engine=None):
    return get_alerts(9, engine or get_engine())


def parse_alert(check, headline):
    """Turn an alert row into (kind, args)."""
    if check.startswith("Denial rate: insurer"):
        insurer, hospital = headline.split(" at ", 1)
        return "pair", (insurer, hospital)
    if check.startswith("Denial rate: hospital department"):
        hospital, department = headline.rsplit(" - ", 1)
        return "department", (hospital, department)
    if check.startswith("Pending"):
        return "pending", (headline,)
    if check.startswith("Settlement"):
        return "settlement", (headline,)
    if check.startswith("Monthly"):
        return "month", (headline.replace("Denial spike in ", ""),)
    raise ValueError(f"Unknown alert type: {check}")


RUNNERS = {"pair": investigate_pair, "department": investigate_department, "pending": investigate_pending,
           "settlement": investigate_settlement, "month": investigate_month}


def investigate(check, headline, engine=None):
    """Return dict: title, facts, table, narrative, mode, unverified, cause, action."""
    engine = engine or get_engine()
    kind, args = parse_alert(check, headline)
    facts, table, cause, action = RUNNERS[kind](engine, *args)
    facts_text = "\n".join(f"- {f}" for f in facts)
    prompt = (f"Alert: {headline}\n\nFacts from drill-down queries:\n{facts_text}\n\n"
              f"Suggested direction: cause = {cause}; action = {action}")
    ai = ask_llm(SYSTEM, prompt, temperature=0.2, max_tokens=300)
    if ai is None:
        narrative = (f"**What is happening:** " + "; ".join(facts) + f".\n\n**Likely cause (hypothesis to verify):** {cause}.\n\n"
                     f"**Recommended action:** {action}")
        mode, bad = "template", []
    else:
        narrative, mode, bad = ai, f"LLM ({model_label()})", unverified_numbers(ai, prompt)
    return {"title": headline, "facts": facts, "table": table, "narrative": narrative, "mode": mode,
            "unverified": bad, "cause": cause, "action": action}


if __name__ == "__main__":
    eng = get_engine()
    for _, a in alert_table(eng).head(9).iterrows():
        out = investigate(a["check"], a["headline"], eng)
        print(f"\n=== {out['title']} [{out['mode']}] ===\n{out['narrative']}")
