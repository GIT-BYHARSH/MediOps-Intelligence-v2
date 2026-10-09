import random
from pathlib import Path

import pandas as pd

RANDOM_SEED = 42

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOSPITALS_PATH = PROJECT_ROOT / "data" / "raw" / "hospitals.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "departments.csv"

# Every hospital always has these two
ALWAYS_PRESENT = ["Emergency Medicine", "General Medicine"]

# Each hospital also gets a random selection of these
OPTIONAL_DEPARTMENTS = [
    "Cardiology", "Orthopedics", "Oncology", "Pediatrics",
    "Neurology", "Gynecology and Obstetrics", "Nephrology", "General Surgery",
]

# Same seed = same data every time you run the script
random.seed(RANDOM_SEED)

hospitals_df = pd.read_csv(HOSPITALS_PATH)

records = []
department_id = 1

for _, hospital in hospitals_df.iterrows():
    # How many optional departments this hospital gets (between 4 and 8)
    n_optional = random.randint(4, 8)

    # Pick that many different departments from the optional list
    chosen = random.sample(OPTIONAL_DEPARTMENTS, n_optional)

    # Always-present departments plus the chosen ones
    for department_name in ALWAYS_PRESENT + chosen:
        records.append(
            {
                "department_id": department_id,
                "hospital_id": hospital["hospital_id"],
                "department_name": department_name,
            }
        )
        department_id += 1

df = pd.DataFrame(records)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)

print(f"Saved {len(df)} departments for {df['hospital_id'].nunique()} hospitals to {OUTPUT_PATH}")
