# Data Model

## Columns required by the KPI dictionary
1.claim_amount
2.approved_amount
3.claim_status
4.rejection_reason
5.claim_date 
6.settlement_date

## Extra information needed to answer "which one?"
## Extra information needed to answer "which one?"
- Insurer (which company decided the claim)
- Hospital (where the care happened)
- Department (which unit treated the patient)
- Patient details (age, gender, city)
- Visit details (visit type, diagnosis, treatment type)
- Bill details (total amount, payment status)
- Dates (for trends by month and year)

## Tables

### Dimension tables (descriptions)
- dim_hospital: hospital_id, hospital_name, city, state, hospital_type, total_beds
- dim_department: department_id, hospital_id, department_name
- dim_insurer: insurer_id, insurer_name, insurer_type
- dim_patient: patient_id, gender, age, city, state, insurer_id
- dim_date: date, month, quarter, year (built later in the database or Power BI)

### Fact tables (events with numbers)
- fact_visit: visit_id, patient_id, hospital_id, department_id, visit_date, visit_type, diagnosis, treatment_type, waiting_minutes, length_of_stay
- fact_bill: bill_id, visit_id, bill_date, total_amount, payment_method, payment_status
- fact_claim: claim_id, bill_id, visit_id, insurer_id, claim_amount, approved_amount, claim_status, rejection_reason, claim_date, settlement_date

## Relationships
- One hospital has many departments
- One patient has many visits
- One visit has one bill
- One bill has zero or one claim (self-pay patients have no claim)
- One insurer receives many claims

## Design decision
Doctors are excluded from v1. The project focuses on revenue recovery, not clinician workload.