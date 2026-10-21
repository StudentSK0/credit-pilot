import json
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from fastapi.testclient import TestClient

import applications
from auth import COOKIE_NAME, token_hash
from database import connection_parameters
from main import app
from seed import seed_demo
from test_applications import VALID, create


def history(client, application_id):
    response = client.get(f"/api/applications/{application_id}/events")
    assert response.status_code == 200, response.text
    return response.json()


def authenticated(login="client-a", password="demo-client-a-local"):
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


def test_history_includes_actor_changes_and_status_transition(client):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    assert client.patch(path, json={"amount": "100000.50"}).status_code == 200
    assert client.post(f"{path}/submit").status_code == 200
    events = history(client, draft["id"])
    actor_id = client.get("/api/me").json()["id"]
    assert draft["owner_id"] == actor_id
    assert draft["created_by"] == actor_id
    assert [event["event_type"] for event in events] == ["DRAFT_CREATED", "DRAFT_UPDATED", "SUBMITTED"]
    assert [event["application_version"] for event in events] == [1, 2, 3]
    assert [(e["previous_status"], e["new_status"]) for e in events] == [(None, "DRAFT"), ("DRAFT", "DRAFT"), ("DRAFT", "SUBMITTED")]
    assert all(e["actor_id"] == actor_id and e["actor_role"] == "CLIENT" for e in events)
    assert all(e["application_id"] == draft["id"] and e["occurred_at"] for e in events)
    assert events[1]["changes"] == {"amount": {"old": "125000.25", "new": "100000.50"}}
    assert client.get(path).json()["version"] == 3
    assert history(client, draft["id"]) == events  # Reads do not manufacture business events.
    page = client.get(f"{path}/events", params={"limit": 1, "after_id": events[0]["id"]}).json()
    assert page == [events[1]]


def test_idempotent_patch_and_repeated_submission_do_not_duplicate_events(client):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    for payload in [{}, {"amount": "125000.25"}, {"company_name": VALID["company_name"]}]:
        assert client.patch(path, json=payload).json() == draft
    assert len(history(client, draft["id"])) == 1
    updated = client.patch(path, json={"term": 18}).json()
    assert client.patch(path, json={"term": 18}).json() == updated
    assert len(history(client, draft["id"])) == 2
    assert client.post(f"{path}/submit").status_code == 200
    submitted = client.get(path).json()
    events = history(client, draft["id"])
    assert client.post(f"{path}/submit").status_code == 409
    assert client.patch(path, json={"term": 24}).status_code == 409
    assert client.get(path).json() == submitted
    assert history(client, draft["id"]) == events


def test_invalid_commands_leave_history_and_application_unchanged(client):
    draft = create(client)
    path = f"/api/applications/{draft['id']}"
    events = history(client, draft["id"])
    assert client.post(f"{path}/submit").status_code == 422
    assert client.patch(path, json={"amount": "1.001"}).status_code == 422
    for field in ["actor_id", "owner_id", "role", "company_id", "created_by", "version", "password", "token"]:
        assert client.patch(path, json={field: "forged"}).status_code == 422
        assert client.post("/api/applications", json={field: "forged"}).status_code == 422
    assert client.get(path).json() == draft
    assert history(client, draft["id"]) == events


@pytest.mark.parametrize("operation", ["create", "update", "submit"])
def test_event_failure_rolls_back_business_change(client, monkeypatch, operation):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    events = history(client, draft["id"])
    with psycopg.connect(**connection_parameters()) as connection:
        count = connection.execute("SELECT count(*) FROM applications").fetchone()[0]

    def fail(*args, **kwargs):
        raise RuntimeError("Simulated journal failure")

    with monkeypatch.context() as patch:
        patch.setattr(applications, "record_event", fail)
        with pytest.raises(RuntimeError, match="Simulated journal failure"):
            if operation == "create":
                client.post("/api/applications", json=VALID)
            elif operation == "update":
                client.patch(path, json={"term": 24})
            else:
                client.post(f"{path}/submit")
    assert client.get(path).json() == draft
    assert history(client, draft["id"]) == events
    with psycopg.connect(**connection_parameters()) as connection:
        assert connection.execute("SELECT count(*) FROM applications").fetchone()[0] == count


