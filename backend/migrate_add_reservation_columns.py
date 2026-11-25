r"""
One-time migration: adds the unit-reservation columns to the existing `properties` table.
create_all() does NOT add columns to tables that already exist, so run this once:

    .\backend\venv\Scripts\python.exe -m backend.migrate_add_reservation_columns

Put this file in backend/ (next to app/). Safe to run more than once.
BACK UP the database file first.
"""
from sqlalchemy import inspect, text

from backend.app.core.database import engine


def main():
    insp = inspect(engine)
    existing = {c["name"] for c in insp.get_columns("properties")}
    statements = []
    if "reserved_for_lead_id" not in existing:
        statements.append("ALTER TABLE properties ADD COLUMN reserved_for_lead_id INTEGER")
    if "reserved_at" not in existing:
        statements.append("ALTER TABLE properties ADD COLUMN reserved_at TIMESTAMP")

    if not statements:
        print("Nothing to do: columns already exist.")
        return

    with engine.begin() as conn:
        for stmt in statements:
            print("Running:", stmt)
            conn.execute(text(stmt))
        # Units that are already RESERVED/SOLD but not linked to any lead stay as they are.
    print("Done.")


if __name__ == "__main__":
    main()