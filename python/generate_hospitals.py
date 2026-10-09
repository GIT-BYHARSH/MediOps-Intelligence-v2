from pathlib import Path

import pandas as pd

# Find the project folder, then decide where to save the CSV
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "hospitals.csv"

# Each hospital is one dictionary: column name -> value
hospitals = [
    {"hospital_id": 1, "hospital_name": "Sunrise Multispeciality Hospital", "city": "Delhi", "state": "Delhi", "hospital_type": "Private", "total_beds": 850},
    {"hospital_id": 2, "hospital_name": "Lotus Care Hospital", "city": "Mumbai", "state": "Maharashtra", "hospital_type": "Private", "total_beds": 600},
    {"hospital_id": 3, "hospital_name": "Riverside Medical Centre", "city": "Kolkata", "state": "West Bengal", "hospital_type": "Government", "total_beds": 1200},
    {"hospital_id": 4, "hospital_name": "Meridian Heart and Research Centre", "city": "Gurugram", "state": "Haryana", "hospital_type": "Private", "total_beds": 700},
    {"hospital_id": 5, "hospital_name": "Evergreen Healthcare", "city": "Noida", "state": "Uttar Pradesh", "hospital_type": "Private", "total_beds": 550},
    {"hospital_id": 6, "hospital_name": "Banyan Tree Hospital", "city": "Bengaluru", "state": "Karnataka", "hospital_type": "Private", "total_beds": 900},
    {"hospital_id": 7, "hospital_name": "Coastal Care Hospital", "city": "Chennai", "state": "Tamil Nadu", "hospital_type": "Private", "total_beds": 800},
    {"hospital_id": 8, "hospital_name": "Deccan Medical Institute", "city": "Hyderabad", "state": "Telangana", "hospital_type": "Government", "total_beds": 1500},
    {"hospital_id": 9, "hospital_name": "Saffron Life Hospital", "city": "Pune", "state": "Maharashtra", "hospital_type": "Private", "total_beds": 650},
    {"hospital_id": 10, "hospital_name": "Lakeview General Hospital", "city": "Bhopal", "state": "Madhya Pradesh", "hospital_type": "Government", "total_beds": 1100},
    {"hospital_id": 11, "hospital_name": "Pinecrest Medical Institute", "city": "Dehradun", "state": "Uttarakhand", "hospital_type": "Government", "total_beds": 900},
    {"hospital_id": 12, "hospital_name": "Pearl City Hospital", "city": "Jaipur", "state": "Rajasthan", "hospital_type": "Private", "total_beds": 500},
    {"hospital_id": 13, "hospital_name": "Ganga Valley Medical College Hospital", "city": "Varanasi", "state": "Uttar Pradesh", "hospital_type": "Government", "total_beds": 1400},
    {"hospital_id": 14, "hospital_name": "Harbour Light Hospital", "city": "Kochi", "state": "Kerala", "hospital_type": "Trust", "total_beds": 750},
    {"hospital_id": 15, "hospital_name": "Orchid Women and Child Hospital", "city": "Ahmedabad", "state": "Gujarat", "hospital_type": "Private", "total_beds": 400},
    {"hospital_id": 16, "hospital_name": "Unity Trust Hospital", "city": "Lucknow", "state": "Uttar Pradesh", "hospital_type": "Trust", "total_beds": 1000},
    {"hospital_id": 17, "hospital_name": "Silverline Super Speciality Hospital", "city": "Chandigarh", "state": "Chandigarh", "hospital_type": "Private", "total_beds": 450},
    {"hospital_id": 18, "hospital_name": "Tulip Care Centre", "city": "Patna", "state": "Bihar", "hospital_type": "Private", "total_beds": 350},
    {"hospital_id": 19, "hospital_name": "Green Valley Hospital", "city": "Indore", "state": "Madhya Pradesh", "hospital_type": "Private", "total_beds": 600},
    {"hospital_id": 20, "hospital_name": "Sundarban Regional Hospital", "city": "Kolkata", "state": "West Bengal", "hospital_type": "Government", "total_beds": 900},
    {"hospital_id": 21, "hospital_name": "Nilgiri Health Institute", "city": "Coimbatore", "state": "Tamil Nadu", "hospital_type": "Trust", "total_beds": 700},
    {"hospital_id": 22, "hospital_name": "Mahanadi Medical Centre", "city": "Bhubaneswar", "state": "Odisha", "hospital_type": "Government", "total_beds": 1000},
    {"hospital_id": 23, "hospital_name": "Kaveri Speciality Hospital", "city": "Mysuru", "state": "Karnataka", "hospital_type": "Private", "total_beds": 400},
    {"hospital_id": 24, "hospital_name": "Brahmaputra Care Hospital", "city": "Guwahati", "state": "Assam", "hospital_type": "Government", "total_beds": 800},
    {"hospital_id": 25, "hospital_name": "Marina Bay Hospital", "city": "Visakhapatnam", "state": "Andhra Pradesh", "hospital_type": "Private", "total_beds": 500},
]
# Turn the list into a table (a DataFrame)
df = pd.DataFrame(hospitals)

# Make sure the folder exists, then save as CSV
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)

print(f"Saved {len(df)} hospitals to {OUTPUT_PATH}")