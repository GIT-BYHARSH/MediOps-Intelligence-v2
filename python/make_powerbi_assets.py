"""Create the reusable Power BI 'templates':
  powerbi/themes/mediops_theme.json          colours + fonts (View > Themes > Browse for themes)
  powerbi/backgrounds/page1..page4_*.png     1280 x 720 page backgrounds (Format page > Canvas background)
  powerbi/layout_guide.md                    where to place every visual (pixel positions)
No database needed. Pages 1 and 3 follow the approved mockups; pages 2 and 4 are first drafts."""
import json
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_DIR = ROOT / "powerbi" / "themes"
BG_DIR = ROOT / "powerbi" / "backgrounds"
THEME_DIR.mkdir(parents=True, exist_ok=True)
BG_DIR.mkdir(parents=True, exist_ok=True)

NAVY, NAVY_LIGHT = "#12263f", "#23436b"
BG, CARD, EDGE = "#eef1f5", "#ffffff", "#dde3ea"
RED, BLUE, ORANGE, GREEN, GREY, TEXT = "#d64545", "#2f6db5", "#e8912d", "#2e9e6b", "#8a95a5", "#1c2733"
NAV_ITEMS = ["Command Center", "Where Money Is Lost", "Recovery Worklist", "Outlook & Alerts"]
W, H = 1280, 720

# ---------------------------------------------------------------- theme
theme = {
    "name": "MediOps Intelligence",
    "dataColors": [BLUE, RED, GREEN, ORANGE, "#7a5cc2", "#c3cbd6", NAVY_LIGHT, "#f2c230"],
    "background": "#FFFFFF",
    "foreground": TEXT,
    "tableAccent": NAVY,
    "good": GREEN,
    "neutral": ORANGE,
    "bad": RED,
    "maximum": BLUE,
    "center": "#f2c230",
    "minimum": "#c3cbd6",
    "textClasses": {
        "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": TEXT},
        "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": GREY},
        "callout": {"fontSize": 28, "fontFace": "Segoe UI Semibold", "color": TEXT},
        "header": {"fontSize": 10, "fontFace": "Segoe UI Semibold", "color": TEXT},
    },
}
(THEME_DIR / "mediops_theme.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")
print("saved", THEME_DIR / "mediops_theme.json")

# ---------------------------------------------------------------- pages
# panels: (name, x, y, w, h) in the same 0-100 percent system as the mockups (y measured upwards)
KPI_ROW = ("KPI cards row", 12.5, 69, 85, 13)
SLICER_ROW = ("Slicers row", 12.5, 85.2, 85, 4.2)
PAGES = [
    ("page1_command_center", 0, [
        ("Denial rate by month", 12.5, 35, 34, 31.5),
        ("Denial hotspots", 47.5, 35, 25, 31.5),
        ("Alerts", 73.5, 35, 24, 31.5),
        ("Claim gap by treatment", 12.5, 4, 34, 29.5),
        ("Recovery by strategy", 47.5, 4, 25, 29.5),
        ("Claim outcomes", 73.5, 4, 24, 29.5)]),
    ("page2_where_money_is_lost", 1, [
        ("Hospital x insurer denial heatmap (matrix)", 12.5, 4, 40, 62.5),
        ("Denial reasons", 53.5, 35, 44, 31.5),
        ("Claim gap by hospital", 53.5, 4, 44, 29.5)]),
    ("page3_recovery_worklist", 2, [
        ("Recovery curve", 12.5, 4, 36, 62.5),
        ("Claims to chase first (table)", 49.5, 4, 48, 62.5)]),
    ("page4_outlook_alerts", 3, [
        ("Forecast with actuals", 12.5, 4, 52, 62.5),
        ("Alerts list", 65.5, 4, 32, 62.5)]),
]


def draw_page(file_stem, active, panels):
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 92), 100, 8, fc=NAVY, ec="none"))
    ax.text(1.5, 96, "MediOps Intelligence", color="white", fontsize=18, fontweight="bold", va="center")
    ax.text(98.5, 96, "Healthcare Revenue Recovery   |   Simulated data, Jan 2024 - Dec 2025",
            color="#b8c7dc", fontsize=9, ha="right", va="center")
    ax.add_patch(Rectangle((0, 0), 11, 92, fc=NAVY, ec="none"))
    for i, name in enumerate(NAV_ITEMS):
        y = 83 - i * 7
        if i == active:
            ax.add_patch(FancyBboxPatch((0.8, y - 2.4), 9.4, 5, boxstyle="round,pad=0,rounding_size=0.6",
                                        fc=NAVY_LIGHT, ec="none"))
        ax.text(1.6, y, name, color="white" if i == active else "#9fb2cc", fontsize=7.2, va="center",
                fontweight="bold" if i == active else "normal")
    for _, x, y, w, h in panels:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.7",
                                    fc=CARD, ec=EDGE, lw=1))
    fig.savefig(BG_DIR / f"{file_stem}.png", dpi=100, facecolor=BG)
    plt.close(fig)
    print("saved", BG_DIR / f"{file_stem}.png")


def px(x, y, w, h):
    """percent (y up) -> Power BI pixels (y down): left, top, width, height"""
    return round(x * W / 100), round((100 - y - h) * H / 100), round(w * W / 100), round(h * H / 100)


lines = [
    "# Power BI layout guide",
    "",
    "Page size: **16:9, 1280 x 720** (View > Page view > Actual size; Format page > Canvas settings).",
    "Set the page background image to the matching file in `powerbi/backgrounds/`, with **transparency 0%** and fit = *Fit*.",
    "Then use Format > Size and position in Power BI to place each visual at the Left / Top / Width / Height below.",
    "Pages 1 and 3 follow the approved mockups; pages 2 and 4 are first drafts.",
    "",
]
for stem, active, panels in PAGES:
    draw_page(stem, active, panels)
    lines += [f"## {stem}", "", "| Visual | Left | Top | Width | Height |", "|---|---|---|---|---|"]
    extras = [SLICER_ROW, KPI_ROW] if stem != "page3_recovery_worklist" else [SLICER_ROW, ("KPI cards row", 12.5, 69, 85, 13)]
    for name, x, y, w, h in extras + panels:
        left, top, width, height = px(x, y, w, h)
        lines.append(f"| {name} | {left} | {top} | {width} | {height} |")
    lines.append("")
(ROOT / "powerbi" / "layout_guide.md").write_text("\n".join(lines), encoding="utf-8")
print("saved", ROOT / "powerbi" / "layout_guide.md")
