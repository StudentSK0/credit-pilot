from pathlib import Path
from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from fastapi.testclient import TestClient

from database import connection_parameters
from main import app
from seed import seed_demo


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


def test_t05_upgrade_preserves_legacy_drafts_submissions_history_and_sessions(monkeypatch):
    name = f"credit_pilot_t05_migration_{uuid4().hex}"
    with psycopg.connect(**connection_parameters(), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            with monkeypatch.context() as patch:
                patch.setenv("POSTGRES_DB", name)
                patch.setenv("DEMO_CLIENT_PASSWORD", "demo-client-a-local")
                patch.setenv("DEMO_BANK_PASSWORD", "demo-bank-local")
                patch.setenv("COOKIE_SECURE", "false")
                patch.setenv("ALLOWED_ORIGINS", "http://testserver")
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                command.upgrade(config, "0003_application_owner")
                with psycopg.connect(**connection_parameters()) as connection:
                    seed_demo(connection)
                    owner, company = connection.execute("SELECT id, company_id FROM users WHERE login = 'client-a'").fetchone()
                    ids = []
                    for status, version in [("DRAFT", 1), ("SUBMITTED", 2)]:
                        application_id = connection.execute(
                            "INSERT INTO applications (company_name, inn, credit_purpose, amount, term, "
                            "status, version, owner_id, created_by, company_id) "
                            "VALUES ('Legacy synthetic company', '1234567890', 'Working capital', 100000.25, 12, %s, %s, %s, %s, %s) RETURNING id",
                            (status, version, owner, owner, company),
                        ).fetchone()[0]
                        ids.append(application_id)
                        connection.execute(
                            "INSERT INTO application_events (application_id, event_type, actor_id, actor_role, new_status, application_version, changes) "
                            "VALUES (%s, 'DRAFT_CREATED', %s, 'CLIENT', 'DRAFT', 1, '{}')", (application_id, owner),
                        )
                        if status == "SUBMITTED":
                            connection.execute(
                                "INSERT INTO application_events (application_id, event_type, actor_id, actor_role, previous_status, new_status, application_version, changes) "
                                "VALUES (%s, 'SUBMITTED', %s, 'CLIENT', 'DRAFT', 'SUBMITTED', 2, '{}')", (application_id, owner),
                            )
                    before = connection.execute("SELECT row_to_json(a) FROM applications a ORDER BY id").fetchall()
                    events = connection.execute("SELECT * FROM application_events ORDER BY id").fetchall()
                with TestClient(app) as client, TestClient(app) as bank:
                    login = client.post("/api/auth/login", json={"login": "client-a", "password": "demo-client-a-local"})
                    assert login.status_code == 200
                    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
                    bank_login = bank.post("/api/auth/login", json={"login": "bank", "password": "demo-bank-local"})
                    assert bank_login.status_code == 200
                    bank.headers["X-CSRF-Token"] = bank_login.json()["csrf_token"]
                    with psycopg.connect(**connection_parameters()) as connection:
                        sessions = connection.execute("SELECT * FROM sessions ORDER BY token_hash").fetchall()
                    command.upgrade(config, "head")
                    command.upgrade(config, "head")
                    new_fields = {"product_code", "product_version", "monthly_revenue", "monthly_operating_expenses", "existing_monthly_debt_payments"}
                    with psycopg.connect(**connection_parameters()) as connection:
                        after = connection.execute("SELECT row_to_json(a) FROM applications a ORDER BY id").fetchall()
                        for (old,), (new,) in zip(before, after, strict=True):
                            assert all(new[field] is None for field in new_fields)
                            assert {key: value for key, value in new.items() if key not in new_fields} == old
                        assert connection.execute("SELECT * FROM application_events ORDER BY id").fetchall() == events
                        assert connection.execute("SELECT * FROM sessions ORDER BY token_hash").fetchall() == sessions
                        assert connection.execute("SELECT count(*) FROM credit_products").fetchone()[0] == 2
                    for application_id in ids:
                        path = f"/api/applications/{application_id}"
                        own = client.get(path)
                        assert own.status_code == 200
                        assert all(own.json()[field] is None for field in new_fields)
                        assert bank.get(path).json() == own.json()
                        assert bank.patch(path, json={"product_code": "WORKING_CAPITAL"}).status_code == 403
                    draft_path = f"/api/applications/{ids[0]}"
                    before_draft = client.get(draft_path).json()
                    errors = client.post(f"{draft_path}/submit")
                    assert errors.status_code == 422
                    assert {e["loc"][-1] for e in errors.json()["detail"]} == new_fields - {"product_version"}
                    assert client.get(draft_path).json() == before_draft
                    submitted_path = f"/api/applications/{ids[1]}"
                    old_submitted = client.get(submitted_path).json()
                    assert client.patch(submitted_path, json={"product_code": "WORKING_CAPITAL"}).status_code == 409
                    assert client.post(f"{submitted_path}/submit").status_code == 409
                    assert client.get(submitted_path).json() == old_submitted
                    assert client.patch(draft_path, json={
                        "product_code": "WORKING_CAPITAL", "monthly_revenue": "200000",
                        "monthly_operating_expenses": "100000", "existing_monthly_debt_payments": "0",
                    }).status_code == 200
                    submitted = client.post(f"{draft_path}/submit")
                    assert submitted.status_code == 200
                    assert submitted.json()["product_version"] == "product_v1"
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
