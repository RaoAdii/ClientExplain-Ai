"""Persist safe terminal intent independently of a locked generation_jobs row."""

import sqlalchemy as sa
from alembic import op

revision = "d14c3a7f2901"
down_revision = "a27d9c4e8b11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_recoveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "firm_id", sa.Uuid(), sa.ForeignKey("firms.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("error_code", sa.String(60), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "firm_id", "project_id", "job_id", "attempt_id", name="uq_job_recoveries_attempt"
        ),
        sa.CheckConstraint(
            "error_code IN ('timeout','database_unavailable','job_failed')",
            name="ck_job_recoveries_safe_code",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_job_recoveries_retry_count"),
    )
    op.create_index("ix_job_recoveries_firm_id", "job_recoveries", ["firm_id"])
    op.create_index("ix_job_recoveries_job", "job_recoveries", ["job_id", "firm_id", "project_id"])
    op.execute(
        "CREATE TRIGGER update_timestamp BEFORE UPDATE ON job_recoveries FOR EACH ROW EXECUTE FUNCTION touch_updated_at()"
    )
    op.execute("ALTER TABLE job_recoveries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job_recoveries FORCE ROW LEVEL SECURITY")
    firm = "NULLIF(current_setting('app.firm_id', true), '')::uuid"
    op.execute(
        f"CREATE POLICY tenant_access ON job_recoveries USING (firm_id = {firm}) WITH CHECK (firm_id = {firm})"
    )


def downgrade():
    # The table owner must see every tenant's pending intent before deciding
    # that dropping this recovery queue is safe. ALTER holds the table lock.
    op.execute("ALTER TABLE job_recoveries NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT FROM job_recoveries) THEN
            RAISE EXCEPTION 'Pending job recovery intents must be reconciled before downgrade.';
        END IF;
    END $$""")
    op.drop_table("job_recoveries")
