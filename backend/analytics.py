from fastapi import APIRouter

from auth import CurrentActor, Database, Role
from workflow import json_safe, role_required, row, rows
from ml.inference import artifact
import json
from pathlib import Path

router = APIRouter(tags=["analytics"])


@router.get("/api/bank/analytics")
def analytics(connection: Database, actor: CurrentActor):
    role_required(actor, Role.BANK_EMPLOYEE)
    connection.commit()
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        counts = rows(
            connection,
            "SELECT status,count(*)::int AS count FROM applications WHERE status<>'DRAFT' GROUP BY status",
        )
        totals = row(
            connection,
            """SELECT count(*)::int AS total,
            count(*) FILTER (WHERE status NOT IN ('DISBURSED','REJECTED'))::int AS active,
            count(*) FILTER (WHERE status NOT IN ('DISBURSED','REJECTED') AND updated_at < clock_timestamp()-interval '24 hours')::int AS delayed
            FROM applications WHERE status<>'DRAFT'""",
        )
        funnel = rows(
            connection,
            """SELECT new_status AS status,count(DISTINCT application_id)::int AS count
            FROM application_events WHERE new_status IN ('SUBMITTED','UNDER_REVIEW','OFFERED','SIGNED','DISBURSED') GROUP BY new_status""",
        )
        bottlenecks = rows(
            connection,
            """SELECT status,reason_code,count(*)::int AS count,
            extract(epoch FROM (clock_timestamp()-min(updated_at)))/3600 AS oldest_hours
            FROM (
              SELECT a.status,a.updated_at,CASE
                WHEN a.status='NEEDS_INFO' THEN 'CLIENT_REPLY'
                WHEN a.status='OFFERED' THEN 'CLIENT_SIGNATURE'
                WHEN a.status='SIGNED' THEN 'BANK_DISBURSEMENT'
                WHEN a.status='SUBMITTED' THEN 'CHECKS_NOT_STARTED'
                WHEN a.status='CHECKING' AND r.state='FAILED' THEN 'CHECKS_FAILED'
                WHEN a.status='CHECKING' THEN 'CHECKS_RUNNING'
                WHEN a.status='UNDER_REVIEW' AND r.state='INCOMPLETE' THEN 'DATA_INCOMPLETE'
                ELSE 'BANK_DECISION' END AS reason_code
              FROM applications a LEFT JOIN LATERAL (
                SELECT state FROM processing_runs WHERE application_id=a.id ORDER BY id DESC LIMIT 1
              ) r ON true WHERE a.status NOT IN ('DRAFT','DISBURSED','REJECTED')
            ) pending GROUP BY status,reason_code ORDER BY count(*) DESC""",
        )
        decisions = rows(
            connection,
            """SELECT d.id,d.application_id,a.company_name,d.kind,d.reason_code,d.explanation,d.terms,d.created_at,u.login AS actor
            FROM decisions d JOIN applications a ON a.id=d.application_id JOIN users u ON u.id=d.actor_id
            ORDER BY d.created_at DESC LIMIT 20""",
        )
        reasons = rows(
            connection,
            "SELECT reason_code,count(*)::int AS count FROM decisions GROUP BY reason_code ORDER BY count(*) DESC",
        )
        issued = row(
            connection,
            "SELECT coalesce(sum(amount),0) AS amount FROM simulated_disbursements",
        )
        return json_safe(
            dict(
                **totals,
                counts=counts,
                funnel=funnel,
                bottlenecks=bottlenecks,
                decisions=decisions,
                reasons=reasons,
                issued_amount=issued["amount"],
                delay_threshold_hours=24
            )
        )


@router.get("/api/bank/model")
def model_card(actor: CurrentActor):
    role_required(actor, Role.BANK_EMPLOYEE)
    model = artifact()
    report = json.loads((Path(__file__).parent / "ml" / "metrics.json").read_text())
    return dict(
        model_version=model["model_version"],
        target=model["target"],
        report=report,
        features=[
            "Покрытие платежей",
            "Операционная маржа",
            "Возраст бизнеса",
            "Максимальная просрочка",
        ],
        limitation="Модель обучена только на синтетических компаниях. Метрики не подтверждают качество на реальных заёмщиках. ML не принимает кредитное решение.",
    )