def test_new_app_instance_and_new_connection_preserve_history(client):
    draft = create(client, VALID)
    before = history(client, draft["id"])
    # Build a new ASGI app rather than reusing the old application's state.
    from fastapi import FastAPI
    from auth import router as auth_router
    restarted = FastAPI()
    restarted.include_router(applications.router)
    restarted.include_router(auth_router)
    with TestClient(restarted) as fresh:
        fresh.cookies.update(client.cookies)
        assert fresh.get(f"/api/applications/{draft['id']}/events").json() == before


def test_concurrent_identical_patches_and_submissions(client):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"

    def command(kind):
        with TestClient(app) as concurrent:
            concurrent.cookies.update(client.cookies)
            concurrent.headers["X-CSRF-Token"] = client.headers["X-CSRF-Token"]
            if kind == "patch":
                return concurrent.patch(path, json={"term": 18}).status_code
            return concurrent.post(f"{path}/submit").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(command, ["patch", "patch"])) == [200, 200]
        assert sorted(pool.map(command, ["submit", "submit"])) == [200, 409]
    assert [e["event_type"] for e in history(client, draft["id"])] == ["DRAFT_CREATED", "DRAFT_UPDATED", "SUBMITTED"]


def test_other_owner_and_bank_permissions(client):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    events = history(client, draft["id"])
    with authenticated("client-b", "demo-client-b-local") as other:
        assert other.get(path).status_code == 404
        assert other.get(f"{path}/events").status_code == 404
        assert other.patch(path, json={"term": 18}).status_code == 404
        assert other.post(f"{path}/submit").status_code == 404
    with authenticated("bank", "demo-bank-local") as bank:
        assert bank.get("/api/me").json()["role"] == "BANK_EMPLOYEE"
        assert bank.get(path).status_code == 200
        assert history(bank, draft["id"]) == events
        assert bank.post("/api/applications", json={}).status_code == 403
        assert bank.patch(path, json={"term": 18}).status_code == 403
        assert bank.post(f"{path}/submit").status_code == 403
    assert client.get(path).json() == draft
    assert history(client, draft["id"]) == events


def test_client_cannot_access_another_owners_application_in_same_company(client):
    with authenticated("client-b", "demo-client-b-local") as other:
        other_draft = create(other, VALID)
        other_id = other.get("/api/me").json()["id"]
        path = f"/api/applications/{other_draft['id']}"
        with psycopg.connect(**connection_parameters()) as connection:
            original_company = connection.execute("SELECT company_id FROM users WHERE id = %s", (other_id,)).fetchone()[0]
            connection.execute("UPDATE users SET company_id = %s WHERE id = %s", (client.get("/api/me").json()["company_id"], other_id))
        try:
            # Session uses the same company as client-a now, but ownership remains distinct.
            draft = create(client, VALID)
            foreign_path = f"/api/applications/{draft['id']}"
            before = history(client, draft["id"])
            assert other.get(foreign_path).status_code == 404
            assert other.get(f"{foreign_path}/events").status_code == 404
            assert other.patch(foreign_path, json={"term": 24}).status_code == 404
            assert other.post(f"{foreign_path}/submit").status_code == 404
            assert other.get(path).status_code == 200
            assert client.get(path).status_code == 404
            assert history(client, draft["id"]) == before
        finally:
            with psycopg.connect(**connection_parameters()) as connection:
                connection.execute("UPDATE users SET company_id = %s WHERE id = %s", (original_company, other_id))


def test_no_credentials_and_forged_identity(database, client):
    draft = create(client)
    with TestClient(app) as anonymous:
        anonymous.headers.update({"X-Actor-Id": "1", "X-Role": "BANK_EMPLOYEE", "Authorization": "Bearer forged"})
        path = f"/api/applications/{draft['id']}"
        assert anonymous.post("/api/applications", json={}).status_code == 401
        assert anonymous.get(path).status_code == 401
        assert anonymous.get(f"{path}/events").status_code == 401
        assert anonymous.patch(path, json={}).status_code == 401
        assert anonymous.post(f"{path}/submit").status_code == 401
        assert anonymous.get("/api/health").status_code == 200
        anonymous.cookies.set(COOKIE_NAME, "forged")
        assert anonymous.get(path).status_code == 401


