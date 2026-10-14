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
- FINAL headline KPIs (after the winter fix): 305,835 claims, 288,986 decided, denial rate 11.1%, approval rate 73.1%, claim gap Rs 95.57 crore, recoverable amount Rs 61.06 crore (about 64% of the gap), average settlement 23.7 days. The first KPI numbers in this log (10.4%, 73.8%, 93.67, 59.31) were measured before the winter fix. Use the FINAL numbers in the report, README and resume.
- SQL skills added: CASE WHEN buckets, EXTRACT(MONTH ...), date subtraction for aging.

## Step 7: Recovery priority and strategy simulation (SQL, analysis_04 and 05)
- Built: a priority score for every recoverable claim = recoverable amount x win chance / effort hours. Win chance assumed: Incomplete Documents 70%, Coding Error 60%, Medical Necessity Not Met 35%. Effort assumed: 1, 2 and 5 hours. These are documented assumptions, not measured values, and must be stated in the report and tested with a sensitivity check.
- Result 1: 49,069 recoverable claims with about Rs 31.3 crore expected recovery and about 126,000 hours of effort. The top 10% of claims by priority hold 64% of the expected recovery with 6% of the hours. The top 20% hold 86% with 16% of the hours. Best decile earns Rs 25,256 per hour, worst decile Rs 24.
- Result 2 (simulation, 10,000 hours): priority score recovers Rs 21.87 crore, largest amount first Rs 16.68 crore, quickest first Rs 14.00 crore, random order Rs 2.44 crore. Priority score is 9.0 times better than random and 31% better than largest first, using the same time.
- Why: this answers the project question (which claims to chase first) and gives the headline number for the resume, README and report.
- SQL skills added: CTE (WITH), RANK() OVER, NTILE, running total with SUM() OVER (ROWS UNBOUNDED PRECEDING), UNION ALL, MAX() FILTER ... OVER.

## Step 8: Python connection and data-quality checks
- Built: python/db.py (one shared database connection that reads the password from the private .env file, which Git ignores), python/data_quality_checks.py (27 automatic checks that write docs/data_quality_report.md).
- Check groups: duplicates, impossible values, date logic, missing values, business rules. A check passes when it finds 0 bad rows.
- Problem found: the first run passed 25 of 27. 1,056 bills were dated after the reporting date (31 Dec 2025) because bill_date = visit_date + length_of_stay for patients admitted late in December. 662 claims were dated before their own bill because of that. Fix: bill dates are capped at 31 Dec 2025 (an interim bill for patients still admitted at year-end). Amounts did not change.
- Result after fixing the generator and reloading the database: 27 of 27 checks pass. Row counts unchanged, pending claims unchanged (16,849).
- Expected empty values (not errors): 28.0% self-pay patients (no insurer), 5.5% pending claims (no approved amount or settlement date), 74.6% of claims have no rejection reason (approved or pending).
- Lesson: write checks that can fail, run them, and fix the cause at the source (the generator), then rebuild in the same order: bills, claims, schema, load. Keep the quality report in the project as evidence.
- Charts (make_charts.py, assets/charts): winter overload, denial hotspots, recovery strategies, claim gap by treatment. Each title states the insight (for example "Surgery is 7% of claims but 75% of the money not paid").

## Step 9: Machine learning, models and the theoretical ceiling
- Built: build_features.py (one row per decided claim, 288,986 rows; labels kept separate from inputs to avoid data leakage) and train_models.py.
- Leakage: columns known only after the decision (approved_amount, rejection_reason, settlement_date, claim_status) are never used as inputs.
- Split by time, not at random: train on visits before 1 Jul 2025 (228,452 claims), test on 1 Jul 2025 onward (60,534 claims). This mimics predicting the future from the past.
- Two questions: REJECTION (fully rejected, 11% of claims) and SHORTFALL (rejected or partially approved, 27% of claims). Models: logistic regression (simple baseline) and gradient boosting (finds combinations such as insurer + hospital).
- Results (AUC, 0.5 = guessing): rejection 0.528 logistic, 0.532 boosting, ceiling 0.533. Shortfall 0.557 logistic, 0.559 boosting, ceiling 0.559. The top 10% riskiest claims catch about 15% of rejections and 18% of shortfalls.
- Ceiling: the best AUC any model could reach if it knew the exact rules used to build the data. Because simulated outcomes are random draws with raised odds, the ceiling is low, and the model reaches 99.8% of it. So the low AUC is a property of the simulated outcomes, not a weak model. State this clearly in the report. Real denial models also use signals we do not simulate (documentation completeness, prior authorisation); list this as future work.
- Do not headline AUC 0.53 on the resume without the ceiling comparison. The strongest headline remains the SQL recovery result.

