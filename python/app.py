"""MediOps Copilot demo app.   Run from the project root:  streamlit run python/app.py
Three tabs: Daily brief, Appeal letters, Ask the data. All data is simulated."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import appeal_letters  # noqa: E402
import copilot  # noqa: E402
import daily_brief  # noqa: E402
from copilot_facts import get_kpis, get_top_claims  # noqa: E402
from llm import llm_available, model_label  # noqa: E402

st.set_page_config(page_title="MediOps Copilot", layout="wide")


@st.cache_data(show_spinner=False)
def cached_kpis():
    return get_kpis()


@st.cache_data(show_spinner=False)
def cached_claims(n):
    return get_top_claims(n)


st.title("MediOps Copilot")
st.caption("AI assistant for the revenue-recovery team. All data is simulated (fictional hospitals and insurers). "
           "Numbers come from the database; the AI only writes and explains.")

with st.sidebar:
    st.subheader("Mode")
    st.write(f"**{model_label()}**")
    if not llm_available():
        st.info("No LLM key found. Templates and the built-in question list are used. "
                "Add LLM_API_KEY and LLM_MODEL to .env to enable free-form AI.")
    st.subheader("Safety")
    st.markdown("- AI-written SQL: SELECT only, allow-listed views, row limit\n"
                "- Runs in a read-only transaction\n"
                "- Numbers in AI text are checked against the data\n"
                "- Letters are drafts for a person to review")

k = cached_kpis()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Denial rate", f"{k['denial_rate_pct']:.1f}%")
c2.metric("Claim gap (Cr)", f"{k['claim_gap_cr']:.2f}")
c3.metric("Recoverable (Cr)", f"{k['recoverable_cr']:.2f}")
c4.metric("Pending over 90 days", f"{k['pending_over_90_days']:,.0f}")
c5.metric("Avg settlement days", f"{k['avg_settlement_days']:.2f}")

tab_brief, tab_letters, tab_ask = st.tabs(["Daily brief", "Appeal letters", "Ask the data"])

with tab_brief:
    st.write("A short brief for the finance head, written from the live numbers.")
    if st.button("Generate today's brief"):
        with st.spinner("Writing..."):
            brief, mode, unverified, facts = daily_brief.build_brief()
        st.markdown(brief)
        st.caption(f"Mode: {mode}")
        if unverified:
            st.warning(f"Check these numbers by hand (not found in the data): {unverified}")
        else:
            st.success("Grounding check passed: every number is in the data.")
        with st.expander("Facts given to the writer"):
            st.code(facts)

with tab_letters:
    st.write("Draft letters for the claims with the highest expected recovery per hour of effort.")
    n = st.slider("How many top claims?", 1, 10, 3)
    claims = cached_claims(n)
    st.dataframe(claims[["priority_rank", "claim_id", "hospital_name", "insurer_name", "rejection_reason",
                         "recoverable_amount", "effort_hours"]], hide_index=True)
    if st.button("Draft letters"):
        for _, c in claims.iterrows():
            with st.spinner(f"Claim {c['claim_id']}..."):
                letter, mode, note = appeal_letters.build_letter(c)
            with st.expander(f"Priority {c['priority_rank']}: claim {c['claim_id']} ({c['hospital_name']} / {c['insurer_name']})"):
                st.markdown(letter)
                st.caption(f"Mode: {mode}" + (f". {note}" if note else ""))

with tab_ask:
    st.write("Ask a question about the claims data.")
    if not llm_available():
        st.caption("Without an LLM key, pick one of the built-in questions:")
        pick = st.selectbox("Built-in questions", [""] + copilot.available_questions())
        question = pick
    else:
        question = st.text_input("Your question", placeholder="Which insurer has the highest denial rate in winter?")
    if question and st.button("Ask"):
        with st.spinner("Thinking..."):
            result = copilot.ask(question)
        st.write(result["answer"])
        if not result["table"].empty:
            st.dataframe(result["table"], hide_index=True)
        if result["unverified"]:
            st.warning(f"Numbers in the explanation not found in the result: {result['unverified']}")
        if result["sql"]:
            with st.expander("SQL that was run"):
                st.code(result["sql"], language="sql")
        st.caption(f"Mode: {result['mode']}")
