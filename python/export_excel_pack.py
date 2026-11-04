"""Build the finance team's Excel pack: docs/MediOps_Finance_Pack.xlsx

Sheets: Summary (KPIs, strategy table, chart) | Worklist_Top100 (live formulas) | Assumptions (editable inputs)
        | Alerts | Forecast (chart).
Change a win chance or effort hour on the Assumptions sheet and the worklist's expected recovery and
recovery-per-hour recalculate in Excel (the ORDER of the list stays as ranked with the base assumptions).
All data is simulated.     Run from the project root:  python python/export_excel_pack.py
"""
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from copilot_facts import get_alerts, get_kpis, get_strategies, get_top_claims, get_expected_recovery_cr
from db import PROJECT_ROOT, get_engine

OUT_PATH = PROJECT_ROOT / "docs" / "MediOps_Finance_Pack.xlsx"
NAVY, BLUE_INPUT, LIGHT, GREY = "12263F", "0000FF", "EAF1FB", "F2F2F2"
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
INPUT_FILL = PatternFill("solid", fgColor="FFF8DC")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
REASONS = ["Incomplete Documents", "Coding Error", "Medical Necessity Not Met"]
BASE_WIN = [0.70, 0.60, 0.35]
BASE_EFF = [1, 2, 5]
N_TOP = 100

engine = get_engine()
kpis = get_kpis(engine)
strategies = get_strategies(engine)
alerts = get_alerts(9, engine)
claims = get_top_claims(N_TOP, engine)
expected_total = get_expected_recovery_cr(engine)
forecast = pd.read_sql("SELECT * FROM report_forecast ORDER BY month_start", engine)

wb = Workbook()


def title(ws, text, note):
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    ws["A2"] = note
    ws["A2"].font = Font(italic=True, color="7F7F7F")


def header(ws, row, labels):
    for col, label in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=col, value=label)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def widths(ws, values):
    for col, w in enumerate(values, start=1):
        ws.column_dimensions[get_column_letter(col)].width = w


# ------------------------------------------------------------------ Summary
ws = wb.active
ws.title = "Summary"
title(ws, "MediOps Intelligence: Finance Pack", "Simulated data (25 fictional hospitals, 8 fictional insurers), Jan 2024 - Dec 2025")
header(ws, 4, ["KPI", "Value", "Meaning"])
rows = [
    ("Claims", kpis["claims"], "#,##0", "Insurance claims in the period"),
    ("Denial rate (%)", kpis["denial_rate_pct"], "0.0", "Rejected / decided claims"),
    ("Approval rate (%)", kpis["approval_rate_pct"], "0.0", "Approved in full / decided claims"),
    ("Claim gap (Rs crore)", kpis["claim_gap_cr"], "0.00", "Claimed but not paid (decided claims)"),
    ("Recoverable amount (Rs crore)", kpis["recoverable_cr"], "0.00", "Gap with a fixable reason"),
    ("Expected recovery (Rs crore)", expected_total, "0.00", "Recoverable x assumed win chance"),
    ("Claims pending over 90 days", kpis["pending_over_90_days"], "#,##0", "Needs follow-up"),
    ("Average settlement (days)", kpis["avg_settlement_days"], "0.0", "Claim date to settlement"),
]
for i, (label, value, fmt, meaning) in enumerate(rows, start=5):
    ws.cell(row=i, column=1, value=label).border = BORDER
    cell = ws.cell(row=i, column=2, value=float(value))
    cell.number_format, cell.border = fmt, BORDER
    ws.cell(row=i, column=3, value=meaning).border = BORDER

strat_row = 15
ws.cell(row=strat_row - 1, column=1, value="Recovery by strategy (same 10,000 team hours)").font = Font(bold=True, color=NAVY)
header(ws, strat_row, ["Strategy", "Expected recovery (Rs crore)", "Times random order"])
for i, (_, s) in enumerate(strategies.iterrows(), start=strat_row + 1):
    ws.cell(row=i, column=1, value=s["strategy"]).border = BORDER
    c = ws.cell(row=i, column=2, value=float(s["expected_recovery_crore"]))
    c.number_format, c.border = "0.00", BORDER
    c = ws.cell(row=i, column=3, value=float(s["times_better_than_random"]))
    c.number_format, c.border = '0.0"x"', BORDER
widths(ws, [34, 26, 40])
chart = BarChart()
chart.type, chart.style = "bar", 10
chart.title = "Expected recovery by strategy (Rs crore)"
chart.add_data(Reference(ws, min_col=2, min_row=strat_row, max_row=strat_row + 4), titles_from_data=True)
chart.set_categories(Reference(ws, min_col=1, min_row=strat_row + 1, max_row=strat_row + 4))
chart.legend = None
chart.height, chart.width = 7.5, 16
ws.add_chart(chart, "E4")

# ------------------------------------------------------------------ Assumptions
wa = wb.create_sheet("Assumptions")
title(wa, "Assumptions (edit the yellow cells)", "These are assumed, not measured. The Worklist sheet recalculates when you change them.")
header(wa, 3, ["Denial reason", "Win chance", "Effort (hours)"])
for i, (reason, win, eff) in enumerate(zip(REASONS, BASE_WIN, BASE_EFF), start=4):
    wa.cell(row=i, column=1, value=reason).border = BORDER
    for col, value, fmt in ((2, win, "0%"), (3, eff, "0.0")):
        c = wa.cell(row=i, column=col, value=value)
        c.font, c.fill, c.border, c.number_format = Font(color=BLUE_INPUT), INPUT_FILL, BORDER, fmt
