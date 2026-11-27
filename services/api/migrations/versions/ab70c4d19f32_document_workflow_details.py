"""Persist structured details for document-aware workflow stages."""

import sqlalchemy as sa
from alembic import op

revision = "ab70c4d19f32"
down_revision = "f4a8d1c7e902"
branch_labels = None
depends_on = None


def upgrade():
    for column in ("inputs", "actions", "expected_outputs", "decision_points"):
        op.add_column(
            "process_stages",
            sa.Column(column, sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade():
    for column in ("decision_points", "expected_outputs", "actions", "inputs"):
        op.drop_column("process_stages", column)
