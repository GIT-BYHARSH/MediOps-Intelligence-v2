from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 42
INSURED_USES_INSURANCE = 0.85   # insured patients who actually file an insurance claim

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = RAW / "bills.csv"

# Private hospitals charge the most, government hospitals the least
PRICE_MULTIPLIER = {"Private": 1.0, "Trust": 0.7, "Government": 0.35}

# Base consultation fee per department (INR, before the hospital-type multiplier)
CONSULT_BASE = {
    "Emergency Medicine": 600, "General Medicine": 400, "Cardiology": 900,
    "Orthopedics": 700, "Oncology": 1000, "Pediatrics": 500, "Neurology": 900,
    "Gynecology and Obstetrics": 600, "Nephrology": 800, "General Surgery": 700,
}

rng = np.random.default_rng(RANDOM_SEED)

visits_df = pd.read_csv(RAW / "visits.csv", parse_dates=["visit_date"])
hospitals_df = pd.read_csv(RAW / "hospitals.csv")
departments_df = pd.read_csv(RAW / "departments.csv")
patients_df = pd.read_csv(RAW / "patients.csv")

# Bring in everything we need to price each visit
df = visits_df.merge(hospitals_df[["hospital_id", "hospital_type"]], on="hospital_id", how="left")
df = df.merge(departments_df[["department_id", "department_name"]], on="department_id", how="left")
df = df.merge(patients_df[["patient_id", "insurer_id"]], on="patient_id", how="left")

n = len(df)
mult = df["hospital_type"].map(PRICE_MULTIPLIER).to_numpy()
visit_type = df["visit_type"].to_numpy()

# ---------- Consultation ----------
consult = df["department_name"].map(CONSULT_BASE).to_numpy() * mult * rng.uniform(0.9, 1.15, n)
consultation_charge = np.round(consult / 10) * 10

# ---------- Medicine (depends on visit type) ----------
medicine = np.zeros(n)
for vtype, (low, high) in {"OPD": (100, 800), "Emergency": (300, 1500), "IPD": (800, 6000)}.items():
    mask = visit_type == vtype
    medicine[mask] = rng.integers(low, high, size=mask.sum())
medicine_charge = np.round(medicine * mult)

# ---------- Lab (likely for diagnostic tests, sometimes otherwise) ----------
is_diagnostic = (df["treatment_type"] == "Diagnostic Test").to_numpy()
has_lab = rng.random(n) < np.where(is_diagnostic, 0.90, 0.35)
lab = np.zeros(n)
lab[has_lab] = rng.integers(300, 4000, size=has_lab.sum())
lab_charge = np.round(lab * mult)

# ---------- Room (days stayed x daily rate) ----------
daily_rate = rng.integers(1500, 8000, size=n)
room_charge = np.round(df["length_of_stay"].to_numpy() * daily_rate * mult)

# ---------- Surgery (only for surgery treatments) ----------
is_surgery = (df["treatment_type"] == "Surgery").to_numpy()
surgery = np.zeros(n)
surgery[is_surgery] = rng.integers(30_000, 250_000, size=is_surgery.sum())
surgery_charge = np.round(surgery * mult)

total_amount = consultation_charge + medicine_charge + lab_charge + room_charge + surgery_charge

# ---------- Bill date = day of discharge ----------
# Patients still admitted at year-end get an interim bill dated on the reporting date
bill_date = (df["visit_date"] + pd.to_timedelta(df["length_of_stay"], unit="D")).clip(upper=pd.Timestamp("2025-12-31"))

# ---------- Who pays? ----------
has_insurer = df["insurer_id"].notna().to_numpy()
uses_insurance = has_insurer & (rng.random(n) < INSURED_USES_INSURANCE)
other_method = rng.choice(["Cash", "Card", "UPI"], size=n, p=[0.30, 0.30, 0.40])
payment_method = np.where(uses_insurance, "Insurance", other_method)

# Patient-paid bills are almost always paid.
# Insurance bills wait for the claim result, which the claims generator will fill in later.
patient_status = rng.choice(["Paid", "Pending", "Partially Paid"], size=n, p=[0.95, 0.03, 0.02])
payment_status = np.where(uses_insurance, "Awaiting Claim", patient_status)

bills_df = pd.DataFrame(
    {
        "bill_id": df["visit_id"].to_numpy(),
        "visit_id": df["visit_id"].to_numpy(),
        "bill_date": bill_date,
        "consultation_charge": consultation_charge,
        "medicine_charge": medicine_charge,
        "lab_charge": lab_charge,
        "room_charge": room_charge,
        "surgery_charge": surgery_charge,
        "total_amount": total_amount,
        "payment_method": payment_method,
        "payment_status": payment_status,
    }
)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
bills_df.to_csv(OUTPUT_PATH, index=False)

# ---------- Quality checks ----------
print(f"Saved {len(bills_df):,} bills to {OUTPUT_PATH}")
print(f"Total billed: INR {total_amount.sum() / 1e7:,.1f} crore")

print("\nAverage bill (INR) by hospital type:")
print(pd.Series(total_amount).groupby(df["hospital_type"].to_numpy()).mean().round(0))

print(f"\nBills above 2,00,000 INR: {(total_amount > 200_000).sum():,}")

print("\nPayment method share (%):")
print((bills_df["payment_method"].value_counts(normalize=True) * 100).round(1))