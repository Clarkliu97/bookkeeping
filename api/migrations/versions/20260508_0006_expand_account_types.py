"""expand account types for setup management

Revision ID: 20260508_0006
Revises: 20260508_0005
Create Date: 2026-05-08 00:06:00
"""

from alembic import op


revision = "20260508_0006"
down_revision = "20260508_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'REVENUE'")
    op.execute("ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'COST_OF_SALES'")
    op.execute("ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'OTHER_INCOME'")
    op.execute("ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'OTHER_EXPENSE'")
    op.execute("ALTER TYPE accounttype ADD VALUE IF NOT EXISTS 'NON_POSTING'")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for accounttype enum expansion")