from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 42
NUM_PATIENTS = 100_000
SELF_PAY_SHARE = 0.28  # patients with no insurance

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOSPITALS_PATH = PROJECT_ROOT / "data" / "raw" / "hospitals.csv"
INSURERS_PATH = PROJECT_ROOT / "data" / "raw" / "insurers.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "patients.csv"

# Age groups and how common each one is among hospital patients
AGE_BINS = [(0, 5), (6, 17), (18, 24), (25, 40), (41, 55), (56, 70), (71, 90)]
AGE_WEIGHTS = np.array([10, 8, 9, 24, 20, 19, 10], dtype=float)

# Share of insured patients per insurer (same order as insurers.csv, ids 1 to 8)
INSURER_WEIGHTS = np.array([16, 12, 10, 15, 12, 14, 8, 13], dtype=float)

rng = np.random.default_rng(RANDOM_SEED)

hospitals_df = pd.read_csv(HOSPITALS_PATH)
insurers_df = pd.read_csv(INSURERS_PATH).sort_values("insurer_id")

# --- City: more beds in a city means more patients live there ---
cities = hospitals_df.groupby(["city", "state"], as_index=False)["total_beds"].sum()
city_probs = cities["total_beds"] / cities["total_beds"].sum()
city_idx = rng.choice(len(cities), size=NUM_PATIENTS, p=city_probs)

# --- Age: pick an age group, then a random age inside it ---
bin_idx = rng.choice(len(AGE_BINS), size=NUM_PATIENTS, p=AGE_WEIGHTS / AGE_WEIGHTS.sum())
age_low = np.array([b[0] for b in AGE_BINS])
age_high = np.array([b[1] for b in AGE_BINS])
ages = rng.integers(age_low[bin_idx], age_high[bin_idx] + 1)

# --- Gender ---
gender = rng.choice(["Male", "Female"], size=NUM_PATIENTS, p=[0.51, 0.49])

# --- Insurance: some patients are self-pay (no insurer) ---
has_insurance = rng.random(NUM_PATIENTS) >= SELF_PAY_SHARE
insurer_choice = rng.choice(
    insurers_df["insurer_id"].to_numpy(),
    size=NUM_PATIENTS,
    p=INSURER_WEIGHTS / INSURER_WEIGHTS.sum(),
)
insurer_id = pd.Series(insurer_choice).where(has_insurance).astype("Int64")

patients_df = pd.DataFrame(
    {
        "patient_id": np.arange(1, NUM_PATIENTS + 1),
        "gender": gender,
        "age": ages,
        "city": cities["city"].to_numpy()[city_idx],
        "state": cities["state"].to_numpy()[city_idx],
        "insurer_id": insurer_id,
    }
)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
patients_df.to_csv(OUTPUT_PATH, index=False)

self_pay_pct = patients_df["insurer_id"].isna().mean() * 100
print(f"Saved {len(patients_df):,} patients to {OUTPUT_PATH}")
print(f"Self-pay share: {self_pay_pct:.1f}%")
print(f"Average age: {patients_df['age'].mean():.1f}")
