from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 42
NUM_VISITS = 500_000
START_DATE = "2024-01-01"
END_DATE = "2025-12-31"
WINTER_MONTHS = [12, 1]   # December and January
WINTER_BOOST = 1.4        # winter days are 40% busier
LOCAL_SHARE = 0.85        # share of visits to a hospital in the patient's own city

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = RAW / "visits.csv"

rng = np.random.default_rng(RANDOM_SEED)

patients_df = pd.read_csv(RAW / "patients.csv")
hospitals_df = pd.read_csv(RAW / "hospitals.csv")
departments_df = pd.read_csv(RAW / "departments.csv")

# ---------- Part 1: dates and patients ----------
all_days = pd.date_range(START_DATE, END_DATE)
is_winter = all_days.month.isin(WINTER_MONTHS)
weights = np.where(is_winter, WINTER_BOOST, 1.0)
probs = weights / weights.sum()

visit_dates = rng.choice(all_days.to_numpy(), size=NUM_VISITS, p=probs)
patient_ids = rng.choice(patients_df["patient_id"].to_numpy(), size=NUM_VISITS)

visits_df = pd.DataFrame({"patient_id": patient_ids, "visit_date": visit_dates})

# Attach each patient's city (needed to choose a nearby hospital)
visits_df = visits_df.merge(patients_df[["patient_id", "city"]], on="patient_id", how="left")

# Sort by date, then number the visits in date order
visits_df = visits_df.sort_values("visit_date").reset_index(drop=True)
visits_df.insert(0, "visit_id", np.arange(1, len(visits_df) + 1))

# ---------- Part 2a: hospital ----------
# Default for every visit: any hospital, bigger hospitals more likely
all_probs = hospitals_df["total_beds"] / hospitals_df["total_beds"].sum()
hospital_id = rng.choice(hospitals_df["hospital_id"].to_numpy(), size=NUM_VISITS, p=all_probs)

# Most visits go to a hospital in the patient's own city
stays_local = rng.random(NUM_VISITS) < LOCAL_SHARE

for city, city_hospitals in hospitals_df.groupby("city"):
    in_city = (visits_df["city"] == city).to_numpy() & stays_local
    n = in_city.sum()
    if n > 0:
        city_probs = city_hospitals["total_beds"] / city_hospitals["total_beds"].sum()
        hospital_id[in_city] = rng.choice(
            city_hospitals["hospital_id"].to_numpy(), size=n, p=city_probs
        )

visits_df["hospital_id"] = hospital_id

# ---------- Part 2b: department (must belong to that hospital) ----------
department_id = np.zeros(NUM_VISITS, dtype=int)

for hid, hospital_depts in departments_df.groupby("hospital_id"):
    in_hospital = (visits_df["hospital_id"] == hid).to_numpy()
    n = in_hospital.sum()
    if n > 0:
        department_id[in_hospital] = rng.choice(
            hospital_depts["department_id"].to_numpy(), size=n
        )

visits_df["department_id"] = department_id

# ---------- Part 2c: visit type ----------
visits_df["visit_type"] = rng.choice(
    ["OPD", "Emergency", "IPD"], size=NUM_VISITS, p=[0.65, 0.15, 0.20]
)
# ---------- Part 3a: treatment type (depends on visit type) ----------
TREATMENTS = {
    "OPD": (["Consultation", "Diagnostic Test", "Medication"], [0.60, 0.25, 0.15]),
    "Emergency": (["Emergency Care", "Diagnostic Test", "Minor Procedure"], [0.55, 0.25, 0.20]),
    "IPD": (["Surgery", "Medication", "Therapy", "Diagnostic Test"], [0.35, 0.30, 0.20, 0.15]),
}

treatment_type = np.empty(NUM_VISITS, dtype=object)
for vtype, (options, type_probs) in TREATMENTS.items():
    mask = (visits_df["visit_type"] == vtype).to_numpy()
    treatment_type[mask] = rng.choice(options, size=mask.sum(), p=type_probs)
visits_df["treatment_type"] = treatment_type

