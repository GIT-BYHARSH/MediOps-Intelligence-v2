"""MediOps Copilot: ask a question about the claims data in plain English.

With an LLM key: the model writes ONE read-only SQL query for the question, sql_guard.py checks it,
the query runs in a READ ONLY transaction with a time limit, and the model explains the result in a
few sentences (a grounding check flags numbers that are not in the result).
Without a key: a built-in library of common questions is used (same guarded runner).

Run from the project root:
    python python/copilot.py "which insurer is slowest to settle?"
    python python/copilot.py            (interactive)
"""
import re
import sys

import pandas as pd
from sqlalchemy import text

from db import get_engine
from llm import ask_llm, llm_available, model_label, unverified_numbers
from sql_guard import add_row_limit, validate_sql

SCHEMA = """
PostgreSQL views you may query (ONLY these):

report_claim  (one row per insurance claim, 305,835 rows)
  claim_id, hospital_id, department_id, insurer_id, visit_date, claim_date, settlement_date,
  visit_type, treatment_type, diagnosis, gender, age_group,
  claim_status ('Approved','Partially Approved','Rejected','Pending'),
  rejection_reason ('Incomplete Documents','Coding Error','Medical Necessity Not Met','Policy Exclusion','Duplicate Claim'; NULL if none),
  is_decided, is_rejected, is_approved (booleans), bill_amount, claim_amount, approved_amount,
  claim_gap (rupees claimed but not paid; decided claims only),
  recoverable_amount (gap from fixable reasons: Incomplete Documents, Coding Error, Medical Necessity Not Met),
  is_preventable (1/0/NULL), settlement_days, pending_age_days (pending claims only),
  aging_bucket ('0-30 days','31-60 days','61-90 days','90+ days'; pending claims only)
report_recovery_priority (one row per recoverable claim)
  claim_id, recoverable_amount, win_chance, effort_hours, expected_recovery, priority_score, priority_rank, priority_decile
report_alert (automatic anomaly alerts)  alert_rank, check, headline, detail, severity, value, typical, z, impact, impact_unit
report_strategy (recovery strategies under 10,000 team hours)  strategy, claims_worked, hours_used, expected_recovery_crore, times_better_than_random, sort_order
dim_hospital (hospital_id, hospital_name, city, state, hospital_type, total_beds)
dim_department (department_id, hospital_id, department_name)
dim_insurer (insurer_id, insurer_name, insurer_type)
dim_date (date_id, year, quarter, month_number, month_name, year_month, day_name, is_winter)

Join keys: report_claim.hospital_id = dim_hospital.hospital_id; report_claim.insurer_id = dim_insurer.insurer_id;
report_claim.department_id = dim_department.department_id; report_claim.visit_date = dim_date.date_id;
report_recovery_priority.claim_id = report_claim.claim_id.

Definitions:
- Denial rate (percent) = 100 * rejected claims / decided claims. Pending claims are NOT decided.
- 1 crore = 10,000,000 rupees; 1 lakh = 100,000 rupees. Show money in crore (divide by 1e7) unless small.
- Winter = December and January.
"""

SQL_SYSTEM = (
    "You are a careful PostgreSQL analyst for a hospital revenue-recovery database.\n" + SCHEMA +
    "\nRules: return ONLY one SELECT statement (a WITH ... SELECT is fine). No explanation, no markdown, "
    "no semicolons, no comments. Use only the views above. Round percentages to 1 decimal and crore values to 2. "
    "Always include a sensible ORDER BY and keep results small (LIMIT 20 unless the user asks for more). "
    "If the question cannot be answered from these views, return: SELECT 'Cannot answer from this data' AS message"
)

SUMMARY_SYSTEM = (
    "You explain query results to a hospital finance manager. Use ONLY the numbers in the result table; never "
    "invent or estimate a number. Answer in at most 4 sentences. Say if the result is empty. "
    "The data is simulated; do not name real hospitals or insurers as real."
)

