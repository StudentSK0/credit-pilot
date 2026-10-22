from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient

from database import connection_parameters
from main import app
from test_applications import LEGACY_VALID, VALID, create
from test_events import authenticated, history

FINANCIAL_FIELDS = (
    "monthly_revenue",
    "monthly_operating_expenses",
    "existing_monthly_debt_payments",
)
BOUNDS = [
    ("WORKING_CAPITAL", "50000", "3000000", 3, 24),
    ("EQUIPMENT", "100000", "5000000", 6, 36),
]


def unchanged_after_submit_error(client, draft, fields):
    path = f"/api/applications/{draft['id']}"
    before = history(client, draft["id"])
    response = client.post(f"{path}/submit")
    assert response.status_code == 422, response.text
    assert set(fields) <= {item["loc"][-1] for item in response.json()["detail"]}
    assert client.get(path).json() == draft
    assert history(client, draft["id"]) == before


def test_catalogue_conditions_access_and_decimal_serialization(client):
    expected = [
        {"code": "EQUIPMENT", "version": "product_v1", "name": "Приобретение оборудования", "currency": "RUB",
         "min_amount": "100000", "max_amount": "5000000", "min_term": 6, "max_term": 36, "annual_rate": "0.18"},
        {"code": "WORKING_CAPITAL", "version": "product_v1", "name": "Пополнение оборотных средств", "currency": "RUB",
         "min_amount": "50000", "max_amount": "3000000", "min_term": 3, "max_term": 24, "annual_rate": "0.20"},
    ]
    assert client.get("/api/products").json() == expected
    with authenticated("bank", "demo-bank-local") as bank:
        assert bank.get("/api/products").json() == expected
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/products").status_code == 401
    assert client.post("/api/products", json={}).status_code == 405


def test_old_five_field_draft_now_requires_product_and_finances(client):
    draft = create(client, LEGACY_VALID)
    for field in ("product_code", "product_version", *FINANCIAL_FIELDS):
        assert draft[field] is None
    unchanged_after_submit_error(client, draft, ("product_code", *FINANCIAL_FIELDS))
    path = f"/api/applications/{draft['id']}"
    assert client.patch(path, json={key: VALID[key] for key in ("product_code", *FINANCIAL_FIELDS)}).status_code == 200
    assert client.post(f"{path}/submit").status_code == 200


@pytest.mark.parametrize("code,minimum,maximum,min_term,max_term", BOUNDS)
@pytest.mark.parametrize("upper_amount,upper_term", [(False, False), (False, True), (True, False), (True, True)])
def test_product_inclusive_boundaries(client, code, minimum, maximum, min_term, max_term, upper_amount, upper_term):
    draft = create(client, {**VALID, "product_code": code, "amount": maximum if upper_amount else minimum,
                            "term": max_term if upper_term else min_term})
    response = client.post(f"/api/applications/{draft['id']}/submit")
    assert response.status_code == 200, response.text
    assert response.json()["product_version"] == "product_v1"


@pytest.mark.parametrize("code,minimum,maximum,min_term,max_term", BOUNDS)
@pytest.mark.parametrize("field,upper", [("amount", False), ("amount", True), ("term", False), ("term", True)])
def test_product_outside_boundaries_is_rejected_without_mutation(client, code, minimum, maximum, min_term, max_term, field, upper):
    if field == "amount":
        value = str(Decimal(maximum) + Decimal("0.01") if upper else Decimal(minimum) - Decimal("0.01"))
    else:
        value = max_term + 1 if upper else min_term - 1
    draft = create(client, {**VALID, "product_code": code, field: value})
    unchanged_after_submit_error(client, draft, [field])


@pytest.mark.parametrize("code", [None, "", " \t", "UNKNOWN", "equipment"])
def test_missing_or_unknown_product_cannot_be_submitted(client, code):
    draft = create(client, {**VALID, "product_code": code})
    unchanged_after_submit_error(client, draft, ["product_code"])


def test_product_code_and_version_are_constrained(client):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    before = history(client, draft["id"])
    for payload in [{"product_code": "x" * 65}, {"product_code": True}, {"product_version": "product_v1"}]:
        assert client.post("/api/applications", json=payload).status_code == 422
        assert client.patch(path, json=payload).status_code == 422
    assert client.get(path).json() == draft
    assert history(client, draft["id"]) == before


