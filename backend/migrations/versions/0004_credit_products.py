"""Versioned teaching products and nullable application financial data."""

from alembic import op
import sqlalchemy as sa

revision = "0004_credit_products"
down_revision = "0003_application_owner"
branch_labels = None
depends_on = None

FINANCIAL_FIELDS = (
    "monthly_revenue",
    "monthly_operating_expenses",
    "existing_monthly_debt_payments",
)


def exact_money(column):
    return (
        f"scale({column}) <= 2 AND "
        f"{column} NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)"
    )


def upgrade():
    op.create_table(
        "credit_products",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        # No fixed scale: reject excess decimal places rather than round silently.
        sa.Column("min_amount", sa.Numeric(), nullable=False),
        sa.Column("max_amount", sa.Numeric(), nullable=False),
        sa.Column("min_term", sa.BigInteger(), nullable=False),
        sa.Column("max_term", sa.BigInteger(), nullable=False),
        sa.Column("annual_rate", sa.Numeric(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("currency = 'RUB'", name="credit_product_currency"),
        sa.CheckConstraint(exact_money("min_amount"), name="credit_product_min_amount_precision"),
        sa.CheckConstraint(exact_money("max_amount"), name="credit_product_max_amount_precision"),
        sa.CheckConstraint("min_amount > 0 AND max_amount >= min_amount", name="credit_product_amount_bounds"),
        sa.CheckConstraint("min_term > 0 AND max_term >= min_term", name="credit_product_term_bounds"),
        sa.CheckConstraint(
            "annual_rate >= 0 AND annual_rate NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)",
            name="credit_product_rate",
        ),
    )
    op.create_index("credit_products_active_code", "credit_products", ["code"], unique=True, postgresql_where=sa.text("is_active"))
    # Team-proposed synthetic conditions from docs/architecture.md, not bank offers.
    op.execute("""
        INSERT INTO credit_products
            (code, version, name, currency, min_amount, max_amount, min_term, max_term, annual_rate)
        VALUES
            ('WORKING_CAPITAL', 'product_v1', 'Пополнение оборотных средств', 'RUB', 50000, 3000000, 3, 24, 0.20),
            ('EQUIPMENT', 'product_v1', 'Приобретение оборудования', 'RUB', 100000, 5000000, 6, 36, 0.18)
    """)
    op.execute("""
        CREATE FUNCTION protect_credit_product_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Published product versions cannot be deleted' USING ERRCODE = '23514';
            END IF;
            IF (to_jsonb(NEW) - 'is_active') IS DISTINCT FROM (to_jsonb(OLD) - 'is_active') THEN
                RAISE EXCEPTION 'Product terms are immutable; insert a new version' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER credit_product_version_immutable BEFORE UPDATE OR DELETE ON credit_products
        FOR EACH ROW EXECUTE FUNCTION protect_credit_product_version()
    """)
    op.add_column("applications", sa.Column("product_code", sa.String(64)))
    op.add_column("applications", sa.Column("product_version", sa.String(32)))
    op.create_foreign_key(
        "application_product_fk", "applications", "credit_products",
        ["product_code", "product_version"], ["code", "version"],
    )
    op.create_check_constraint(
        "application_product_version", "applications",
        "product_version IS NULL OR (product_code IS NOT NULL AND status <> 'DRAFT')",
    )
    for field in FINANCIAL_FIELDS:
        op.add_column("applications", sa.Column(field, sa.Numeric()))
        op.create_check_constraint(f"application_{field}_precision", "applications", exact_money(field))
    # No backfill: neither a product nor financial values are known for legacy rows.


def downgrade():
    for field in reversed(FINANCIAL_FIELDS):
        op.drop_constraint(f"application_{field}_precision", "applications", type_="check")
        op.drop_column("applications", field)
    op.drop_constraint("application_product_version", "applications", type_="check")
    op.drop_constraint("application_product_fk", "applications", type_="foreignkey")
    op.drop_column("applications", "product_version")
    op.drop_column("applications", "product_code")
    op.drop_table("credit_products")
    op.execute("DROP FUNCTION protect_credit_product_version()")
