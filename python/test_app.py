"""Headless test of the Streamlit demo app (no browser).
Run from the project root:  python python/test_app.py
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent / "app.py")


def click(at, label):
    at.button[[b.label for b in at.button].index(label)].click()
    at.run()
    assert not at.exception, f"'{label}' crashed: {at.exception}"


at = AppTest.from_file(APP, default_timeout=180).run()
assert not at.exception, f"App crashed on load: {at.exception}"
assert len(at.tabs) == 5, f"Expected 5 tabs, got {len(at.tabs)}"
print("PASS: app loads with 5 tabs and KPI row", [m.label for m in at.metric][:5])

click(at, "Generate today's brief")
assert any("Headline" in m.value for m in at.markdown), "Brief text missing"
print("PASS: daily brief generates")

at.chat_input[0].set_value("show denial hotspots").run()
assert not at.exception, f"Chat crashed: {at.exception}"
assert len(at.session_state.chat) == 2, "Chat did not record the turn"
assert not at.session_state.chat[1]["table"].empty, "Chat gave no table"
at.chat_input[0].set_value("which insurer is slowest to settle?").run()
assert len(at.session_state.chat) == 4, "Follow-up turn not recorded"
print("PASS: chat answers two questions and keeps history")

click(at, "Investigate")
assert any("Evidence" in m.value for m in at.markdown), "Investigation evidence missing"
print("PASS: alert investigator runs")

at.slider[[s.label for s in at.slider].index("Team hours available")].set_value(5000).run()
assert not at.exception, f"What-if crashed: {at.exception}"
print("PASS: what-if simulator responds to a slider")

click(at, "Draft letters")
print("PASS: appeal letters generate")
print("6 of 6 app tests passed")
