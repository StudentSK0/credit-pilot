from pathlib import Path
from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql

from database import connection_parameters


def test_upgrade_preserves_existing_draft_without_fabricated_history(monkeypatch):
    name = f"credit_pilot_migration_{uuid4().hex}"
    with psycopg.connect(**connection_parameters(), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with monkeypatch.context() as patch:
                patch.setenv("POSTGRES_DB", name)
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                command.upgrade(config, "0001_applications")
                with psycopg.connect(**connection_parameters()) as connection:
                    before = connection.execute(
                        "INSERT INTO applications (company_name, amount) VALUES ('Old draft', 123.45) "
                        "RETURNING id, company_name, amount, status, created_at, updated_at"
                    ).fetchone()
                command.upgrade(config, "head")
                command.upgrade(config, "head")  # Safe migration rerun at startup.
                with psycopg.connect(**connection_parameters()) as connection:
                    assert connection.execute(
                        "SELECT id, company_name, amount, status, created_at, updated_at FROM applications WHERE id = %s",
                        (before[0],),
                    ).fetchone() == before
                    assert connection.execute("SELECT company_id, created_by, owner_id, version FROM applications WHERE id = %s", (before[0],)).fetchone() == (None, None, None, 1)
                    assert connection.execute("SELECT count(*) FROM application_events").fetchone()[0] == 0
                # Rollback is exercised only on this disposable database.
                command.downgrade(config, "0001_applications")
                with psycopg.connect(**connection_parameters()) as connection:
                    assert connection.execute("SELECT id, company_name, amount, status, created_at, updated_at FROM applications").fetchone() == before
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def test_owner_migration_preserves_events_sessions_and_recorded_authors(monkeypatch):
    name = f"credit_pilot_owner_migration_{uuid4().hex}"
    with psycopg.connect(**connection_parameters(), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with monkeypatch.context() as patch:
                patch.setenv("POSTGRES_DB", name)
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                command.upgrade(config, "0002_application_events")
                with psycopg.connect(**connection_parameters()) as connection:
                    company = connection.execute("INSERT INTO companies (name, inn) VALUES ('Synthetic company', '1234567890') RETURNING id").fetchone()[0]
                    owner = connection.execute("INSERT INTO users (login, password_hash, role, company_id) VALUES ('owner', 'unused', 'CLIENT', %s) RETURNING id", (company,)).fetchone()[0]
                    employee = connection.execute("INSERT INTO users (login, password_hash, role) VALUES ('employee', 'unused', 'BANK') RETURNING id").fetchone()[0]
                    application_id = connection.execute("INSERT INTO applications (company_name, company_id, created_by) VALUES ('Owned draft', %s, %s) RETURNING id", (company, owner)).fetchone()[0]
                    unassigned_id = connection.execute("INSERT INTO applications (company_name, company_id) VALUES ('Unassigned draft', %s) RETURNING id", (company,)).fetchone()[0]
                    connection.execute(
                        "INSERT INTO application_events (application_id, event_type, actor_id, actor_role, new_status, application_version, changes) "
                        "VALUES (%s, 'DRAFT_CREATED', %s, 'CLIENT', 'DRAFT', 1, '{}')", (application_id, owner),
                    )
                    connection.execute("INSERT INTO sessions (token_hash, csrf_hash, user_id, expires_at) VALUES (%s, %s, %s, clock_timestamp() + interval '1 hour')", ('a' * 64, 'b' * 64, employee))
                    event_before = connection.execute("SELECT * FROM application_events").fetchone()
                    session_before = connection.execute("SELECT * FROM sessions").fetchone()
                command.upgrade(config, "head")
                with psycopg.connect(**connection_parameters()) as connection:
                    assert connection.execute("SELECT owner_id FROM applications WHERE id = %s", (application_id,)).fetchone()[0] == owner
                    assert connection.execute("SELECT owner_id FROM applications WHERE id = %s", (unassigned_id,)).fetchone()[0] is None
                    assert connection.execute("SELECT role FROM users WHERE id = %s", (employee,)).fetchone()[0] == 'BANK_EMPLOYEE'
                    assert connection.execute("SELECT * FROM application_events").fetchone() == event_before
                    assert connection.execute("SELECT * FROM sessions").fetchone() == session_before
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