@pytest.mark.parametrize("field", FINANCIAL_FIELDS)
@pytest.mark.parametrize("value", [None, "", " \t", "-0.01"])
def test_missing_or_negative_finances_are_rejected_at_submit(client, field, value):
    draft = create(client, {**VALID, field: value})
    unchanged_after_submit_error(client, draft, [field])


def test_revenue_must_be_positive_but_zero_expenses_and_negative_balance_are_valid(client):
    zero = create(client, {**VALID, "monthly_revenue": "0"})
    unchanged_after_submit_error(client, zero, ["monthly_revenue"])
    for revenue, expenses, debt in [("0.01", "0", "0"), ("1", "200000", "10000")]:
        draft = create(client, {**VALID, "monthly_revenue": revenue, "monthly_operating_expenses": expenses,
                                "existing_monthly_debt_payments": debt})
        assert client.post(f"/api/applications/{draft['id']}/submit").status_code == 200


@pytest.mark.parametrize("field", FINANCIAL_FIELDS)
@pytest.mark.parametrize("value", ["1.001", "1.230", "NaN", "Infinity", "-Infinity", True])
def test_invalid_financial_precision_and_types_are_never_persisted(client, field, value):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    before = history(client, draft["id"])
    assert client.post("/api/applications", json={field: value}).status_code == 422
    assert client.patch(path, json={field: value}).status_code == 422
    assert client.get(path).json() == draft
    assert history(client, draft["id"]) == before


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_numbers_return_validation_errors(client, value):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    before = history(client, draft["id"])
    for field in ("amount", *FINANCIAL_FIELDS):
        body = '{"' + field + '": ' + value + '}'
        assert client.post("/api/applications", content=body, headers={"Content-Type": "application/json"}).status_code == 422
        assert client.patch(path, content=body, headers={"Content-Type": "application/json"}).status_code == 422
    assert client.get(path).json() == draft
    assert history(client, draft["id"]) == before


