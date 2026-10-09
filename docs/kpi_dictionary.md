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