# ---------------------------------------------------------------- built-in questions (no LLM needed)
_DENIED = "COUNT(*) FILTER (WHERE c.is_decided)"
CANNED = [
    (["hotspot", "highest denial", "denial rate by insurer", "which insurer at which hospital"],
     "Top 5 insurer-at-hospital denial hotspots",
     f"""SELECT i.insurer_name, h.hospital_name, {_DENIED} AS decided_claims,
       ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_rejected) / NULLIF({_DENIED}, 0), 1) AS denial_rate_pct
FROM report_claim c
JOIN dim_insurer i ON i.insurer_id = c.insurer_id
JOIN dim_hospital h ON h.hospital_id = c.hospital_id
GROUP BY 1, 2 HAVING {_DENIED} >= 200
ORDER BY denial_rate_pct DESC LIMIT 5"""),
    (["slowest", "settle", "settlement", "pays slowly", "takes longest"],
     "Average settlement days by insurer (slowest first)",
     """SELECT i.insurer_name, ROUND(AVG(c.settlement_days), 1) AS avg_settlement_days
FROM report_claim c JOIN dim_insurer i ON i.insurer_id = c.insurer_id
WHERE c.settlement_days IS NOT NULL
GROUP BY 1 ORDER BY avg_settlement_days DESC"""),
    (["pending", "older than 90", "over 90", "backlog", "aging", "ageing"],
     "Hospitals with claims pending over 90 days",
     """SELECT h.hospital_name, COUNT(*) AS claims_pending_over_90_days
FROM report_claim c JOIN dim_hospital h ON h.hospital_id = c.hospital_id
WHERE c.pending_age_days > 90
GROUP BY 1 ORDER BY claims_pending_over_90_days DESC LIMIT 5"""),
    (["treatment", "surgery", "where is the money", "claim gap by"],
     "Claim gap by treatment type (Rs crore)",
     """SELECT treatment_type, ROUND(SUM(claim_gap) / 1e7, 2) AS claim_gap_cr,
       ROUND(100.0 * SUM(claim_gap) / SUM(SUM(claim_gap)) OVER (), 1) AS share_of_gap_pct
FROM report_claim WHERE claim_gap IS NOT NULL
GROUP BY 1 ORDER BY claim_gap_cr DESC"""),
    (["reason", "why denied", "why are claims", "rejection"],
     "Claim gap by rejection reason (Rs crore)",
     """SELECT rejection_reason, COUNT(*) AS claims, ROUND(SUM(claim_gap) / 1e7, 2) AS claim_gap_cr
FROM report_claim WHERE rejection_reason IS NOT NULL AND claim_gap IS NOT NULL
GROUP BY 1 ORDER BY claim_gap_cr DESC"""),
    (["winter", "december", "january", "month", "season"],
     "Denial rate by calendar month",
     f"""SELECT EXTRACT(MONTH FROM c.visit_date)::int AS month_number,
       ROUND(100.0 * COUNT(*) FILTER (WHERE c.is_rejected) / NULLIF({_DENIED}, 0), 1) AS denial_rate_pct
FROM report_claim c GROUP BY 1 ORDER BY 1"""),
    (["strategy", "strategies", "random order", "better than random", "recover"],
     "Recovery strategies compared (same 10,000 team hours)",
     "SELECT strategy, expected_recovery_crore, times_better_than_random FROM report_strategy ORDER BY sort_order"),
    (["alert", "anomal", "unusual"],
     "Automatic alerts",
     "SELECT alert_rank, headline, detail, severity FROM report_alert ORDER BY alert_rank"),
    (["chase first", "worklist", "top claims", "priority claims", "which claims"],
     "Top 10 claims to chase first",
     """SELECT p.priority_rank, h.hospital_name, i.insurer_name, c.rejection_reason,
       ROUND(p.expected_recovery / 1e5, 2) AS expected_recovery_lakh, p.effort_hours
FROM report_recovery_priority p
JOIN report_claim c ON c.claim_id = p.claim_id
JOIN dim_hospital h ON h.hospital_id = c.hospital_id
JOIN dim_insurer i ON i.insurer_id = c.insurer_id
ORDER BY p.priority_rank, c.claim_id LIMIT 10"""),
]


def run_query(sql, engine=None):
    """Validate, then run inside a READ ONLY transaction with a time limit."""
    ok, cleaned = validate_sql(sql)
    if not ok:
        raise ValueError(f"Blocked by safety check: {cleaned}")
    guarded = add_row_limit(cleaned)
    guarded = re.sub(r"(?<!:):(?!:)", r"\\:", guarded)  # a lone colon would look like a bind parameter
    engine = engine or get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text("SET LOCAL statement_timeout = 15000"))
        df = pd.read_sql(text(guarded), conn)
        conn.rollback()
    return df


def df_to_text(df, max_rows=30):
    return "(no rows)" if df.empty else df.head(max_rows).to_string(index=False)


def match_canned(question):
    q = question.lower()
    scored = [(sum(k in q for k in keys), title, sql) for keys, title, sql in CANNED]
    best = max(scored, key=lambda s: s[0])
    return best if best[0] > 0 else None


def available_questions():
    return [title for _, title, _ in CANNED]


