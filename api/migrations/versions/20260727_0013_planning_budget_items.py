"""add recurring budget items and monthly planning floors

Revision ID: 20260727_0013
Revises: 20260727_0012
Create Date: 2026-07-27 01:13:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260727_0013"
down_revision = "20260727_0012"
branch_labels = None
depends_on = None


budget_item_frequency = postgresql.ENUM(
    "ONE_OFF",
    "MONTHLY",
    "QUARTERLY",
    "HALF_YEARLY",
    "ANNUALLY",
    name="planningbudgetitemfrequency",
    create_type=False,
)


def upgrade() -> None:
    budget_item_frequency.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "planning_budget_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "planning_plan_id",
            sa.Uuid(),
            sa.ForeignKey("planning_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("occurrence_frequency", budget_item_frequency, nullable=False),
        sa.Column(
            "start_period_id",
            sa.Uuid(),
            sa.ForeignKey("planning_periods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "end_period_id",
            sa.Uuid(),
            sa.ForeignKey("planning_periods.id", ondelete="RESTRICT"),
        ),
        sa.Column("note", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_planning_budget_items_company_id",
        "planning_budget_items",
        ["company_id"],
    )
    op.create_index(
        "ix_planning_budget_items_planning_plan_id",
        "planning_budget_items",
        ["planning_plan_id"],
    )
    op.create_index(
        "ix_planning_budget_items_account_id",
        "planning_budget_items",
        ["account_id"],
    )
    op.create_index(
        "ix_planning_budget_items_start_period_id",
        "planning_budget_items",
        ["start_period_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_planning_budget_items_start_period_id",
        table_name="planning_budget_items",
    )
    op.drop_index(
        "ix_planning_budget_items_account_id",
        table_name="planning_budget_items",
    )
    op.drop_index(
        "ix_planning_budget_items_planning_plan_id",
        table_name="planning_budget_items",
    )
    op.drop_index(
        "ix_planning_budget_items_company_id",
        table_name="planning_budget_items",
    )
    op.drop_table("planning_budget_items")
    budget_item_frequency.drop(op.get_bind(), checkfirst=True)
