import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.routing import APIRoute
from psycopg import Connection, sql
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from audit import ApplicationEvent, record_event
from auth import Actor, CurrentActor, Database, Role, require_client
from products import submission_product


class DecimalJSONRequest(Request):
    async def json(self):
        # Preserve decimal JSON numbers before Pydantic sees them.
        def reject_nonfinite(value):
            raise json.JSONDecodeError("Non-finite JSON numbers are not allowed", value, 0)

        if not hasattr(self, "_json"):
            self._json = json.loads(await self.body(), parse_float=Decimal, parse_constant=reject_nonfinite)
        return self._json


class DecimalJSONRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            return await handler(DecimalJSONRequest(request.scope, request.receive))

        return handle


class Status(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


class ApplicationFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: Annotated[str, Field(max_length=255)] | None = None
    inn: str | None = None
    credit_purpose: Annotated[str, Field(max_length=1000)] | None = None
    amount: Decimal | None = None
    term: Annotated[int, Field(strict=True, ge=-(2**63), le=2**63 - 1)] | None = None
    product_code: Annotated[str, Field(max_length=64)] | None = None
    monthly_revenue: Decimal | None = None
    monthly_operating_expenses: Decimal | None = None
    existing_monthly_debt_payments: Decimal | None = None

    @field_validator(
        "amount", "term", "product_code", "monthly_revenue",
        "monthly_operating_expenses", "existing_monthly_debt_payments", mode="before",
    )
    @classmethod
    def empty_number(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("amount", "monthly_revenue", "monthly_operating_expenses", "existing_monthly_debt_payments")
    @classmethod
    def exact_amount(cls, value):
        if value is not None and value.as_tuple().exponent < -2:
            raise ValueError("Money must have at most two decimal places")
        return value


class SubmissionFields(ApplicationFields):
    company_name: Annotated[str, Field(min_length=1, max_length=255)]
    inn: Annotated[str, Field(pattern=r"^[0-9]{10}([0-9]{2})?$")]
    credit_purpose: Annotated[str, Field(min_length=1, max_length=1000)]
    amount: Annotated[Decimal, Field(gt=0)]
    term: Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
    product_code: Annotated[str, Field(min_length=1, max_length=64)]
    monthly_revenue: Annotated[Decimal, Field(gt=0)]
    monthly_operating_expenses: Annotated[Decimal, Field(ge=0)]
    existing_monthly_debt_payments: Annotated[Decimal, Field(ge=0)]

    @field_validator("company_name", "credit_purpose")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Field must not contain only whitespace")
        return value


class Application(ApplicationFields):
    product_version: str | None = Field(default=None, json_schema_extra={"readOnly": True})
    id: int
    status: Status
    created_at: datetime
    updated_at: datetime
    company_id: int | None
    created_by: int | None
    version: int
    owner_id: int | None


router = APIRouter(prefix="/api/applications", tags=["applications"], route_class=DecimalJSONRoute)


def find_application(connection: Connection, application_id: int, actor: Actor, *, lock=False):
    if not -(2**63) <= application_id < 2**63:
        raise HTTPException(status_code=404, detail="Application not found")
    query = "SELECT * FROM applications WHERE id = %s"
    parameters = [application_id]
    if actor.role == Role.CLIENT:
        query += " AND owner_id = %s"
        parameters.append(actor.id)
    elif actor.role != Role.BANK_EMPLOYEE:
        raise HTTPException(status_code=403, detail="Role is not allowed")
    if lock:
        query += " FOR UPDATE"
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, parameters)
        application = cursor.fetchone()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def require_draft(application):
    if application["status"] != Status.DRAFT:
        raise HTTPException(status_code=409, detail="Application is not a draft")


@router.post("", response_model=Application, status_code=201)
def create_application(fields: ApplicationFields, connection: Database, actor: CurrentActor):
    require_client(actor)
    values = fields.model_dump()
    values.update(company_id=actor.company_id, created_by=actor.id, owner_id=actor.id)
    with connection.transaction(), connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            sql.SQL("INSERT INTO applications ({}) VALUES ({}) RETURNING *").format(
                sql.SQL(", ").join(map(sql.Identifier, values)),
                sql.SQL(", ").join(sql.Placeholder() for _ in values),
            ),
            list(values.values()),
        )
        application = cursor.fetchone()
        record_event(
            connection, application, actor, "DRAFT_CREATED", None,
            {field: (None, application[field]) for field in ApplicationFields.model_fields},
        )
        return application


@router.get("/{application_id}", response_model=Application)
def get_application(application_id: int, connection: Database, actor: CurrentActor):
    return find_application(connection, application_id, actor)


@router.get("/{application_id}/events", response_model=list[ApplicationEvent])
def get_events(
    application_id: int, connection: Database, actor: CurrentActor,
    after_id: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    find_application(connection, application_id, actor)
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT * FROM application_events WHERE application_id = %s AND id > %s ORDER BY id LIMIT %s",
            (application_id, after_id, limit),
        )
        return cursor.fetchall()


@router.patch("/{application_id}", response_model=Application)
def update_application(application_id: int, fields: ApplicationFields, connection: Database, actor: CurrentActor):
    require_client(actor)
    with connection.transaction():
        application = find_application(connection, application_id, actor, lock=True)
        require_draft(application)
        values = fields.model_dump(exclude_unset=True)
        values = {field: value for field, value in values.items() if value != application[field]}
        if not values:
            return application
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    "UPDATE applications SET {}, updated_at = clock_timestamp(), version = version + 1 "
                    "WHERE id = %s RETURNING *"
                ).format(
                    sql.SQL(", ").join(
                        sql.SQL("{} = %s").format(sql.Identifier(field)) for field in values
                    )
                ),
                [*values.values(), application_id],
            )
            updated = cursor.fetchone()
            record_event(
                connection, updated, actor, "DRAFT_UPDATED", application["status"],
                {field: (application[field], updated[field]) for field in values},
            )
            return updated


@router.post("/{application_id}/submit", response_model=Application)
def submit_application(application_id: int, connection: Database, actor: CurrentActor):
    require_client(actor)
    with connection.transaction():
        application = find_application(connection, application_id, actor, lock=True)
        require_draft(application)
        try:
            fields = SubmissionFields.model_validate(
                {field: application[field] for field in ApplicationFields.model_fields}
            )
        except ValidationError as error:
            raise HTTPException(
                status_code=422,
                detail=[
                    {"loc": ["body", *item["loc"]], "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()
                ],
            ) from error
        product = submission_product(connection, fields.product_code, fields.amount, fields.term)
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "UPDATE applications SET status = 'SUBMITTED', product_version = %s, "
                "updated_at = clock_timestamp(), version = version + 1 "
                "WHERE id = %s RETURNING *",
                (product["version"], application_id),
            )
            submitted = cursor.fetchone()
            record_event(
                connection, submitted, actor, "SUBMITTED", application["status"],
                {"product_version": (application["product_version"], submitted["product_version"])},
            )
            return submitted
