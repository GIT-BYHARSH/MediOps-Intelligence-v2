"""Make the project's first analyst charts from the mediops database.
Saves PNG files to assets/charts/."""
import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from db import PROJECT_ROOT, get_engine

OUT = PROJECT_ROOT / "assets" / "charts"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, RED, GREY = "#1f4e79", "#c0392b", "#b0b7bf"
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

engine = get_engine()


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("saved", OUT / name)


# ---------- Chart 1: winter overload ----------
visits_month = pd.read_sql("""
    SELECT TO_CHAR(visit_date, 'YYYY-MM') AS month, COUNT(*) AS visits
    FROM fact_visit GROUP BY 1 ORDER BY 1""", engine)
denial_month = pd.read_sql("""
    SELECT TO_CHAR(v.visit_date, 'YYYY-MM') AS month,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate
    FROM fact_claim c JOIN fact_visit v ON v.visit_id = c.visit_id
    GROUP BY 1 ORDER BY 1""", engine)
m = visits_month.merge(denial_month, on="month")
m["denial_rate"] = m["denial_rate"].astype(float)
winter = m["month"].str[-2:].isin(["12", "01"])

fig, ax1 = plt.subplots(figsize=(11, 5))
ax1.bar(m["month"], m["visits"] / 1000, color=[RED if w else GREY for w in winter])
ax1.set_ylabel("Visits (thousands)")
ax1.tick_params(axis="x", rotation=60)
ax2 = ax1.twinx()
ax2.plot(m["month"], m["denial_rate"], color=BLUE, marker="o", linewidth=2)
ax2.set_ylabel("Denial rate (%)", color=BLUE)
ax2.set_ylim(0, 18)
ax2.spines["right"].set_visible(True)
ax1.set_title("Winter overload: December and January bring about 40% more visits and higher denial rates")
save(fig, "01_winter_overload.png")

# ---------- Chart 2: where the denials hide ----------
pairs = pd.read_sql("""
    SELECT i.insurer_name || ' at ' || h.hospital_name AS pair,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate
    FROM fact_claim c
    JOIN fact_visit v ON v.visit_id = c.visit_id
    JOIN dim_hospital h ON h.hospital_id = v.hospital_id
    JOIN dim_insurer i ON i.insurer_id = c.insurer_id
    GROUP BY 1
    HAVING COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') >= 200
    ORDER BY denial_rate DESC LIMIT 10""", engine)
pairs["denial_rate"] = pairs["denial_rate"].astype(float)
overall = float(pd.read_sql("""
    SELECT 100.0 * COUNT(*) FILTER (WHERE claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE claim_status <> 'Pending') AS r
    FROM fact_claim""", engine)["r"][0])
pairs = pairs.iloc[::-1]  # biggest bar on top

fig, ax = plt.subplots(figsize=(10, 5.5))
ax.barh(pairs["pair"], pairs["denial_rate"],
        color=[RED if r > 20 else GREY for r in pairs["denial_rate"]])
ax.axvline(overall, color=BLUE, linestyle="--", linewidth=1.5,
           label=f"Network average {overall:.1f}%")
ax.legend(loc="lower right")
ax.set_xlabel("Denial rate (%)")
ax.set_title("Two insurer-hospital pairs reject about 27% of claims, more than twice the network average")
save(fig, "02_denial_hotspots.png")

# ---------- Chart 3: recovery strategies ----------
claims = pd.read_sql("""
    SELECT claim_amount - approved_amount AS recoverable,
           CASE rejection_reason WHEN 'Incomplete Documents' THEN 0.70
                                 WHEN 'Coding Error' THEN 0.60
                                 WHEN 'Medical Necessity Not Met' THEN 0.35 END AS win_chance,
           CASE rejection_reason WHEN 'Incomplete Documents' THEN 1
                                 WHEN 'Coding Error' THEN 2
                                 WHEN 'Medical Necessity Not Met' THEN 5 END AS effort
    FROM fact_claim
    WHERE claim_status IN ('Rejected', 'Partially Approved')
      AND rejection_reason IN ('Incomplete Documents', 'Coding Error', 'Medical Necessity Not Met')""", engine)
claims = claims.astype(float)
claims["expected"] = claims["recoverable"] * claims["win_chance"]
claims["priority"] = claims["expected"] / claims["effort"]

rng = np.random.default_rng(42)
orders = {
    "Priority score": claims.sort_values("priority", ascending=False),
    "Largest amount first": claims.sort_values("recoverable", ascending=False),
    "Quickest first": claims.sort_values(["effort", "recoverable"], ascending=[True, False]),
    "Random order": claims.iloc[rng.permutation(len(claims))],
}
colors = {"Priority score": BLUE, "Largest amount first": "#e67e22",
          "Quickest first": "#27ae60", "Random order": GREY}

BUDGET = 10_000
fig, ax = plt.subplots(figsize=(10, 5.5))
at_budget = {}
for name, d in orders.items():
    hours = d["effort"].cumsum().to_numpy()
    recovered = d["expected"].cumsum().to_numpy() / 1e7
    at_budget[name] = recovered[(hours <= BUDGET).sum() - 1]
    ax.plot(hours / 1000, recovered, color=colors[name], linewidth=2.2,
            label=f"{name}: Rs {at_budget[name]:.1f} crore")
ax.axvline(BUDGET / 1000, color="black", linestyle=":", linewidth=1.2)
ax.text(BUDGET / 1000 + 0.4, 31, "10,000-hour team budget", va="top")
ax.set_xlim(0, 40)
ax.set_xlabel("Hours of follow-up work (thousands)")
ax.set_ylabel("Expected cash recovered (Rs crore)")
ax.legend(title="Strategy: recovery at 10,000 hours", loc="lower right")
times_better = at_budget["Priority score"] / at_budget["Random order"]
ax.set_title(f"Same team, same hours: priority scoring recovers about {times_better:.0f}x more than random")
save(fig, "03_recovery_strategies.png")

# ---------- Chart 4: where the money is lost ----------
gap = pd.read_sql("""
    SELECT v.treatment_type,
           COUNT(*) AS claims,
           SUM(c.claim_amount - c.approved_amount) / 10000000.0 AS gap_crore
    FROM fact_claim c JOIN fact_visit v ON v.visit_id = c.visit_id
    WHERE c.claim_status <> 'Pending'
    GROUP BY 1 ORDER BY gap_crore""", engine)
gap["gap_crore"] = gap["gap_crore"].astype(float)
surgery = gap[gap["treatment_type"] == "Surgery"].iloc[0]
claim_share = 100 * surgery["claims"] / gap["claims"].sum()
gap_share = 100 * surgery["gap_crore"] / gap["gap_crore"].sum()

fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(gap["treatment_type"], gap["gap_crore"],
        color=[RED if t == "Surgery" else GREY for t in gap["treatment_type"]])
ax.set_xlabel("Claim gap (Rs crore)")
ax.set_title(f"Surgery is {claim_share:.0f}% of claims but {gap_share:.0f}% of the money not paid")
save(fig, "04_claim_gap_by_treatment.png")