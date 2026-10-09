# MediOps Intelligence: KPI Dictionary

All amounts are in Indian Rupees (INR). All data is simulated.

## Claim Lifecycle
Bill -> Claim -> Insurer decision -> Payment

## KPIs

### Denial Rate
- Business meaning: - Business meaning: Of all the claims where the insurer has made a decision, the share that were fully rejected.
- Formula: Rejected claims / (Approved + Partially Approved + Rejected claims) x 100. Pending claims are excluded.
- Data used: claim_status in the claims table
- Why it matters: A high denial rate means the hospital is losing money before the claim is even paid. Leaders use it to find which insurers or hospitals cause the most trouble.
### Approval Rate
- Business meaning: Of all the claims where the insurer has made a decision, the share that were approved in full.
- Formula: Approved claims / (Approved + Partially Approved + Rejected claims) x 100. Pending claims are excluded because no decision has been made yet.
- Data used: claim_status in the claims table
- Why it matters: A falling approval rate means insurers are paying in full less often. Finance leaders use it to spot which insurers or hospitals need documentation fixes or contract renegotiation.

### Claim Gap Amount
- Business meaning: The total money the hospital asked insurers to pay but will not receive, across all claims where the insurer has made a decision.
- Formula: Sum of (claim_amount - approved_amount) for claims with status Approved, Partially Approved or Rejected. Pending claims are excluded because no decision has been made yet.
- Data used: claim_amount, approved_amount, claim_status in the claims table
- Why it matters: This is the money left on the table. It is the starting point for estimating how much cash the finance team could recover by appealing or correcting claims.

### Recoverable Amount
- Business meaning: The part of the Claim Gap that the finance team can realistically try to win back, because the denial reason is fixable or appealable.
- Formula: Sum of (claim_amount - approved_amount) for Rejected and Partially Approved claims whose rejection_reason is Incomplete Documents, Coding Error or Medical Necessity Not Met. Claims denied for Policy Exclusion or Duplicate Claim are excluded.
- Data used: claim_amount, approved_amount, claim_status, rejection_reason in the claims table
- Why it matters: This is the headline number of the project. It tells leadership how many rupees are worth chasing, so the team does not waste time on denials that cannot be reversed.

### Preventable Denial Share
- Business meaning: Of all denied or partially approved claims, the share that happened because of avoidable mistakes by the hospital.
- Formula: Claims with rejection_reason Incomplete Documents, Coding Error or Duplicate Claim / All Rejected and Partially Approved claims with a rejection_reason x 100
- Data used: claim_status, rejection_reason in the claims table
- Why it matters: A high share means the hospital is causing its own losses. Fixing paperwork and coding processes would stop the money leaking before a claim is even sent.

### Claim Aging (Days Outstanding)
- Business meaning: How long a claim has been waiting for an insurer decision.
- Formula: Reporting date - claim_date, for claims with status Pending. Grouped into buckets: 0-30, 31-60, 61-90 and 90+ days.
- Data used: claim_date, claim_status in the claims table
- Why it matters: The older a claim gets, the less likely it is to be paid. Finance teams chase the oldest and largest claims first.

### Average Settlement Days
- Business meaning: On average, how many days insurers take to settle a claim after it was submitted.
- Formula: Average of (settlement_date - claim_date) for claims that have a settlement_date.
- Data used: claim_date, settlement_date in the claims table
- Why it matters: Slow insurers tie up hospital cash. This helps finance rank insurers by how fast they pay, not only by how often they approve.