"""Tests for the AI features using a FAKE language model (no API key, no cost).
Needs the database. Run from the project root:  python python/test_ai_flow.py

Checks: the LLM path works end to end; unsafe SQL from a model is blocked and nothing changes in the
database; invented numbers are flagged or rejected; the database itself refuses writes in the copilot's
read-only transaction; everything falls back to templates when the LLM is unavailable.
"""
from unittest import mock

from sqlalchemy import text

import appeal_letters
import copilot
import daily_brief
from copilot_facts import get_top_claims
from db import get_engine

engine = get_engine()
results = []


def check(name, condition, detail=""):
    results.append(condition)
    print(f"{'PASS' if condition else 'FAIL'}: {name}" + (f"  [{detail}]" if detail and not condition else ""))


def claim_count():
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM fact_claim")).scalar()


before = claim_count()

# 1. LLM path: valid SQL, then an explanation
replies = iter(["```sql\nSELECT hospital_name FROM dim_hospital ORDER BY hospital_id LIMIT 3\n```",
                "The first three hospitals are listed. There are 999 of them."])
with mock.patch("copilot.llm_available", return_value=True), \
        mock.patch("copilot.ask_llm", side_effect=lambda *a, **k: next(replies)):
    r = copilot.ask("list some hospitals", engine)
check("LLM path returns a table", len(r["table"]) == 3 and r["sql"] is not None, r["mode"])
check("Invented number 999 in the explanation is flagged", 999.0 in r["unverified"], str(r["unverified"]))

# 2. A malicious model: tries to drop a table, twice
evil = iter(["DROP TABLE fact_claim", "SELECT * FROM fact_claim; DROP TABLE fact_claim"])
with mock.patch("copilot.llm_available", return_value=True), \
        mock.patch("copilot.ask_llm", side_effect=lambda *a, **k: next(evil)):
    r = copilot.ask("delete everything", engine)
check("Unsafe SQL is refused", r["sql"] is None and "could not produce a safe" in r["answer"], r["answer"])
check("Database unchanged after the attack", claim_count() == before)

# 3. The model's first query is unsafe, the retry is fine
retry = iter(["SELECT * FROM dim_patient", "SELECT COUNT(*) AS n FROM report_claim",
              "There are 305,835 claims."])
with mock.patch("copilot.llm_available", return_value=True), \
        mock.patch("copilot.ask_llm", side_effect=lambda *a, **k: next(retry)):
    r = copilot.ask("how many claims", engine)
check("Retry after a blocked query works", r["sql"] is not None and int(r["table"].iloc[0, 0]) == 305835)
check("Correct number in the explanation is not flagged", r["unverified"] == [], str(r["unverified"]))

# 4. LLM unavailable -> built-in question library
with mock.patch("copilot.llm_available", return_value=True), mock.patch("copilot.ask_llm", return_value=None):
    r = copilot.ask("which insurer is slowest to settle?", engine)
check("Falls back to built-in question when the LLM fails", r["mode"] == "template" and not r["table"].empty)
r = copilot.ask("what is the meaning of life", engine)
check("Unknown question without LLM lists what it can answer", "without an LLM key" in r["answer"])

# 5. Layer 5: the database itself refuses writes in a read-only transaction
refused = False
with engine.connect() as conn:
    conn.execute(text("SET TRANSACTION READ ONLY"))
    try:
        conn.execute(text("CREATE TEMP TABLE should_fail (x int)"))
    except Exception:
        refused = True
    conn.rollback()
check("Read-only transaction refuses a write", refused)

# 6. Appeal letters: a good AI letter is kept, one with invented numbers is rejected
claim = get_top_claims(1, engine).iloc[0]
good = (f"Subject: Re-review of claim {claim['claim_id']}\nWe ask you to review claim {claim['claim_id']} "
        f"submitted on {claim['claim_date']}. Claimed amount {float(claim['claim_amount']):.0f}.")
with mock.patch("appeal_letters.ask_llm", return_value=good):
    letter, mode, note = appeal_letters.build_letter(claim)
check("Grounded AI letter is accepted", mode.startswith("LLM"), mode)
bad = good + " We will also pay a penalty of 123456 rupees."
with mock.patch("appeal_letters.ask_llm", return_value=bad):
    letter, mode, note = appeal_letters.build_letter(claim)
check("AI letter with an invented number is replaced by the template", mode.startswith("template") and "[Name]" in letter, mode)
with mock.patch("appeal_letters.ask_llm", return_value=None):
    letter, mode, note = appeal_letters.build_letter(claim)
check("Letter works with no LLM", mode == "template" and "Subject" in letter)

# 7. Daily brief: invented number is flagged
with mock.patch("daily_brief.ask_llm", return_value="Denial rate is 11.1 percent and losses reached 888.88 crore."):
    brief, mode, unverified, facts = daily_brief.build_brief()
check("Brief flags the invented number", 888.88 in unverified and 11.1 not in unverified, str(unverified))
with mock.patch("daily_brief.ask_llm", return_value=None):
    brief, mode, unverified, facts = daily_brief.build_brief()
check("Brief works with no LLM", mode == "template" and "Headline" in brief)

passed = sum(results)
print(f"\n{passed} of {len(results)} AI flow tests passed")
raise SystemExit(0 if passed == len(results) else 1)
