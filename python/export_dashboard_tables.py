"""Create two small display tables for Power BI inside PostgreSQL:
  report_alert     the unusual-behaviour alerts, with a ready-to-show headline, detail line and severity
  report_strategy  the four follow-up strategies compared under the same 10,000 team hours
Run anomaly_alerts.py first (it creates data/processed/alerts.csv). In Power BI: Home > Refresh,
or Get data > PostgreSQL to add the new tables the first time."""
import pandas as pd

from db import PROJECT_ROOT, get_engine

engine = get_engine()
ALERTS_CSV = PROJECT_ROOT / "data" / "processed" / "alerts.csv"
STRATEGY_SQL = PROJECT_ROOT / "sql" / "analysis_05_strategy_simulation.sql"

# ---------------------------------------------------------------- alerts
alerts = pd.read_csv(ALERTS_CSV)


def detail(row):
    """One short plain-English line under each headline."""
    check = row["check"]
    if check.startswith("Denial rate"):
        return f"{row['value']:.1f}% denial, +{int(row['impact']):,} rejections"
    if check.startswith("Pending"):
        return f"{int(row['impact']):,} claims stuck over 90 days"
    if check.startswith("Settlement"):
        return f"settles in {row['value']:.0f} days vs {row['typical']:.0f} typical"
    return f"{row['value']:.1f}% denial vs {row['typical']:.1f}% typical"


alerts["headline"] = alerts["entity"].str.replace(" / ", " - ", regex=False)
is_month = alerts["check"].str.startswith("Monthly")
alerts.loc[is_month, "headline"] = "Denial spike in " + alerts.loc[is_month, "entity"]
alerts["detail"] = alerts.apply(detail, axis=1)
alerts["severity"] = alerts["z"].apply(lambda z: "High" if z >= 10 else "Medium")
# Show variety first: the strongest alert of every check, then the rest by strength
alerts = alerts.sort_values("z", ascending=False)
alerts["is_top_of_check"] = ~alerts.duplicated("check")
alerts = alerts.sort_values(["is_top_of_check", "z"], ascending=[False, False]).reset_index(drop=True)
alerts["alert_rank"] = alerts.index + 1
alerts = alerts[["alert_rank", "check", "headline", "detail", "severity", "value", "typical", "z", "impact",
                 "impact_unit"]]
alerts.to_sql("report_alert", engine, if_exists="replace", index=False)

# Ready-made list for the Command Center panel: top 5 only, numbered, so a plain table needs no filter or sort
top5 = alerts.head(5).copy()
top5["alert_line"] = top5["alert_rank"].astype(str) + ". " + top5["headline"]
top5[["alert_rank", "alert_line", "detail", "severity"]].to_sql("report_alert_top5", engine, if_exists="replace", index=False)
print(f"report_alert: {len(alerts)} rows")
print(alerts[["alert_rank", "headline", "detail", "severity"]].head(8).to_string(index=False))

# ---------------------------------------------------------------- strategies
strategy = pd.read_sql(STRATEGY_SQL.read_text(encoding="utf-8"), engine)
order = {"Priority score": 1, "Largest amount first": 2, "Quickest first": 3, "Random order": 4}
strategy["sort_order"] = strategy["strategy"].map(order)
strategy = strategy.sort_values("sort_order").reset_index(drop=True)
strategy.to_sql("report_strategy", engine, if_exists="replace", index=False)
print(f"\nreport_strategy: {len(strategy)} rows")
print(strategy.to_string(index=False))

# ---------------------------------------------------------------- recovery curve (downsampled so Power BI plots ~80 points, not 49k claims)
pri = pd.read_sql(
    "SELECT expected_recovery, effort_hours FROM report_recovery_priority ORDER BY priority_rank",
    engine,
)
pri["hours_cum"] = pri["effort_hours"].cumsum()
pri["recovery_cum"] = pri["expected_recovery"].cumsum()
total_h = float(pri["hours_cum"].iloc[-1])
total_r = float(pri["recovery_cum"].iloc[-1])
pri["random_cum"] = pri["hours_cum"] / total_h * total_r