def test_csrf_and_origin_do_not_modify_history(client):
    draft = create(client)
    path = f"/api/applications/{draft['id']}"
    events = history(client, draft["id"])
    with TestClient(app) as browser:
        browser.cookies.update(client.cookies)
        assert browser.patch(path, json={"term": 12}).status_code == 403
        browser.headers["X-CSRF-Token"] = "forged"
        assert browser.patch(path, json={"term": 12}).status_code == 403
        browser.headers["X-CSRF-Token"] = client.headers["X-CSRF-Token"]
        browser.headers["Origin"] = "https://evil.invalid"
        assert browser.patch(path, json={"term": 12}).status_code == 403
        assert browser.post("/api/auth/login", json={"login": "client-a", "password": "demo-client-a-local"}).status_code == 403
    assert history(client, draft["id"]) == events


def test_login_logout_expiry_and_stored_secrets(database):
    with TestClient(app) as browser:
        assert browser.post("/api/auth/login", json={"login": "client-a", "password": "wrong"}).status_code == 401
        assert browser.post("/api/auth/login", json={"login": "missing", "password": "wrong"}).status_code == 401
        response = browser.post("/api/auth/login", json={"login": "client-a", "password": "demo-client-a-local"})
        assert response.status_code == 200
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=lax" in response.headers["set-cookie"].lower()
        assert response.headers["cache-control"] == "no-store"
        csrf, token = response.json()["csrf_token"], browser.cookies[COOKIE_NAME]
        browser.headers["X-CSRF-Token"] = csrf
        with psycopg.connect(**connection_parameters()) as connection:
            row = connection.execute("SELECT token_hash, csrf_hash FROM sessions WHERE token_hash = %s", (token_hash(token),)).fetchone()
            assert row == (token_hash(token), token_hash(csrf))
            assert token not in row and csrf not in row
            encoded = connection.execute("SELECT password_hash FROM users WHERE login = 'client-a'").fetchone()[0]
            assert "demo-client-a-local" not in encoded
        assert browser.post("/api/auth/logout").status_code == 204
        browser.cookies.set(COOKIE_NAME, token)
        assert browser.get("/api/me").status_code == 401
        browser.cookies.clear()
        response = browser.post("/api/auth/login", json={"login": "client-a", "password": "demo-client-a-local"})
        assert response.status_code == 200
        with psycopg.connect(**connection_parameters()) as connection:
            connection.execute("UPDATE sessions SET expires_at = clock_timestamp() - interval '1 second' WHERE token_hash = %s", (token_hash(browser.cookies[COOKIE_NAME]),))
        assert browser.get("/api/me").status_code == 401


def test_journal_contains_no_session_or_request_secrets(client):
    draft = create(client, VALID)
    client.headers["Authorization"] = "Bearer never-record-this"
    client.headers["X-Debug-Password"] = "also-secret"
    path = f"/api/applications/{draft['id']}"
    assert client.patch(path, json={"term": 18}).status_code == 200
    assert client.post(f"{path}/submit").status_code == 200
    with psycopg.connect(**connection_parameters()) as connection:
        rows = connection.execute("SELECT row_to_json(e) FROM application_events e WHERE application_id = %s", (draft["id"],)).fetchall()
    stored = json.dumps(rows)
    for secret in [client.cookies[COOKIE_NAME], client.headers["X-CSRF-Token"], "never-record-this", "also-secret", "demo-client-a-local"]:
        assert secret not in stored


def test_seed_is_idempotent_and_preserves_unassigned_applications(client):
    with psycopg.connect(**connection_parameters()) as connection:
        legacy_id = connection.execute("INSERT INTO applications (company_name) VALUES ('Legacy draft') RETURNING id").fetchone()[0]
        before = connection.execute("SELECT login, password_hash, company_id FROM users ORDER BY id").fetchall()
        seed_demo(connection)
        assert connection.execute("SELECT login, password_hash, company_id FROM users ORDER BY id").fetchall() == before
    assert client.get(f"/api/applications/{legacy_id}").status_code == 404
    with authenticated("bank", "demo-bank-local") as bank:
        assert bank.get(f"/api/applications/{legacy_id}").json()["owner_id"] is None
        assert history(bank, legacy_id) == []


def test_history_missing_id(client):
    assert client.get("/api/applications/0/events").status_code == 404
    assert client.get(f"/api/applications/{2**63}/events").status_code == 404
