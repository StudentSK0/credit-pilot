from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from database import connection_parameters
from demo import SCENARIOS, scenario_fields, seed_scenarios
from main import app
from scoring import assess, payment


@pytest.fixture
def bank(database):
    with TestClient(app) as session:
        response = session.post(
            "/api/auth/login", json={"login": "bank", "password": "demo-bank-local"}
        )
        session.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield session


def create(client, code="growth", **overrides):
    fields = scenario_fields(next(s for s in SCENARIOS if s["code"] == code))
    response = client.post("/api/applications", json={**fields, **overrides})
    assert response.status_code == 201, response.text
    application = response.json()
    response = client.post(f"/api/applications/{application['id']}/submit")
    assert response.status_code == 200, response.text
    return response.json()


def command(session, application, action, **values):
    body = dict(
        expected_version=application["version"], command_id=str(uuid4()), **values
    )
    response = session.post(
        f"/api/applications/{application['id']}/{action}", json=body
    )
    assert response.status_code == 200, response.text
    return response.json(), body


def dossier(session, application):
    response = session.get(f"/api/applications/{application['id']}/dossier")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("code", ["growth", "clarification", "risk", "counter"])
def test_four_end_to_end_scenarios(client, bank, code):
    application = create(client, code)
    application, _ = command(bank, application, "checks")
    first = dossier(bank, application)
    assert first["runs"][0]["assessment"]["ml"]["model_version"] == "synthetic_logit_v1"
    if code == "clarification":
        old = first["runs"][0]["input_snapshot"]
        application, _ = command(
            bank,
            application,
            "information-requests",
            message="Уточните регулярные расходы без разовой покупки",
            fields=["monthly_operating_expenses"],
            document_kind="FINANCIAL_REPORT",
        )
        request = dossier(client, application)["information_requests"][0]
        application, _ = command(
            client,
            application,
            f"information-requests/{request['id']}/reply",
            explanation="Разовая покупка исключена из регулярных расходов",
            fields={"monthly_operating_expenses": "400000.00"},
            documents=[
                {
                    "name": "report.txt",
                    "content": "СИНТЕТИЧЕСКИЙ ОТЧЁТ\nРегулярные расходы: 400000.00 RUB",
                }
            ],
        )
        application, _ = command(bank, application, "checks")
        updated = dossier(bank, application)
        assert updated["runs"][1]["input_snapshot"] == old
        assert (
            updated["runs"][0]["input_snapshot"]["monthly_operating_expenses"]
            == "400000.00"
        )
        document = updated["documents"][0]
        response = bank.get(
            f"/api/applications/{application['id']}/documents/{document['id']}"
        )
        assert response.status_code == 200 and "400000.00" in response.text
        assert "attachment" in response.headers["content-disposition"]
    if code == "risk":
        application, _ = command(
            bank,
            application,
            "decisions",
            kind="REJECT",
            reason_code="CREDIT_HISTORY",
            explanation="Просрочка 65 дней и высокая долговая нагрузка",
        )
        assert application["status"] == "REJECTED"
    else:
        amount = application["amount"]
        if code == "counter":
            assessment = dossier(bank, application)["runs"][0]["assessment"]
            assert not assessment["eligible"]
            amount = assessment["alternative"]["amount"]
            assert Decimal(amount) < Decimal(application["amount"])
        application, _ = command(
            bank,
            application,
            "decisions",
            kind="OFFER",
            reason_code="COUNTER_OFFER" if code == "counter" else "STANDARD",
            explanation="Денежный остаток позволяет обслуживать предложенную сумму",
            offered_amount=amount,
        )
        detail = dossier(client, application)
        assert "не имеет юридической силы" in detail["contract_preview"]
        application, sign_body = command(
            client,
            application,
            "sign",
            decision_id=detail["decision"]["id"],
            confirmed=True,
        )
        assert application["status"] == "SIGNED"
        repeat = client.post(
            f"/api/applications/{application['id']}/sign", json=sign_body
        )
        assert repeat.status_code == 200 and repeat.json() == application
        application, payload = command(bank, application, "disburse")
        assert application["status"] == "DISBURSED"
        repeat = bank.post(
            f"/api/applications/{application['id']}/disburse", json=payload
        )
        assert repeat.json() == application
        assert dossier(client, application)["disbursement"]["amount"] == amount
    events = client.get(f"/api/applications/{application['id']}/events").json()
    versions = [e["application_version"] for e in events]
    assert versions == list(range(1, application["version"] + 1))
    assert all(e["actor_role"] in {"CLIENT", "BANK_EMPLOYEE"} for e in events)


