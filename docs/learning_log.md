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

- Visits (500,000): dates weighted so December and January are about 40% busier (story 4). Hospital chosen mostly in the patient's own city, bigger hospitals get more visits. Department always belongs to the visit's hospital (checked: 0 mismatches). Waiting time is 35% longer in winter. Surgery is about 35% of admitted visits.
- Why: consistent keys and verified planted patterns make later SQL findings trustworthy.

- Bills (500,000, one per visit): charges built from department, visit type, stay length and surgery. Private hospitals cost most (price multiplier). 61% of bills are insurance (72% insured x 85% who file). Insurance bills start as "Awaiting Claim" and the claims step will set their final status.
- Why: bill size drives how much money a denial puts at risk, and it makes private-hospital and surgery claims the biggest recovery opportunities.

- Claims (305,835, one per insurance bill): each claim gets its own chance of rejection (baseline 10%) and partial approval (baseline 14%), and the planted stories raise those chances for specific groups. A claim whose settlement date falls after the reporting date (31 Dec 2025) stays Pending. The outcome is written back to the bills (Approved = Paid, Partially Approved = Partially Paid, Rejected or Pending = Pending).
- Verified stories: insurer 4 at hospitals 6 and 7 rejects 27.4% vs 10.0% (63% Incomplete Documents); Cardiology at hospital 4 rejects 22.2% (71% Coding Error); insurer 3 settles in 60 days vs 20; hospital 10 holds all 1,389 pending claims older than 90 days; bills over 2 lakh are rejected 20.7% vs 10.2%; surgery is partially approved 40.2% vs 14.0%.
- Why: this table is the core of the project. Every later SQL, Python, ML and dashboard result must rediscover these known stories, which proves the analysis works.
- Run order matters: the claims script edits bills.csv, so always run generators in this order: hospitals, departments, insurers, patients, visits, bills, claims.
## Step 5: PostgreSQL database
- Built: database mediops, sql/schema.sql (7 tables with primary and foreign keys), sql/load_data.sql (bulk load with COPY).
- Result: row counts match the CSV files exactly (25 hospitals, 205 departments, 8 insurers, 100,000 patients, 500,000 visits, 500,000 bills, 305,835 claims).
- Why: foreign keys stop impossible data (a visit at a hospital that does not exist). Empty cells load as NULL, which means no value (self-pay insurer, pending claim amounts and dates). Load order follows the keys: dimensions first, then facts.
- Re-running: load_data.sql adds rows, so run schema.sql first (it drops and recreates the tables) before loading again.

## Step 6: SQL analysis (in progress)
- Overall KPIs (analysis_01): denial rate 10.4%, approval rate 73.8%, claim gap Rs 93.67 crore, recoverable amount Rs 59.31 crore (about 63% of the gap is fixable), average settlement 23.7 days. Pending claims are excluded from rates, so approval rate (73.8%) is higher than the raw approved share (69.8%).
- By insurer: Unity General Insurance takes 59.9 days vs about 20 for the others (story 3 found). Aegis looks only slightly high overall (11.4%), because its problem is hidden by averaging.
- Drill-down (analysis_02): Aegis at Coastal Care and Banyan Tree rejects 27.5% and 27.4% with 62-64% Incomplete Documents (story 1 found). Meridian Heart Cardiology rejects 22.2% with 71% Coding Error (story 2 found).
- Lessons: a summary can hide a problem, so drill down by another dimension. Use HAVING to ignore tiny groups. A problem in one dimension can leak into another (confounding): Coastal Care and Banyan Tree departments look high only because of Aegis.
- SQL skills used: COUNT FILTER, JOIN across 4 tables, GROUP BY, HAVING, ORDER BY, LIMIT.
- Other stories (analysis_03): Lakeview General Hospital has 1,389 claims pending over 90 days and no other hospital has any (story 5). Bills above Rs 2,00,000 are denied 21.3% vs about 10.9%, with 64% Medical Necessity (story 6). Surgery is partially approved 40.3% vs about 14% and causes Rs 72.02 crore of the claim gap, about three quarters of the total, from only 7% of claims (story 7). December and January have about 40% more visits and waits of 46.9 vs 34.8 minutes (story 4).
- Fix found by SQL: the winter denial effect of story 4 was missing from the claims generator. After adding a +4 point rejection boost for December/January visits, denial rate is 14.7% in December and 14.4% in January vs about 10-11% in other months. Lesson: checking the data against the written story catches gaps in the data, and the claims generator can be re-run safely (same seed, same results elsewhere).
- Numbers in analysis_01 and analysis_02 above were measured before this fix, so they move slightly. They are refreshed in the next task.
- SQL skills added: CASE WHEN buckets, EXTRACT(MONTH ...), date subtraction for aging.
