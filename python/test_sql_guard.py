"""Offline tests for sql_guard.py (no database needed).
Run from the project root:  python python/test_sql_guard.py
"""
from sql_guard import add_row_limit, validate_sql

SHOULD_PASS = [
    "SELECT hospital_name FROM dim_hospital",
    "select count(*) from report_claim",
    "SELECT 1",
    "SELECT * FROM report_claim;",
    "```sql\nSELECT insurer_name FROM dim_insurer\n```",
    "SELECT EXTRACT(MONTH FROM visit_date) AS m, COUNT(*) FROM report_claim GROUP BY 1",
    "WITH x AS (SELECT hospital_id, COUNT(*) n FROM report_claim GROUP BY 1) "
    "SELECT h.hospital_name, x.n FROM x JOIN dim_hospital h ON h.hospital_id = x.hospital_id",
    "SELECT i.insurer_name, ROUND(AVG(c.settlement_days), 1) FROM report_claim c "
    "JOIN dim_insurer i ON i.insurer_id = c.insurer_id GROUP BY 1",
    "SELECT * FROM public.report_alert",
]

SHOULD_FAIL = [
    "DROP TABLE report_claim",
    "SELECT 1; DROP TABLE dim_hospital",
    "DELETE FROM report_alert",
    "UPDATE dim_insurer SET insurer_name = 'x'",
    "INSERT INTO dim_hospital VALUES (1)",
    "SELECT * FROM fact_claim",
    "SELECT * FROM dim_patient",
    "SELECT * FROM report_claim c, fact_bill b",
    "SELECT * FROM information_schema.tables",
    "SELECT pg_sleep(30)",
    "SELECT * INTO new_table FROM report_claim",
    "SELECT 1 -- hidden comment",
    "SELECT /* sneaky */ 1",
    "COPY report_claim TO 'x.csv'",
    "WITH d AS (DELETE FROM report_alert RETURNING *) SELECT * FROM d",
    "SELECT * FROM some_other_table",
    "SELECT * FROM pg_catalog.pg_tables",
    "EXPLAIN ANALYZE SELECT 1",
    "SELECT set_config('x', 'y', false)",
    "",
]


def main():
    failures = 0
    for sql in SHOULD_PASS:
        ok, info = validate_sql(sql)
        if not ok:
            failures += 1
            print(f"FAIL (should pass): {sql!r} -> {info}")
    for sql in SHOULD_FAIL:
        ok, info = validate_sql(sql)
        if ok:
            failures += 1
            print(f"FAIL (should be blocked): {sql!r}")

    ok, cleaned = validate_sql("SELECT * FROM report_claim;")
    wrapped = add_row_limit(cleaned)
    if "LIMIT 200" not in wrapped or cleaned.endswith(";"):
        failures += 1
        print("FAIL: row limit wrapper")

    total = len(SHOULD_PASS) + len(SHOULD_FAIL) + 1
    print(f"{total - failures} of {total} guard tests passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
