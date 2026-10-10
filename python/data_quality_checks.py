"""Data-quality checks for the mediops database.
Each check counts the 'bad rows'. A check passes when it finds 0.
Writes a readable report to docs/data_quality_report.md."""
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from db import get_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "docs" / "data_quality_report.md"
REPORT_DATE = "2025-12-31"

# (group, what we check, SQL that counts the bad rows)
CHECKS = [
    # ---------- Duplicates ----------
    ("Duplicates", "More than one claim for the same bill",
     "SELECT COUNT(*) FROM (SELECT bill_id FROM fact_claim GROUP BY bill_id HAVING COUNT(*) > 1) t"),
    ("Duplicates", "More than one bill for the same visit",
     "SELECT COUNT(*) FROM (SELECT visit_id FROM fact_bill GROUP BY visit_id HAVING COUNT(*) > 1) t"),

    # ---------- Impossible values ----------
    ("Impossible values", "Patient age outside 0-100",
     "SELECT COUNT(*) FROM dim_patient WHERE age < 0 OR age > 100"),
    ("Impossible values", "Visit date outside 2024-2025",
     "SELECT COUNT(*) FROM fact_visit WHERE visit_date < '2024-01-01' OR visit_date > '2025-12-31'"),
    ("Impossible values", "Negative waiting time or length of stay",
     "SELECT COUNT(*) FROM fact_visit WHERE waiting_minutes < 0 OR length_of_stay < 0"),
    ("Impossible values", "Bill total is zero or negative",
     "SELECT COUNT(*) FROM fact_bill WHERE total_amount <= 0"),
    ("Impossible values", "Bill total differs from the sum of its charges",
     """SELECT COUNT(*) FROM fact_bill WHERE ABS(total_amount -
        (consultation_charge + medicine_charge + lab_charge + room_charge + surgery_charge)) > 1"""),
    ("Impossible values", "Approved amount higher than claim amount",
     "SELECT COUNT(*) FROM fact_claim WHERE approved_amount > claim_amount"),
    ("Impossible values", "Claim amount higher than the bill total",
     "SELECT COUNT(*) FROM fact_claim c JOIN fact_bill b ON b.bill_id = c.bill_id WHERE c.claim_amount > b.total_amount"),

    # ---------- Date logic ----------
    ("Date logic", "Bill dated before its visit",
     "SELECT COUNT(*) FROM fact_bill b JOIN fact_visit v ON v.visit_id = b.visit_id WHERE b.bill_date < v.visit_date"),
    ("Date logic", "Bill dated after the reporting date (31 Dec 2025)",
     f"SELECT COUNT(*) FROM fact_bill WHERE bill_date > '{REPORT_DATE}'"),
    ("Date logic", "Claim dated before its bill",
     "SELECT COUNT(*) FROM fact_claim c JOIN fact_bill b ON b.bill_id = c.bill_id WHERE c.claim_date < b.bill_date"),
    ("Date logic", "Claim dated after the reporting date",
     f"SELECT COUNT(*) FROM fact_claim WHERE claim_date > '{REPORT_DATE}'"),
    ("Date logic", "Settlement dated before the claim",
     "SELECT COUNT(*) FROM fact_claim WHERE settlement_date < claim_date"),
    ("Date logic", "Settlement dated after the reporting date",
     f"SELECT COUNT(*) FROM fact_claim WHERE settlement_date > '{REPORT_DATE}'"),

    # ---------- Missing values ----------
    ("Missing values", "Pending claim that has an approved amount or settlement date",
     """SELECT COUNT(*) FROM fact_claim
        WHERE claim_status = 'Pending' AND (approved_amount IS NOT NULL OR settlement_date IS NOT NULL)"""),
    ("Missing values", "Decided claim without an approved amount",
     "SELECT COUNT(*) FROM fact_claim WHERE claim_status <> 'Pending' AND approved_amount IS NULL"),
    ("Missing values", "Decided claim without a settlement date",
     "SELECT COUNT(*) FROM fact_claim WHERE claim_status <> 'Pending' AND settlement_date IS NULL"),
    ("Missing values", "Rejected or partially approved claim without a reason",
     """SELECT COUNT(*) FROM fact_claim
        WHERE claim_status IN ('Rejected', 'Partially Approved') AND rejection_reason IS NULL"""),
    ("Missing values", "Approved claim that has a rejection reason",
     "SELECT COUNT(*) FROM fact_claim WHERE claim_status = 'Approved' AND rejection_reason IS NOT NULL"),
    ("Missing values", "Rejected claim with an approved amount above zero",
     "SELECT COUNT(*) FROM fact_claim WHERE claim_status = 'Rejected' AND approved_amount > 0"),

    # ---------- Business rules ----------
    ("Business rules", "Insurance bill without a claim",
     """SELECT COUNT(*) FROM fact_bill b WHERE b.payment_method = 'Insurance'
        AND NOT EXISTS (SELECT 1 FROM fact_claim c WHERE c.bill_id = b.bill_id)"""),
    ("Business rules", "Claim on a bill that is not an insurance bill",
     "SELECT COUNT(*) FROM fact_claim c JOIN fact_bill b ON b.bill_id = c.bill_id WHERE b.payment_method <> 'Insurance'"),
    ("Business rules", "Claim insurer differs from the patient's insurer",
     """SELECT COUNT(*) FROM fact_claim c
        JOIN fact_visit v ON v.visit_id = c.visit_id
        JOIN dim_patient p ON p.patient_id = v.patient_id
        WHERE p.insurer_id IS DISTINCT FROM c.insurer_id"""),
    ("Business rules", "Visit department does not belong to the visit hospital",
     """SELECT COUNT(*) FROM fact_visit v JOIN dim_department d ON d.department_id = v.department_id
        WHERE d.hospital_id <> v.hospital_id"""),
    ("Business rules", "Bill payment status disagrees with its claim status",
     """SELECT COUNT(*) FROM fact_claim c JOIN fact_bill b ON b.bill_id = c.bill_id
        WHERE (c.claim_status = 'Approved' AND b.payment_status <> 'Paid')
           OR (c.claim_status = 'Partially Approved' AND b.payment_status <> 'Partially Paid')
           OR (c.claim_status IN ('Rejected', 'Pending') AND b.payment_status <> 'Pending')"""),
    ("Business rules", "Bill still marked 'Awaiting Claim'",
     "SELECT COUNT(*) FROM fact_bill WHERE payment_status = 'Awaiting Claim'"),
]