def test_unknown_sources_do_not_get_good_score_or_risk_rejection(client, bank):
    application = create(client, inn="9999999999")
    application, _ = command(bank, application, "checks")
    detail = dossier(bank, application)
    assert detail["runs"][0]["state"] == "INCOMPLETE"
    assert detail["runs"][0]["assessment"] is None
    for kind, reason in [("OFFER", "STANDARD"), ("REJECT", "HIGH_RISK")]:
        response = bank.post(
            f"/api/applications/{application['id']}/decisions",
            json=dict(
                expected_version=application["version"],
                command_id=str(uuid4()),
                kind=kind,
                reason_code=reason,
                explanation="Проверка недоступных исходных данных",
            ),
        )
        assert response.status_code == 422
    assert dossier(bank, application)["application"] == application


def test_source_failure_retry_preserves_runs(client, bank):
    application = create(client, inn="7700000099")
    for _ in range(2):
        application, _ = command(bank, application, "checks")
        assert application["status"] == "CHECKING"
    runs = dossier(bank, application)["runs"]
    assert len(runs) == 2 and all(r["state"] == "FAILED" for r in runs)


def test_version_conflict_and_receipt_payload_conflict(client, bank):
    application = create(client)
    updated, body = command(bank, application, "checks")
    assert (
        bank.post(f"/api/applications/{application['id']}/checks", json=body).json()
        == updated
    )
    assert (
        bank.post(
            f"/api/applications/{application['id']}/checks",
            json={**body, "expected_version": updated["version"]},
        ).status_code
        == 409
    )
    assert (
        bank.post(
            f"/api/applications/{application['id']}/information-requests",
            json=dict(
                expected_version=application["version"],
                command_id=str(uuid4()),
                message="Предоставьте пояснение расходов",
            ),
        ).status_code
        == 409
    )
    assert dossier(bank, application)["application"] == updated


def test_response_allows_only_requested_fields_and_requires_document(client, bank):
    application = create(client, "clarification")
    application, _ = command(bank, application, "checks")
    application, _ = command(
        bank,
        application,
        "information-requests",
        message="Предоставьте отчёт и уточнение расходов",
        fields=["monthly_operating_expenses"],
        document_kind="FINANCIAL_REPORT",
    )
    request = dossier(client, application)["information_requests"][0]
    url = f"/api/applications/{application['id']}/information-requests/{request['id']}/reply"
    common = dict(
        expected_version=application["version"],
        command_id=str(uuid4()),
        explanation="Уточнены операционные расходы",
    )
    for fields, documents in [
        ({"amount": "1.00"}, []),
        ({"monthly_operating_expenses": "400000.00"}, []),
        (
            {"monthly_operating_expenses": "1.001"},
            [{"name": "doc.txt", "content": "test"}],
        ),
    ]:
        assert (
            client.post(
                url, json=dict(**common, fields=fields, documents=documents)
            ).status_code
            == 422
        )
    assert dossier(client, application)["application"] == application
    assert (
        client.patch(
            f"/api/applications/{application['id']}",
            json={"monthly_operating_expenses": "400000.00"},
        ).status_code
        == 409
    )


