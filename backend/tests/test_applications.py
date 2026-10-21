from decimal import Decimal

import psycopg
import pytest

from database import connection_parameters

VALID = {
    "company_name": "Example business",
    "inn": "1234567890",
    "credit_purpose": "Purchase equipment",
    "amount": "125000.25",
    "term": 12,
}


def create(client, fields=None):
    response = client.post("/api/applications", json={} if fields is None else fields)
    assert response.status_code == 201, response.text
    return response.json()


def test_incomplete_draft_is_persisted(client):
    draft = create(client)
    assert draft["status"] == "DRAFT"
    assert isinstance(draft["id"], int)
    assert all(draft[field] is None for field in VALID)
    assert draft["created_at"] == draft["updated_at"]
    assert client.get(f"/api/applications/{draft['id']}").json() == draft
    with psycopg.connect(**connection_parameters()) as connection:
        assert connection.execute("SELECT status FROM applications WHERE id = %s", (draft["id"],)).fetchone() == ("DRAFT",)


def test_empty_fields_are_allowed_in_draft(client):
    draft = create(client, {field: "" for field in VALID})
    assert draft["company_name"] == ""
    assert draft["inn"] == ""
    assert draft["credit_purpose"] == ""
    assert draft["amount"] is None
    assert draft["term"] is None


def test_partial_update_and_explicit_clear(client):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    response = client.patch(path, json={"credit_purpose": "Working capital"})
    assert response.status_code == 200
    updated = response.json()
    for field in VALID.keys() - {"credit_purpose"}:
        assert updated[field] == draft[field]
    assert updated["credit_purpose"] == "Working capital"
    assert updated["created_at"] == draft["created_at"]
    assert updated["updated_at"] > draft["updated_at"]
    assert client.patch(path, json={}).json() == updated
    cleared = client.patch(path, json={"amount": None}).json()
    assert cleared["amount"] is None
    assert cleared["company_name"] == draft["company_name"]


@pytest.mark.parametrize("fields", [
    {},
    {**VALID, "company_name": " \t\n"},
    {**VALID, "credit_purpose": " \t\n"},
    *({**VALID, "inn": inn} for inn in ["", "123456789", "12345678901", "１２３４５６７８９０", "1234567890\n", "abcdefghij"]),
    {**VALID, "amount": "0"},
    {**VALID, "amount": "-1.25"},
    {**VALID, "term": 0},
    {**VALID, "term": -1},
])
def test_failed_submission_leaves_draft_unchanged(client, fields):
    draft = create(client, fields)
    path = f"/api/applications/{draft['id']}"
    assert client.post(f"{path}/submit").status_code == 422
    assert client.get(path).json() == draft


@pytest.mark.parametrize("inn", ["1234567890", "123456789012"])
def test_successful_submission_and_blocked_changes(client, inn):
    draft = create(client, {**VALID, "inn": inn})
    path = f"/api/applications/{draft['id']}"
    response = client.post(f"{path}/submit")
    assert response.status_code == 200
    submitted = response.json()
    assert submitted["status"] == "SUBMITTED"
    assert submitted["created_at"] == draft["created_at"]
    assert submitted["updated_at"] > draft["updated_at"]
    for field in VALID:
        assert submitted[field] == draft[field]
    assert client.patch(path, json={"amount": "1"}).status_code == 409
    assert client.patch(path, json={}).status_code == 409
    assert client.post(f"{path}/submit").status_code == 409
    assert client.get(path).json() == submitted


@pytest.mark.parametrize("amount", ["1.001", "1.230", "NaN", "Infinity", "-Infinity"])
def test_invalid_amount_is_never_rounded_or_persisted(client, amount):
    assert client.post("/api/applications", json={"amount": amount}).status_code == 422
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    assert client.patch(path, json={"amount": amount}).status_code == 422
    assert client.get(path).json() == draft


def test_decimal_json_number_is_preserved_exactly(client):
    response = client.post(
        "/api/applications",
        content='{"amount": 12345678901234567890.12}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["amount"] == "12345678901234567890.12"
    with psycopg.connect(**connection_parameters()) as connection:
        assert connection.execute("SELECT amount FROM applications WHERE id = %s", (draft["id"],)).fetchone()[0] == Decimal(draft["amount"])
    assert client.post("/api/applications", content='{"amount": 1.00000000000000001}', headers={"Content-Type": "application/json"}).status_code == 422


@pytest.mark.parametrize("field,value", [("id", 42), ("status", "SUBMITTED"), ("created_at", "2026-01-01T00:00:00Z"), ("updated_at", "2026-01-01T00:00:00Z")])
def test_server_fields_cannot_be_assigned(client, field, value):
    assert client.post("/api/applications", json={field: value}).status_code == 422
    draft = create(client)
    path = f"/api/applications/{draft['id']}"
    assert client.patch(path, json={field: value}).status_code == 422
    assert client.get(path).json() == draft


@pytest.mark.parametrize("fields", [{"company_name": "a" * 256}, {"credit_purpose": "a" * 1001}, {"term": 1.5}, {"term": True}, {"term": 2**63}])
def test_field_constraints(client, fields):
    assert client.post("/api/applications", json=fields).status_code == 422


@pytest.mark.parametrize("application_id", [0, 2**63])
def test_missing_application(client, application_id):
    path = f"/api/applications/{application_id}"
    assert client.get(path).status_code == 404
    assert client.patch(path, json={"company_name": "Missing"}).status_code == 404
    assert client.post(f"{path}/submit").status_code == 404


def test_health(client, monkeypatch):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    monkeypatch.setenv("POSTGRES_PORT", "1")
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