def _history_block(history):
    """Last few questions and their SQL, so follow-ups like 'and in winter?' make sense."""
    if not history:
        return ""
    lines = ["Earlier in this conversation (use it only to understand follow-up questions):"]
    for q, sql in history[-3:]:
        lines.append(f"Q: {q}")
        if sql:
            lines.append(f"SQL: {sql}")
    return "\n".join(lines) + "\n\nNew question: "


def chart_frame(df):
    """Pick a simple chart for a result table. Returns (kind, frame) or None.
    Labels are the text columns joined together; the value is the most relevant number column."""
    if df is None or len(df) < 2 or len(df.columns) < 2:
        return None
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    labels = [c for c in df.columns if c not in numeric]
    if not numeric:
        return None
    preferred = ["denial_rate", "rate", "expected_recovery", "gap", "days", "claims", "count"]
    value = next((c for p in preferred for c in numeric if p in c.lower() and c.lower() != "priority_rank"), None)
    if value is None:
        value = numeric[-1]
    if labels:
        index = df[labels].astype(str).agg(" @ ".join, axis=1)
        kind = "line" if any(k in labels[0].lower() for k in ("month", "date", "year")) else "bar"
    else:
        x_candidates = [c for c in numeric if c != value]
        if not x_candidates:
            return None
        index = df[x_candidates[0]].astype(str)
        kind = "line" if any(k in x_candidates[0].lower() for k in ("month", "date", "year")) else "bar"
    frame = pd.DataFrame({value: df[value].astype(float).to_numpy()}, index=index.to_numpy())
    return kind, frame


def _ask_with_llm(question, engine, history=None):
    """Return a result dict, or None if the LLM path did not work (caller falls back)."""
    sql, df, problem = None, None, ""
    context = _history_block(history)
    for _ in range(2):  # one retry, telling the model what went wrong
        prompt = (context + question) if not problem else (
            f"{context}{question}\n\nYour previous query failed: {problem}\nWrite a corrected single SELECT statement.")
        raw = ask_llm(SQL_SYSTEM, prompt, temperature=0, max_tokens=500)
        if raw is None:
            return None
        ok, info = validate_sql(raw)
        if not ok:
            problem = info
            continue
        try:
            df = run_query(info, engine)
            sql = info
            break
        except Exception as error:
            problem = str(error).splitlines()[0][:200]
    if sql is None:
        return {"mode": f"LLM ({model_label()})", "sql": None, "table": pd.DataFrame(), "unverified": [],
                "answer": f"I could not produce a safe, working query for that question. Last problem: {problem}"}

    table_text = df_to_text(df)
    answer = ask_llm(SUMMARY_SYSTEM, f"Question: {question}\n\nSQL result:\n{table_text}", temperature=0.1, max_tokens=300)
    unverified = unverified_numbers(answer, table_text) if answer else []
    return {"mode": f"LLM ({model_label()})", "sql": sql, "table": df, "unverified": unverified,
            "answer": answer or "Result shown below (the explanation step was unavailable)."}


def ask(question, engine=None, history=None):
    """Answer a question. history = list of (question, sql) from earlier turns.
    Returns dict: mode, sql, table, answer, unverified."""
    engine = engine or get_engine()
    if llm_available():
        result = _ask_with_llm(question, engine, history)
        if result is not None:
            return result
    match = match_canned(question)
    if match is None:
        options = "\n".join(f"- {t}" for t in available_questions())
        return {"mode": "template", "sql": None, "table": pd.DataFrame(), "unverified": [],
                "answer": ("I can answer these topics without an LLM key:\n" + options +
                           "\n\nAdd LLM_API_KEY and LLM_MODEL to .env to ask any question.")}
    _, title, sql = match
    df = run_query(sql, engine)
    return {"mode": "template", "sql": sql, "table": df, "unverified": [], "answer": title}


def print_result(result):
    print(f"\n[{result['mode']}]")
    if result["sql"]:
        print(f"SQL:\n{result['sql']}\n")
    if not result["table"].empty:
        print(df_to_text(result["table"]))
        print()
    print(result["answer"])
    if result["unverified"]:
        print(f"\nWARNING: numbers in the explanation not found in the result: {result['unverified']}")


def main():
    if len(sys.argv) > 1:
        print_result(ask(" ".join(sys.argv[1:])))
        return
    print("MediOps Copilot (type 'quit' to exit). Simulated data.")
    while True:
        question = input("\nAsk: ").strip()
        if question.lower() in {"quit", "exit", ""}:
            break
        print_result(ask(question))


if __name__ == "__main__":
    main()
