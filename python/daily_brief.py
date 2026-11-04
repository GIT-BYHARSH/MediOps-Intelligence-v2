"""Daily recovery brief for the finance head.

The numbers come from the database (copilot_facts.py). If an LLM key is set, the model only
WRITES the brief from those facts; a check then flags any number it used that is not in the facts.
Without a key, a fixed template is used. Output: docs/sample_outputs/daily_brief.md

Run from the project root:  python python/daily_brief.py
"""
from db import PROJECT_ROOT
from copilot_facts import facts_text
from llm import ask_llm, llm_available, model_label, unverified_numbers

OUT_PATH = PROJECT_ROOT / "docs" / "sample_outputs" / "daily_brief.md"

SYSTEM = (
    "You are a revenue-cycle analyst writing the daily recovery brief for a hospital finance head. "
    "Use ONLY the facts provided. Never invent or estimate a number; copy numbers exactly as given. "
    "Write at most 180 words in plain business English with these parts: "
    "1) one-sentence headline, 2) three numbered priorities for today (start with which claims to chase "
    "and which alerts to investigate), 3) one risk to watch. "
    "State once that the data is simulated."
)


def template_brief(parts):
    k, claims, alerts, strategies = parts["kpis"], parts["claims"], parts["alerts"], parts["strategies"]
    best = strategies.iloc[0]
    top = claims.iloc[0]
    high = alerts[alerts["severity"] == "High"]
    first_alert = alerts.iloc[0]
    return (
        f"**Headline:** Rs {k['claim_gap_cr']:.2f} crore was claimed but not paid, and Rs {k['recoverable_cr']:.2f} crore "
        f"of it is recoverable. Denial rate is {k['denial_rate_pct']:.1f} percent (simulated data).\n\n"
        f"**Priorities today**\n"
        f"1. Work the claims list in priority order. Rank 1 is {top['hospital_name']} / {top['insurer_name']} "
        f"({top['rejection_reason']}), expected recovery Rs {top['expected_recovery'] / 1e5:.2f} lakh for "
        f"{top['effort_hours']:.0f} hour(s). Priority order is {best['times_better_than_random']:.1f} times better than "
        f"random order with the same 10,000 hours.\n"
        f"2. Investigate the top alert: {first_alert['headline']} ({first_alert['detail']}). "
        f"There are {len(high)} high-severity alerts in total.\n"
        f"3. Chase the {k['pending_over_90_days']:,.0f} claims pending over 90 days before they age further.\n\n"
        f"**Risk to watch:** average settlement time is {k['avg_settlement_days']:.2f} days overall, but one insurer is far slower "
        f"(see the alerts), which ties up cash."
    )


def build_brief():
    """Return (brief_text, mode, unverified_numbers, facts_text)."""
    facts, parts = facts_text()
    text = ask_llm(SYSTEM, facts, temperature=0.2, max_tokens=500)
    if text is None:
        return template_brief(parts), "template", [], facts
    return text, f"LLM ({model_label()})", unverified_numbers(text, facts), facts


def main():
    brief, mode, unverified, facts = build_brief()
    status = ("all numbers found in the facts" if not unverified
              else f"CHECK THESE NUMBERS BY HAND: {unverified}")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        "# Daily Recovery Brief\n\n"
        "> Simulated data. AI-written briefs must be reviewed by a person before use.\n\n"
        f"{brief}\n\n---\n**Mode:** {mode}  \n**Grounding check:** {status}\n\n"
        f"<details><summary>Facts given to the writer</summary>\n\n```\n{facts}\n```\n</details>\n",
        encoding="utf-8",
    )
    print(brief)
    print(f"\nMode: {mode}\nGrounding check: {status}\nSaved: {OUT_PATH}")


if __name__ == "__main__":
    main()
