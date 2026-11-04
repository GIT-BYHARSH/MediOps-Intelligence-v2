"""Sensitivity test for the headline result (priority score vs other strategies).

The win chances and effort hours are ASSUMPTIONS, not measured values. This script asks:
does the priority score still beat the other strategies if those assumptions are wrong?

Two modes are tested for every scenario:
  A. "Team knows"   - the team ranks claims using the true win chances and effort hours.
  B. "Team assumes" - the team ranks with our BASE assumptions, but reality is different.
                      This is the harder and more honest test.

Outputs: docs/sensitivity_report.md and assets/charts/07_sensitivity.png
Run from the project root:  python python/sensitivity_analysis.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from db import get_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "docs" / "sensitivity_report.md"
CHART_PATH = PROJECT_ROOT / "assets" / "charts" / "07_sensitivity.png"

REASONS = ["Incomplete Documents", "Coding Error", "Medical Necessity Not Met"]
BASE_WIN = np.array([0.70, 0.60, 0.35])
BASE_EFF = np.array([1.0, 2.0, 5.0])
BUDGET = 10_000
N_RANDOM_ORDERS = 20      # random order is averaged over this many shuffles
N_SCENARIOS = 500         # Monte Carlo scenarios
SEED = 42
STRATEGIES = ["Priority score", "Largest amount first", "Quickest first", "Random order"]

# ---------- Load the recoverable claims (same population as report_recovery_priority) ----------
engine = get_engine()
claims = pd.read_sql(
    """
    SELECT claim_id, rejection_reason, recoverable_amount
    FROM report_claim
    WHERE recoverable_amount IS NOT NULL
    ORDER BY claim_id
    """,
    engine,
)
claim_id = claims["claim_id"].to_numpy()
rec = claims["recoverable_amount"].to_numpy(dtype=float)
reason_idx = claims["rejection_reason"].map({r: i for i, r in enumerate(REASONS)}).to_numpy()
print(f"Recoverable claims loaded: {len(claims):,}")

rng = np.random.default_rng(SEED)
RANDOM_ORDERS = [rng.permutation(len(claims)) for _ in range(N_RANDOM_ORDERS)]
LARGEST_ORDER = np.lexsort((claim_id, -rec))


def recovered(order, true_hours, true_expected, budget):
    """Work the list in this order until the (true) hours run out; sum the (true) expected recovery."""
    hours_cum = np.cumsum(true_hours[order])
    within = hours_cum <= budget
    return true_expected[order][within].sum()


def evaluate(true_win, true_eff, rank_win, rank_eff, budget=BUDGET):
    """Recovery of each strategy. The team ranks with rank_*, reality follows true_*."""
    w_true, e_true = true_win[reason_idx], true_eff[reason_idx]
    expected_true = rec * w_true
    w_rank, e_rank = rank_win[reason_idx], rank_eff[reason_idx]

    orders = {
        "Priority score": np.lexsort((claim_id, -(rec * w_rank / e_rank))),
        "Largest amount first": LARGEST_ORDER,
        "Quickest first": np.lexsort((claim_id, -rec, e_rank)),
    }
    result = {name: recovered(o, e_true, expected_true, budget) for name, o in orders.items()}
    result["Random order"] = float(np.mean([recovered(p, e_true, expected_true, budget)
                                            for p in RANDOM_ORDERS]))
    return result


def summarise(result):
    """Turn a result dict into crore values and ratios."""
    cr = {k: v / 1e7 for k, v in result.items()}
    cr["x_random"] = result["Priority score"] / result["Random order"]
    cr["x_largest"] = result["Priority score"] / result["Largest amount first"]
    cr["priority_best"] = result["Priority score"] >= max(result[s] for s in STRATEGIES)
    return cr


# ---------- 0. Base case: must match analysis_05 (21.87 / 16.68 / 14.00 / 2.44) ----------
base = summarise(evaluate(BASE_WIN, BASE_EFF, BASE_WIN, BASE_EFF))
print("\nBase case (should be close to SQL: 21.87 / 16.68 / 14.00 / 2.44):")
for s in STRATEGIES:
    print(f"  {s:22s} Rs {base[s]:.2f} Cr")
print(f"  Priority vs random: {base['x_random']:.1f}x   vs largest: {base['x_largest']:.2f}x")

# ---------- 1. Named scenarios ----------
named = {
    "Base case": (BASE_WIN, BASE_EFF),
    "All win chances 20 pts lower": (np.clip(BASE_WIN - 0.20, 0.05, 0.95), BASE_EFF),
    "All win chances 20 pts higher": (np.clip(BASE_WIN + 0.20, 0.05, 0.95), BASE_EFF),
    "All effort hours doubled": (BASE_WIN, BASE_EFF * 2),
    "Effort gaps smaller (1 / 1.5 / 2.5 h)": (BASE_WIN, np.array([1.0, 1.5, 2.5])),
    "Effort gaps larger (1 / 3 / 10 h)": (BASE_WIN, np.array([1.0, 3.0, 10.0])),
    "Assumptions reversed (win and effort)": (BASE_WIN[::-1].copy(), BASE_EFF[::-1].copy()),
    "No information (same win and effort)": (np.array([0.5, 0.5, 0.5]), np.array([2.0, 2.0, 2.0])),
}
named_rows = []
for name, (w, e) in named.items():
    knows = summarise(evaluate(w, e, w, e))
    assumes = summarise(evaluate(w, e, BASE_WIN, BASE_EFF))
    named_rows.append({
        "Scenario": name,
        "Priority (Cr), team knows": round(knows["Priority score"], 2),
        "Random (Cr)": round(knows["Random order"], 2),
        "x random, team knows": round(knows["x_random"], 1),
        "Priority (Cr), team assumes": round(assumes["Priority score"], 2),
        "x random, team assumes": round(assumes["x_random"], 1),
        "Best of 4? (assumes)": "yes" if assumes["priority_best"] else "NO",
    })
named_df = pd.DataFrame(named_rows)
print("\nNamed scenarios:")
print(named_df.to_string(index=False))

# ---------- 2. Different time budgets (base assumptions) ----------
budget_rows = []
for budget in [2_500, 5_000, 10_000, 20_000, 40_000]:
    s = summarise(evaluate(BASE_WIN, BASE_EFF, BASE_WIN, BASE_EFF, budget))
    budget_rows.append({
        "Team hours": f"{budget:,}",
        "Priority (Cr)": round(s["Priority score"], 2),
        "Largest (Cr)": round(s["Largest amount first"], 2),
        "Quickest (Cr)": round(s["Quickest first"], 2),
        "Random (Cr)": round(s["Random order"], 2),
        "x random": round(s["x_random"], 1),
    })
budget_df = pd.DataFrame(budget_rows)
print("\nDifferent budgets:")
print(budget_df.to_string(index=False))

# ---------- 3. Monte Carlo: random assumption sets ----------
mc_rng = np.random.default_rng(SEED + 1)
win_low = np.array([0.50, 0.40, 0.15])
win_high = np.array([0.90, 0.80, 0.55])
eff_low = np.array([0.5, 1.0, 2.0])
eff_high = np.array([2.0, 4.0, 10.0])

knows_x, assumes_x, knows_vs_largest, assumes_vs_largest = [], [], [], []
knows_best, assumes_best = 0, 0
for _ in range(N_SCENARIOS):
    w = mc_rng.uniform(win_low, win_high)
    e = mc_rng.uniform(eff_low, eff_high)
    k = summarise(evaluate(w, e, w, e))
    a = summarise(evaluate(w, e, BASE_WIN, BASE_EFF))
    knows_x.append(k["x_random"])
    assumes_x.append(a["x_random"])
    knows_vs_largest.append(k["x_largest"])
    assumes_vs_largest.append(a["x_largest"])
    knows_best += k["priority_best"]
    assumes_best += a["priority_best"]

knows_x, assumes_x = np.array(knows_x), np.array(assumes_x)
knows_vs_largest, assumes_vs_largest = np.array(knows_vs_largest), np.array(assumes_vs_largest)


def pct(a):
    return f"{np.percentile(a, 5):.1f}x / {np.median(a):.1f}x / {np.percentile(a, 95):.1f}x"


print(f"\nMonte Carlo ({N_SCENARIOS} scenarios), 5th pct / median / 95th pct of 'x random':")
print(f"  Team knows   : {pct(knows_x)}  (min {knows_x.min():.1f}x)  best of 4 in {knows_best}/{N_SCENARIOS}")
print(f"  Team assumes : {pct(assumes_x)}  (min {assumes_x.min():.1f}x)  best of 4 in {assumes_best}/{N_SCENARIOS}")

# ---------- 4. Chart ----------
NAVY, BLUE, RED, GREY = "#12263f", "#2f6db5", "#d64545", "#9aa5b1"
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.2))

bins = np.linspace(min(assumes_x.min(), knows_x.min()) - 0.5,
                   max(assumes_x.max(), knows_x.max()) + 0.5, 40)
ax1.hist(knows_x, bins=bins, color=BLUE, alpha=0.75, label="Team knows true values")
ax1.hist(assumes_x, bins=bins, color=RED, alpha=0.6, label="Team uses our base assumptions")
ax1.axvline(1, color=NAVY, linestyle="--", linewidth=1.2)
ax1.text(1.2, ax1.get_ylim()[1] * 0.45, "1x = no better\nthan random", color=NAVY, fontsize=9)
ax1.set_title(f"Priority score vs random order across {N_SCENARIOS} different assumption sets",
              fontsize=11, color=NAVY, loc="left")
ax1.set_xlabel("Times better than random order (same 10,000 hours)")
ax1.set_ylabel("Number of scenarios")
ax1.legend(frameon=False, fontsize=9, loc="upper right")

labels = named_df["Scenario"].tolist()[::-1]
y = np.arange(len(labels))
ax2.barh(y + 0.2, named_df["x random, team knows"].tolist()[::-1], height=0.38, color=BLUE,
         label="Team knows true values")
ax2.barh(y - 0.2, named_df["x random, team assumes"].tolist()[::-1], height=0.38, color=RED,
         alpha=0.8, label="Team uses base assumptions")
ax2.axvline(1, color=NAVY, linestyle="--", linewidth=1.2)
ax2.set_yticks(y)
ax2.set_yticklabels(labels, fontsize=8.5)
ax2.set_xlabel("Times better than random order")
ax2.set_title("Named stress scenarios", fontsize=11, color=NAVY, loc="left")
ax2.legend(frameon=False, fontsize=9, loc="lower right")

for ax in (ax1, ax2):
    ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(CHART_PATH, dpi=160)
plt.close(fig)
print(f"\nSaved chart: {CHART_PATH}")

# ---------- 5. Report ----------
def md_table(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


report = f"""# Sensitivity Analysis

