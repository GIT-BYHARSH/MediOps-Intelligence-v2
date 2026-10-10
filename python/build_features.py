"""Build the machine-learning feature table: one row per DECIDED claim.
Pending claims are left out because we do not know their outcome yet.
Saves data/processed/ml_features.csv (ignored by Git; regenerate any time)."""
import pandas as pd

from db import PROJECT_ROOT, get_engine

OUT_PATH = PROJECT_ROOT / "data" / "processed" / "ml_features.csv"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

QUERY = """
SELECT
    c.claim_id,
    -- labels (what we want to predict; never used as inputs)
    c.claim_status,
    c.rejection_reason,
    -- known BEFORE the claim is submitted (inputs)
    v.visit_date,
    v.hospital_id,
    h.hospital_type,
    h.total_beds,
    d.department_name,
    c.insurer_id,
    i.insurer_type,
    v.visit_type,
    v.treatment_type,
    v.diagnosis,
    v.waiting_minutes,
    v.length_of_stay,
    p.age,
    p.gender,
    c.claim_amount,
    b.consultation_charge,
    b.medicine_charge,
    b.lab_charge,
    b.room_charge,
    b.surgery_charge
FROM fact_claim      c
JOIN fact_bill       b ON b.bill_id       = c.bill_id
JOIN fact_visit      v ON v.visit_id      = c.visit_id
JOIN dim_patient     p ON p.patient_id    = v.patient_id
JOIN dim_hospital    h ON h.hospital_id   = v.hospital_id
JOIN dim_department  d ON d.department_id = v.department_id
JOIN dim_insurer     i ON i.insurer_id    = c.insurer_id
WHERE c.claim_status <> 'Pending'
"""

df = pd.read_sql(QUERY, get_engine(), parse_dates=["visit_date"])

# PostgreSQL money columns arrive as Decimal objects; convert to normal numbers
money_columns = ["claim_amount", "consultation_charge", "medicine_charge",
                 "lab_charge", "room_charge", "surgery_charge"]
df[money_columns] = df[money_columns].astype(float)

# Target: 1 if the claim was fully rejected, otherwise 0
df["is_rejected"] = (df["claim_status"] == "Rejected").astype(int)

# Two simple date features
df["visit_month"] = df["visit_date"].dt.month
df["is_winter"] = df["visit_month"].isin([12, 1]).astype(int)

df.to_csv(OUT_PATH, index=False)

# ---------- Summary ----------
print(f"Saved {len(df):,} rows and {df.shape[1]} columns to {OUT_PATH}")
print(f"\nShare of rejected claims: {df['is_rejected'].mean() * 100:.1f}%")
print(f"Visit dates: {df['visit_date'].min().date()} to {df['visit_date'].max().date()}")
print("\nRows per half-year (this decides our train/test split later):")
half = df["visit_date"].dt.year.astype(str) + "-H" + ((df["visit_date"].dt.month > 6) + 1).astype(str)
print(half.value_counts().sort_index())
print(f"\nMissing values in any column: {int(df.isna().sum().sum())}")
print("\nNEVER use as inputs: claim_status, rejection_reason, is_rejected, claim_id, visit_date")