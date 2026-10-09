from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "insurers.csv"

# Fictional insurers. Patients with no insurance (self-pay) simply have no insurer_id.
# insurer_type: Private companies vs government-owned (Public) insurers.
insurers = [
    {"insurer_id": 1, "insurer_name": "Shield Health Insurance", "insurer_type": "Private"},
    {"insurer_id": 2, "insurer_name": "Bharat Care Assurance", "insurer_type": "Public"},
    {"insurer_id": 3, "insurer_name": "Unity General Insurance", "insurer_type": "Public"},
    {"insurer_id": 4, "insurer_name": "Aegis Health Cover", "insurer_type": "Private"},
    {"insurer_id": 5, "insurer_name": "Lifeline Mutual Insurance", "insurer_type": "Private"},
    {"insurer_id": 6, "insurer_name": "Prime Wellness Insurance", "insurer_type": "Private"},
    {"insurer_id": 7, "insurer_name": "Nation First Insurance", "insurer_type": "Public"},
    {"insurer_id": 8, "insurer_name": "Trustwell Health Insurance", "insurer_type": "Private"},
]

df = pd.DataFrame(insurers)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)

print(f"Saved {len(df)} insurers to {OUTPUT_PATH}")
