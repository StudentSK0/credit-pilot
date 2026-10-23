from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel

from auth import Actor


class ApplicationEvent(BaseModel):
    id: int
    application_id: int
    event_type: Literal[
        "DRAFT_CREATED",
        "DRAFT_UPDATED",
        "SUBMITTED",
        "CHECKS_STARTED",
        "CHECKS_COMPLETED",
        "CHECKS_FAILED",
        "INFORMATION_REQUESTED",
        "INFORMATION_PROVIDED",
        "OFFER_ISSUED",
        "REJECTED",
        "SIGNED_SIMULATED",
        "DISBURSED_SIMULATED",
    ]
    occurred_at: datetime
    actor_id: int
    actor_role: str
    previous_status: str | None
    new_status: str
    application_version: int
    changes: dict[str, Any]


def json_value(value):
    return str(value) if isinstance(value, Decimal) else value


def record_event(
    connection, application, actor: Actor, event_type, previous_status, changes
):
    # Explicit business-field payload only: never serialize requests, headers or sessions.
    payload = {
        name: {"old": json_value(old), "new": json_value(new)}
        for name, (old, new) in changes.items()
    }
    connection.execute(
        "INSERT INTO application_events "
        "(application_id, event_type, actor_id, actor_role, previous_status, new_status, "
        "application_version, changes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            application["id"],
            event_type,
            actor.id,
            actor.role,
            previous_status,
            application["status"],
            application["version"],
            Jsonb(payload),
        ),
    )
