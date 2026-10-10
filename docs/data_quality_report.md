# Data Quality Report

Generated on 10 Oct 2026 14:00. Result: **27 of 27 checks passed**.

Each check counts the rows that break a rule. A check passes when it finds 0.

| Group | Check | Bad rows | Result |
|---|---|---|---|
| Duplicates | More than one claim for the same bill | 0 | PASS |
| Duplicates | More than one bill for the same visit | 0 | PASS |
| Impossible values | Patient age outside 0-100 | 0 | PASS |
| Impossible values | Visit date outside 2024-2025 | 0 | PASS |
| Impossible values | Negative waiting time or length of stay | 0 | PASS |
| Impossible values | Bill total is zero or negative | 0 | PASS |
| Impossible values | Bill total differs from the sum of its charges | 0 | PASS |
| Impossible values | Approved amount higher than claim amount | 0 | PASS |
| Impossible values | Claim amount higher than the bill total | 0 | PASS |
| Date logic | Bill dated before its visit | 0 | PASS |
| Date logic | Bill dated after the reporting date (31 Dec 2025) | 0 | PASS |
| Date logic | Claim dated before its bill | 0 | PASS |
| Date logic | Claim dated after the reporting date | 0 | PASS |
| Date logic | Settlement dated before the claim | 0 | PASS |
| Date logic | Settlement dated after the reporting date | 0 | PASS |
| Missing values | Pending claim that has an approved amount or settlement date | 0 | PASS |
| Missing values | Decided claim without an approved amount | 0 | PASS |
| Missing values | Decided claim without a settlement date | 0 | PASS |
| Missing values | Rejected or partially approved claim without a reason | 0 | PASS |
| Missing values | Approved claim that has a rejection reason | 0 | PASS |
| Missing values | Rejected claim with an approved amount above zero | 0 | PASS |
| Business rules | Insurance bill without a claim | 0 | PASS |
| Business rules | Claim on a bill that is not an insurance bill | 0 | PASS |
| Business rules | Claim insurer differs from the patient's insurer | 0 | PASS |
| Business rules | Visit department does not belong to the visit hospital | 0 | PASS |
| Business rules | Bill payment status disagrees with its claim status | 0 | PASS |
| Business rules | Bill still marked 'Awaiting Claim' | 0 | PASS |

## Expected empty values

These are empty on purpose (not errors).

| Field | Rows | Share |
|---|---|---|
| Self-pay patients (no insurer_id) | 27,985 | 28.0% |
| Pending claims (no approved amount) | 16,849 | 5.5% |
| Claims without a rejection reason | 228,014 | 74.6% |
