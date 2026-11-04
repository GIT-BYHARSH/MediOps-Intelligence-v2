"""Headless test of the Streamlit demo app (no browser).
Run from the project root:  python python/test_app.py
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent / "app.py")

at = AppTest.from_file(APP, default_timeout=120).run()
assert not at.exception, f"App crashed on load: {at.exception}"
print("PASS: app loads, KPI row shows", [m.label for m in at.metric])

buttons = {b.label: b for b in at.button}
buttons["Generate today's brief"].click()
at.run()
assert not at.exception, f"Brief crashed: {at.exception}"
assert any("Headline" in m.value for m in at.markdown), "Brief text missing"
print("PASS: daily brief generates")

at.button[[b.label for b in at.button].index("Draft letters")].click()
at.run()
assert not at.exception, f"Letters crashed: {at.exception}"
print("PASS: appeal letters generate")

at.selectbox[0].select("Automatic alerts")
at.run()
at.button[[b.label for b in at.button].index("Ask")].click()
at.run()
assert not at.exception, f"Ask tab crashed: {at.exception}"
assert len(at.dataframe) >= 1, "No result table"
print("PASS: ask-the-data tab answers a built-in question")
print("4 of 4 app tests passed")