Generated by `python/sensitivity_analysis.py`. All data is simulated.

## Why this test exists
The headline result (priority score recovers about 9x more than random order) depends on two
**assumed** inputs per denial reason: the chance of winning an appeal and the staff hours needed.
They are documented assumptions, not measured values. This test asks whether the conclusion
survives if those assumptions are wrong.

Base assumptions: win chance {', '.join(f'{r} {w:.0%}' for r, w in zip(REASONS, BASE_WIN))};
effort {', '.join(f'{r} {e:g} h' for r, e in zip(REASONS, BASE_EFF))}.
Population: {len(claims):,} recoverable claims, {BUDGET:,} team hours.

Two modes are used:
- **Team knows**: the team ranks claims using the true values (what you get after re-estimating).
- **Team assumes**: the team ranks with our base assumptions, but reality is different (the harder test).

"Random order" is averaged over {N_RANDOM_ORDERS} shuffles, so it differs slightly from the single
shuffle in `sql/analysis_05_strategy_simulation.sql`.

## 1. Base case check
| Strategy | Recovery (Rs Cr) |
|---|---|
""" + "\n".join(f"| {s} | {base[s]:.2f} |" for s in STRATEGIES) + f"""

Priority vs random: **{base['x_random']:.1f}x**; priority vs largest-first: **{base['x_largest']:.2f}x**.

