"""add active flags to reporting categories and tax codes

Revision ID: 20260509_0007
Revises: 20260508_0006
Create Date: 2026-05-09 00:07:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260509_0007"
down_revision = "20260508_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reporting_categories",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "tax_codes",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("reporting_categories", "is_active", server_default=None)
    op.alter_column("tax_codes", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("tax_codes", "is_active")
    op.drop_column("reporting_categories", "is_active")