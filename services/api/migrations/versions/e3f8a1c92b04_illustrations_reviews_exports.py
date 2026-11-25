"""Add stage-linked illustrations, project review history, and export metadata."""

import sqlalchemy as sa
from alembic import op

revision = "e3f8a1c92b04"
down_revision = "d14c3a7f2901"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("generated_assets", sa.Column("stage_id", sa.Uuid(), nullable=True))
    op.add_column(
        "generated_assets",
        sa.Column("media_type", sa.String(80), nullable=False, server_default="image/svg+xml"),
    )
    op.add_column(
        "generated_assets",
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
    )
    op.add_column("generated_assets", sa.Column("error_message", sa.String(300), nullable=True))
    op.create_foreign_key(
        "fk_generated_assets_stage",
        "generated_assets",
        "process_stages",
        ["stage_id", "project_id", "firm_id"],
        ["id", "project_id", "firm_id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_generated_assets_status",
        "generated_assets",
        "status IN ('queued','running','completed','failed')",
    )
    op.create_index(
        "ix_generated_assets_stage", "generated_assets", ["firm_id", "project_id", "stage_id"]
    )

    op.add_column(
        "exports",
        sa.Column("project_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "exports",
        sa.Column("filename", sa.String(255), nullable=False, server_default="workflow-export"),
    )

    op.create_table(
        "project_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "firm_id", sa.Uuid(), sa.ForeignKey("firms.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=True),
        sa.Column(
            "reviewer_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewer_name", sa.String(120), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "firm_id"],
            ["projects.id", "projects.firm_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id", "project_id", "firm_id"],
            ["process_stages.id", "process_stages.project_id", "process_stages.firm_id"],
            ondelete="SET NULL (stage_id)",
        ),
        sa.CheckConstraint(
            "decision IN ('comment','in_review','approved','changes_requested','rejected')",
            name="ck_project_reviews_decision",
        ),
        sa.UniqueConstraint("id", "firm_id"),
    )
    op.create_index("ix_project_reviews_firm_id", "project_reviews", ["firm_id"])
    op.create_index("ix_project_reviews_project_id", "project_reviews", ["project_id"])
    op.create_index(
        "ix_project_reviews_project_created",
        "project_reviews",
        ["firm_id", "project_id", "created_at"],
    )
    op.execute(
        "CREATE TRIGGER update_timestamp BEFORE UPDATE ON project_reviews FOR EACH ROW EXECUTE FUNCTION touch_updated_at()"
    )
    op.execute("ALTER TABLE project_reviews ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_reviews FORCE ROW LEVEL SECURITY")
    firm = "NULLIF(current_setting('app.firm_id', true), '')::uuid"
    op.execute(
        f"CREATE POLICY tenant_access ON project_reviews USING (firm_id = {firm}) WITH CHECK (firm_id = {firm})"
    )


def downgrade():
    op.execute("DROP POLICY tenant_access ON project_reviews")
    op.execute("ALTER TABLE project_reviews NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_reviews DISABLE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER update_timestamp ON project_reviews")
    op.drop_index("ix_project_reviews_project_created", table_name="project_reviews")
    op.drop_index("ix_project_reviews_project_id", table_name="project_reviews", if_exists=True)
    op.drop_index("ix_project_reviews_firm_id", table_name="project_reviews")
    op.drop_table("project_reviews")

    op.drop_column("exports", "filename")
    op.drop_column("exports", "project_version")

    op.drop_index("ix_generated_assets_stage", table_name="generated_assets")
    op.drop_constraint("ck_generated_assets_status", "generated_assets", type_="check")
    op.drop_constraint("fk_generated_assets_stage", "generated_assets", type_="foreignkey")
    op.drop_column("generated_assets", "error_message")
    op.drop_column("generated_assets", "status")
    op.drop_column("generated_assets", "media_type")
    op.drop_column("generated_assets", "stage_id")
