"""align journal recommendation enum labels with runtime models

Revision ID: 20260510_0009
Revises: 20260510_0008
Create Date: 2026-05-10 00:09:00
"""

from alembic import op


revision = "20260510_0009"
down_revision = "20260510_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE documentlinkentitytype ADD VALUE IF NOT EXISTS 'JOURNAL_RECOMMENDATION_RUN'")
    op.execute("ALTER TYPE entitytype ADD VALUE IF NOT EXISTS 'JOURNAL_RECOMMENDATION_RUN'")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for enum label alignment")