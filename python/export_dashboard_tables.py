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
