"""milestone d phase 10 fixed assets

Revision ID: 20260508_0004
Revises: 20260508_0003
Create Date: 2026-05-08 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260508_0004"
down_revision = "20260508_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    fixed_asset_status = postgresql.ENUM("ACTIVE", "DISPOSED", name="fixedassetstatus", create_type=False)
    depreciation_method = postgresql.ENUM(
        "STRAIGHT_LINE",
        "DIMINISHING_VALUE",
        name="depreciationmethod",
        create_type=False,
    )
    depreciation_run_status = postgresql.ENUM("DRAFT", "POSTED", name="depreciationrunstatus", create_type=False)

    bind = op.get_bind()
    for enum_type in [fixed_asset_status, depreciation_method, depreciation_run_status]:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "fixed_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("asset_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("in_service_date", sa.Date(), nullable=False),
        sa.Column("cost_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("salvage_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", depreciation_method, nullable=False),
        sa.Column("diminishing_value_rate", sa.Numeric(9, 4), nullable=True),
        sa.Column("asset_account_id", sa.Uuid(), nullable=False),
        sa.Column("accumulated_depreciation_account_id", sa.Uuid(), nullable=False),
        sa.Column("depreciation_expense_account_id", sa.Uuid(), nullable=False),
        sa.Column("status", fixed_asset_status, nullable=False),
        sa.Column("disposal_date", sa.Date(), nullable=True),
        sa.Column("disposal_reference", sa.String(length=128), nullable=True),
        sa.Column("disposal_note", sa.Text(), nullable=True),
        sa.Column("disposal_proceeds", sa.Numeric(18, 2), nullable=True),
        sa.Column("acquisition_reference", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cost_amount > 0", name="ck_fixed_asset_positive_cost"),
        sa.CheckConstraint("salvage_value >= 0", name="ck_fixed_asset_non_negative_salvage"),
        sa.CheckConstraint("salvage_value <= cost_amount", name="ck_fixed_asset_salvage_lte_cost"),
        sa.CheckConstraint("useful_life_months > 0", name="ck_fixed_asset_useful_life_positive"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["accumulated_depreciation_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["depreciation_expense_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "asset_code", name="uq_fixed_asset_code"),
    )
    op.create_table(
        "fixed_asset_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("fixed_asset_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", fixed_asset_status, nullable=True),
        sa.Column("to_status", fixed_asset_status, nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fixed_asset_id"], ["fixed_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "depreciation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("accounting_period_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", depreciation_run_status, nullable=False),
        sa.Column("journal_entry_id", sa.Uuid(), nullable=True),
        sa.Column("generated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("posted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["accounting_period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"]),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["posted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "accounting_period_id", "start_date", "end_date", name="uq_depreciation_run_range"),
    )
    op.create_table(
        "depreciation_run_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("depreciation_run_id", sa.Uuid(), nullable=False),
        sa.Column("fixed_asset_id", sa.Uuid(), nullable=False),
        sa.Column("depreciation_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("accumulated_depreciation_opening", sa.Numeric(18, 2), nullable=False),
        sa.Column("accumulated_depreciation_closing", sa.Numeric(18, 2), nullable=False),
        sa.Column("carrying_amount_opening", sa.Numeric(18, 2), nullable=False),
        sa.Column("carrying_amount_closing", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["depreciation_run_id"], ["depreciation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fixed_asset_id"], ["fixed_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("depreciation_run_id", "fixed_asset_id", name="uq_depreciation_run_asset"),
    )


def downgrade() -> None:
    for table in ["depreciation_run_lines", "depreciation_runs", "fixed_asset_status_history", "fixed_assets"]:
        op.drop_table(table)

    bind = op.get_bind()
    for enum_name in ["depreciationrunstatus", "depreciationmethod", "fixedassetstatus"]:
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)