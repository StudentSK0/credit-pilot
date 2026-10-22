"""Read the versioned, synthetic teaching-product catalogue."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from auth import CurrentActor, Database


class CreditProduct(BaseModel):
    code: str
    version: str
    name: str
    currency: str
    min_amount: Decimal
    max_amount: Decimal
    min_term: int
    max_term: int
    annual_rate: Decimal


router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[CreditProduct], responses={401: {"description": "Authentication required"}})
def get_products(connection: Database, actor: CurrentActor):
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM credit_products WHERE is_active ORDER BY code")
        return cursor.fetchall()


def submission_product(connection, code, amount, term):
    # Keep the selected version active until the application's transaction commits.
    # Published terms are immutable in the database, including after retirement.
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            "SELECT * FROM credit_products WHERE code = %s AND is_active FOR SHARE",
            (code,),
        )
        product = cursor.fetchone()
    errors = []
    if product is None:
        errors.append({"loc": ["body", "product_code"], "msg": "An active credit product is required", "type": "value_error"})
    else:
        if not product["min_amount"] <= amount <= product["max_amount"]:
            errors.append({
                "loc": ["body", "amount"],
                "msg": f"Amount must be between {product['min_amount']} and {product['max_amount']} RUB",
                "type": "value_error",
            })
        if not product["min_term"] <= term <= product["max_term"]:
            errors.append({
                "loc": ["body", "term"],
                "msg": f"Term must be between {product['min_term']} and {product['max_term']} months",
                "type": "value_error",
            })
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    return product
