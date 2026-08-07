"""
Migration -- creates all tables that don't exist yet and adds/removes
columns on `jobs` that don't match the current model (SQLite doesn't
support altering a table's shape via create_all() alone).

Also drops the legacy `profiles` and `resumes` tables: this app no
longer has profile/resume features (single fixed internal user, no
resume matching) -- see requirements. Safe to run multiple times.

Run with:
    python -m app.migrate
"""
import app.env  # noqa: F401  (loads .env as an import side effect)
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.models import Job  # noqa: F401  (import registers the model with Base)
from app.monitoring.models import CollectorRun  # noqa: F401

# (column_name, SQL type, default_sql) for columns `jobs` should have.
JOBS_ADD_COLUMNS = [
    ("telegram_notified", "INTEGER", "0"),
]
# Columns that used to exist (resume matching, now removed) and should
# be dropped if present.
JOBS_DROP_COLUMNS = ["resume_match_percent"]

LEGACY_TABLES_TO_DROP = ["resumes", "profiles"]


def _migrate_jobs_columns():
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return  # fresh DB -- create_all() below creates it with the right columns already
    existing = {col["name"] for col in inspector.get_columns("jobs")}
    with engine.begin() as conn:
        for name, sql_type, default_sql in JOBS_ADD_COLUMNS:
            if name in existing:
                continue
            ddl = f"ALTER TABLE jobs ADD COLUMN {name} {sql_type}"
            if default_sql is not None:
                ddl += f" DEFAULT {default_sql}"
            conn.execute(text(ddl))
            print(f"Added missing column jobs.{name}")
        for name in JOBS_DROP_COLUMNS:
            if name not in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE jobs DROP COLUMN {name}"))
                print(f"Dropped column jobs.{name}")
            except Exception as exc:
                # Older SQLite (<3.35) doesn't support DROP COLUMN -- leave
                # the unused column in place rather than fail the migration.
                print(f"Could not drop jobs.{name} (leaving it unused): {exc}")


def _drop_legacy_profile_tables():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in LEGACY_TABLES_TO_DROP:
            if table in existing_tables:
                conn.execute(text(f"DROP TABLE {table}"))
                print(f"Dropped legacy table {table}")


def run_migration():
    Base.metadata.create_all(bind=engine)
    _migrate_jobs_columns()
    _drop_legacy_profile_tables()
    print("Tables created (or already existed).")


if __name__ == "__main__":
    run_migration()