def test_role_owner_csrf_and_document_isolation(client, bank):
    application = create(client)
    body = dict(expected_version=application["version"], command_id=str(uuid4()))
    assert (
        client.post(
            f"/api/applications/{application['id']}/checks", json=body
        ).status_code
        == 403
    )
    with TestClient(app) as other:
        assert (
            other.get(f"/api/applications/{application['id']}/dossier").status_code
            == 401
        )
        login = other.post(
            "/api/auth/login",
            json={"login": "client-b", "password": "demo-client-b-local"},
        ).json()
        other.headers["X-CSRF-Token"] = login["csrf_token"]
        for suffix in ["dossier", "events", "documents/1"]:
            assert (
                other.get(f"/api/applications/{application['id']}/{suffix}").status_code
                == 404
            )
        assert all(
            a["id"] != application["id"]
            for a in other.get("/api/applications").json()["items"]
        )
        assert other.get("/api/bank/analytics").status_code == 403
    saved = bank.headers.pop("X-CSRF-Token")
    assert (
        bank.post(
            f"/api/applications/{application['id']}/checks", json=body
        ).status_code
        == 403
    )
    bank.headers["X-CSRF-Token"] = saved


def test_concurrent_decisions_create_one_result(client, bank):
    application = create(client)
    application, _ = command(bank, application, "checks")

    def decide(_):
        # Independent HTTP clients, sharing only the authenticated session cookie.
        with TestClient(app, cookies=bank.cookies) as session:
            return session.post(
                f"/api/applications/{application['id']}/decisions",
                headers={"X-CSRF-Token": bank.headers["X-CSRF-Token"]},
                json=dict(
                    expected_version=application["version"],
                    command_id=str(uuid4()),
                    kind="OFFER",
                    reason_code="STANDARD",
                    explanation="Денежного остатка достаточно для выплаты",
                ),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (
        len(
            [
                e
                for e in client.get(
                    f"/api/applications/{application['id']}/events"
                ).json()
                if e["event_type"] == "OFFER_ISSUED"
            ]
        )
        == 1
    )


def test_seed_idempotent_and_analytics_are_real(database, bank):
    with psycopg.connect(**connection_parameters()) as connection:
        seed_scenarios(connection)
        count = connection.execute("SELECT count(*) FROM applications").fetchone()[0]
        seed_scenarios(connection)
        assert (
            connection.execute("SELECT count(*) FROM applications").fetchone()[0]
            == count
        )
    result = bank.get("/api/bank/analytics")
    assert result.status_code == 200
    assert result.json()["total"] >= 4
    assert bank.get("/api/bank/model").json()["report"]["test"]["n"] == 900


def test_money_and_ml_monotonicity():
    from ml.inference import predict

    assert payment(Decimal("1200"), 12, Decimal("0")) == Decimal("100")
    assert (
        predict(3, 0.3, 60, 0)["probability"] < predict(0.7, 0.05, 8, 90)["probability"]
    )


def test_stale_check_can_recover(client, bank):
    application = create(client)
    with psycopg.connect(**connection_parameters()) as connection:
        connection.execute(
            "INSERT INTO processing_runs (application_id,command_id,state,input_snapshot,started_at) VALUES (%s,%s,'RUNNING','{}',clock_timestamp()-interval '1 minute')",
            (application["id"], uuid4()),
        )
    application, _ = command(bank, application, "checks")
    result = dossier(bank, application)
    assert result["runs"][0]["state"] == "COMPLETE"
    assert result["runs"][1]["error_code"] == "INTERRUPTED"


@pytest.mark.parametrize(
    "bad_source",
    [
        (
            {
                "legal_name": "ООО «Северная пекарня»",
                "registration_active": True,
                "business_age_months": -1,
            },
            {"max_overdue_days": 0},
        ),
        (
            {
                "legal_name": "ООО «Северная пекарня»",
                "registration_active": "true",
                "business_age_months": 48,
            },
            {"max_overdue_days": 0},
        ),
        (
            {
                "legal_name": "ООО «Северная пекарня»",
                "registration_active": True,
                "business_age_months": 48,
            },
            {"max_overdue_days": None},
        ),
    ],
)
def test_invalid_source_is_failed_and_can_recover(
    client, bank, monkeypatch, bad_source
):
    import workflow

    original = workflow.lookup
    application = create(client)
    monkeypatch.setattr(workflow, "lookup", lambda inn: bad_source)
    application, _ = command(bank, application, "checks")
    run = dossier(bank, application)["runs"][0]
    assert run["state"] == "FAILED" and run["error_code"] == "SOURCE_INVALID"
    assert run["assessment"] is None and application["status"] == "CHECKING"
    monkeypatch.setattr(workflow, "lookup", original)
    application, _ = command(bank, application, "checks")
    assert dossier(bank, application)["runs"][0]["state"] == "COMPLETE"


def test_missing_credit_history_does_not_become_zero_overdue(client, bank, monkeypatch):
    import workflow

    original = workflow.lookup
    monkeypatch.setattr(workflow, "lookup", lambda inn: (original(inn)[0], None))
    application = create(client)
    application, _ = command(bank, application, "checks")
    run = dossier(bank, application)["runs"][0]
    assert run["state"] == "INCOMPLETE" and run["assessment"] is None
    assert next(c for c in run["checks"] if c["code"] == "BKI")["result"] == "NO_DATA"
    assert any(
        b["reason_code"] == "DATA_INCOMPLETE"
        for b in bank.get("/api/bank/analytics").json()["bottlenecks"]
    )


def test_processing_exception_is_durable_not_stuck(client, bank, monkeypatch):
    import workflow

    def broken(*args):
        raise ArithmeticError("synthetic failure")

    monkeypatch.setattr(workflow, "evaluate", broken)
    application = create(client)
    application, _ = command(bank, application, "checks")
    run = dossier(bank, application)["runs"][0]
    assert run["state"] == "FAILED" and run["error_code"] == "PROCESSING_ERROR"
    assert any(
        b["reason_code"] == "CHECKS_FAILED"
        for b in bank.get("/api/bank/analytics").json()["bottlenecks"]
    )


def test_decision_and_history_rollback_together(client, bank, monkeypatch):
    import workflow

    application = create(client)
    application, _ = command(bank, application, "checks")

    def unavailable(*args):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(workflow, "record_event", unavailable)
    with TestClient(
        app, cookies=bank.cookies, raise_server_exceptions=False
    ) as session:
        response = session.post(
            f"/api/applications/{application['id']}/decisions",
            headers={"X-CSRF-Token": bank.headers["X-CSRF-Token"]},
            json=dict(
                expected_version=application["version"],
                command_id=str(uuid4()),
                kind="OFFER",
                reason_code="STANDARD",
                explanation="Данные проверены, условия доступны",
            ),
        )
    assert response.status_code == 500
    current = dossier(bank, application)
    assert current["application"] == application and current["decision"] is None
    with psycopg.connect(**connection_parameters()) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM command_receipts WHERE application_id=%s AND action='decision'",
                (application["id"],),
            ).fetchone()[0]
            == 0
        )


