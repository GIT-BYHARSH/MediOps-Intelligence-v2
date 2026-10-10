from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 42
REPORT_DATE = pd.Timestamp("2025-12-31")   # "today" in the simulation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw"
CLAIMS_PATH = RAW / "claims.csv"
BILLS_PATH = RAW / "bills.csv"

REASONS = ["Incomplete Documents", "Policy Exclusion", "Medical Necessity Not Met",
           "Duplicate Claim", "Coding Error"]
BASE_REASON_WEIGHTS = [0.27, 0.22, 0.20, 0.16, 0.15]

# ---------- Baseline behaviour ----------
BASE_REJECT = 0.10       # share of claims rejected
BASE_PARTIAL = 0.14      # share of claims only partly approved
BASE_DAYS = 20           # average days an insurer takes to settle

# ---------- Planted stories ----------
S1_INSURER, S1_HOSPITALS, S1_REJECT, S1_REASON = 4, [6, 7], 0.28, "Incomplete Documents"
S2_HOSPITAL, S2_DEPARTMENT, S2_REJECT, S2_REASON = 4, "Cardiology", 0.22, "Coding Error"
S3_INSURER, S3_DAYS = 3, 60
S5_HOSPITAL, S5_START, S5_END, S5_PENDING = 10, pd.Timestamp("2025-03-01"), pd.Timestamp("2025-09-30"), 0.30
S6_THRESHOLD, S6_REJECT, S6_REASON = 200_000, 0.20, "Medical Necessity Not Met"
S7_PARTIAL = 0.40
S4_MONTHS = [12, 1]      # winter overload months
S4_REJECT_BOOST = 0.04   # winter claims get 4 percentage points more rejection
FOCUS_SHARE = 0.65       # a planted reason makes up this share of denials in its group

rng = np.random.default_rng(RANDOM_SEED)


def focused_weights(reason, share):
    """Reason weights where one reason gets `share` and the rest split the remainder."""
    weights = np.array(BASE_REASON_WEIGHTS, dtype=float)
    idx = REASONS.index(reason)
    others = np.delete(weights, idx)
    others = others / others.sum() * (1 - share)
    return np.insert(others, idx, share)


# ---------- Load and join the data ----------
bills = pd.read_csv(BILLS_PATH, parse_dates=["bill_date"])
visits = pd.read_csv(RAW / "visits.csv",
                    usecols=["visit_id", "patient_id", "visit_date", "hospital_id", "department_id", "treatment_type"])
patients = pd.read_csv(RAW / "patients.csv", usecols=["patient_id", "insurer_id"])
departments = pd.read_csv(RAW / "departments.csv", usecols=["department_id", "department_name"])

# Only insurance bills become claims
df = (
    bills[bills["payment_method"] == "Insurance"]
    .merge(visits, on="visit_id")
    .merge(patients, on="patient_id")
    .merge(departments, on="department_id")
    .reset_index(drop=True)
)
n = len(df)

insurer = df["insurer_id"].to_numpy()
hospital = df["hospital_id"].to_numpy()
total = df["total_amount"].to_numpy()
is_surgery = (df["treatment_type"] == "Surgery").to_numpy()

# ---------- Dates ----------
claim_date = df["bill_date"] + pd.to_timedelta(rng.integers(1, 8, size=n), unit="D")
claim_date = claim_date.clip(upper=REPORT_DATE)

mean_days = np.where(insurer == S3_INSURER, S3_DAYS, BASE_DAYS)       # story 3
settle_days = np.clip(np.round(rng.normal(mean_days, 6)), 5, None).astype(int)
settlement_date = claim_date + pd.to_timedelta(settle_days, unit="D")

# ---------- Which claims are still Pending? ----------
not_settled_yet = (settlement_date > REPORT_DATE).to_numpy()
in_s5_window = ((claim_date >= S5_START) & (claim_date <= S5_END)).to_numpy()
stuck = (hospital == S5_HOSPITAL) & in_s5_window & (rng.random(n) < S5_PENDING)   # story 5
is_pending = not_settled_yet | stuck

# ---------- Story groups ----------
m1 = (insurer == S1_INSURER) & np.isin(hospital, S1_HOSPITALS)
m2 = (hospital == S2_HOSPITAL) & (df["department_name"] == S2_DEPARTMENT).to_numpy()
m6 = total > S6_THRESHOLD
m7 = is_surgery
m4 = np.isin(pd.to_datetime(df["visit_date"]).dt.month.to_numpy(), S4_MONTHS)   # story 4

# ---------- Probability of rejection / partial approval for each claim ----------
p_reject = np.full(n, BASE_REJECT)
p_partial = np.full(n, BASE_PARTIAL)
p_reject[m1] = S1_REJECT
p_reject[m2] = S2_REJECT
p_reject[m6] = S6_REJECT
p_reject[m4] += S4_REJECT_BOOST
p_partial[m7] = S7_PARTIAL

