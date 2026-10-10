"""Automatic anomaly alerts: find hospitals, insurers and months that behave unusually.

Method (robust z-score): for each check we compare every entity with its PEERS.
    typical = median of the peers
    spread  = 1.48 x MAD (median absolute deviation), but never below a minimum 'floor'
    z       = (value - typical) / spread
The median and MAD are not distorted by the very outliers we are hunting, unlike the average.
An alert is raised when z is at least ALERT_Z (the value is unusually HIGH).
"""
import pandas as pd

from db import PROJECT_ROOT, get_engine

OUT_PATH = PROJECT_ROOT / "data" / "processed" / "alerts.csv"
ALERT_Z = 5
MIN_CLAIMS = 200   # ignore groups too small to judge

engine = get_engine()


def find_anomalies(df, check, value_col, size_col, floor, impact_label, value_is_percent=True):
    """Add a robust z-score to every row and return the rows that deserve an alert.
    impact = how many claims (or days) the unusual behaviour adds compared with typical."""
    df = df.copy()
    df[value_col] = df[value_col].astype(float)
    typical = df[value_col].median()
    mad = (df[value_col] - typical).abs().median()
    spread = max(1.4826 * mad, floor)
    df["z"] = (df[value_col] - typical) / spread
    df["typical"] = typical
    df["impact"] = (df[value_col] - typical) * df[size_col] / (100 if value_is_percent else 1)
    df["check"] = check
    df["impact_unit"] = impact_label
    df = df.rename(columns={value_col: "value"})
    return df[df["z"] >= ALERT_Z][["check", "entity", "value", "typical", "z", "impact", "impact_unit"]]


alerts = []

# 1. Denial rate of each insurer-hospital pair, against all other pairs
pairs = pd.read_sql(f"""
    SELECT i.insurer_name || ' at ' || h.hospital_name AS entity,
           COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS claims,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate
    FROM fact_claim c
    JOIN fact_visit v ON v.visit_id = c.visit_id
    JOIN dim_hospital h ON h.hospital_id = v.hospital_id
    JOIN dim_insurer i ON i.insurer_id = c.insurer_id
    GROUP BY 1
    HAVING COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') >= {MIN_CLAIMS}""", engine)
alerts.append(find_anomalies(pairs, "Denial rate: insurer at hospital", "denial_rate", "claims", 1.0,
                             "extra rejected claims"))

# 2. Denial rate of each department within each hospital
departments = pd.read_sql(f"""
    SELECT h.hospital_name || ' / ' || d.department_name AS entity,
           COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS claims,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate
    FROM fact_claim c
    JOIN fact_visit v ON v.visit_id = c.visit_id
    JOIN dim_hospital h ON h.hospital_id = v.hospital_id
    JOIN dim_department d ON d.department_id = v.department_id
    GROUP BY 1
    HAVING COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') >= {MIN_CLAIMS}""", engine)
alerts.append(find_anomalies(departments, "Denial rate: hospital department", "denial_rate", "claims", 1.0,
                             "extra rejected claims"))

# 3. Share of each hospital's claims that have been pending for more than 90 days
backlog = pd.read_sql("""
    SELECT h.hospital_name AS entity,
           COUNT(*) AS claims,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Pending'
                                      AND DATE '2025-12-31' - c.claim_date > 90) / COUNT(*) AS old_pending_pct
    FROM fact_claim c
    JOIN fact_visit v ON v.visit_id = c.visit_id
    JOIN dim_hospital h ON h.hospital_id = v.hospital_id
    GROUP BY 1""", engine)
alerts.append(find_anomalies(backlog, "Pending claims older than 90 days", "old_pending_pct", "claims", 0.5,
                             "extra stuck claims"))

# 4. Average days each insurer takes to settle
speed = pd.read_sql("""
    SELECT i.insurer_name AS entity,
           COUNT(*) AS claims,
           AVG(c.settlement_date - c.claim_date) AS avg_days
    FROM fact_claim c JOIN dim_insurer i ON i.insurer_id = c.insurer_id
    WHERE c.claim_status <> 'Pending'
    GROUP BY 1""", engine)
alerts.append(find_anomalies(speed, "Settlement time (days)", "avg_days", "claims", 1.0,
                             "extra waiting days", value_is_percent=False))

# 5. Monthly denial rate, against the other months
months = pd.read_sql("""
    SELECT TO_CHAR(v.visit_date, 'YYYY-MM') AS entity,
           COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS claims,
           100.0 * COUNT(*) FILTER (WHERE c.claim_status = 'Rejected')
                 / COUNT(*) FILTER (WHERE c.claim_status <> 'Pending') AS denial_rate
    FROM fact_claim c JOIN fact_visit v ON v.visit_id = c.visit_id
    GROUP BY 1""", engine)
alerts.append(find_anomalies(months, "Monthly denial rate", "denial_rate", "claims", 0.3,
                             "extra rejected claims"))

# ---------- Combine, rank and save ----------
result = pd.concat(alerts, ignore_index=True)
result["z"] = result["z"].round(1)
result["value"] = result["value"].round(1)
result["typical"] = result["typical"].round(1)
result["impact"] = result["impact"].round(0).astype(int)
result = result.sort_values(["check", "z"], ascending=[True, False])
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.to_csv(OUT_PATH, index=False)

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 60)
print(f"{len(result)} alerts raised (robust z-score >= {ALERT_Z})\n")
for check, group in result.groupby("check", sort=False):
    print(f"--- {check} ---")
    print(group[["entity", "value", "typical", "z", "impact", "impact_unit"]].to_string(index=False))
    print()
print(f"Saved to {OUT_PATH}")
