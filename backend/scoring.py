"""Transparent teaching score and separate lending policy. No real credit advice."""

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, localcontext

from ml.inference import predict

D = Decimal


def payment(amount, term, annual_rate):
    with localcontext() as context:
        context.prec = 50
        r = D(annual_rate) / 12
        return D(amount) / term if not r else D(amount) * r / (1 - (1 + r) ** -term)


def money(value):
    return str(value.quantize(D("0.01"), rounding=ROUND_HALF_UP))


def assess(fields, product, registry, bki, *, amount=None):
    with localcontext() as context:
        context.prec = 50
        amount = D(amount if amount is not None else fields["amount"])
        revenue, expenses, debt = (
            D(fields[f])
            for f in (
                "monthly_revenue",
                "monthly_operating_expenses",
                "existing_monthly_debt_payments",
            )
        )
        monthly = payment(amount, fields["term"], product["annual_rate"])
        dscr = (revenue - expenses) / (debt + monthly)
        margin = (revenue - expenses) / revenue
        age, overdue = registry["business_age_months"], bki["max_overdue_days"]
        factors = [
            dict(
                code="dscr",
                label="Покрытие платежей",
                value=str(dscr),
                points=(
                    40
                    if dscr >= D("1.5")
                    else 30 if dscr >= D("1.2") else 15 if dscr >= 1 else 0
                ),
                maximum=40,
            ),
            dict(
                code="age",
                label="Возраст бизнеса",
                value=str(age),
                points=15 if age >= 24 else 10 if age >= 12 else 5 if age >= 6 else 0,
                maximum=15,
            ),
            dict(
                code="margin",
                label="Операционная маржа",
                value=str(margin),
                points=20 if margin >= D(".20") else 10 if margin >= D(".10") else 0,
                maximum=20,
            ),
            dict(
                code="overdue",
                label="Платёжная дисциплина",
                value=str(overdue),
                points=25 if overdue == 0 else 10 if overdue <= 30 else 0,
                maximum=25,
            ),
        ]
        score = sum(f["points"] for f in factors)
        risk = "LOW" if score >= 75 else "MEDIUM" if score >= 50 else "HIGH"
        blockers = []
        if not registry["registration_active"]:
            blockers.append("Регистрация компании неактивна")
        if overdue > 90:
            blockers.append("Просрочка более 90 дней")
        if dscr < D("1.2"):
            blockers.append(
                "Денежного остатка недостаточно: покрытие платежей ниже 1,20"
            )
        if risk == "HIGH":
            blockers.append("Высокий риск по учебной балльной модели")
        eligible = not blockers
        ml = predict(dscr, margin, age, overdue)
        return dict(
            score_version="score_v1",
            policy_version="policy_v1",
            score=score,
            risk=risk,
            factors=factors,
            monthly_payment=money(monthly),
            dscr=str(dscr),
            margin=str(margin),
            amount=money(amount),
            term=fields["term"],
            annual_rate=str(product["annual_rate"]),
            eligible=eligible,
            blockers=blockers,
            recommendation="OFFER" if eligible else "REVIEW",
            ml=ml,
        )


def alternative(fields, product, registry, bki):
    with localcontext() as context:
        context.prec = 50
        available = (
            D(fields["monthly_revenue"]) - D(fields["monthly_operating_expenses"])
        ) / D("1.2") - D(fields["existing_monthly_debt_payments"])
        amount = (
            available / payment(D(1), fields["term"], product["annual_rate"])
        ).quantize(D(".01"), rounding=ROUND_FLOOR)
        amount = min(amount, D(fields["amount"]), D(product["max_amount"]))
        if amount < D(product["min_amount"]) or amount >= D(fields["amount"]):
            return None
        result = assess(fields, product, registry, bki, amount=amount)
        return result if result["eligible"] else None
