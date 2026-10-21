"""Application history and minimal local ownership/session support."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_application_events"
down_revision = "0001_applications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("inn", sa.Text(), nullable=False, unique=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("login", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id")),
        sa.CheckConstraint(
            "(role = 'CLIENT' AND company_id IS NOT NULL) OR (role = 'BANK' AND company_id IS NULL)",
            name="user_role_company",
        ),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Existing records stay unassigned: never infer an owner or fabricate old events.
    op.add_column("applications", sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id", name="application_company_fk")))
    op.add_column("applications", sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", name="application_creator_fk")))
    op.add_column("applications", sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"))
    op.create_table(
        "application_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("previous_status", sa.String(9)),
        sa.Column("new_status", sa.String(9), nullable=False),
        sa.Column("application_version", sa.BigInteger(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("event_type IN ('DRAFT_CREATED', 'DRAFT_UPDATED', 'SUBMITTED')", name="application_event_type"),
        sa.UniqueConstraint("application_id", "application_version", name="application_event_version"),
    )
    op.create_index("application_events_order", "application_events", ["application_id", "id"])
    op.create_index("applications_company", "applications", ["company_id"])


def downgrade():
    op.drop_table("application_events")
    op.drop_index("applications_company", table_name="applications")
    op.drop_column("applications", "version")
    op.drop_column("applications", "created_by")
    op.drop_column("applications", "company_id")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("companies")
