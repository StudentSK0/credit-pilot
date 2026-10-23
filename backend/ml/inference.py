import json
import math
from functools import lru_cache
from pathlib import Path

FEATURE_NAMES = ["dscr", "margin", "business_age_months", "max_overdue_days"]
FEATURE_LABELS = [
    "Покрытие платежей",
    "Операционная маржа",
    "Возраст бизнеса",
    "Просрочки",
]


def features(dscr, margin, age, overdue):
    # Floats are used only for statistical inference, never for money/policy.
    return [
        max(-2.0, min(5.0, float(dscr))),
        max(-1.0, min(0.8, float(margin))),
        min(120.0, float(age)) / 12,
        min(180.0, float(overdue)) / 30,
    ]


@lru_cache(maxsize=1)
def artifact():
    return json.loads(Path(__file__).with_name("model.json").read_text())


def predict(dscr, margin, age, overdue):
    model = artifact()
    values = features(dscr, margin, age, overdue)
    terms = [
        coef * (x - mean) / scale
        for x, mean, scale, coef in zip(
            values, model["means"], model["scales"], model["coefficients"]
        )
    ]
    z = model["intercept"] + sum(terms)
    probability = 1 / (1 + math.exp(-max(-40, min(40, z))))
    return dict(
        model_version=model["model_version"],
        feature_version="features_v1",
        probability=round(probability, 6),
        intercept=model["intercept"],
        target=model["target"],
        synthetic=True,
        factors=[
            dict(code=code, label=label, value=value, contribution=round(term, 6))
            for code, label, value, term in zip(
                FEATURE_NAMES, FEATURE_LABELS, values, terms
            )
        ],
    )