@pytest.mark.parametrize("field", FINANCIAL_FIELDS)
def test_financial_json_numbers_preserve_precision_in_database_and_history(client, field):
    response = client.post("/api/applications", content='{"' + field + '": 12345678901234567890.12}',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft[field] == "12345678901234567890.12"
    assert history(client, draft["id"])[0]["changes"][field] == {"old": None, "new": draft[field]}
    with psycopg.connect(**connection_parameters()) as connection:
        row = connection.execute(
            "SELECT monthly_revenue, monthly_operating_expenses, existing_monthly_debt_payments FROM applications WHERE id = %s",
            (draft["id"],),
        ).fetchone()
        assert row[FINANCIAL_FIELDS.index(field)] == Decimal(draft[field])
    assert client.patch(f"/api/applications/{draft['id']}", content='{"' + field + '": 1.00000000000000001}',
                        headers={"Content-Type": "application/json"}).status_code == 422


def test_new_fields_can_be_saved_cleared_and_journaled_atomically(client):
    draft = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    created = history(client, draft["id"])[0]
    for field in ("product_code", *FINANCIAL_FIELDS):
        assert created["changes"][field] == {"old": None, "new": draft[field]}
    cleared = client.patch(path, json={field: None for field in ("product_code", *FINANCIAL_FIELDS)}).json()
    assert cleared["product_version"] is None
    for field in ("product_code", *FINANCIAL_FIELDS):
        assert cleared[field] is None
        assert history(client, draft["id"])[1]["changes"][field] == {"old": draft[field], "new": None}
    payload = {"product_code": "WORKING_CAPITAL", "monthly_revenue": "0.01", "monthly_operating_expenses": "0",
               "existing_monthly_debt_payments": "0.00"}
    updated = client.patch(path, json=payload).json()
    assert client.patch(path, json=payload).json() == updated
    assert len(history(client, draft["id"])) == 3
    submitted = client.post(f"{path}/submit").json()
    assert submitted["product_version"] == "product_v1"
    assert history(client, draft["id"])[-1]["changes"] == {"product_version": {"old": None, "new": "product_v1"}}
    assert client.patch(path, json={"product_code": "EQUIPMENT", "monthly_revenue": "999"}).status_code == 409
    assert client.get(path).json() == submitted


def test_financial_update_is_rolled_back_if_history_fails(client, monkeypatch):
    import applications

    draft = create(client, VALID)
    before = history(client, draft["id"])

    def fail(*args, **kwargs):
        raise RuntimeError("Simulated journal failure")

    with monkeypatch.context() as patch:
        patch.setattr(applications, "record_event", fail)
        with pytest.raises(RuntimeError, match="Simulated journal failure"):
            client.patch(f"/api/applications/{draft['id']}", json={"monthly_revenue": "0.01", "product_code": "WORKING_CAPITAL"})
    assert client.get(f"/api/applications/{draft['id']}").json() == draft
    assert history(client, draft["id"]) == before


def test_retired_product_rejected_and_version_frozen_at_submission(client):
    draft = create(client, VALID)
    second = create(client, VALID)
    path = f"/api/applications/{draft['id']}"
    first = client.post(f"{path}/submit").json()
    first_history = history(client, draft["id"])
    with psycopg.connect(**connection_parameters()) as connection:
        connection.execute("UPDATE credit_products SET is_active = false WHERE code = 'EQUIPMENT'")
    try:
        assert [p["code"] for p in client.get("/api/products").json()] == ["WORKING_CAPITAL"]
        unchanged_after_submit_error(client, second, ["product_code"])
        with psycopg.connect(**connection_parameters()) as connection:
            connection.execute(
                "INSERT INTO credit_products (code, version, name, currency, min_amount, max_amount, min_term, max_term, annual_rate) "
                "SELECT code, 'product_v2_test', name, currency, min_amount, 2000000, min_term, max_term, 0.22 "
                "FROM credit_products WHERE code = 'EQUIPMENT' AND version = 'product_v1'"
            )
        products = client.get("/api/products").json()
        assert products[0]["version"] == "product_v2_test"
        assert products[0]["annual_rate"] == "0.22"
        submitted = client.post(f"/api/applications/{second['id']}/submit").json()
        assert submitted["product_version"] == "product_v2_test"
        assert client.get(path).json() == first
        assert history(client, draft["id"]) == first_history
    finally:
        with psycopg.connect(**connection_parameters()) as connection:
            connection.execute("UPDATE credit_products SET is_active = false WHERE code = 'EQUIPMENT'")
            connection.execute("UPDATE credit_products SET is_active = true WHERE code = 'EQUIPMENT' AND version = 'product_v1'")


def test_database_protects_published_product_terms_and_single_active_version(database):
    with psycopg.connect(**connection_parameters()) as connection:
        for statement in [
            "UPDATE credit_products SET annual_rate = 0.01 WHERE code = 'WORKING_CAPITAL'",
            "UPDATE credit_products SET name = 'Changed' WHERE code = 'WORKING_CAPITAL'",
            "DELETE FROM credit_products WHERE code = 'WORKING_CAPITAL'",
        ]:
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            connection.execute(
                "INSERT INTO credit_products (code, version, name, currency, min_amount, max_amount, min_term, max_term, annual_rate) "
                "SELECT code, 'duplicate_active', name, currency, min_amount, max_amount, min_term, max_term, annual_rate "
                "FROM credit_products WHERE code = 'WORKING_CAPITAL' AND version = 'product_v1'"
            )


def test_database_requires_real_product_version_and_only_freezes_after_draft(database):
    with psycopg.connect(**connection_parameters()) as connection:
        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute(
                "INSERT INTO applications (status, product_code, product_version) VALUES ('SUBMITTED', 'EQUIPMENT', 'missing_version')"
            )
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "INSERT INTO applications (product_code, product_version) VALUES ('EQUIPMENT', 'product_v1')"
            )


@pytest.mark.parametrize("field", FINANCIAL_FIELDS)
@pytest.mark.parametrize("value", ["0.001", "1.230", "NaN", "Infinity", "-Infinity"])
def test_database_rejects_financial_rounding_and_nonfinite_values(database, field, value):
    with psycopg.connect(**connection_parameters()) as connection:
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                psycopg.sql.SQL("INSERT INTO applications ({}) VALUES (%s)").format(psycopg.sql.Identifier(field)),
                (Decimal(value),),
            )
