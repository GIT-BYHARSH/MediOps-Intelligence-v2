"""Safety checks for SQL written by an AI model.

An LLM may write the SQL for the "Ask the data" copilot, so we never run it blindly.
Layers of protection (this file is layer 1; copilot.py adds the others):
  1. Only ONE read-only SELECT (or WITH ... SELECT) statement. No comments, no semicolon tricks.
  2. Dangerous keywords are rejected (DROP, DELETE, UPDATE, INTO, COPY, pg_sleep, ...).
  3. Only an allow-list of reporting views and dimension tables may be used.
     Raw fact tables and the patient table are blocked.
  4. Every query is wrapped with a row limit.
  5. (copilot.py) the query runs inside a READ ONLY transaction with a time limit.
"""
import re

ALLOWED_TABLES = {
    "report_claim", "report_recovery_priority", "report_alert", "report_strategy",
    "report_worklist_top10", "dim_hospital", "dim_department", "dim_insurer", "dim_date",
}
BLOCKED_TABLES = {"fact_claim", "fact_bill", "fact_visit", "dim_patient"}
MAX_ROWS = 200

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|execute|vacuum|"
    r"analyze|listen|notify|lock|merge|into|pg_[a-z0-9_]+|information_schema|set_config|"
    r"current_setting|lo_[a-z_]+)\b",
    re.IGNORECASE,
)
# EXTRACT(MONTH FROM d), SUBSTRING(x FROM 1), TRIM(... FROM x) contain the word FROM but are not tables
_SPECIAL_FROM = re.compile(r"\b(extract|substring|trim|overlay)\s*\((?:[^()]|\([^()]*\))*\)", re.IGNORECASE)
_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)", re.IGNORECASE)
_CTE_NAME = re.compile(
    r"(?:\bwith|,)\s*(?:recursive\s+)?([a-z_][a-z0-9_]*)\s+as\s*(?:not\s+materialized\s*|materialized\s*)?\(",
    re.IGNORECASE,
)


def clean_sql(raw):
    """Remove markdown fences and trailing semicolons that models often add."""
    sql = (raw or "").strip()
    sql = re.sub(r"^```[a-zA-Z]*\s*", "", sql)
    sql = re.sub(r"\s*```$", "", sql)
    return sql.strip().rstrip(";").strip()


def validate_sql(raw):
    """Return (True, cleaned_sql) if the query is safe, otherwise (False, reason)."""
    sql = clean_sql(raw)
    if not sql:
        return False, "Empty query."
    if ";" in sql:
        return False, "Only one statement is allowed."
    if "--" in sql or "/*" in sql or "*/" in sql:
        return False, "Comments are not allowed."
    if not re.match(r"(select|with)\b", sql, re.IGNORECASE):
        return False, "Only SELECT queries are allowed."

    forbidden = _FORBIDDEN.search(sql)
    if forbidden:
        return False, f"Forbidden keyword: {forbidden.group(0)}"

    for table in BLOCKED_TABLES:
        if re.search(rf"\b{table}\b", sql, re.IGNORECASE):
            return False, f"Table not allowed: {table}"

    scan = _SPECIAL_FROM.sub(" ", sql)
    ctes = {name.lower() for name in _CTE_NAME.findall(scan)}
    for ref in _TABLE_REF.findall(scan):
        name = ref.lower()
        if name.startswith("public."):
            name = name[len("public."):]
        if name in ctes:
            continue
        if name not in ALLOWED_TABLES:
            return False, f"Table not allowed: {ref}"
    return True, sql


def add_row_limit(sql):
    """Wrap a validated query so it can never return more than MAX_ROWS rows."""
    return f"SELECT * FROM (\n{sql}\n) AS guarded LIMIT {MAX_ROWS}"
