"""Persist journal analysis progress and failure diagnostics."""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0015"
down_revision = "20260803_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("journal_recommendation_runs", sa.Column("analysis_diagnostics", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("journal_recommendation_runs", "analysis_diagnostics")
