"""Four reproducible fictional cases and a small local contextual feed."""

from fastapi import APIRouter

from auth import CurrentActor, Database, require_client
from fixtures import COMPANIES
from workflow import rows

router = APIRouter(tags=["demo"])

SCENARIOS = [
    dict(
        code="growth",
        title="Пекарня открывает вторую точку",
        label="Предложение и выдача",
        description="Устойчивый денежный поток, чистая кредитная история. Пройдите путь до демонстрационной выдачи.",
        inn="7700000001",
        amount="600000.00",
        term=18,
        product_code="WORKING_CAPITAL",
        credit_purpose="Закупка сырья и запуск второй пекарни",
        monthly_revenue="450000.00",
        monthly_operating_expenses="300000.00",
        existing_monthly_debt_payments="15000.00",
    ),
    dict(
        code="clarification",
        title="Мастерская уточняет расходы",
        label="Запрос документа",
        description="В расходы включили разовую покупку. Запросите отчёт и уточнение: регулярные расходы — 400 000 ₽ в месяц.",
        inn="7700000002",
        amount="900000.00",
        term=24,
        product_code="EQUIPMENT",
        credit_purpose="Покупка станка. В расходах пока учтена разовая закупка оборудования.",
        monthly_revenue="600000.00",
        monthly_operating_expenses="540000.00",
        existing_monthly_debt_payments="10000.00",
    ),
    dict(
        code="risk",
        title="Логистика с высокой нагрузкой",
        label="Обоснованный отказ",
        description="Просрочка 65 дней и недостаточный денежный остаток. Рассмотрите факторы и объясните решение клиенту.",
        inn="7700000003",
        amount="800000.00",
        term=18,
        product_code="WORKING_CAPITAL",
        credit_purpose="Пополнение оборотных средств для исполнения заказов",
        monthly_revenue="350000.00",
        monthly_operating_expenses="315000.00",
        existing_monthly_debt_payments="50000.00",
    ),
    dict(
        code="counter",
        title="Магазин выбирает посильную сумму",
        label="Встречное предложение",
        description="Исходная сумма создаёт высокую нагрузку. Проверьте рассчитанную альтернативу и предложите меньший кредит.",
        inn="7700000004",
        amount="1500000.00",
        term=24,
        product_code="WORKING_CAPITAL",
        credit_purpose="Расширение ассортимента освещения",
        monthly_revenue="300000.00",
        monthly_operating_expenses="240000.00",
        existing_monthly_debt_payments="10000.00",
    ),
]


def scenario_fields(scenario):
    return {
        **{
            key: value
            for key, value in scenario.items()
            if key not in {"code", "title", "label", "description"}
        },
        "company_name": COMPANIES[scenario["inn"]]["legal_name"],
    }


@router.get("/api/demo-scenarios")
def scenarios(actor: CurrentActor):
    require_client(actor)
    return [
        dict(
            code=s["code"],
            title=s["title"],
            label=s["label"],
            description=s["description"],
            fields=scenario_fields(s),
        )
        for s in SCENARIOS
    ]


@router.get("/api/feed")
def feed(connection: Database, actor: CurrentActor):
    require_client(actor)
    applications = rows(
        connection,
        "SELECT status,product_code FROM applications WHERE owner_id=%s ORDER BY updated_at DESC LIMIT 20",
        (actor.id,),
    )
    needs = any(a["status"] == "NEEDS_INFO" for a in applications)
    equipment = any(a["product_code"] == "EQUIPMENT" for a in applications)
    offered = any(a["status"] in {"OFFERED", "SIGNED"} for a in applications)
    return [
        dict(
            id="next-step",
            tag="ВАШ СЛЕДУЮЩИЙ ШАГ",
            title=(
                "Как ответить на запрос банка"
                if needs
                else (
                    "Как читать кредитное предложение"
                    if offered
                    else "Подготовьте цифры за обычный месяц"
                )
            ),
            body=(
                "Откройте заявку со статусом «Нужны сведения». В запросе указаны конкретные поля и документ. Ответ сохранится в истории, после чего сотрудник выполнит новую проверку."
                if needs
                else (
                    "Сравните исходную и предложенную суммы, срок и ежемесячный платёж. Встречное предложение не меняет вашу исходную заявку. В демо подписание и выдача моделируются."
                    if offered
                    else "Укажите выручку, регулярные операционные расходы и платежи по существующим долгам за один и тот же месяц. Разовые покупки поясните отдельно. Это помогает оценить запас для нового платежа."
                )
            ),
        ),
        dict(
            id="product-guide",
            tag="ГИД ПО ПРОДУКТУ",
            title=(
                "Покупка оборудования: что подготовить"
                if equipment
                else "Оборотные средства без лишней нагрузки"
            ),
            body=(
                "Опишите оборудование и его назначение. Сотрудник может запросить синтетическую спецификацию или пояснение расходов. Оценка опирается на денежный остаток и существующие платежи."
                if equipment
                else "Опишите, для каких закупок или заказов нужны средства. Сопоставьте новый платёж с остатком после операционных расходов и текущих долгов. Слишком большая сумма может привести к встречному предложению."
            ),
        ),
        dict(
            id="risk-guide",
            tag="ПОНЯТНО О ФИНАНСАХ",
            title="Что означает покрытие платежей",
            body="Покрытие платежей (DSCR) — отношение выручки за вычетом операционных расходов ко всем платежам по долгам, включая новый кредит. Значение 1 означает отсутствие запаса. В учебной политике предложения нужен коэффициент не ниже 1,20. Это правило команды, не условие банка.",
        ),
    ]


def seed_scenarios(connection):
    from applications import ApplicationFields, create_application, submit_application
    from auth import Actor, Role
    from workflow import row

    owner = row(connection, "SELECT * FROM users WHERE login='client-a'")
    actor = Actor(owner["id"], Role.CLIENT, owner["company_id"])
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(71206501)")
        for scenario in SCENARIOS:
            if row(
                connection,
                "SELECT application_id FROM demo_scenarios WHERE owner_id=%s AND code=%s",
                (actor.id, scenario["code"]),
            ):
                continue
            application = create_application(
                ApplicationFields(**scenario_fields(scenario)), connection, actor
            )
            submit_application(application["id"], connection, actor)
            connection.execute(
                "INSERT INTO demo_scenarios (owner_id,code,application_id) VALUES (%s,%s,%s)",
                (actor.id, scenario["code"], application["id"]),
            )


if __name__ == "__main__":
    import psycopg
    from database import connection_parameters
    from seed import seed_demo

    with psycopg.connect(**connection_parameters()) as connection:
        seed_demo(connection)
        seed_scenarios(connection)
    print("Four synthetic scenarios ready. Existing applications preserved.")
