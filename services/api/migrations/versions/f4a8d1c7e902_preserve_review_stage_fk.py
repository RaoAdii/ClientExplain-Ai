"""Preserve review history when a reviewed stage is removed."""

from alembic import op

revision = "f4a8d1c7e902"
down_revision = "e3f8a1c92b04"
branch_labels = None
depends_on = None

CONSTRAINT = "project_reviews_stage_id_project_id_firm_id_fkey"


def upgrade():
    op.drop_constraint(CONSTRAINT, "project_reviews", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT,
        "project_reviews",
        "process_stages",
        ["stage_id", "project_id", "firm_id"],
        ["id", "project_id", "firm_id"],
        ondelete="SET NULL (stage_id)",
    )


def downgrade():
    op.drop_constraint(CONSTRAINT, "project_reviews", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT,
        "project_reviews",
        "process_stages",
        ["stage_id", "project_id", "firm_id"],
        ["id", "project_id", "firm_id"],
        ondelete="SET NULL",
    )