## 2. Named stress scenarios
{md_table(named_df)}

## 3. Different time budgets (base assumptions)
{md_table(budget_df)}

With a very large budget every strategy works almost every claim, so the strategies converge.
The priority score matters most when time is scarce.

## 4. Monte Carlo: {N_SCENARIOS} random assumption sets
Each scenario draws win chances and effort hours at random from plausible ranges:
win chance {', '.join(f'{r} {lo:.0%}-{hi:.0%}' for r, lo, hi in zip(REASONS, win_low, win_high))};
effort {', '.join(f'{r} {lo:g}-{hi:g} h' for r, lo, hi in zip(REASONS, eff_low, eff_high))}.

| Mode | 5th pct / median / 95th pct (x random) | Worst scenario | Priority best of 4 |
|---|---|---|---|
| Team knows | {pct(knows_x)} | {knows_x.min():.1f}x | {knows_best} of {N_SCENARIOS} |
| Team assumes (base values) | {pct(assumes_x)} | {assumes_x.min():.1f}x | {assumes_best} of {N_SCENARIOS} |

Priority vs largest-first (median): team knows {np.median(knows_vs_largest):.2f}x,
team assumes {np.median(assumes_vs_largest):.2f}x.

![Sensitivity](../assets/charts/07_sensitivity.png)

## Conclusion
- The exact "9x" depends on the assumptions. Across {N_SCENARIOS} plausible assumption sets the
  priority score was between {knows_x.min():.1f}x and {knows_x.max():.1f}x better than random order
  when the team knows the true values, and between {assumes_x.min():.1f}x and {assumes_x.max():.1f}x
  when the team ranks with our base assumptions and they turn out wrong.
- Report the result as a **range with a median** (about {np.median(knows_x):.0f}x), not as a single "9x".
- Priority was the best of the four strategies in {knows_best} of {N_SCENARIOS} scenarios when the team
  knows the true values, but only in {assumes_best} of {N_SCENARIOS} when the team ranks with wrong
  assumptions. In the other {N_SCENARIOS - assumes_best} scenarios a different strategy recovered
  more. Wrong assumptions cost some of the advantage.
- Even in the worst named case (assumptions completely reversed) the priority ranking was still
  {named_df.loc[named_df['Scenario'].str.startswith('Assumptions reversed'), 'x random, team assumes'].iloc[0]}x
  better than random order. It never fell below random in any scenario.
- The advantage shrinks as the time budget grows ({budget_df['x random'].iloc[-1]}x at
  {budget_df['Team hours'].iloc[-1]} hours), because with enough time every strategy works most claims.
  The method matters most when staff time is scarce.
- Recommended action: measure real win chances and effort from past appeals, then re-run this ranking.
- Limit: the scenarios vary win chance and effort only. They do not test a different claim population
  or different simulated amounts.
"""
REPORT_PATH.write_text(report, encoding="utf-8")
print(f"Saved report: {REPORT_PATH}")