## Step 10: Explaining the model
- Method: permutation importance (shuffle one input at a time on unseen test claims and measure the drop in AUC). Chart: assets/charts/05_model_drivers.png.
- Rejection drivers: hospital_id 0.016, is_winter 0.011, insurer_id 0.009, claim_amount 0.002 (large bills). Hospital and insurer matter together because the insurer problem only happens at two hospitals (an interaction a boosting model can learn).
- Shortfall drivers: treatment_type 0.044 (surgery) far above everything else, then hospital, winter, diagnosis, insurer. Diagnosis probably acts as a stand-in for surgery cases.
- The model points at the planted stories without being told: insurer and hospital (story 1), big bills (story 6), surgery (story 7), winter (story 4).
## Step 11: Forecasting
- Built: forecast.py. It forecasts monthly claim volume and denial rate (by month of the visit) for Jan-Mar 2026 and saves assets/charts/06_forecast.png.
- Method: backtest first. Pretend it is 30 Jun 2025, forecast Jul-Dec 2025, compare with what really happened (error = MAPE, mean absolute percentage error, lower is better). Four simple methods: last value, 12-month average, same month last year, and same month last year adjusted by the recent trend.
- Backtest result (claims per month): last value 6.1%, 12-month average 10.0%, same month last year 0.9%, last year x recent trend 0.8%. Denial rate: 6.6%, 10.5%, 2.5%, 2.5%. The seasonal methods win because winter is a repeating pattern that the other methods cannot see.
- Forecast: Jan 2026 about 16,900 claims and a 14.7% denial rate, then Feb about 10,900 claims at 10.7% and Mar about 12,200 at 10.8%.
- Limits to state in the report: only 24 months of history, so only one earlier winter to learn from and 6 test months. The very low error is partly because simulated seasonality repeats exactly and there is no growth trend. Real data would be noisier, so treat 0.8% as a best case. A simple method that is checked in a backtest is better than a complex one that is not.

## Step 12: Anomaly alerts
- Built: anomaly_alerts.py. It compares every hospital, insurer-hospital pair, department and month with its peers and writes data/processed/alerts.csv.
- Method (robust z-score): typical = median of the peers, spread = 1.48 x MAD (median absolute deviation) but never below a minimum floor. z = (value - typical) / spread. Alert when z is at least 5 (unusually high). Median and MAD are not pulled around by the very outliers being hunted, unlike mean and standard deviation. The floor stops tiny differences from looking big when peers are almost identical (for example, almost no hospital has old pending claims).
- Five checks: denial rate of insurer-hospital pairs, denial rate of hospital departments, share of claims pending over 90 days per hospital, average settlement days per insurer, monthly denial rate. Groups under 200 decided claims are skipped.
- Result: exactly 9 alerts, all genuine and none false. Aegis at Coastal Care (z 17.6, 307 extra rejections) and at Banyan Tree (z 17.5, 374); Meridian Heart Cardiology (z 11.5, 124); Lakeview General Hospital pending backlog (z 16.2, 1,389 stuck claims); Unity General settlement time (z 40, about 1.1 million extra waiting days); December and January denial spikes (z 12 to 15). Note December 2025 shows fewer extra rejections (153) because many of its claims are still pending.
- Confounding handled: the other Coastal Care and Banyan Tree departments look slightly high only because of Aegis. They stay under the alert threshold, so only the real cause is flagged.
- Limit: the alerts compare against peers, not against a model of cause. They tell the team where to look, not why.

## Step 13: Reporting layer for Power BI
- Built: sql/reporting_layer.sql with dim_date (731 days), view report_claim (one row per claim, 305,835 rows) and view report_recovery_priority (49,069 recoverable claims).
- Why: the operational tables form a chain (claim, bill, visit, hospital). Power BI works best with a star: one central fact table linked directly to each dimension. The view flattens the chain so the report model stays simple and filters work in one direction.
- report_claim already holds the KPI building blocks: is_decided, is_rejected, is_approved, claim_gap, recoverable_amount, is_preventable, settlement_days, pending_age_days, aging_bucket. Calculating them once in SQL means Power BI and SQL give the same answers.
- Checks: claim gap Rs 95.57 crore, recoverable Rs 61.06 crore, 1,389 claims pending over 90 days and expected recovery Rs 31.27 crore all match the earlier analyses.
- schema.sql now drops the views first, so reloading the base tables never fails because of dependent views. Re-run order after any data change: schema.sql, load_data.sql, reporting_layer.sql.

## Step 10 (continued): limits of the importance method
- Limits: permutation importance splits credit between related inputs (room charge, surgery charge and claim amount move together), so a small bar does not prove an input is unimportant. Story 2 (one department at one hospital) affects only about 1,000 claims, so it does not show up in the top inputs.

