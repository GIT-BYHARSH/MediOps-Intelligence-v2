"""Forecast monthly claim volume and denial rate for the next 3 months.

Step 1 (backtest): pretend it is 30 Jun 2025, forecast Jul-Dec 2025, compare with what really
        happened, and pick the best method.
Step 2 (forecast): use the best method with all data to forecast Jan-Mar 2026.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from db import PROJECT_ROOT, get_engine

CHART_PATH = PROJECT_ROOT / "assets" / "charts" / "06_forecast.png"
BLUE, RED, GREY = "#1f4e79", "#c0392b", "#b0b7bf"

# ---------- Monthly history (by month of the visit) ----------
monthly = pd.read_sql("""
    SELECT TO_CHAR(v.visit_date, 'YYYY-MM') AS month,
           COUNT(*) AS claims,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate
    FROM fact_claim c JOIN fact_visit v ON v.visit_id = c.visit_id
    GROUP BY 1 ORDER BY 1""", get_engine())
monthly.index = pd.PeriodIndex(monthly["month"], freq="M")
monthly["denial_rate"] = monthly["denial_rate"].astype(float)
SERIES = {"claims": "Claims per month", "denial_rate": "Denial rate (%)"}


# ---------- Four simple forecasting methods ----------
def predict(train, target_month):
    """Return one forecast per method for one future month."""
    same_month_last_year = train[target_month - 12]
    recent = train.iloc[-6:]                                  # last 6 months we know
    trend = recent.mean() / train[recent.index - 12].mean()   # this year vs the same months last year
    return {
        "Last value": train.iloc[-1],
        "12-month average": train.iloc[-12:].mean(),
        "Same month last year": same_month_last_year,
        "Last year x recent trend": same_month_last_year * trend,
    }


def forecast(train, months):
    return pd.DataFrame([predict(train, m) for m in months], index=months)


# ---------- Step 1: backtest on Jul-Dec 2025 ----------
test_months = pd.period_range("2025-07", "2025-12", freq="M")
print("BACKTEST: forecast Jul-Dec 2025 from data up to Jun 2025 (error = MAPE, lower is better)\n")
backtests = {}
for column, label in SERIES.items():
    y = monthly[column]
    predicted = forecast(y[:"2025-06"], test_months)
    backtests[column] = predicted
    actual = y[test_months]
    mape = predicted.sub(actual, axis=0).abs().div(actual, axis=0).mean() * 100
    print(label)
    print(mape.round(1).astype(str).add("%").to_string(), "\n")

# ---------- Step 2: forecast Jan-Mar 2026 ----------
BEST = "Last year x recent trend"
future_months = pd.period_range("2026-01", periods=3, freq="M")
print(f"FORECAST for Jan-Mar 2026 (method: {BEST})\n")
future = {}
for column, label in SERIES.items():
    future[column] = forecast(monthly[column], future_months)[BEST]
    values = ", ".join(f"{m.strftime('%b %Y')}: {v:,.1f}" for m, v in future[column].items())
    print(f"{label}: {values}")

# ---------- Chart ----------
plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "axes.titleweight": "bold",
                     "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for ax, (column, label) in zip(axes, SERIES.items()):
    y = monthly[column]
    ax.plot(y.index.to_timestamp(), y.values, color=BLUE, marker="o", linewidth=2, label="Actual")
    back = backtests[column][BEST]
    ax.plot(back.index.to_timestamp(), back.values, color=GREY, linestyle="--", marker="o",
            label="Backtest forecast (Jul-Dec 2025)")
    ax.plot(future[column].index.to_timestamp(), future[column].values, color=RED, linestyle="--",
            marker="o", linewidth=2, label="Forecast (Jan-Mar 2026)")
    ax.axvspan(future_months[0].to_timestamp(), future_months[-1].to_timestamp(), color=RED, alpha=0.08)
    ax.set_title(label)
    ax.tick_params(axis="x", rotation=45)
axes[0].set_ylim(bottom=0)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
fig.suptitle("Winter pressure returns: claim volume and denial rate are forecast to rise again in Jan 2026",
             fontweight="bold")
fig.tight_layout(rect=[0, 0.07, 1, 0.95])
fig.savefig(CHART_PATH, dpi=150, bbox_inches="tight")
print(f"\nSaved chart to {CHART_PATH}")
