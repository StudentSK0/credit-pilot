import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.routing import APIRoute
from psycopg import Connection, sql
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from database import get_connection


class DecimalJSONRequest(Request):
    async def json(self):
        # Preserve decimal JSON numbers before Pydantic sees them.
        if not hasattr(self, "_json"):
            self._json = json.loads(await self.body(), parse_float=Decimal)
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

    @field_validator("amount", "term", mode="before")
    @classmethod
    def empty_number(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("amount")
    @classmethod
    def exact_amount(cls, value):
        if value is not None and value.as_tuple().exponent < -2:
            raise ValueError("Amount must have at most two decimal places")
        return value


class SubmissionFields(ApplicationFields):
    company_name: Annotated[str, Field(min_length=1, max_length=255)]
    inn: Annotated[str, Field(pattern=r"^[0-9]{10}([0-9]{2})?$")]
    credit_purpose: Annotated[str, Field(min_length=1, max_length=1000)]
    amount: Annotated[Decimal, Field(gt=0)]
    term: Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]

    @field_validator("company_name", "credit_purpose")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Field must not contain only whitespace")
        return value


class Application(ApplicationFields):
    id: int
    status: Status
    created_at: datetime
    updated_at: datetime


router = APIRouter(prefix="/api/applications", tags=["applications"], route_class=DecimalJSONRoute)
Database = Annotated[Connection, Depends(get_connection)]


def find_application(connection: Connection, application_id: int, *, lock=False):
    if not -(2**63) <= application_id < 2**63:
        raise HTTPException(status_code=404, detail="Application not found")
    query = "SELECT * FROM applications WHERE id = %s"
    if lock:
        query += " FOR UPDATE"
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, (application_id,))
        application = cursor.fetchone()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def require_draft(application):
    if application["status"] != Status.DRAFT:
        raise HTTPException(status_code=409, detail="Application is not a draft")


@router.post("", response_model=Application, status_code=201)
def create_application(fields: ApplicationFields, connection: Database):
    values = fields.model_dump()
    with connection.transaction(), connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            sql.SQL("INSERT INTO applications ({}) VALUES ({}) RETURNING *").format(
                sql.SQL(", ").join(map(sql.Identifier, values)),
                sql.SQL(", ").join(sql.Placeholder() for _ in values),
            ),
            list(values.values()),
        )
        return cursor.fetchone()


@router.get("/{application_id}", response_model=Application)
def get_application(application_id: int, connection: Database):
    return find_application(connection, application_id)


@router.patch("/{application_id}", response_model=Application)
def update_application(application_id: int, fields: ApplicationFields, connection: Database):
    with connection.transaction():
        application = find_application(connection, application_id, lock=True)
        require_draft(application)
        values = fields.model_dump(exclude_unset=True)
        if not values:
            return application
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL(
                    "UPDATE applications SET {}, updated_at = clock_timestamp() "
                    "WHERE id = %s RETURNING *"
                ).format(
                    sql.SQL(", ").join(
                        sql.SQL("{} = %s").format(sql.Identifier(field)) for field in values
                    )
                ),
                [*values.values(), application_id],
            )
            return cursor.fetchone()


@router.post("/{application_id}/submit", response_model=Application)
def submit_application(application_id: int, connection: Database):
    with connection.transaction():
        application = find_application(connection, application_id, lock=True)
        require_draft(application)
        try:
            SubmissionFields.model_validate(
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
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "UPDATE applications SET status = 'SUBMITTED', updated_at = clock_timestamp() "
                "WHERE id = %s RETURNING *",
                (application_id,),
            )
            return cursor.fetchone()