## Step 14: Power BI model and Command Center page (in progress)
- Model: 5 relationships, all many-to-one with single direction from report_claim to dim_hospital, dim_department, dim_insurer and dim_date (visit_date to date_id), plus one-to-one between report_recovery_priority and report_claim on claim_id. The extra dim_department to dim_hospital link was deleted, because two paths to the same table make filters ambiguous.
- Tables renamed (removed the "public " prefix) so DAX stays readable.
- Measures verified against SQL: Total Claims 305,835; Denial Rate 11.1%; Approval Rate 73.1%; Claim Gap Rs 95.57 Cr; Recoverable Rs 61.06 Cr; Pending Over 90 Days 1,389; Avg Settlement 23.74 days; Preventable Denial Share 57.6%; Expected Recovery Rs 31.27 Cr.
- Bug found and fixed: Preventable Denial Share first showed 139.5% (then 57.9%). Reason: in report_claim the rejection_reason is filled for Rejected AND Partially Approved claims, so a measure restricted to Rejected gives a different number. The KPI dictionary counts both, which gives 57.6%, so the measure uses both statuses.
- Lesson: a "1K" card is Power BI shortening a number; a text-formatted measure shows the full 1,389. A text axis sorts by value unless told otherwise, so the month chart was in the wrong order until it was sorted; a real date column (Month Start) gives a clean time axis.
- Added: dim_date[Month Start], report_claim[Hotspot Label] (insurer @ hospital), measure Decided Claims. Hotspot chart uses two visual filters: decided claims at least 200, then top 5 by denial rate.
- Templates in powerbi/ (theme json, 4 page backgrounds, layout_guide.md with pixel positions) were generated by python/make_powerbi_assets.py.
- Interactivity done so far: 4 dropdown slicers (hospital, insurer, treatment, year) and a Reset filters button linked to a bookmark. Cross-filtering between charts works by default.
- Page 1 polish: donut title "Claim outcomes"; Pending Over 90 Days (Text) uses + 0 so a blank becomes 0; Reset Filters (Ctrl+click) works.
- Still optional on page 1: tooltip page, Rate/Volume/Winter toggle.

## Step 15: Where Money Is Lost (page 2)
- Built by duplicating page 1, swapping the background to page2_where_money_is_lost.png, and deleting the six Command Center charts. Slicers, KPI cards and Reset came along, so filters stay consistent across pages.
- Heatmap: matrix with hospital_name on rows, Insurer Label (first word of insurer_name) on columns, Denial Rate as values. Conditional formatting gradient green #2E9E6B to red #D64545. The planted story is visible: Aegis at Banyan Tree 28.6% and Coastal Care 28.8% are the only red cells.
- Lesson: long labels hide a heatmap. A DAX column `Insurer Label = PATHITEM(SUBSTITUTE(dim_insurer[insurer_name], " ", "|"), 1)` plus turning Auto-size from Fit to content to Grow to fit, then dragging the row-header divider, fitted most of the 8 insurers.
- Denial reasons bar: Claim Gap (Cr) by rejection_reason, Blank filtered out. Claim gap by hospital: same visual copied, Y-axis swapped to hospital_name. Banyan Tree, Sunrise and Coastal Care lead, which matches the planted revenue-loss story.
- Still to do: navigation buttons on the sidebar, tooltip/toggle extras.

## Step 17: Outlook & Alerts (page 4)
- Built by duplicating page 3, swapping the background to page4_outlook_alerts.png.
- Python writes report_forecast (24 months of actuals plus Jan-Mar 2026 using "last year x recent trend", the method chosen in forecast.py). Jan 2026 is forecast at about 14.7% denial, which continues the planted winter story.
- Line chart: month_start on X (date, not hierarchy), denial_rate on Y, series in Legend (Actual vs Forecast). Lesson: a date hierarchy rolled the months up to years and hid the winter spikes; Count of series on Y drew a flat line.
- Alerts table: report_alert with Don't summarize on alert_rank, sorted 1 to 9.

## Step 16: Recovery Worklist (page 3)
- Built by duplicating page 2, swapping the background to page3_recovery_worklist.png, and deleting the three page-2 charts.
- Python now also writes report_recovery_curve (~250 points of cumulative hours vs expected recovery, plus a random-order diagonal) and report_worklist_top10 (10 claims, ready-made columns). At 10,000 hours the priority path recovers Rs 21.87 Cr, matching the strategy table.
- Lesson: never put 49,000 claim rows on a line chart. Downsample the curve in Python. Never let Power BI Sum a rank column; set Don't summarize, or include a unique field so rows do not collapse.
- Curve: X = hours_thousand (max 40), Y = Priority order (blue) and Random order (grey). Table: Rank, Hospital, Insurer, Reason, Expected (L), Hours.

- Added python/export_dashboard_tables.py: it builds report_alert (9 alerts with headline, detail, severity, rank), report_strategy (4 strategies with expected recovery) and report_alert_top5 (top 5 alerts as numbered text lines) in PostgreSQL. Why: Power BI cannot compute these itself (the alerts come from Python anomaly checks, the strategy results from a 10,000-hour simulation), so Python writes them as tables and Power BI only displays them.
- Built: Recovery by strategy column chart (Priority score 21.87 Cr vs Random 2.44 Cr, about 9x) and the Alerts panel on page 1.
- Lesson: a first version of the alerts panel used a filter 'bottom 5 by alert_rank' plus a sort, which took many steps. It is simpler to prepare the data so that a plain table is already correct (numbered text, top 5 only). Do the shaping in the data, not in the visual.
- Lesson: a visual that shows only its title is just too small to draw; check size before suspecting the fields.