keep = {0, len(pri) - 1}
keep.add(int((pri["hours_cum"] - 10_000).abs().idxmin()))
step = 500
for h in range(step, int(pri["hours_cum"].iloc[-1]), step):
    keep.add(int((pri["hours_cum"] - h).abs().idxmin()))
curve = pri.loc[sorted(keep), ["hours_cum", "recovery_cum", "random_cum"]].drop_duplicates("hours_cum")
curve = pd.DataFrame({
    "hours_thousand": curve["hours_cum"] / 1000,
    "priority_crore": curve["recovery_cum"] / 1e7,
    "random_crore": curve["random_cum"] / 1e7,
})
curve.to_sql("report_recovery_curve", engine, if_exists="replace", index=False)
at_10k = pri.loc[(pri["hours_cum"] - 10_000).abs().idxmin()]
print(f"\nreport_recovery_curve: {len(curve)} rows")
print(f"at 10,000 hours: Rs {at_10k['recovery_cum'] / 1e7:.2f} Cr")

# ---------------------------------------------------------------- top 10 worklist (ready-made columns, no Power BI shaping)
top = pd.read_sql(
    """
    SELECT r.priority_rank,
           h.hospital_name,
           i.insurer_name,
           c.rejection_reason,
           r.expected_recovery,
           r.effort_hours
    FROM report_recovery_priority r
    JOIN report_claim c ON c.claim_id = r.claim_id
    JOIN dim_hospital h ON h.hospital_id = c.hospital_id
    JOIN dim_insurer i ON i.insurer_id = c.insurer_id
    ORDER BY r.priority_rank
    LIMIT 10
    """,
    engine,
)
short_reason = {
    "Incomplete Documents": "Incomplete docs",
    "Coding Error": "Coding error",
    "Medical Necessity Not Met": "Medical necessity",
}
top["rank_label"] = "#" + top["priority_rank"].astype(int).astype(str)
top["insurer_short"] = top["insurer_name"].str.split().str[0]
top["reason_short"] = top["rejection_reason"].map(short_reason)
top["expected_lakh"] = (top["expected_recovery"].astype(float) / 1e5).round(2)
worklist = top[["priority_rank", "rank_label", "hospital_name", "insurer_short",
                "reason_short", "expected_lakh", "effort_hours"]]
worklist.to_sql("report_worklist_top10", engine, if_exists="replace", index=False)
print(f"report_worklist_top10: {len(worklist)} rows")
print(worklist.to_string(index=False))

# ---------------------------------------------------------------- forecast (actuals + Jan-Mar 2026, method from python/forecast.py)
monthly = pd.read_sql(
    """
    SELECT TO_CHAR(v.visit_date, 'YYYY-MM') AS month,
           COUNT(*) AS claims,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / NULLIF(COUNT(*) FILTER (WHERE c.claim_status <> 'Pending'), 0) AS denial_rate
    FROM fact_claim c JOIN fact_visit v ON v.visit_id = c.visit_id
    GROUP BY 1 ORDER BY 1
    """,
    engine,
)
monthly["month_start"] = pd.to_datetime(monthly["month"] + "-01")
actuals = monthly[["month_start", "claims", "denial_rate"]].copy()
actuals["series"] = "Actual"
y_claims = monthly.set_index("month_start")["claims"].astype(float)
y_denial = monthly.set_index("month_start")["denial_rate"].astype(float)
future_starts = pd.date_range("2026-01-01", periods=3, freq="MS")


def last_year_x_trend(series, target):
    last_year = series.loc[target - pd.DateOffset(years=1)]
    recent = series.iloc[-6:]
    prior = series.reindex(recent.index - pd.DateOffset(years=1))
    trend = recent.mean() / prior.mean()
    return float(last_year * trend)


pred_claims = [last_year_x_trend(y_claims, t) for t in future_starts]
pred_denial = [last_year_x_trend(y_denial, t) for t in future_starts]
forecast_rows = pd.DataFrame({
    "month_start": future_starts,
    "claims": pred_claims,
    "denial_rate": pred_denial,
    "series": "Forecast",
})
report_forecast = pd.concat([actuals, forecast_rows], ignore_index=True)
report_forecast.to_sql("report_forecast", engine, if_exists="replace", index=False)
print(f"\nreport_forecast: {len(report_forecast)} rows")
print(forecast_rows.to_string(index=False))


