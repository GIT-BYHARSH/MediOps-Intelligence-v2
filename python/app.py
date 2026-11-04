"""MediOps Copilot demo app.   Run from the project root:  streamlit run python/app.py
Tabs: Daily brief | Ask the data (chat) | Investigate alerts | What-if simulator | Appeal letters.
All data is simulated. Numbers come from the database; the AI only writes and explains."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import appeal_letters  # noqa: E402
import copilot  # noqa: E402
import daily_brief  # noqa: E402
import investigate  # noqa: E402
import whatif  # noqa: E402
from copilot_facts import get_kpis, get_top_claims  # noqa: E402
import altair as alt  # noqa: E402

from llm import config_problem, llm_available, model_label  # noqa: E402

st.set_page_config(page_title="MediOps Copilot", layout="wide")


def show_chart(kind, frame, highlight=None):
    """Readable charts: horizontal bars in the given order (labels never cut off), or a line over time."""
    data = frame.reset_index()
    data.columns = ["label", "value"]
    if kind == "line":
        chart = alt.Chart(data).mark_line(point=True, color="#2f6db5").encode(
            x=alt.X("label:N", sort=None, title=None), y=alt.Y("value:Q", title=frame.columns[0]))
    else:
        data["highlight"] = data["label"] == highlight if highlight else False
        chart = alt.Chart(data).mark_bar().encode(
            y=alt.Y("label:N", sort=None, title=None, axis=alt.Axis(labelLimit=320, labelOverlap=False)),
            x=alt.X("value:Q", title=frame.columns[0]),
            color=alt.condition(alt.datum.highlight, alt.value("#2e9e6b"), alt.value("#2f6db5")),
            tooltip=["label", "value"])
    st.altair_chart(chart.properties(height=max(200, 40 * len(data)) if kind != "line" else 260),
                    use_container_width=True)

SUGGESTIONS = [
    "Show denial hotspots",
    "Which insurer is slowest to settle?",
    "Which hospitals have claims pending over 90 days?",
    "Claim gap by treatment",
    "Denial rate by month",
    "Compare the recovery strategies",
]


@st.cache_data(show_spinner=False)
def cached_kpis():
    return get_kpis()


@st.cache_data(show_spinner=False)
def cached_claims(n):
    return get_top_claims(n)


@st.cache_data(show_spinner=False)
def cached_alerts():
    return investigate.alert_table()


@st.cache_resource(show_spinner=False)
def cached_whatif_data():
    return whatif.load_claims()


st.title("MediOps Copilot")
st.caption("AI assistant for the revenue-recovery team. All data is simulated (fictional hospitals and insurers). "
           "Numbers come from the database; the AI only writes and explains.")

with st.sidebar:
    st.subheader("Mode")
    st.write(f"**{model_label()}**")
    if not llm_available():
        st.info("Templates and the built-in question list are in use. " + (config_problem() or "") +
                " Fix .env to turn on free-form AI.")
    st.subheader("Safety")
    st.markdown("- AI-written SQL: SELECT only, approved views only, row limit\n"
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

tab_brief, tab_chat, tab_alert, tab_whatif, tab_letters = st.tabs(
    ["Daily brief", "Ask the data", "Investigate alerts", "What-if simulator", "Appeal letters"])

# ------------------------------------------------------------------ daily brief
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
        st.download_button("Download brief", brief, file_name="daily_brief.md")
        with st.expander("Facts given to the writer"):
            st.code(facts)

# ------------------------------------------------------------------ chat
with tab_chat:
    st.write("Ask about the claims data. Follow-up questions work (for example: \"and only in winter?\").")
    if "chat" not in st.session_state:
        st.session_state.chat = []

    def answer(question):
        history = [(m["question"], m["sql"]) for m in st.session_state.chat if m["role"] == "assistant"]
        with st.spinner("Thinking..."):
            result = copilot.ask(question, history=history)
        st.session_state.chat.append({"role": "user", "content": question})
        st.session_state.chat.append({"role": "assistant", "question": question, "sql": result["sql"],
                                      "content": result["answer"], "table": result["table"],
                                      "unverified": result["unverified"], "mode": result["mode"]})

    if not st.session_state.chat:
        st.caption("Try one of these:")
        cols = st.columns(3)
        for i, s in enumerate(SUGGESTIONS):
            if cols[i % 3].button(s, key=f"sugg_{i}"):
                answer(s)
                st.rerun()

    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m["role"] == "assistant":
                if not m["table"].empty:
                    chart = copilot.chart_frame(m["table"])
                    if chart:
                        show_chart(*chart)
                    st.dataframe(m["table"], hide_index=True)
                if m["unverified"]:
                    st.warning(f"Numbers in the explanation not found in the result: {m['unverified']}")
                if m["sql"]:
                    with st.expander("SQL that was run"):
                        st.code(m["sql"], language="sql")
                st.caption(f"Mode: {m['mode']}")

    prompt = st.chat_input("Ask a question about claims, insurers, hospitals or recovery")
    if prompt:
        answer(prompt)
        st.rerun()
    if st.session_state.chat and st.button("Clear conversation"):
        st.session_state.chat = []
        st.rerun()

# ------------------------------------------------------------------ alert investigator
with tab_alert:
    st.write("Pick an automatic alert. The app runs drill-down queries, then explains the likely cause and a next action.")
    alerts = cached_alerts()
    labels = [f"{r['alert_rank']}. {r['headline']} ({r['severity']})" for _, r in alerts.iterrows()]
    choice = st.selectbox("Alert", labels)
    if st.button("Investigate"):
        row = alerts.iloc[labels.index(choice)]
        with st.spinner("Running drill-down queries..."):
            out = investigate.investigate(row["check"], row["headline"])
        st.subheader(out["title"])
        st.markdown("**Evidence from the data**")
        for f in out["facts"]:
            st.write(f"- {f}")
        if not out["table"].empty:
            chart = copilot.chart_frame(out["table"])
            if chart:
                show_chart(*chart)
            st.dataframe(out["table"], hide_index=True)
        st.markdown(out["narrative"])
        st.caption(f"Mode: {out['mode']}. The cause is a hypothesis to verify, not proof.")
        if out["unverified"]:
            st.warning(f"Numbers not found in the evidence: {out['unverified']}")

# ------------------------------------------------------------------ what-if simulator
with tab_whatif:
    st.write("Change the assumptions and see how much each way of working the claims list would recover. "
             "Win chances and effort hours are assumptions (base: 70% / 60% / 35% and 1 / 2 / 5 hours).")
    a, b = st.columns(2)
    hours = a.slider("Team hours available", 1_000, 40_000, 10_000, step=500)
    cost = a.slider("Staff cost per hour (Rs)", 200, 2_000, 500, step=50)
    win_mult = b.slider("Win chance vs base (1.0 = base)", 0.5, 1.5, 1.0, step=0.05)
    eff_mult = b.slider("Effort hours vs base (1.0 = base)", 0.5, 2.0, 1.0, step=0.1)
    result = whatif.simulate(cached_whatif_data(), hours, win_mult, eff_mult, cost)
    best = result.iloc[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Priority score recovers (Rs Cr)", f"{best['recovery_cr']:.2f}")
    m2.metric("Times better than random", f"{best['times_random']:.1f}x")
    m3.metric("Return per Rs 1 of staff cost", f"{best['return_per_rs1_cost']:.1f}")
    show_chart("bar", result.set_index("strategy")[["recovery_cr"]], highlight="Priority score")
    st.dataframe(result.round(2), hide_index=True)
    st.caption("Staff cost is a user input, not a measured value. The full robustness test is in docs/sensitivity_report.md.")

# ------------------------------------------------------------------ appeal letters
with tab_letters:
    st.write("Draft letters for the claims with the highest expected recovery per hour of effort.")
    n = st.slider("How many top claims?", 1, 10, 3)
    claims = cached_claims(n)
    st.dataframe(claims[["priority_rank", "claim_id", "hospital_name", "insurer_name", "rejection_reason",
                         "recoverable_amount", "effort_hours"]], hide_index=True)
    if st.button("Draft letters"):
        combined = ["# Draft Appeal Letters (simulated data, for human review)\n"]
        for _, c in claims.iterrows():
            with st.spinner(f"Claim {c['claim_id']}..."):
                letter, mode, note = appeal_letters.build_letter(c)
            combined.append(f"\n---\n\n## Priority {c['priority_rank']}: claim {c['claim_id']}\n\n{letter}\n")
            with st.expander(f"Priority {c['priority_rank']}: claim {c['claim_id']} ({c['hospital_name']} / {c['insurer_name']})"):
                st.markdown(letter)
                st.caption(f"Mode: {mode}" + (f". {note}" if note else ""))
        st.download_button("Download all letters", "".join(combined), file_name="appeal_letters.md")