# Missing values that are EXPECTED (informational only, not pass/fail)
EXPECTED_NULLS = [
    ("Self-pay patients (no insurer_id)", "SELECT COUNT(*) FROM dim_patient WHERE insurer_id IS NULL", "SELECT COUNT(*) FROM dim_patient"),
    ("Pending claims (no approved amount)", "SELECT COUNT(*) FROM fact_claim WHERE approved_amount IS NULL", "SELECT COUNT(*) FROM fact_claim"),
    ("Claims without a rejection reason", "SELECT COUNT(*) FROM fact_claim WHERE rejection_reason IS NULL", "SELECT COUNT(*) FROM fact_claim"),
]


def main():
    engine = get_engine()
    results = []
    with engine.connect() as conn:
        for group, name, sql in CHECKS:
            bad_rows = conn.execute(text(sql)).scalar()
            results.append((group, name, bad_rows))

        nulls = []
        for name, sql_count, sql_total in EXPECTED_NULLS:
            count = conn.execute(text(sql_count)).scalar()
            total = conn.execute(text(sql_total)).scalar()
            nulls.append((name, count, 100.0 * count / total))

    passed = sum(1 for _, _, bad in results if bad == 0)

    # ---------- Print to the screen ----------
    print(f"\nDATA QUALITY: {passed} of {len(results)} checks passed\n")
    for group, name, bad in results:
        mark = "PASS" if bad == 0 else "FAIL"
        print(f"[{mark}] {group:<18} {name}  (bad rows: {bad:,})")
    print("\nExpected empty values (not errors):")
    for name, count, pct in nulls:
        print(f"  {name}: {count:,} ({pct:.1f}%)")

    # ---------- Save the report ----------
    lines = [
        "# Data Quality Report",
        "",
        f"Generated on {datetime.now():%d %b %Y %H:%M}. Result: **{passed} of {len(results)} checks passed**.",
        "",
        "Each check counts the rows that break a rule. A check passes when it finds 0.",
        "",
        "| Group | Check | Bad rows | Result |",
        "|---|---|---|---|",
    ]
    for group, name, bad in results:
        lines.append(f"| {group} | {name} | {bad:,} | {'PASS' if bad == 0 else 'FAIL'} |")
    lines += ["", "## Expected empty values", "",
              "These are empty on purpose (not errors).", "",
              "| Field | Rows | Share |", "|---|---|---|"]
    for name, count, pct in nulls:
        lines.append(f"| {name} | {count:,} | {pct:.1f}% |")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()