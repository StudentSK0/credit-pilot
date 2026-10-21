"""Persist credit application drafts and submitted applications."""

from alembic import op
import sqlalchemy as sa

revision = "0001_applications"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "applications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("company_name", sa.String(255)),
        sa.Column("inn", sa.Text()),
        sa.Column("credit_purpose", sa.String(1000)),
        # Unconstrained NUMERIC avoids PostgreSQL silently rounding to a fixed scale.
        sa.Column("amount", sa.Numeric()),
        sa.Column("term", sa.BigInteger()),
        sa.Column("status", sa.String(9), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.CheckConstraint("status IN ('DRAFT', 'SUBMITTED')", name="application_status"),
        sa.CheckConstraint("scale(amount) <= 2 AND amount NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)", name="application_amount_precision"),
    )


def downgrade():
    op.drop_table("applications")
