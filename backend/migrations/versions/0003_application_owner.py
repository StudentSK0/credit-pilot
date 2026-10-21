"""Use explicit user ownership and the BANK_EMPLOYEE role."""

from alembic import op
import sqlalchemy as sa

revision = "0003_application_owner"
down_revision = "0002_application_events"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "applications",
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", name="application_owner_fk")),
    )
    # Only migrate a previously recorded, server-assigned client author.
    # Unassigned legacy rows remain unassigned; company membership is not ownership.
    op.execute(
        "UPDATE applications a SET owner_id = a.created_by "
        "FROM users u WHERE u.id = a.created_by AND u.role = 'CLIENT'"
    )
    op.create_index("applications_owner", "applications", ["owner_id"])
    op.drop_constraint("user_role_company", "users", type_="check")
    op.execute("UPDATE users SET role = 'BANK_EMPLOYEE' WHERE role = 'BANK'")
    op.create_check_constraint(
        "user_role_company", "users",
        "(role = 'CLIENT' AND company_id IS NOT NULL) "
        "OR (role = 'BANK_EMPLOYEE' AND company_id IS NULL)",
    )


def downgrade():
    op.drop_constraint("user_role_company", "users", type_="check")
    op.execute("UPDATE users SET role = 'BANK' WHERE role = 'BANK_EMPLOYEE'")
    op.create_check_constraint(
        "user_role_company", "users",
        "(role = 'CLIENT' AND company_id IS NOT NULL) OR (role = 'BANK' AND company_id IS NULL)",
    )
    op.drop_index("applications_owner", table_name="applications")
    op.drop_column("applications", "owner_id")
