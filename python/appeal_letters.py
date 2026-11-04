"""Draft appeal / correction letters for the top-priority claims.

Facts (hospital, insurer, amounts, reason) come from the database. With an LLM key the model writes
the letter; a check then rejects any letter that contains a number not in the claim facts and falls
back to the template. Internal estimates (win chance, expected recovery) are never given to the model
because they must not appear in a letter to an insurer. Output: docs/sample_outputs/appeal_letters.md

Run from the project root:  python python/appeal_letters.py [how_many]
"""
import sys

from db import PROJECT_ROOT
from copilot_facts import get_top_claims, inr
from llm import ask_llm, model_label, unverified_numbers

OUT_PATH = PROJECT_ROOT / "docs" / "sample_outputs" / "appeal_letters.md"

REASON_GUIDE = {
    "Incomplete Documents": {
        "action": "Resubmit the claim with the documents that were missing.",
        "paragraph": ("The claim was returned because documentation was reported as incomplete. We are resubmitting it "
                      "with the complete set of supporting documents and ask you to re-assess it on that basis."),
        "enclosures": ["Signed claim form", "Discharge summary", "Itemised final bill",
                       "Investigation and laboratory reports", "Treating doctor's notes"],
    },
    "Coding Error": {
        "action": "Send a corrected claim with the right diagnosis and procedure codes.",
        "paragraph": ("The claim was affected by a coding error on our side. We have reviewed the diagnosis and procedure "
                      "codes against the clinical record and are submitting a corrected claim for re-adjudication."),
        "enclosures": ["Corrected claim form with revised codes", "Discharge summary",
                       "Itemised final bill", "Coding review note"],
    },
    "Medical Necessity Not Met": {
        "action": "Appeal with the clinical justification from the treating doctor.",
        "paragraph": ("The claim was not approved on grounds of medical necessity. The treating clinician has documented why "
                      "the treatment was clinically required, and we ask you to review the enclosed justification."),
        "enclosures": ["Treating doctor's clinical justification letter", "Relevant investigation reports",
                       "Treatment and admission notes", "Itemised final bill"],
    },
}


def claim_facts_text(c):
    """Facts the letter may use. No internal estimates."""
    return (
        f"claim_id: {c['claim_id']}\nhospital: {c['hospital_name']}, {c['city']}\ninsurer: {c['insurer_name']}\n"
        f"treatment: {c['treatment_type']} ({c['diagnosis']})\nclaim_date: {c['claim_date']}\n"
        f"claimed_amount: {float(c['claim_amount']):.0f} ({inr(c['claim_amount'])})\n"
        f"approved_amount: {float(c['approved_amount']):.0f} ({inr(c['approved_amount'])})\n"
        f"unpaid_amount: {float(c['recoverable_amount']):.0f} ({inr(c['recoverable_amount'])})\n"
        f"status: {c['claim_status']}\nrejection_reason: {c['rejection_reason']}\n"
    )


def template_letter(c):
    guide = REASON_GUIDE[c["rejection_reason"]]
    if c["claim_status"] == "Rejected":
        outcome = f"The claim was rejected in full. Stated reason: {c['rejection_reason']}."
    else:
        outcome = (f"The claim was partially approved ({inr(c['approved_amount'])} of {inr(c['claim_amount'])}). "
                   f"Stated reason: {c['rejection_reason']}.")
    items = "\n".join(f"- {e}" for e in guide["enclosures"])
    return (
        f"**Subject:** Request for re-review of claim {c['claim_id']}\n\n"
        f"To the Claims Review Team, {c['insurer_name']}\n\n"
        f"We write about claim {c['claim_id']}, submitted on {c['claim_date']} by {c['hospital_name']}, {c['city']}, "
        f"for {c['treatment_type']} ({c['diagnosis']}). The claimed amount was {inr(c['claim_amount'])}. {outcome} "
        f"The unpaid amount is {inr(c['recoverable_amount'])}.\n\n"
        f"{guide['paragraph']} We request re-review and payment of the unpaid amount.\n\n"
        f"**Enclosures:**\n{items}\n\n"
        f"Sincerely,\n[Name], Revenue Cycle Team, {c['hospital_name']}\nPolicy / member reference: [to be filled]"
    )


SYSTEM = (
    "You write short, polite, professional appeal letters from a hospital finance team to an insurer. "
    "Use ONLY the claim facts given. Do not invent policy numbers, patient names, dates, clinical details "
    "or any number. Use [square brackets] as placeholders for anything missing. Do not mention internal "
    "estimates. Maximum 170 words. Include a subject line, the reason, what we are sending, a clear request, "
    "and a closing with [Name]."
)


def build_letter(c):
    """Return (letter, mode, note)."""
    facts = claim_facts_text(c)
    guide = REASON_GUIDE[c["rejection_reason"]]
    prompt = (f"{facts}\nWhat we are doing: {guide['action']}\n"
              f"Documents to list as enclosed: {', '.join(guide['enclosures'])}")
    text = ask_llm(SYSTEM, prompt, temperature=0.3, max_tokens=450)
    if text is None:
        return template_letter(c), "template", ""
    bad = unverified_numbers(text, facts)
    if bad:
        return template_letter(c), "template (AI letter rejected)", f"AI letter used numbers not in the facts: {bad}"
    return text, f"LLM ({model_label()})", ""


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    claims = get_top_claims(n)
    parts = ["# Draft Appeal Letters\n\n"
             "> Simulated data. These are drafts for a person to review and sign. "
             "They are listed in priority order (highest expected recovery per hour first).\n"]
    for _, c in claims.iterrows():
        letter, mode, note = build_letter(c)
        parts.append(f"\n---\n\n## Priority {c['priority_rank']}: claim {c['claim_id']} "
                     f"({c['hospital_name']} / {c['insurer_name']})\n\n{letter}\n\n"
                     f"*Mode: {mode}{'. ' + note if note else ''}*\n")
        print(f"Priority {c['priority_rank']}: claim {c['claim_id']} -> {mode}")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("".join(parts), encoding="utf-8")
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
