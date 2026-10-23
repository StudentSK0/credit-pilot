"""Credit workflow, immutable assessments, requests and simulated settlement."""

from alembic import op

revision = "0005_credit_workflow"
down_revision = "0004_credit_products"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE applications DROP CONSTRAINT application_status")
    op.execute("ALTER TABLE applications ALTER COLUMN status TYPE varchar(24)")
    op.execute("""ALTER TABLE applications ADD CONSTRAINT application_status CHECK
        (status IN ('DRAFT','SUBMITTED','CHECKING','UNDER_REVIEW','NEEDS_INFO',
                   'OFFERED','REJECTED','SIGNED','DISBURSED'))""")
    op.execute(
        "ALTER TABLE application_events ALTER COLUMN previous_status TYPE varchar(24)"
    )
    op.execute(
        "ALTER TABLE application_events ALTER COLUMN new_status TYPE varchar(24)"
    )
    op.execute("ALTER TABLE application_events DROP CONSTRAINT application_event_type")
    op.execute(
        """ALTER TABLE application_events ADD CONSTRAINT application_event_type CHECK
        (event_type IN ('DRAFT_CREATED','DRAFT_UPDATED','SUBMITTED','CHECKS_STARTED',
         'CHECKS_COMPLETED','CHECKS_FAILED','INFORMATION_REQUESTED','INFORMATION_PROVIDED',
         'OFFER_ISSUED','REJECTED','SIGNED_SIMULATED','DISBURSED_SIMULATED'))"""
    )
    op.execute(
        "CREATE INDEX applications_queue ON applications(status, updated_at, id)"
    )
    op.execute("""CREATE TABLE processing_runs (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id bigint NOT NULL REFERENCES applications(id),
        command_id uuid NOT NULL,
        state varchar(16) NOT NULL CHECK (state IN ('RUNNING','COMPLETE','INCOMPLETE','FAILED')),
        input_snapshot jsonb NOT NULL,
        product_snapshot jsonb,
        checks jsonb NOT NULL DEFAULT '[]',
        assessment jsonb,
        error_code varchar(64),
        started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        completed_at timestamptz,
        UNIQUE(application_id, command_id)
    )""")
    op.execute(
        "CREATE INDEX processing_runs_application ON processing_runs(application_id, id DESC)"
    )
    op.execute("""CREATE TABLE information_requests (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id bigint NOT NULL REFERENCES applications(id),
        actor_id bigint NOT NULL REFERENCES users(id),
        message text NOT NULL,
        fields jsonb NOT NULL,
        document_kind varchar(64),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        answered_at timestamptz,
        response jsonb
    )""")
    op.execute(
        "CREATE UNIQUE INDEX one_open_request ON information_requests(application_id) WHERE answered_at IS NULL"
    )
    op.execute("""CREATE TABLE application_documents (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id bigint NOT NULL REFERENCES applications(id),
        request_id bigint NOT NULL REFERENCES information_requests(id),
        uploaded_by bigint NOT NULL REFERENCES users(id),
        name varchar(160) NOT NULL,
        content text NOT NULL CHECK (octet_length(content) <= 65536),
        sha256 varchar(64) NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute("""CREATE TABLE decisions (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id bigint NOT NULL UNIQUE REFERENCES applications(id),
        run_id bigint NOT NULL REFERENCES processing_runs(id),
        actor_id bigint NOT NULL REFERENCES users(id),
        kind varchar(8) NOT NULL CHECK (kind IN ('OFFER','REJECT')),
        reason_code varchar(64) NOT NULL,
        explanation text NOT NULL,
        terms jsonb,
        assessment jsonb,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute("""CREATE TABLE simulated_contracts (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id bigint NOT NULL UNIQUE REFERENCES applications(id),
        decision_id bigint NOT NULL UNIQUE REFERENCES decisions(id),
        signed_by bigint NOT NULL REFERENCES users(id),
        document_version varchar(32) NOT NULL,
        document_text text NOT NULL,
        document_sha256 varchar(64) NOT NULL,
        signed_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute("""CREATE TABLE simulated_disbursements (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id bigint NOT NULL UNIQUE REFERENCES applications(id),
        contract_id bigint NOT NULL UNIQUE REFERENCES simulated_contracts(id),
        actor_id bigint NOT NULL REFERENCES users(id),
        amount numeric NOT NULL CHECK (amount > 0 AND scale(amount) <= 2 AND amount NOT IN ('NaN'::numeric,'Infinity'::numeric)),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute("""CREATE TABLE command_receipts (
        application_id bigint NOT NULL REFERENCES applications(id),
        command_id uuid NOT NULL,
        actor_id bigint NOT NULL REFERENCES users(id),
        action varchar(32) NOT NULL,
        request_hash varchar(64) NOT NULL,
        response jsonb NOT NULL,
        PRIMARY KEY(application_id, command_id)
    )""")
    op.execute("""CREATE TABLE demo_scenarios (
        owner_id bigint NOT NULL REFERENCES users(id),
        code varchar(32) NOT NULL,
        application_id bigint NOT NULL UNIQUE REFERENCES applications(id),
        PRIMARY KEY(owner_id, code)
    )""")


def downgrade():
    # Refuse a lossy downgrade if the new workflow has actually been used.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM applications WHERE status NOT IN ('DRAFT','SUBMITTED'))
           OR EXISTS (SELECT 1 FROM processing_runs) THEN
            RAISE EXCEPTION 'Workflow data exists; downgrade would destroy business history';
        END IF;
    END $$""")
    for table in (
        "demo_scenarios",
        "command_receipts",
        "simulated_disbursements",
        "simulated_contracts",
        "decisions",
        "application_documents",
        "information_requests",
        "processing_runs",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP INDEX applications_queue")
    op.execute("ALTER TABLE application_events DROP CONSTRAINT application_event_type")
    op.execute(
        "ALTER TABLE application_events ADD CONSTRAINT application_event_type CHECK (event_type IN ('DRAFT_CREATED','DRAFT_UPDATED','SUBMITTED'))"
    )
    op.execute(
        "ALTER TABLE application_events ALTER COLUMN previous_status TYPE varchar(9)"
    )
    op.execute("ALTER TABLE application_events ALTER COLUMN new_status TYPE varchar(9)")
    op.execute("ALTER TABLE applications DROP CONSTRAINT application_status")
    op.execute("ALTER TABLE applications ALTER COLUMN status TYPE varchar(9)")
    op.execute(
        "ALTER TABLE applications ADD CONSTRAINT application_status CHECK (status IN ('DRAFT','SUBMITTED'))"
    )