def test_if_match_prevents_stale_draft_updates_and_submit(client):
    fields = scenario_fields(SCENARIOS[0])
    draft = client.post("/api/applications", json=fields).json()
    url = f"/api/applications/{draft['id']}"
    updated = client.patch(
        url,
        json={"credit_purpose": "Новый план расширения"},
        headers={"If-Match": str(draft["version"])},
    )
    assert updated.status_code == 200
    for path, method, payload in [
        (url, client.patch, {"amount": "700000.00"}),
        (url + "/submit", client.post, None),
    ]:
        response = method(
            path, json=payload, headers={"If-Match": str(draft["version"])}
        )
        assert response.status_code == 409
    assert client.get(url).json() == updated.json()


def test_estimate_rejects_subcent_json_before_float_rounding(client):
    response = client.post(
        "/api/products/estimate",
        content='{"product_code":"WORKING_CAPITAL","amount":100000.00000000001,"term":12}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_workflow_path_identifiers_are_bounded(client, bank):
    application = create(client)
    base = f"/api/applications/{application['id']}"
    assert client.get(base + "/documents/" + str(2**64)).status_code == 422
    response = client.post(
        base + "/information-requests/" + str(2**64) + "/reply",
        json=dict(
            expected_version=application["version"],
            command_id=str(uuid4()),
            explanation="Синтетическое пояснение",
        ),
    )
    assert response.status_code == 422