wa["A8"] = "Blue text on yellow = input you can change. Black = formula. See docs/sensitivity_report.md for how robust the result is."
wa["A8"].font = Font(italic=True, color="7F7F7F")
widths(wa, [30, 14, 16])

# ------------------------------------------------------------------ Worklist
wl = wb.create_sheet("Worklist_Top100", 1)
title(wl, f"Claims to chase first: top {N_TOP}", "Ranked by expected recovery per hour of effort (base assumptions). Columns G-J are live formulas.")
cols = ["Rank", "Claim ID", "Hospital", "Insurer", "Denial reason", "Recoverable (Rs)", "Win chance",
        "Expected recovery (Rs)", "Effort (hours)", "Expected per hour (Rs)"]
HR = 4
header(wl, HR, cols)
first, last = HR + 1, HR + len(claims)
for i, (_, c) in enumerate(claims.iterrows(), start=first):
    values = [int(c["priority_rank"]), int(c["claim_id"]), c["hospital_name"], c["insurer_name"], c["rejection_reason"],
              float(c["recoverable_amount"])]
    for col, v in enumerate(values, start=1):
        cell = wl.cell(row=i, column=col, value=v)
        cell.border = BORDER
    wl.cell(row=i, column=6).number_format = "#,##0"
    wl.cell(row=i, column=7, value=f"=INDEX(Assumptions!$B$4:$B$6,MATCH(E{i},Assumptions!$A$4:$A$6,0))").number_format = "0%"
    wl.cell(row=i, column=8, value=f"=F{i}*G{i}").number_format = "#,##0"
    wl.cell(row=i, column=9, value=f"=INDEX(Assumptions!$C$4:$C$6,MATCH(E{i},Assumptions!$A$4:$A$6,0))").number_format = "0.0"
    wl.cell(row=i, column=10, value=f"=H{i}/I{i}").number_format = "#,##0"
    for col in range(7, 11):
        wl.cell(row=i, column=col).border = BORDER
tot = last + 1
wl.cell(row=tot, column=1, value="Total (rows shown after any filter)").font = Font(bold=True)
for col, letter in ((6, "F"), (8, "H"), (9, "I")):
    c = wl.cell(row=tot, column=col, value=f"=SUBTOTAL(109,{letter}{first}:{letter}{last})")
    c.font, c.number_format = Font(bold=True), "#,##0"
c = wl.cell(row=tot, column=10, value=f"=H{tot}/I{tot}")
c.font, c.number_format = Font(bold=True), "#,##0"
for col in range(1, 11):
    wl.cell(row=tot, column=col).fill = PatternFill("solid", fgColor=LIGHT)
wl.freeze_panes = f"A{first}"
wl.auto_filter.ref = f"A{HR}:J{last}"
wl.conditional_formatting.add(f"J{first}:J{last}", DataBarRule(start_type="min", end_type="max", color="2F6DB5"))
widths(wl, [7, 11, 36, 28, 26, 17, 12, 20, 14, 20])
wl.row_dimensions[HR].height = 32

# ------------------------------------------------------------------ Alerts
wt = wb.create_sheet("Alerts")
title(wt, "Automatic alerts", "Unusual behaviour found by robust z-scores against peers (python/anomaly_alerts.py)")
header(wt, 4, ["#", "Alert", "Detail", "Severity"])
for i, (_, a) in enumerate(alerts.iterrows(), start=5):
    for col, v in enumerate([int(a["alert_rank"]), a["headline"], a["detail"], a["severity"]], start=1):
        wt.cell(row=i, column=col, value=v).border = BORDER
widths(wt, [5, 56, 44, 12])

# ------------------------------------------------------------------ Forecast
wf = wb.create_sheet("Forecast")
title(wf, "Denial rate outlook", "Actuals Jan 2024 - Dec 2025; forecast Jan - Mar 2026 (last year x recent trend, backtested)")
header(wf, 4, ["Month", "Claims", "Denial rate (%)", "Series"])
for i, (_, r) in enumerate(forecast.iterrows(), start=5):
    wf.cell(row=i, column=1, value=pd.to_datetime(r["month_start"]).date()).number_format = "mmm yyyy"
    wf.cell(row=i, column=2, value=float(r["claims"])).number_format = "#,##0"
    wf.cell(row=i, column=3, value=float(r["denial_rate"])).number_format = "0.0"
    wf.cell(row=i, column=4, value=r["series"])
    for col in range(1, 5):
        wf.cell(row=i, column=col).border = BORDER
widths(wf, [12, 12, 16, 12])
line = LineChart()
line.title, line.height, line.width = "Denial rate by month (%)", 8, 18
line.add_data(Reference(wf, min_col=3, min_row=4, max_row=4 + len(forecast)), titles_from_data=True)
line.set_categories(Reference(wf, min_col=1, min_row=5, max_row=4 + len(forecast)))
line.legend = None
wf.add_chart(line, "F4")

wb.calculation.fullCalcOnLoad = True  # Excel recalculates the formulas when the file opens
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT_PATH)
print(f"Saved {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")
print(f"Sheets: {wb.sheetnames}; worklist rows: {len(claims)}; forecast rows: {len(forecast)}")