# ---------- Decide the status by "rolling a die" for every claim ----------
roll = rng.random(n)
status = np.where(roll < p_reject, "Rejected",
                  np.where(roll < p_reject + p_partial, "Partially Approved", "Approved"))
status = np.where(is_pending, "Pending", status)

# ---------- Reasons (only for rejected or partially approved claims) ----------
has_reason = np.isin(status, ["Rejected", "Partially Approved"])
reason = np.full(n, "", dtype=object)
reason[has_reason] = rng.choice(REASONS, size=has_reason.sum(), p=BASE_REASON_WEIGHTS)

for group, focus_reason in [(m1, S1_REASON), (m2, S2_REASON), (m6, S6_REASON)]:
    target = group & has_reason
    reason[target] = rng.choice(REASONS, size=target.sum(), p=focused_weights(focus_reason, FOCUS_SHARE))

# ---------- Amounts ----------
claim_amount = np.round(total * rng.uniform(0.85, 1.0, n))

approved = np.zeros(n)                                  # Rejected stays 0
ok = status == "Approved"
approved[ok] = claim_amount[ok] * rng.uniform(0.92, 1.0, ok.sum())

part = status == "Partially Approved"
low = np.where(is_surgery[part], 0.40, 0.30)            # story 7: surgery gets cut harder
high = np.where(is_surgery[part], 0.70, 0.75)
approved[part] = claim_amount[part] * rng.uniform(low, high)

approved = np.round(approved)
approved = np.where(status == "Pending", np.nan, approved)   # no decision yet

settlement_out = settlement_date.where(~is_pending)          # blank if still pending

claims_df = pd.DataFrame(
    {
        "claim_id": np.arange(1, n + 1),
        "bill_id": df["bill_id"].to_numpy(),
        "visit_id": df["visit_id"].to_numpy(),
        "insurer_id": insurer.astype(int),
        "claim_amount": claim_amount,
        "approved_amount": approved,
        "claim_status": status,
        "rejection_reason": reason,
        "claim_date": claim_date,
        "settlement_date": settlement_out,
    }
)
claims_df.to_csv(CLAIMS_PATH, index=False)

# ---------- Write the outcome back to the bills ----------
STATUS_TO_BILL = {"Approved": "Paid", "Partially Approved": "Partially Paid",
                  "Rejected": "Pending", "Pending": "Pending"}
bill_status = pd.Series(pd.Series(status).map(STATUS_TO_BILL).to_numpy(), index=df["bill_id"].to_numpy())

bills_all = pd.read_csv(BILLS_PATH)
is_insurance = bills_all["payment_method"] == "Insurance"
bills_all.loc[is_insurance, "payment_status"] = bills_all.loc[is_insurance, "bill_id"].map(bill_status)
bills_all.to_csv(BILLS_PATH, index=False)

# ---------- Quality checks: did the stories get planted? ----------
decided = status != "Pending"


def rate(mask, target):
    chosen = mask & decided
    return (status[chosen] == target).mean() * 100


print(f"Saved {len(claims_df):,} claims to {CLAIMS_PATH}")
print("\nStatus share (%):")
print((claims_df["claim_status"].value_counts(normalize=True) * 100).round(1))

rest = ~m1 & ~m2 & ~m6
print(f"\nStory 1: rejection rate {rate(m1, 'Rejected'):.1f}% vs {rate(rest, 'Rejected'):.1f}% for ordinary claims")
print(f"         Incomplete Documents share of those rejections: "
      f"{(reason[m1 & (status == 'Rejected')] == S1_REASON).mean() * 100:.0f}%")
print(f"Story 2: rejection rate {rate(m2, 'Rejected'):.1f}%, "
      f"Coding Error share {(reason[m2 & (status == 'Rejected')] == S2_REASON).mean() * 100:.0f}%")
print(f"Story 3: average settlement days, insurer {S3_INSURER}: "
      f"{settle_days[(insurer == S3_INSURER) & decided].mean():.0f} vs others: "
      f"{settle_days[(insurer != S3_INSURER) & decided].mean():.0f}")

old_pending = is_pending & ((REPORT_DATE - claim_date).dt.days > 90).to_numpy()
print("\nStory 5: Pending claims older than 90 days, top hospitals:")
print(pd.Series(hospital[old_pending]).value_counts().head(3))
print(f"Story 4: rejection rate for December/January visits {rate(m4, 'Rejected'):.1f}% vs other months {rate(~m4, 'Rejected'):.1f}%")
print(f"\nStory 6: rejection rate for bills over 2 lakh {rate(m6, 'Rejected'):.1f}% vs {rate(~m6, 'Rejected'):.1f}% for others")
print(f"Story 7: partial approval rate, surgery {rate(m7, 'Partially Approved'):.1f}% vs other treatments {rate(~m7, 'Partially Approved'):.1f}%")

print("\nBill payment status after claims (%):")
print((bills_all["payment_status"].value_counts(normalize=True) * 100).round(1))