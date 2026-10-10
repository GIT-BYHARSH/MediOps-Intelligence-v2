-- MediOps Intelligence v2: database schema
-- Order matters: tables that others point to are created first.

-- Views from sql/reporting_layer.sql depend on these tables, so remove them first
DROP VIEW IF EXISTS report_recovery_priority;
DROP VIEW IF EXISTS report_claim;

DROP TABLE IF EXISTS fact_claim;
DROP TABLE IF EXISTS fact_bill;
DROP TABLE IF EXISTS fact_visit;
DROP TABLE IF EXISTS dim_patient;
DROP TABLE IF EXISTS dim_department;
DROP TABLE IF EXISTS dim_insurer;
DROP TABLE IF EXISTS dim_hospital;

-- ---------- Dimensions (descriptive tables) ----------

CREATE TABLE dim_hospital (
    hospital_id    INTEGER PRIMARY KEY,
    hospital_name  VARCHAR(100) NOT NULL,
    city           VARCHAR(50)  NOT NULL,
    state          VARCHAR(50)  NOT NULL,
    hospital_type  VARCHAR(20)  NOT NULL,
    total_beds     INTEGER      NOT NULL
);

CREATE TABLE dim_department (
    department_id    INTEGER PRIMARY KEY,
    hospital_id      INTEGER NOT NULL REFERENCES dim_hospital (hospital_id),
    department_name  VARCHAR(50) NOT NULL
);

CREATE TABLE dim_insurer (
    insurer_id    INTEGER PRIMARY KEY,
    insurer_name  VARCHAR(100) NOT NULL,
    insurer_type  VARCHAR(20)  NOT NULL
);

CREATE TABLE dim_patient (
    patient_id  INTEGER PRIMARY KEY,
    gender      VARCHAR(10) NOT NULL,
    age         INTEGER     NOT NULL,
    city        VARCHAR(50) NOT NULL,
    state       VARCHAR(50) NOT NULL,
    insurer_id  INTEGER REFERENCES dim_insurer (insurer_id)   -- empty for self-pay patients
);

-- ---------- Facts (event tables) ----------

CREATE TABLE fact_visit (
    visit_id         INTEGER PRIMARY KEY,
    patient_id       INTEGER NOT NULL REFERENCES dim_patient (patient_id),
    visit_date       DATE    NOT NULL,
    hospital_id      INTEGER NOT NULL REFERENCES dim_hospital (hospital_id),
    department_id    INTEGER NOT NULL REFERENCES dim_department (department_id),
    visit_type       VARCHAR(20) NOT NULL,
    treatment_type   VARCHAR(30) NOT NULL,
    diagnosis        VARCHAR(80) NOT NULL,
    waiting_minutes  INTEGER NOT NULL,
    length_of_stay   INTEGER NOT NULL
);

CREATE TABLE fact_bill (
    bill_id             INTEGER PRIMARY KEY,
    visit_id            INTEGER NOT NULL REFERENCES fact_visit (visit_id),
    bill_date           DATE    NOT NULL,
    consultation_charge NUMERIC(12, 2) NOT NULL,
    medicine_charge     NUMERIC(12, 2) NOT NULL,
    lab_charge          NUMERIC(12, 2) NOT NULL,
    room_charge         NUMERIC(12, 2) NOT NULL,
    surgery_charge      NUMERIC(12, 2) NOT NULL,
    total_amount        NUMERIC(12, 2) NOT NULL,
    payment_method      VARCHAR(20) NOT NULL,
    payment_status      VARCHAR(20) NOT NULL
);

CREATE TABLE fact_claim (
    claim_id          INTEGER PRIMARY KEY,
    bill_id           INTEGER NOT NULL REFERENCES fact_bill (bill_id),
    visit_id          INTEGER NOT NULL REFERENCES fact_visit (visit_id),
    insurer_id        INTEGER NOT NULL REFERENCES dim_insurer (insurer_id),
    claim_amount      NUMERIC(12, 2) NOT NULL,
    approved_amount   NUMERIC(12, 2),     -- empty while the claim is Pending
    claim_status      VARCHAR(20) NOT NULL,
    rejection_reason  VARCHAR(40),        -- empty unless Rejected or Partially Approved
    claim_date        DATE NOT NULL,
    settlement_date   DATE                -- empty while the claim is Pending
);