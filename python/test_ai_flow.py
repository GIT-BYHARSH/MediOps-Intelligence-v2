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
with mock.patch("copilot.llm_available", return_value=True), mock.patch("copilot.ask_llm", return_value=None), \
        mock.patch.dict("copilot.last_failure", {"reason": "HTTP 429"}):
    r = copilot.ask("what is the meaning of life", engine)
check("Rate-limited AI gives a 'try again' message, not 'add a key'",
      "try again" in r["answer"] and "Add LLM_API_KEY" not in r["answer"], r["answer"][:80])
with mock.patch("copilot.llm_available", return_value=False):
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

# 8. Chat memory: earlier question and SQL are passed to the model for follow-ups
seen_prompts = []


def spy(system, user, **kwargs):
    seen_prompts.append(user)
    return "SELECT COUNT(*) AS n FROM report_claim" if len(seen_prompts) % 2 == 1 else "There are 305,835 claims."


history = [("how many claims?", "SELECT COUNT(*) FROM report_claim")]
with mock.patch("copilot.llm_available", return_value=True), mock.patch("copilot.ask_llm", side_effect=spy):
    copilot.ask("and only the rejected ones?", engine, history=history)
check("Follow-up question carries the earlier question and SQL",
      "Earlier in this conversation" in seen_prompts[0] and "how many claims?" in seen_prompts[0]
      and "and only the rejected ones?" in seen_prompts[0])

# 9. Auto-chart picks sensible labels and values
hot = copilot.run_query(copilot.CANNED[0][2], engine)
kind, frame = copilot.chart_frame(hot)
check("Chart for hotspots: bar chart, labels joined, rate column", kind == "bar" and "denial_rate_pct" in frame.columns
      and "@" in str(frame.index[0]), f"{kind} {list(frame.columns)}")
months = copilot.run_query(copilot.CANNED[5][2], engine)
check("Chart for monthly denial rate is a line", copilot.chart_frame(months)[0] == "line")

# 10. Alert investigator: facts come from the data; AI text is grounded-checked
import investigate  # noqa: E402

alerts = investigate.alert_table(engine)
kinds = {investigate.parse_alert(r["check"], r["headline"])[0] for _, r in alerts.iterrows()}
check("All 9 alerts can be parsed (5 types)", len(alerts) == 9 and kinds == {"pair", "department", "pending", "settlement", "month"}, str(kinds))
pair_alert = alerts[alerts["headline"].str.contains("Coastal Care")].iloc[0]
with mock.patch("investigate.ask_llm", return_value=None):
    out = investigate.investigate(pair_alert["check"], pair_alert["headline"], engine)
check("Investigation shows 28.6% and finds Incomplete Documents", any("28.6" in f for f in out["facts"])
      and "Incomplete Documents" in " ".join(out["facts"]))
with mock.patch("investigate.ask_llm", return_value="Denial is 28.6 percent and caused 777 extra rejections."):
    out = investigate.investigate(pair_alert["check"], pair_alert["headline"], engine)
check("Investigator flags an invented number from the AI", 777.0 in out["unverified"] and 28.6 not in out["unverified"],
      str(out["unverified"]))
pending_alert = alerts[alerts["check"].str.startswith("Pending")].iloc[0]
with mock.patch("investigate.ask_llm", return_value=None):
    out = investigate.investigate(pending_alert["check"], pending_alert["headline"], engine)
check("Pending alert finds 1,389 claims and no other hospital", any("1,389" in f for f in out["facts"])
      and any("0 claims pending" in f for f in out["facts"]))

# 11. What-if simulator reproduces the base case
import whatif  # noqa: E402

sim = whatif.simulate(whatif.load_claims(engine), 10_000, 1.0, 1.0)
rec = dict(zip(sim["strategy"], sim["recovery_cr"]))
check("What-if base case matches the SQL simulation (21.87 / 16.68 / 14.00)",
      abs(rec["Priority score"] - 21.87) < 0.01 and abs(rec["Largest amount first"] - 16.68) < 0.01
      and abs(rec["Quickest first"] - 14.00) < 0.01, str(rec))
sim_more = whatif.simulate(whatif.load_claims(engine), 20_000, 1.0, 1.0)
check("More hours recover more", sim_more["recovery_cr"].iloc[0] > sim["recovery_cr"].iloc[0])

passed = sum(results)
print(f"\n{passed} of {len(results)} AI flow tests passed")
raise SystemExit(0 if passed == len(results) else 1)
