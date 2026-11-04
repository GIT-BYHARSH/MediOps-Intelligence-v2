"""Copy the report-level tables the demo app needs from the local database to a cloud PostgreSQL
database (for example a free Neon project), then create a READ-ONLY user for the deployed app.

Run from the project root:   python python/export_to_cloud.py

Setup: put the cloud connection string in the private .env file as
    CLOUD_DATABASE_URL=postgresql://owner:password@host/dbname?sslmode=require
When it finishes, the read-only connection string is saved in .env as CLOUD_READER_URL.
That reader URL is the only one the deployed app needs (it becomes DATABASE_URL in the app's secrets).
Passwords are never printed.

Only report-level data is copied. The raw patient-level tables stay on this computer.
All data is simulated.
"""
import re
import secrets
import tempfile
from urllib.parse import urlsplit, urlunsplit

import psycopg2

from db import PROJECT_ROOT, get_engine
import os

# Views are copied as plain tables, so the cloud copy needs no other objects.
RELATIONS = ["dim_hospital", "dim_department", "dim_insurer", "dim_date",
             "report_claim", "report_recovery_priority", "report_alert",
             "report_strategy", "report_worklist_top10"]

INDEXES = [
    "CREATE UNIQUE INDEX ON report_claim (claim_id)",
    "CREATE INDEX ON report_claim (hospital_id)",
    "CREATE INDEX ON report_claim (insurer_id)",
    "CREATE INDEX ON report_claim (department_id)",
    "CREATE INDEX ON report_claim (visit_date)",
    "CREATE UNIQUE INDEX ON report_recovery_priority (claim_id)",
    "CREATE UNIQUE INDEX ON dim_hospital (hospital_id)",
    "CREATE UNIQUE INDEX ON dim_department (department_id)",
    "CREATE UNIQUE INDEX ON dim_insurer (insurer_id)",
]

READER_ROLE = "mediops_reader"


def column_ddl(cur, relation):
    """Exact column names and types of a table or view, as CREATE TABLE text."""
    cur.execute("""SELECT a.attname, format_type(a.atttypid, a.atttypmod)
                   FROM pg_attribute a
                   WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
                   ORDER BY a.attnum""", (f"public.{relation}",))
    return ", ".join(f'"{name}" {sql_type}' for name, sql_type in cur.fetchall())


def copy_relation(local, remote, relation):
    with local.cursor() as lc, remote.cursor() as rc:
        rc.execute(f"DROP TABLE IF EXISTS {relation} CASCADE")
        rc.execute(f"CREATE TABLE {relation} ({column_ddl(lc, relation)})")
        with tempfile.TemporaryFile() as buffer:  # binary COPY keeps every type exactly
            lc.copy_expert(f"COPY (SELECT * FROM {relation}) TO STDOUT WITH (FORMAT binary)", buffer)
            buffer.seek(0)
            rc.copy_expert(f"COPY {relation} FROM STDIN WITH (FORMAT binary)", buffer)
    remote.commit()


def count_rows(connection, relation):
    with connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {relation}")
        return cur.fetchone()[0]


def make_reader_role(remote, owner_url):
    """Create (or reset) a user that can only SELECT. Returns its connection string."""
    password = secrets.token_urlsafe(24)
    database = urlsplit(owner_url).path.lstrip("/")
    with remote.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (READER_ROLE,))
        verb = "ALTER" if cur.fetchone() else "CREATE"
        cur.execute(f"{verb} ROLE {READER_ROLE} WITH LOGIN PASSWORD %s", (password,))
        cur.execute(f'GRANT CONNECT ON DATABASE "{database}" TO {READER_ROLE}')
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {READER_ROLE}")
        cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {READER_ROLE}")
    remote.commit()
    parts = urlsplit(owner_url)
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme, f"{READER_ROLE}:{password}@{host}", parts.path, parts.query, ""))


def save_to_env(name, value):
    """Add or replace NAME=value in the private .env file."""
    path = PROJECT_ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if not re.match(rf"^{name}\s*=", line)]
    lines.append(f"{name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    owner_url = os.environ.get("CLOUD_DATABASE_URL", "").strip()
    if not owner_url.startswith(("postgres://", "postgresql://")):
        raise SystemExit("Put CLOUD_DATABASE_URL=postgresql://... in your .env file first (see the docstring).")
    local = get_engine().raw_connection()
    remote = psycopg2.connect(owner_url)
    try:
        for relation in RELATIONS:
            copy_relation(local, remote, relation)
            local_n, remote_n = count_rows(local, relation), count_rows(remote, relation)
            status = "OK" if local_n == remote_n else "MISMATCH"
            print(f"{relation:28s} {local_n:>9,} rows copied -> {remote_n:>9,} in cloud  {status}")
            if local_n != remote_n:
                raise SystemExit("Row counts differ; stopping.")
        with remote.cursor() as cur:
            for statement in INDEXES:
                cur.execute(statement)
            remote.commit()
            remote.autocommit = True
            cur.execute("ANALYZE")
        remote.autocommit = False
        reader_url = make_reader_role(remote, owner_url)
        save_to_env("CLOUD_READER_URL", reader_url)
        print(f"\nRead-only user '{READER_ROLE}' created. Its connection string was saved to .env as "
              "CLOUD_READER_URL (not printed).")
    finally:
        local.close()
        remote.close()


if __name__ == "__main__":
    main()