# ---------- Part 3b: diagnosis (depends on department) ----------
dept_names = departments_df.set_index("department_id")["department_name"]
visits_df["department_name"] = visits_df["department_id"].map(dept_names)  # helper column

DIAGNOSES = {
    "Emergency Medicine": ["Road Accident Injury", "Acute Poisoning", "Severe Allergic Reaction", "Chest Pain"],
    "General Medicine": ["Viral Fever", "Diabetes", "Hypertension", "Typhoid", "Pneumonia"],
    "Cardiology": ["Coronary Artery Disease", "Arrhythmia", "Heart Failure", "Hypertension"],
    "Orthopedics": ["Fracture", "Arthritis", "Ligament Tear", "Back Pain"],
    "Oncology": ["Breast Cancer", "Lung Cancer", "Leukemia", "Colon Cancer"],
    "Pediatrics": ["Viral Fever", "Pneumonia", "Asthma", "Malnutrition"],
    "Neurology": ["Migraine", "Epilepsy", "Stroke", "Parkinson's Disease"],
    "Gynecology and Obstetrics": ["Pregnancy Care", "PCOS", "Menstrual Disorder", "Delivery"],
    "Nephrology": ["Chronic Kidney Disease", "Kidney Stones", "Urinary Infection"],
    "General Surgery": ["Appendicitis", "Hernia", "Gallstones"],
}

diagnosis = np.empty(NUM_VISITS, dtype=object)
for dept, options in DIAGNOSES.items():
    mask = (visits_df["department_name"] == dept).to_numpy()
    diagnosis[mask] = rng.choice(options, size=mask.sum())
visits_df["diagnosis"] = diagnosis

# ---------- Part 3c: waiting minutes (longer in winter) ----------
base_wait = visits_df["visit_type"].map({"OPD": 35, "Emergency": 20, "IPD": 45}).to_numpy()
is_winter_visit = visits_df["visit_date"].dt.month.isin(WINTER_MONTHS).to_numpy()
wait_scale = np.where(is_winter_visit, 1.35, 1.0)
waiting = rng.normal(base_wait * wait_scale, 12)
visits_df["waiting_minutes"] = np.clip(np.round(waiting), 0, None).astype(int)

# ---------- Part 3d: length of stay ----------
length_of_stay = np.zeros(NUM_VISITS, dtype=int)
is_ipd = (visits_df["visit_type"] == "IPD").to_numpy()
is_er = (visits_df["visit_type"] == "Emergency").to_numpy()
length_of_stay[is_ipd] = np.clip(np.round(rng.normal(5, 3, size=is_ipd.sum())), 1, None)
length_of_stay[is_er] = rng.choice([0, 1, 2, 3], size=is_er.sum(), p=[0.4, 0.3, 0.2, 0.1])
visits_df["length_of_stay"] = length_of_stay

# City was only a helper column, so drop it
visits_df = visits_df.drop(columns=["city", "department_name"])

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
visits_df.to_csv(OUTPUT_PATH, index=False)

# ---------- Quality checks ----------
print(f"Saved {len(visits_df):,} visits to {OUTPUT_PATH}")

check = visits_df.merge(
    departments_df[["department_id", "hospital_id"]],
    on="department_id", suffixes=("", "_dept"),
)
print("Visits whose department is not in their hospital:",
      (check["hospital_id"] != check["hospital_id_dept"]).sum())

print("\nVisit type share (%):")
print((visits_df["visit_type"].value_counts(normalize=True) * 100).round(1))

print("\nVisits per month:")
print(visits_df.groupby(visits_df["visit_date"].dt.to_period("M")).size())
print("\nAverage waiting minutes, winter vs other months:")
winter_flag = visits_df["visit_date"].dt.month.isin(WINTER_MONTHS)
print(visits_df.groupby(winter_flag)["waiting_minutes"].mean().round(1))

print("\nTreatment share (%) for IPD visits:")
ipd = visits_df[visits_df["visit_type"] == "IPD"]
print((ipd["treatment_type"].value_counts(normalize=True) * 100).round(1))

print("\nAverage length of stay by visit type:")
print(visits_df.groupby("visit_type")["length_of_stay"].mean().round(1))