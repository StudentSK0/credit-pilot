"""Server-owned workflow. Every command is locked, versioned and audited."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from applications import (
    Application,
    ApplicationFields,
    DecimalJSONRoute,
    SubmissionFields,
    find_application,
)
from audit import record_event
from auth import CurrentActor, Database, Role
from fixtures import FIXTURE_VERSION, RegistryRecord, CreditHistoryRecord, lookup
from scoring import alternative, assess

router = APIRouter(
    prefix="/api/applications", tags=["workflow"], route_class=DecimalJSONRoute
)
EDITABLE_REPLY = {
    "company_name",
    "credit_purpose",
    "monthly_revenue",
    "monthly_operating_expenses",
    "existing_monthly_debt_payments",
}
STALE_SECONDS = 30
EntityId = Annotated[int, Path(gt=0, le=2**63 - 1)]
logger = logging.getLogger(__name__)


def json_safe(value):
    return json.loads(
        json.dumps(
            value,
            default=lambda x: (
                str(x) if isinstance(x, (Decimal, UUID)) else x.isoformat()
            ),
        )
    )


def row(connection, query, params=()):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


def rows(connection, query, params=()):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, ge=1, le=2**63 - 1)]
    command_id: UUID


class InformationCommand(Command):
    message: str = Field(min_length=10, max_length=1800)
    fields: list[
        Literal[
            "company_name",
            "credit_purpose",
            "monthly_revenue",
            "monthly_operating_expenses",
            "existing_monthly_debt_payments",
        ]
    ] = Field(default_factory=list, max_length=5)
    document_kind: Literal["FINANCIAL_REPORT", "PURPOSE_EVIDENCE"] | None = None

    @field_validator("message")
    @classmethod
    def meaningful_message(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Объясните причину: не менее 10 символов")
        return value.strip()

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Поля не должны повторяться")
        return value


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(
        min_length=5, max_length=160, pattern=r"^[^/\\\x00-\x1f]+\.(txt|csv)$"
    )
    content: str = Field(min_length=1, max_length=65536)

    @field_validator("content")
    @classmethod
    def safe_text(cls, value):
        if (
            not value.strip()
            or len(value.encode("utf-8")) > 65536
            or any(ord(c) < 32 and c not in "\n\r\t" for c in value)
        ):
            raise ValueError("Нужен текстовый синтетический документ до 64 КиБ")
        return value


class ReplyCommand(Command):
    explanation: str = Field(min_length=10, max_length=1800)
    fields: ApplicationFields = Field(default_factory=ApplicationFields)
    documents: list[DocumentInput] = Field(default_factory=list, max_length=3)

    @field_validator("explanation")
    @classmethod
    def meaningful_explanation(cls, value):
        return InformationCommand.meaningful_message(value)


class DecisionCommand(Command):
    kind: Literal["OFFER", "REJECT"]
    reason_code: Literal[
        "STANDARD",
        "COUNTER_OFFER",
        "AFFORDABILITY",
        "CREDIT_HISTORY",
        "INACTIVE_BUSINESS",
        "HIGH_RISK",
    ]
    explanation: str = Field(min_length=10, max_length=1800)
    offered_amount: Decimal | None = None

    @field_validator("explanation")
    @classmethod
    def meaningful_explanation(cls, value):
        return InformationCommand.meaningful_message(value)

    @field_validator("offered_amount")
    @classmethod
    def exact_amount(cls, value):
        if value is not None and (
            not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2
        ):
            raise ValueError(
                "Сумма должна быть положительной, не более двух знаков после запятой"
            )
        return value


class SignCommand(Command):
    decision_id: Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
    confirmed: Literal[True]


def role_required(actor, role):
    if actor.role != role:
        raise HTTPException(403, "Действие недоступно для вашей роли")


def fingerprint(command):
    return hashlib.sha256(
        json.dumps(
            command.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def cached_result(connection, application, actor, action, command):
    receipt = row(
        connection,
        "SELECT * FROM command_receipts WHERE application_id=%s AND command_id=%s",
        (application["id"], command.command_id),
    )
    if receipt:
        if (
            receipt["actor_id"] != actor.id
            or receipt["action"] != action
            or receipt["request_hash"] != fingerprint(command)
        ):
            raise HTTPException(409, "Ключ команды уже использован с другими данными")
        return receipt["response"]


def validate_version(application, command, allowed):
    if application["version"] != command.expected_version:
        raise HTTPException(
            409, "Заявка уже изменилась. Обновите досье перед действием"
        )
    if application["status"] not in allowed:
        raise HTTPException(409, "Действие недоступно на текущем этапе заявки")


def advance(connection, application, actor, status, event, changes):
    updated = row(
        connection,
        "UPDATE applications SET status=%s, version=version+1, updated_at=clock_timestamp() WHERE id=%s RETURNING *",
        (status, application["id"]),
    )
    record_event(connection, updated, actor, event, application["status"], changes)
    return updated


def receipt(connection, application, actor, action, command):
    response = Application.model_validate(application).model_dump(mode="json")
    connection.execute(
        "INSERT INTO command_receipts (application_id,command_id,actor_id,action,request_hash,response) VALUES (%s,%s,%s,%s,%s,%s)",
        (
            application["id"],
            command.command_id,
            actor.id,
            action,
            fingerprint(command),
            Jsonb(response),
        ),
    )
    return application


def mutate(connection, actor, application_id, command, action, role, allowed, handler):
    role_required(actor, role)
    with connection.transaction():
        application = find_application(connection, application_id, actor, lock=True)
        cached = cached_result(connection, application, actor, action, command)
        if cached:
            return cached
        validate_version(application, command, allowed)
        status, event, changes = handler(application)
        updated = advance(connection, application, actor, status, event, changes)
        return receipt(connection, updated, actor, action, command)


def latest_run(connection, application_id):
    return row(
        connection,
        "SELECT * FROM processing_runs WHERE application_id=%s ORDER BY id DESC LIMIT 1",
        (application_id,),
    )


def evaluate(snapshot, product):
    now = datetime.now(timezone.utc).isoformat()
    checks = []

    def check(code, label, result, detail, evidence=None):
        checks.append(
            dict(
                code=code,
                label=label,
                result=result,
                detail=detail,
                evidence=evidence,
                source=(
                    "LOCAL_SIMULATOR" if code in ("REGISTRY", "BKI") else "APPLICATION"
                ),
                fixture_version=FIXTURE_VERSION,
                checked_at=now,
            )
        )

    try:
        SubmissionFields.model_validate(snapshot)
        valid = (
            product is not None
            and product["min_amount"]
            <= Decimal(snapshot["amount"])
            <= product["max_amount"]
            and product["min_term"] <= snapshot["term"] <= product["max_term"]
        )
    except (ValidationError, TypeError, KeyError):
        valid = False
    check(
        "COMPLETENESS",
        "Анкета и условия продукта",
        "PASS" if valid else "NO_DATA",
        (
            "Обязательные поля заполнены, версия продукта сохранена"
            if valid
            else "Не хватает обязательных данных или сохранённой версии продукта"
        ),
    )
    registry, bki = lookup(snapshot["inn"])
    if registry is None:
        check(
            "REGISTRY",
            "Реестр компаний",
            "NO_DATA",
            "Для этого синтетического ИНН нет записи",
        )
        check(
            "BKI",
            "Кредитная история",
            "NO_DATA",
            "Отсутствие истории не считается хорошей историей",
        )
        return checks, None
    registry = RegistryRecord.model_validate(registry).model_dump()
    if bki is not None:
        bki = CreditHistoryRecord.model_validate(bki).model_dump()
    match = snapshot["company_name"] == registry["legal_name"]
    check(
        "REGISTRY",
        "Реестр компаний",
        "PASS" if match and registry["registration_active"] else "ISSUE",
        (
            "Компания активна, название совпадает"
            if match and registry["registration_active"]
            else (
                "Регистрация компании неактивна"
                if not registry["registration_active"]
                else "Название не совпадает с локальным реестром"
            )
        ),
        registry,
    )
    if bki is None:
        check(
            "BKI",
            "Кредитная история",
            "NO_DATA",
            "История отсутствует; оценка не рассчитывается",
        )
        return checks, None
    check(
        "BKI",
        "Кредитная история",
        "PASS" if bki["max_overdue_days"] == 0 else "ISSUE",
        f"Максимальная просрочка: {bki['max_overdue_days']} дн.",
        bki,
    )
    if not valid or not match:
        return checks, None
    result = assess(snapshot, product, registry, bki)
    result["alternative"] = (
        alternative(snapshot, product, registry, bki)
        if not result["eligible"]
        else None
    )
    check(
        "FINANCIALS",
        "Долговая нагрузка",
        "PASS" if result["eligible"] else "ISSUE",
        (
            "Денежный остаток покрывает выплаты с запасом"
            if result["eligible"]
            else "; ".join(result["blockers"])
        ),
    )
    return checks, result


@router.post("/{application_id}/checks", response_model=Application)
def run_checks(
    application_id: int, command: Command, connection: Database, actor: CurrentActor
):
    role_required(actor, Role.BANK_EMPLOYEE)
    # Auth SELECT opened a transaction. End it before the two durable phases.
    connection.commit()
    with connection.transaction():
        application = find_application(connection, application_id, actor, lock=True)
        cached = cached_result(connection, application, actor, "checks", command)
        if cached:
            return cached
        validate_version(
            application, command, {"SUBMITTED", "UNDER_REVIEW", "CHECKING"}
        )
        previous = latest_run(connection, application_id)
        if previous and previous["command_id"] == command.command_id:
            raise HTTPException(
                409,
                "Эта попытка уже началась. Обновите досье и используйте новую команду повтора",
            )
        if previous and previous["state"] == "RUNNING":
            if (
                datetime.now(timezone.utc) - previous["started_at"]
            ).total_seconds() < STALE_SECONDS:
                raise HTTPException(409, "Проверки ещё выполняются")
            connection.execute(
                "UPDATE processing_runs SET state='FAILED',error_code='INTERRUPTED',completed_at=clock_timestamp() WHERE id=%s",
                (previous["id"],),
            )
        snapshot = {
            field: application[field] for field in ApplicationFields.model_fields
        }
        product = row(
            connection,
            "SELECT * FROM credit_products WHERE code=%s AND version=%s",
            (application["product_code"], application["product_version"]),
        )
        run = row(
            connection,
            "INSERT INTO processing_runs (application_id,command_id,state,input_snapshot,product_snapshot) VALUES (%s,%s,'RUNNING',%s,%s) RETURNING *",
            (
                application_id,
                command.command_id,
                Jsonb(json_safe(snapshot)),
                Jsonb(json_safe(product)),
            ),
        )
        advance(
            connection,
            application,
            actor,
            "CHECKING",
            "CHECKS_STARTED",
            {"run_id": (None, run["id"])},
        )
    error_code = None
    try:
        checks, assessment = evaluate(snapshot, product)
        state = "COMPLETE" if assessment else "INCOMPLETE"
    except TimeoutError:
        checks, assessment, state, error_code = [], None, "FAILED", "SOURCE_UNAVAILABLE"
    except ValidationError:
        checks, assessment, state, error_code = [], None, "FAILED", "SOURCE_INVALID"
    except Exception as error:
        # Preserve a failed attempt without leaking input, credentials or internals.
        logger.error("Processing run %s failed: %s", run["id"], type(error).__name__)
        checks, assessment, state, error_code = [], None, "FAILED", "PROCESSING_ERROR"
    with connection.transaction():
        application = find_application(connection, application_id, actor, lock=True)
        current = latest_run(connection, application_id)
        if current["id"] != run["id"] or current["state"] != "RUNNING":
            raise HTTPException(409, "Эту проверку уже заменила новая попытка")
        connection.execute(
            "UPDATE processing_runs SET state=%s, checks=%s, assessment=%s, error_code=%s, completed_at=clock_timestamp() WHERE id=%s",
            (state, Jsonb(json_safe(checks)), Jsonb(assessment), error_code, run["id"]),
        )
        updated = advance(
            connection,
            application,
            actor,
            "CHECKING" if error_code else "UNDER_REVIEW",
            "CHECKS_FAILED" if error_code else "CHECKS_COMPLETED",
            {"run_id": (None, run["id"]), "result": (None, state)},
        )
        return receipt(connection, updated, actor, "checks", command)


@router.post("/{application_id}/information-requests", response_model=Application)
def request_information(
    application_id: int,
    command: InformationCommand,
    connection: Database,
    actor: CurrentActor,
):
    def handler(application):
        result = row(
            connection,
            "INSERT INTO information_requests (application_id,actor_id,message,fields,document_kind) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (
                application_id,
                actor.id,
                command.message,
                Jsonb(command.fields),
                command.document_kind,
            ),
        )
        return (
            "NEEDS_INFO",
            "INFORMATION_REQUESTED",
            {
                "request_id": (None, result["id"]),
                "message": (None, command.message),
                "fields": (None, command.fields),
                "document_kind": (None, command.document_kind),
            },
        )

    return mutate(
        connection,
        actor,
        application_id,
        command,
        "request_information",
        Role.BANK_EMPLOYEE,
        {"UNDER_REVIEW"},
        handler,
    )


@router.post(
    "/{application_id}/information-requests/{request_id}/reply",
    response_model=Application,
)
def reply_information(
    application_id: int,
    request_id: EntityId,
    command: ReplyCommand,
    connection: Database,
    actor: CurrentActor,
):
    def handler(application):
        request = row(
            connection,
            "SELECT * FROM information_requests WHERE id=%s AND application_id=%s AND answered_at IS NULL",
            (request_id, application_id),
        )
        if not request:
            raise HTTPException(409, "Запрос уже закрыт или не относится к заявке")
        fields = command.fields.model_dump(exclude_unset=True)
        if set(fields) != set(request["fields"]) or not set(fields) <= EDITABLE_REPLY:
            raise HTTPException(422, "Ответ должен содержать ровно запрошенные поля")
        snapshot = {
            field: fields.get(field, application[field])
            for field in ApplicationFields.model_fields
        }
        try:
            SubmissionFields.model_validate(snapshot)
        except ValidationError as error:
            raise HTTPException(
                422, "Проверьте заполнение и значения запрошенных полей"
            ) from error
        if request["document_kind"] and not command.documents:
            raise HTTPException(
                422, "Приложите запрошенный синтетический документ (.txt или .csv)"
            )
        from psycopg import sql

        if fields:
            connection.execute(
                sql.SQL("UPDATE applications SET {} WHERE id=%s").format(
                    sql.SQL(",").join(
                        sql.SQL("{}=%s").format(sql.Identifier(f)) for f in fields
                    )
                ),
                [*fields.values(), application_id],
            )
        document_ids = []
        for document in command.documents:
            stored = row(
                connection,
                "INSERT INTO application_documents (application_id,request_id,uploaded_by,name,content,sha256) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (
                    application_id,
                    request_id,
                    actor.id,
                    document.name,
                    document.content,
                    hashlib.sha256(document.content.encode()).hexdigest(),
                ),
            )
            document_ids.append(stored["id"])
        response = dict(
            explanation=command.explanation,
            fields=json_safe(fields),
            document_ids=document_ids,
        )
        connection.execute(
            "UPDATE information_requests SET response=%s,answered_at=clock_timestamp() WHERE id=%s",
            (Jsonb(response), request_id),
        )
        changes = {
            field: (application[field], value) for field, value in fields.items()
        }
        changes.update(
            request_id=(None, request_id),
            explanation=(None, command.explanation),
            document_ids=(None, document_ids),
        )
        return "SUBMITTED", "INFORMATION_PROVIDED", changes

    return mutate(
        connection,
        actor,
        application_id,
        command,
        f"reply:{request_id}",
        Role.CLIENT,
        {"NEEDS_INFO"},
        handler,
    )


@router.post("/{application_id}/decisions", response_model=Application)
def decide(
    application_id: int,
    command: DecisionCommand,
    connection: Database,
    actor: CurrentActor,
):
    def handler(application):
        run = latest_run(connection, application_id)
        if not run or run["state"] not in {"COMPLETE", "INCOMPLETE"}:
            raise HTTPException(409, "Сначала завершите проверки")
        registry = next(
            (c["evidence"] for c in run["checks"] if c["code"] == "REGISTRY"), None
        )
        bki = next((c["evidence"] for c in run["checks"] if c["code"] == "BKI"), None)
        assessment, terms = run["assessment"], None
        if command.kind == "OFFER":
            if assessment is None or command.reason_code not in {
                "STANDARD",
                "COUNTER_OFFER",
            }:
                raise HTTPException(
                    422, "Предложение требует полной оценки и причины предложения"
                )
            amount = (
                command.offered_amount
                if command.offered_amount is not None
                else application["amount"]
            )
            product = run["product_snapshot"]
            if not Decimal(product["min_amount"]) <= amount <= application["amount"]:
                raise HTTPException(
                    422,
                    "Можно предложить исходную или меньшую сумму в пределах продукта",
                )
            assessment = assess(
                run["input_snapshot"], product, registry, bki, amount=amount
            )
            if not assessment["eligible"]:
                raise HTTPException(422, "; ".join(assessment["blockers"]))
            expected_reason = (
                "COUNTER_OFFER" if amount < application["amount"] else "STANDARD"
            )
            if command.reason_code != expected_reason:
                raise HTTPException(
                    422,
                    "Причина должна соответствовать исходным или встречным условиям",
                )
            terms = {
                k: assessment[k]
                for k in ("amount", "term", "annual_rate", "monthly_payment")
            }
            terms.update(
                product_code=application["product_code"],
                product_version=application["product_version"],
            )
        else:
            if (
                command.reason_code in {"STANDARD", "COUNTER_OFFER"}
                or command.offered_amount is not None
            ):
                raise HTTPException(
                    422, "Укажите причину отказа без условий предложения"
                )
            inactive = registry is not None and registry["registration_active"] is False
            if assessment is None and not (
                inactive and command.reason_code == "INACTIVE_BUSINESS"
            ):
                raise HTTPException(
                    422, "Недостаток данных не является основанием для отказа по риску"
                )
            evidence = {
                "INACTIVE_BUSINESS": inactive,
                "AFFORDABILITY": assessment is not None
                and Decimal(assessment["dscr"]) < Decimal("1.2"),
                "CREDIT_HISTORY": bki is not None and bki["max_overdue_days"] > 0,
                "HIGH_RISK": assessment is not None and assessment["risk"] == "HIGH",
            }
            if not evidence.get(command.reason_code):
                raise HTTPException(
                    422, "Выбранная причина не подтверждена текущими проверками"
                )
        decision = row(
            connection,
            "INSERT INTO decisions (application_id,run_id,actor_id,kind,reason_code,explanation,terms,assessment) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                application_id,
                run["id"],
                actor.id,
                command.kind,
                command.reason_code,
                command.explanation,
                Jsonb(terms),
                Jsonb(assessment),
            ),
        )
        return (
            "OFFERED" if command.kind == "OFFER" else "REJECTED",
            "OFFER_ISSUED" if command.kind == "OFFER" else "REJECTED",
            {
                "decision_id": (None, decision["id"]),
                "reason_code": (None, command.reason_code),
                "explanation": (None, command.explanation),
                "terms": (None, terms),
            },
        )

    return mutate(
        connection,
        actor,
        application_id,
        command,
        "decision",
        Role.BANK_EMPLOYEE,
        {"UNDER_REVIEW"},
        handler,
    )


def contract_text(application, decision):
    terms = decision["terms"]
    return (
        f"CREDIT PILOT · ДЕМОНСТРАЦИОННЫЙ ДОГОВОР\nВерсия contract_v1\n\n"
        f"Заявка №{application['id']} · Решение №{decision['id']}\nКомпания: {application['company_name']}\n"
        f"ИНН: {application['inn']}\nПродукт: {terms['product_code']} / {terms['product_version']}\n"
        f"Сумма: {terms['amount']} ₽\nСрок: {terms['term']} мес.\n"
        f"Учебная ставка: {Decimal(terms['annual_rate'])*100}% годовых\n"
        f"Расчётный ежемесячный платёж: {terms['monthly_payment']} ₽\n\n"
        "Подтверждение в кабинете моделирует принятие условий и подписание. "
        "Документ не имеет юридической силы. Реальная подпись и перевод денег не выполняются."
    )


@router.post("/{application_id}/sign", response_model=Application)
def sign(
    application_id: int, command: SignCommand, connection: Database, actor: CurrentActor
):
    def handler(application):
        decision = row(
            connection,
            "SELECT * FROM decisions WHERE application_id=%s AND id=%s AND kind='OFFER'",
            (application_id, command.decision_id),
        )
        if not decision:
            raise HTTPException(409, "Предложение изменилось или недоступно")
        text = contract_text(application, decision)
        contract = row(
            connection,
            "INSERT INTO simulated_contracts (application_id,decision_id,signed_by,document_version,document_text,document_sha256) VALUES (%s,%s,%s,'contract_v1',%s,%s) RETURNING id",
            (
                application_id,
                decision["id"],
                actor.id,
                text,
                hashlib.sha256(text.encode()).hexdigest(),
            ),
        )
        return "SIGNED", "SIGNED_SIMULATED", {"contract_id": (None, contract["id"])}

    return mutate(
        connection,
        actor,
        application_id,
        command,
        "sign",
        Role.CLIENT,
        {"OFFERED"},
        handler,
    )


@router.post("/{application_id}/disburse", response_model=Application)
def disburse(
    application_id: int, command: Command, connection: Database, actor: CurrentActor
):
    def handler(application):
        contract = row(
            connection,
            "SELECT c.id, d.terms FROM simulated_contracts c JOIN decisions d ON d.id=c.decision_id WHERE c.application_id=%s",
            (application_id,),
        )
        if not contract:
            raise HTTPException(409, "Сначала требуется подписание")
        result = row(
            connection,
            "INSERT INTO simulated_disbursements (application_id,contract_id,actor_id,amount) VALUES (%s,%s,%s,%s) RETURNING id",
            (
                application_id,
                contract["id"],
                actor.id,
                Decimal(contract["terms"]["amount"]),
            ),
        )
        return (
            "DISBURSED",
            "DISBURSED_SIMULATED",
            {
                "disbursement_id": (None, result["id"]),
                "amount": (None, contract["terms"]["amount"]),
            },
        )

    return mutate(
        connection,
        actor,
        application_id,
        command,
        "disburse",
        Role.BANK_EMPLOYEE,
        {"SIGNED"},
        handler,
    )


@router.get("/{application_id}/dossier")
def dossier(application_id: int, connection: Database, actor: CurrentActor):
    # A single read snapshot avoids combining an old application with a new decision.
    connection.commit()
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        application = find_application(connection, application_id, actor)
        runs = rows(
            connection,
            "SELECT * FROM processing_runs WHERE application_id=%s ORDER BY id DESC",
            (application_id,),
        )
        requests = rows(
            connection,
            "SELECT * FROM information_requests WHERE application_id=%s ORDER BY id DESC",
            (application_id,),
        )
        decision = row(
            connection,
            "SELECT * FROM decisions WHERE application_id=%s",
            (application_id,),
        )
        contract = row(
            connection,
            "SELECT * FROM simulated_contracts WHERE application_id=%s",
            (application_id,),
        )
        disbursement = row(
            connection,
            "SELECT * FROM simulated_disbursements WHERE application_id=%s",
            (application_id,),
        )
        documents = rows(
            connection,
            "SELECT id,request_id,name,sha256,created_at FROM application_documents WHERE application_id=%s ORDER BY id",
            (application_id,),
        )
        actions = []
        if actor.role == Role.CLIENT:
            actions = {
                "DRAFT": ["edit", "submit"],
                "NEEDS_INFO": ["reply"],
                "OFFERED": ["sign"],
            }.get(application["status"], [])
        else:
            actions = {
                "SUBMITTED": ["checks"],
                "UNDER_REVIEW": ["checks", "request_information", "decision"],
                "CHECKING": ["checks"],
                "SIGNED": ["disburse"],
            }.get(application["status"], [])
        return json_safe(
            dict(
                application=Application.model_validate(application).model_dump(
                    mode="json"
                ),
                runs=runs,
                information_requests=requests,
                decision=decision,
                contract=contract,
                disbursement=disbursement,
                documents=documents,
                allowed_actions=actions,
                contract_preview=(
                    contract_text(application, decision)
                    if decision and decision["kind"] == "OFFER"
                    else None
                ),
            )
        )


@router.get("/{application_id}/documents/{document_id}")
def download_document(
    application_id: int,
    document_id: EntityId,
    connection: Database,
    actor: CurrentActor,
):
    find_application(connection, application_id, actor)
    document = row(
        connection,
        "SELECT * FROM application_documents WHERE application_id=%s AND id=%s",
        (application_id, document_id),
    )
    if not document:
        raise HTTPException(404, "Документ не найден")
    from urllib.parse import quote

    return Response(
        content=document["content"],
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document['name'])}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
