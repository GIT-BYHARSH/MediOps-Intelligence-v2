"""Draw reference mockups of the Power BI dashboard using the real project numbers.
These are design targets (with the interactive features marked), not the dashboard itself.
Saves assets/mockups/command_center_mockup.png and assets/mockups/recovery_worklist_mockup.png."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle

from db import PROJECT_ROOT, get_engine

OUT_DIR = PROJECT_ROOT / "assets" / "mockups"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NAVY, NAVY_LIGHT = "#12263f", "#23436b"
BG, CARD, EDGE = "#eef1f5", "#ffffff", "#dde3ea"
RED, BLUE, ORANGE, GREEN, GREY, TEXT, GOLD = ("#d64545", "#2f6db5", "#e8912d", "#2e9e6b",
                                              "#8a95a5", "#1c2733", "#f2c230")
PALE = "#c3cbd6"
NAV_ITEMS = ["Command Center", "Where Money Is Lost", "Recovery Worklist", "Outlook & Alerts"]

engine = get_engine()


class Page:
    """One 16:9 dashboard page. Coordinates are percentages of the picture, y goes up."""

    def __init__(self, active_nav):
        self.fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
        self.c = self.fig.add_axes([0, 0, 1, 1])
        self.c.set_xlim(0, 100)
        self.c.set_ylim(0, 100)
        self.c.axis("off")
        # transparent top layer for tooltips and numbered badges (drawn above every chart)
        self.o = self.fig.add_axes([0, 0, 1, 1], zorder=50)
        self.o.set_xlim(0, 100)
        self.o.set_ylim(0, 100)
        self.o.axis("off")
        # header
        self.c.add_patch(Rectangle((0, 92), 100, 8, fc=NAVY, ec="none"))
        self.text(1.5, 96, "MediOps Intelligence", color="white", fontsize=20, fontweight="bold")
        self.text(98.5, 96, "Healthcare Revenue Recovery   |   Simulated data, Jan 2024 - Dec 2025",
                  color="#b8c7dc", fontsize=10, ha="right")
        # left navigation
        self.c.add_patch(Rectangle((0, 0), 11, 92, fc=NAVY, ec="none"))
        for i, name in enumerate(NAV_ITEMS):
            y = 83 - i * 7
            if i == active_nav:
                self.c.add_patch(FancyBboxPatch((0.8, y - 2.4), 9.4, 5, boxstyle="round,pad=0,rounding_size=0.6",
                                                fc=NAVY_LIGHT, ec="none"))
            self.text(1.6, y, name, color="white" if i == active_nav else "#9fb2cc", fontsize=9.5,
                      fontweight="bold" if i == active_nav else "normal")

    def text(self, x, y, s, **kw):
        kw.setdefault("va", "center")
        return self.c.text(x, y, s, **kw)

    def card(self, x, y, w, h):
        self.c.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.7",
                                        fc=CARD, ec=EDGE, lw=1))

    def axes(self, x, y, w, h):
        ax = self.fig.add_axes([x / 100, y / 100, w / 100, h / 100], facecolor=CARD)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(EDGE)
        ax.tick_params(colors=GREY, labelsize=8, length=0)
        return ax

    def panel_title(self, x, y_top, title, subtitle):
        self.text(x + 1.5, y_top - 2.7, title, color=TEXT, fontsize=12, fontweight="bold")
        self.text(x + 1.5, y_top - 5.3, subtitle, color=GREY, fontsize=9)

    def slicer(self, x, y, label, w=17):
        self.c.add_patch(FancyBboxPatch((x, y), w, 4.2, boxstyle="round,pad=0,rounding_size=0.5",
                                        fc=CARD, ec=EDGE, lw=1))
        self.text(x + 1, y + 2.1, label, color=TEXT, fontsize=10)
        self.text(x + w - 1, y + 2.1, "v", color=GREY, fontsize=9, ha="right")

    def button(self, x, y, w, h, label, active=False, fontsize=9):
        self.c.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8",
                                        fc=NAVY if active else CARD, ec=NAVY if active else EDGE, lw=1))
        self.text(x + w / 2, y + h / 2, label, color="white" if active else TEXT, fontsize=fontsize,
                  ha="center", fontweight="bold" if active else "normal")

    def kpi(self, x, y, w, label, value, note, color):
        self.card(x, y, w, 13)
        self.c.add_patch(Rectangle((x, y + 0.6), 0.5, 11.8, fc=color, ec="none"))
        self.text(x + 1.8, y + 10.3, label, color=GREY, fontsize=10)
        self.text(x + 1.8, y + 6.2, value, color=TEXT, fontsize=22, fontweight="bold")
        self.text(x + 1.8, y + 2.4, note, color=color, fontsize=9)

    def otext(self, x, y, s, **kw):
        kw.setdefault("va", "center")
        return self.o.text(x, y, s, **kw)

    def badge(self, x, y, n):
        self.o.add_patch(Circle((x, y), 1.0, fc=GOLD, ec=NAVY, lw=1.2, zorder=10))
        self.otext(x, y, str(n), color=NAVY, fontsize=9, fontweight="bold", ha="center", zorder=11)

    def save(self, name):
        self.fig.savefig(OUT_DIR / name, dpi=100, facecolor=BG)
        plt.close(self.fig)
        print("saved", OUT_DIR / name)


# =====================================================================
# PAGE 1: COMMAND CENTER
# =====================================================================
monthly = pd.read_sql("""
    SELECT TO_CHAR(v.visit_date, 'YYYY-MM') AS month,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate
    FROM fact_claim c JOIN fact_visit v ON v.visit_id = c.visit_id
    GROUP BY 1 ORDER BY 1""", engine)
monthly["denial_rate"] = monthly["denial_rate"].astype(float)

pairs = pd.read_sql("""
    SELECT i.insurer_name, h.hospital_name,
           COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS decided,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected' AND c.rejection_reason = 'Incomplete Documents')
                 / COUNT(*) FILTER (WHERE c.claim_status = 'Rejected') AS incomplete_share
    FROM fact_claim c
    JOIN fact_visit v ON v.visit_id = c.visit_id
    JOIN dim_hospital h ON h.hospital_id = v.hospital_id
    JOIN dim_insurer i ON i.insurer_id = c.insurer_id
    GROUP BY 1, 2
    HAVING COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') >= 200
    ORDER BY denial_rate DESC LIMIT 5""", engine)
for column in ("denial_rate", "incomplete_share"):
    pairs[column] = pairs[column].astype(float)
pairs["label"] = [f"{r.insurer_name.split()[0]} @ {' '.join(r.hospital_name.split()[:2])}"
                  for r in pairs.itertuples()]

gap = pd.read_sql("""
    SELECT v.treatment_type, SUM(c.claim_amount - c.approved_amount) / 10000000.0 AS gap_crore
    FROM fact_claim c JOIN fact_visit v ON v.visit_id = c.visit_id
    WHERE c.claim_status <> 'Pending'
    GROUP BY 1 ORDER BY gap_crore DESC LIMIT 5""", engine)
gap["gap_crore"] = gap["gap_crore"].astype(float)

status = pd.read_sql("SELECT claim_status, COUNT(*) AS n FROM fact_claim GROUP BY 1",
                     engine).set_index("claim_status")["n"]

p = Page(active_nav=0)

# slicers + reset button
for i, label in enumerate(["Hospital:  All", "Insurer:  All", "Treatment:  All", "Year:  2024 - 2025"]):
    p.slicer(12.5 + i * 18.4, 85.2, label)
p.button(86.2, 85.2, 11.3, 4.2, "Reset filters", fontsize=9.5)

# KPI cards
kpis = [
    ("Denial rate", "11.1%", "Winter months reach 14.7%", RED),
    ("Claim gap", "Rs 95.6 Cr", "Claimed but not paid", BLUE),
    ("Recoverable", "Rs 61.1 Cr", "64% of the gap is fixable", GREEN),
    ("Pending over 90 days", "1,389", "All at Lakeview General", ORANGE),
    ("Avg settlement", "23.7 days", "Unity General takes 59.9", BLUE),
]
for i, (label, value, note, color) in enumerate(kpis):
    p.kpi(12.5 + i * 17.2, 69, 16.2, label, value, note, color)

# Panel A: denial rate by month (with metric toggle buttons)
p.card(12.5, 35, 34, 31.5)
p.panel_title(12.5, 66.5, "Denial rate by month", "Winter overload pushes denials up every Dec and Jan")
p.button(31.2, 61.9, 3.6, 3.3, "Rate", active=True, fontsize=8.5)
p.button(35.0, 61.9, 4.3, 3.3, "Volume", fontsize=8.5)
p.button(39.5, 61.9, 6.3, 3.3, "Winter only", fontsize=8.5)
ax = p.axes(14, 37.5, 31, 19.5)
xs = np.arange(len(monthly))
ax.plot(xs, monthly["denial_rate"], color=BLUE, linewidth=2.2)
ax.fill_between(xs, monthly["denial_rate"], 9, color=BLUE, alpha=0.12)
winter = monthly["month"].str[-2:].isin(["12", "01"]).to_numpy()
ax.scatter(xs[winter], monthly["denial_rate"][winter], color=RED, s=40, zorder=3)
ax.set_ylim(9, 16)
ax.set_xticks(xs[::3])
ax.set_xticklabels(monthly["month"][::3], fontsize=8)
ax.set_yticks([10, 12, 14, 16])
ax.set_yticklabels(["10%", "12%", "14%", "16%"])
ax.grid(axis="y", color=EDGE, linewidth=0.8)
ax.set_axisbelow(True)

# Panel B: denial hotspots
p.card(47.5, 35, 25, 31.5)
p.panel_title(47.5, 66.5, "Denial hotspots", "Insurer @ hospital, top 5")
ax = p.axes(57.5, 37.5, 13.5, 20.5)
ordered = pairs.iloc[::-1]
ax.barh(ordered["label"], ordered["denial_rate"],
        color=[RED if v > 20 else PALE for v in ordered["denial_rate"]], height=0.62)
for y, v in enumerate(ordered["denial_rate"]):
    ax.text(v + 0.5, y, f"{v:.1f}%", va="center", fontsize=8.5, color=TEXT)
ax.set_xlim(0, 36)
ax.set_xticks([])
ax.spines["bottom"].set_visible(False)
ax.tick_params(axis="y", labelsize=8.5, colors=TEXT)

# Panel C: alerts
p.card(73.5, 35, 24, 31.5)
p.panel_title(73.5, 66.5, "Alerts", "Unusual behaviour found automatically")
alerts = [
    (RED, "Aegis at Coastal Care", "28.6% denial, +307 rejections"),
    (RED, "Aegis at Banyan Tree", "28.4% denial, +374 rejections"),
    (RED, "Lakeview General", "1,389 claims stuck over 90 days"),
    (ORANGE, "Unity General Insurance", "settles in 60 days vs 20"),
    (ORANGE, "Meridian Heart Cardiology", "22.8% denial, coding errors"),
]
for i, (color, title, detail) in enumerate(alerts):
    y = 57 - i * 4.7
    p.c.scatter([75.6], [y - 0.4], s=70, color=color, zorder=3)
    p.text(77.2, y + 0.5, title, color=TEXT, fontsize=10, fontweight="bold")
    p.text(77.2, y - 1.6, detail, color=GREY, fontsize=9)

# Panel D: claim gap by treatment
p.card(12.5, 4.0, 34, 29.5)
p.panel_title(12.5, 33.5, "Claim gap by treatment (Rs crore)", "Surgery: 7% of claims, 75% of the money not paid")
ax = p.axes(21, 6.3, 24, 19)
ordered = gap.iloc[::-1]
ax.barh(ordered["treatment_type"], ordered["gap_crore"],
        color=[RED if t == "Surgery" else PALE for t in ordered["treatment_type"]], height=0.62)
for y, v in enumerate(ordered["gap_crore"]):
    ax.text(v + 1, y, f"{v:.1f}", va="center", fontsize=8.5, color=TEXT)
ax.set_xlim(0, 85)
ax.set_xticks([])
ax.spines["bottom"].set_visible(False)
ax.tick_params(axis="y", labelsize=9, colors=TEXT)

# Panel E: recovery strategies
p.card(47.5, 4.0, 25, 29.5)
p.panel_title(47.5, 33.5, "Recovery by strategy (Rs crore)", "Same 10,000 team hours")
ax = p.axes(49.5, 6.3, 21.5, 19)
values = [21.9, 16.7, 14.0, 2.5]
ax.bar(["Priority\nscore", "Largest\nfirst", "Quickest\nfirst", "Random"], values,
       color=[BLUE, PALE, PALE, PALE], width=0.6)
for x, v in enumerate(values):
    ax.text(x, v + 0.6, f"{v:.1f}", ha="center", fontsize=9, color=TEXT, fontweight="bold")
ax.set_ylim(0, 26)
ax.set_yticks([])
ax.spines["left"].set_visible(False)
ax.tick_params(axis="x", labelsize=8.5, colors=TEXT)

# Panel F: claim outcomes
p.card(73.5, 4.0, 24, 29.5)
p.panel_title(73.5, 33.5, "Claim outcomes", "305,835 insurance claims")
ax = p.fig.add_axes([0.745, 0.095, 0.22, 0.18], facecolor=CARD)
order = ["Approved", "Partially Approved", "Rejected", "Pending"]
colors = [GREEN, ORANGE, RED, PALE]
ax.pie([status[s] for s in order], colors=colors, startangle=90, counterclock=False,
       wedgeprops={"width": 0.38, "edgecolor": "white"})
ax.text(0, 0, f"{status['Approved'] / status.sum() * 100:.0f}%\napproved", ha="center", va="center",
        fontsize=11, fontweight="bold", color=TEXT)
for i, (s, color) in enumerate(zip(order, colors)):
    x = 75 + (i % 2) * 11.5
    y = 7.4 - (i // 2) * 2.0
    p.c.scatter([x + 0.4], [y], s=40, color=color)
    p.text(x + 1.2, y, f"{s} {status[s] / status.sum() * 100:.0f}%", fontsize=8.5, color=TEXT)

# Hover tooltip example over the top hotspot
top = pairs.iloc[0]
TX, TY, TW, TH = 54.6, 40.6, 17.4, 12.6
p.o.add_patch(FancyBboxPatch((TX + 0.4, TY - 0.6), TW, TH, boxstyle="round,pad=0,rounding_size=0.7",
                             fc="#b9c3d0", ec="none", zorder=5))   # shadow
p.o.add_patch(FancyBboxPatch((TX, TY), TW, TH, boxstyle="round,pad=0,rounding_size=0.7",
                             fc="white", ec=NAVY, lw=1.2, zorder=6))
p.otext(TX + 1, TY + 10.8, f"{top.insurer_name}", fontsize=8.5, fontweight="bold", color=TEXT, zorder=7)
p.otext(TX + 1, TY + 9.0, f"at {top.hospital_name}", fontsize=8.5, fontweight="bold", color=TEXT, zorder=7)
p.otext(TX + 1, TY + 6.7, f"Denial rate   {top.denial_rate:.1f}%", fontsize=8.5, color=RED, zorder=7)
p.otext(TX + 1, TY + 5.0, f"Decided claims   {int(top.decided):,}", fontsize=8.5, color=TEXT, zorder=7)
p.otext(TX + 1, TY + 3.3, f"Incomplete docs   {top.incomplete_share:.0f}% of rejections", fontsize=8.5,
        color=TEXT, zorder=7)
p.otext(TX + 1, TY + 1.0, "Click: filter page   Right-click: drill through", fontsize=7.2, color=GREY, zorder=7)
p.o.add_patch(Polygon([[TX - 0.6, TY + TH + 3.4], [TX - 0.6, TY + TH + 1.2], [TX + 0.2, TY + TH + 1.8],
                       [TX + 0.8, TY + TH + 0.8], [TX + 1.2, TY + TH + 1.1], [TX + 0.6, TY + TH + 2.1],
                       [TX + 1.4, TY + TH + 2.2]], closed=True, fc=NAVY, ec="white", lw=0.8, zorder=8))

# Numbered callouts + legend line
p.badge(12.0, 90.0, 1)
p.badge(86.0, 90.0, 2)
p.badge(30.4, 65.4, 3)
p.badge(71.7, 64.6, 4)
p.badge(TX + TW + 0.6, TY + TH - 0.2, 5)
p.badge(10.4, 85.8, 6)
p.text(12.5, 2.4, "Interactive features:  1 Slicers filter every panel   2 Reset button (bookmark)   "
                  "3 Rate / Volume / Winter-only toggle (field parameter + bookmarks)   "
                  "4 Click any bar or slice to cross-filter the page",
       color=GREY, fontsize=8.5)
p.text(12.5, 0.9, "5 Hover tooltip with extra detail   6 Page navigation buttons   "
                  "(Mockup built with real project numbers. Data is simulated.)", color=GREY, fontsize=8.5)
p.save("command_center_mockup.png")

# =====================================================================
# PAGE 3: RECOVERY WORKLIST
# =====================================================================
curve = pd.read_sql("""
    SELECT expected_recovery, effort_hours FROM report_recovery_priority ORDER BY priority_rank""", engine)
curve = curve.astype(float)
hours = curve["effort_hours"].cumsum().to_numpy()
recovered = curve["expected_recovery"].cumsum().to_numpy() / 1e7
BUDGET = 10_000
n_within = int((hours <= BUDGET).sum())
got = recovered[n_within - 1]
total_expected = recovered[-1]

rows = pd.read_sql("""
    SELECT r.priority_rank, h.hospital_name, i.insurer_name, c.rejection_reason,
           r.expected_recovery, r.effort_hours
    FROM report_recovery_priority r
    JOIN report_claim c ON c.claim_id = r.claim_id
    JOIN dim_hospital h ON h.hospital_id = c.hospital_id
    JOIN dim_insurer i ON i.insurer_id = c.insurer_id
    ORDER BY r.priority_rank LIMIT 10""", engine)
rows["expected_recovery"] = rows["expected_recovery"].astype(float)

p = Page(active_nav=2)
for i, label in enumerate(["Hospital:  All", "Insurer:  All", "Denial reason:  All"]):
    p.slicer(12.5 + i * 18.4, 85.2, label)

# what-if slider
p.card(68.2, 83.3, 29.3, 7.4)
p.text(69.6, 88.6, "Team hours available", color=GREY, fontsize=9)
p.text(96.2, 88.6, f"{BUDGET:,} h", color=TEXT, fontsize=13, fontweight="bold", ha="right")
track_x0, track_x1, track_y = 69.6, 96.2, 85.4
pos = track_x0 + (BUDGET - 2000) / (40000 - 2000) * (track_x1 - track_x0)
p.c.plot([track_x0, track_x1], [track_y, track_y], color=EDGE, linewidth=5, solid_capstyle="round")
p.c.plot([track_x0, pos], [track_y, track_y], color=BLUE, linewidth=5, solid_capstyle="round")
p.c.add_patch(Circle((pos, track_y), 0.9, fc="white", ec=BLUE, lw=2.2, zorder=5))
p.text(track_x0, 84.0, "2,000", color=GREY, fontsize=7.5)
p.text(track_x1, 84.0, "40,000", color=GREY, fontsize=7.5, ha="right")

kpis = [
    ("Claims you can work", f"{n_within:,}", "with the hours selected", BLUE),
    ("Expected recovery", f"Rs {got:.1f} Cr", f"{got / total_expected * 100:.0f}% of the whole opportunity", GREEN),
    ("Return per hour", f"Rs {got * 1e7 / hours[n_within - 1]:,.0f}", "expected cash per team hour", ORANGE),
    ("Versus random order", "9x more", "same hours, no prioritisation", RED),
]
for i, (label, value, note, color) in enumerate(kpis):
    p.kpi(12.5 + i * 21.2, 69, 20.0, label, value, note, color)

# recovery curve
p.card(12.5, 4.0, 36, 62.5)
p.panel_title(12.5, 66.5, "Recovery curve", "Cash won back as the team works down the priority list")
ax = p.axes(16, 9.5, 31, 42.5)
ax.plot(hours / 1000, recovered, color=BLUE, linewidth=2.5, label="Priority order")
ax.plot([0, hours[-1] / 1000], [0, total_expected], color=PALE, linewidth=2, linestyle="--",
        label="Random order")
ax.axvline(BUDGET / 1000, color=NAVY, linestyle=":", linewidth=1.2)
ax.scatter([BUDGET / 1000], [got], color=RED, s=70, zorder=5)
ax.annotate(f"Rs {got:.1f} Cr at {BUDGET:,} h", (BUDGET / 1000, got), xytext=(14, got - 7),
            fontsize=9.5, fontweight="bold", color=RED, arrowprops={"arrowstyle": "-", "color": RED})
ax.set_xlim(0, 40)
ax.set_ylim(0, 33)
ax.set_xlabel("Hours of follow-up work (thousands)", fontsize=9, color=GREY)
ax.set_ylabel("Expected recovery (Rs crore)", fontsize=9, color=GREY)
ax.grid(axis="y", color=EDGE, linewidth=0.8)
ax.set_axisbelow(True)
ax.legend(loc="lower right", frameon=False, fontsize=9)

# priority table
p.card(49.5, 4.0, 48, 62.5)
p.panel_title(49.5, 66.5, "Claims to chase first", "Ranked by expected recovery per hour of effort")
cols = [(51.0, "Rank", "left"), (55.0, "Hospital", "left"), (70.0, "Insurer", "left"),
        (78.5, "Reason", "left"), (91.6, "Expected", "right"), (95.8, "Hours", "right")]
p.c.add_patch(Rectangle((50.2, 54.6), 46.6, 3.4, fc=NAVY, ec="none"))
for x, label, align in cols:
    p.text(x, 56.3, label, color="white", fontsize=9, fontweight="bold", ha=align)
short_reason = {"Incomplete Documents": "Incomplete docs", "Coding Error": "Coding error",
                "Medical Necessity Not Met": "Medical necessity"}
for i, r in enumerate(rows.itertuples()):
    y = 52.2 - i * 4.7
    if i % 2 == 0:
        p.c.add_patch(Rectangle((50.2, y - 2.1), 46.6, 4.4, fc="#f5f7fa", ec="none"))
    p.text(51.0, y, f"#{int(r.priority_rank)}", color=TEXT, fontsize=9, fontweight="bold")
    p.text(55.0, y, r.hospital_name[:24], color=TEXT, fontsize=9)
    p.text(70.0, y, r.insurer_name.split()[0], color=TEXT, fontsize=9)
    p.text(78.5, y, short_reason[r.rejection_reason], color=GREEN, fontsize=9)
    p.text(91.6, y, f"Rs {r.expected_recovery / 1e5:.2f} L", color=TEXT, fontsize=9, ha="right")
    p.text(95.8, y, f"{int(r.effort_hours)}", color=TEXT, fontsize=9, ha="right")
p.text(51.0, 5.8, "Click a row to drill through to the claim's full details  |  L = lakh (100,000)",
       color=GREY, fontsize=8.5)

p.badge(12.0, 90.0, 1)
p.badge(67.8, 90.6, 2)
p.badge(12.0, 66.8, 3)
p.badge(49.0, 66.8, 4)
p.text(12.5, 2.4, "Interactive features:  1 Slicers filter the list and the curve   "
                  "2 'Team hours' slider (what-if parameter) recalculates every number   "
                  "3 Curve and KPIs move with the slider", color=GREY, fontsize=8.5)
p.text(12.5, 0.9, "4 Click a row to drill through to a claim detail page   "
                  "(Mockup built with real project numbers. Win chances and effort hours are assumptions.)",
       color=GREY, fontsize=8.5)
p.save("recovery_worklist_mockup.png")
