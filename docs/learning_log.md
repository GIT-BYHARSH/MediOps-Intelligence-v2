# Learning Log

Short notes after each step: what I built and why. Used later for the report, viva and interviews.

## Step 0: Setup
- Built: project folder, Git and GitHub repo, Python 3.12 environment, PostgreSQL 18.
- Why: a clean reproducible setup and a commit history that shows steady work.

## Step 1: KPI dictionary
- Built: definitions for Denial Rate, Approval Rate, Claim Gap Amount, Recoverable Amount, Preventable Denial Share, Claim Aging, Average Settlement Days.
- Why: every number must mean one thing everywhere. Pending claims are excluded from rates because no decision has been made yet.

## Step 2: Data model
- Built: star schema with 4 dimensions (hospital, department, insurer, patient) and 3 facts (visit, bill, claim), plus a date table.
- Why: a blueprint for the database and Power BI. A bill has zero or one claim because self-pay patients do not use insurance.

## Step 3: Planted stories
- Built: 7 patterns hidden in the simulated data (insurer rejecting more at two hospitals, coding errors in one department, slow insurer, winter overload, old pending backlog, big bills challenged, surgery partial approvals).
- Why: the data is simulated, so planting known patterns lets me prove my analysis finds them.

## Step 4: Data generation (in progress)
- Built: hospitals (25 fictional), departments (205), insurers (8 fictional), patients (100,000).
- Patients: no names are stored (privacy by design). 28% are self-pay (no insurer_id). Age groups follow hospital-like demand. A city gets more patients when its hospitals have more beds.
- Why: separate small scripts per table, with a fixed random seed so results are reproducible. Fictional names are used because the planted problems must not be attached to real hospitals or insurers.
