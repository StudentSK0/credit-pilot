"""Local synthetic source fixtures. Unknown INN never means a positive check."""

from pydantic import BaseModel, ConfigDict, Field


class RegistryRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    legal_name: str = Field(min_length=1)
    registration_active: bool
    business_age_months: int = Field(ge=0, le=1200)


class CreditHistoryRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    max_overdue_days: int = Field(ge=0, le=36500)


FIXTURE_VERSION = "synthetic_sources_v1"
COMPANIES = {
    "7700000001": dict(
        legal_name="ООО «Северная пекарня»",
        registration_active=True,
        business_age_months=48,
        max_overdue_days=0,
    ),
    "7700000002": dict(
        legal_name="ООО «Мастерская формы»",
        registration_active=True,
        business_age_months=36,
        max_overdue_days=0,
    ),
    "7700000003": dict(
        legal_name="ООО «Вектор логистики»",
        registration_active=True,
        business_age_months=18,
        max_overdue_days=65,
    ),
    "7700000004": dict(
        legal_name="ООО «Линия света»",
        registration_active=True,
        business_age_months=60,
        max_overdue_days=0,
    ),
    "7700000005": dict(
        legal_name="ООО «Архив»",
        registration_active=False,
        business_age_months=30,
        max_overdue_days=0,
    ),
    "1234567890": dict(
        legal_name="Demo client-a",
        registration_active=True,
        business_age_months=36,
        max_overdue_days=0,
    ),
    "123456789012": dict(
        legal_name="Demo client-b",
        registration_active=True,
        business_age_months=24,
        max_overdue_days=10,
    ),
}


def lookup(inn):
    if inn == "7700000099":
        raise TimeoutError("Synthetic source outage")
    fixture = COMPANIES.get(inn)
    if fixture is None:
        return None, None
    return (
        {
            key: fixture[key]
            for key in ("legal_name", "registration_active", "business_age_months")
        },
        {"max_overdue_days": fixture["max_overdue_days"]},
    )
