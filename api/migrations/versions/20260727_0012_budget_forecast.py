"""add budget and forecast planning workspace

Revision ID: 20260727_0012
Revises: 20260722_0011
Create Date: 2026-07-27 00:12:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260727_0012"
down_revision = "20260722_0011"
branch_labels = None
depends_on = None


planning_plan_type = postgresql.ENUM(
    "BUDGET", "FORECAST", name="planningplantype", create_type=False
)
planning_scenario_type = postgresql.ENUM(
    "BASELINE",
    "UPSIDE",
    "DOWNSIDE",
    "CUSTOM",
    name="planningscenariotype",
    create_type=False,
)
planning_status = postgresql.ENUM(
    "DRAFT",
    "IN_REVIEW",
    "APPROVED",
    "LOCKED",
    "ARCHIVED",
    name="planningstatus",
    create_type=False,
)
planning_entry_method = postgresql.ENUM(
    "MANUAL",
    "ANNUAL_SPREAD",
    "PRIOR_ACTUAL",
    "PRIOR_BUDGET",
    "GROWTH_RATE",
    "FORECAST_OVERRIDE",
    "CSV_IMPORT",
    name="planningentrymethod",
    create_type=False,
)
account_type = postgresql.ENUM(
    "ASSET",
    "LIABILITY",
    "EQUITY",
    "INCOME",
    "REVENUE",
    "EXPENSE",
    "COST_OF_SALES",
    "OTHER_INCOME",
    "OTHER_EXPENSE",
    "NON_POSTING",
    "CONTRA_ASSET",
    "CONTRA_LIABILITY",
    "CONTRA_INCOME",
    "CONTRA_EXPENSE",
    name="accounttype",
    create_type=False,
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in [
        planning_plan_type,
        planning_scenario_type,
        planning_status,
        planning_entry_method,
    ]:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "planning_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("plan_type", planning_plan_type, nullable=False),
        sa.Column("scenario_type", planning_scenario_type, nullable=False),
        sa.Column("scenario_label", sa.String(length=120), nullable=False),
        sa.Column("financial_year_start", sa.Date(), nullable=False),
        sa.Column("financial_year_end", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", planning_status, nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column(
            "source_plan_id", sa.Uuid(), sa.ForeignKey("planning_plans.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "baseline_budget_plan_id",
            sa.Uuid(),
            sa.ForeignKey("planning_plans.id", ondelete="RESTRICT"),
        ),
        sa.Column("actual_through_date", sa.Date()),
        sa.Column("assumption_summary", sa.Text()),
        sa.Column("preparer_note", sa.Text()),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("archived_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "financial_year_end >= financial_year_start", name="ck_planning_plan_financial_year"
        ),
        sa.CheckConstraint("version_number > 0", name="ck_planning_plan_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "name", "version_number", name="uq_planning_plan_name_version"
        ),
    )
    op.create_index("ix_planning_plans_company_id", "planning_plans", ["company_id"])

    op.create_table(
        "planning_periods",
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
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("period_label", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "accounting_period_id",
            sa.Uuid(),
            sa.ForeignKey("accounting_periods.id", ondelete="SET NULL"),
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "sequence_number >= 1 AND sequence_number <= 12",
            name="ck_planning_period_sequence",
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_planning_period_dates"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "planning_plan_id", "sequence_number", name="uq_planning_period_sequence"
        ),
        sa.UniqueConstraint(
            "planning_plan_id",
            "start_date",
            "end_date",
            name="uq_planning_period_range",
        ),
    )
    op.create_index("ix_planning_periods_company_id", "planning_periods", ["company_id"])
    op.create_index(
        "ix_planning_periods_planning_plan_id", "planning_periods", ["planning_plan_id"]
    )

    op.create_table(
        "planning_lines",
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
            "planning_period_id",
            sa.Uuid(),
            sa.ForeignKey("planning_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("entry_method", planning_entry_method, nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("account_code_snapshot", sa.String(length=32), nullable=False),
        sa.Column("account_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("account_type_snapshot", account_type, nullable=False),
        sa.Column("reporting_category_code_snapshot", sa.String(length=64)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "planning_plan_id",
            "planning_period_id",
            "account_id",
            name="uq_planning_line_account_period",
        ),
    )
    for column in ["company_id", "planning_plan_id", "planning_period_id", "account_id"]:
        op.create_index(f"ix_planning_lines_{column}", "planning_lines", [column])

    op.create_table(
        "planning_forecast_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "forecast_plan_id",
            sa.Uuid(),
            sa.ForeignKey("planning_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "baseline_budget_plan_id",
            sa.Uuid(),
            sa.ForeignKey("planning_plans.id", ondelete="RESTRICT"),
        ),
        sa.Column("actual_through_date", sa.Date(), nullable=False),
        sa.Column("ledger_calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("calculation_version", sa.String(length=64), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("actual_total_income", sa.Numeric(18, 2), nullable=False),
        sa.Column("actual_total_expenses", sa.Numeric(18, 2), nullable=False),
        sa.Column("forecast_total_income", sa.Numeric(18, 2), nullable=False),
        sa.Column("forecast_total_expenses", sa.Numeric(18, 2), nullable=False),
        sa.Column("projected_total_income", sa.Numeric(18, 2), nullable=False),
        sa.Column("projected_total_expenses", sa.Numeric(18, 2), nullable=False),
        sa.Column("projected_net_profit", sa.Numeric(18, 2), nullable=False),
        sa.Column("budget_net_profit", sa.Numeric(18, 2)),
        sa.Column("variance_to_budget", sa.Numeric(18, 2)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_planning_forecast_runs_company_id", "planning_forecast_runs", ["company_id"]
    )
    op.create_index(
        "ix_planning_forecast_runs_forecast_plan_id",
        "planning_forecast_runs",
        ["forecast_plan_id"],
    )

    op.create_table(
        "planning_forecast_run_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "forecast_run_id",
            sa.Uuid(),
            sa.ForeignKey("planning_forecast_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "planning_period_id",
            sa.Uuid(),
            sa.ForeignKey("planning_periods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("account_code_snapshot", sa.String(length=32), nullable=False),
        sa.Column("account_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("account_type_snapshot", account_type, nullable=False),
        sa.Column("period_label_snapshot", sa.String(length=40), nullable=False),
        sa.Column("actual_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("budget_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("forecast_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("projected_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("variance_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("variance_percentage", sa.Numeric(18, 4)),
        sa.Column("variance_direction", sa.String(length=24), nullable=False),
        sa.Column("value_source", sa.String(length=24), nullable=False),
        sa.Column("warning_code", sa.String(length=64)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "forecast_run_id",
            "planning_period_id",
            "account_id",
            name="uq_planning_forecast_run_line",
        ),
    )
    op.create_index(
        "ix_planning_forecast_run_lines_company_id",
        "planning_forecast_run_lines",
        ["company_id"],
    )
    op.create_index(
        "ix_planning_forecast_run_lines_forecast_run_id",
        "planning_forecast_run_lines",
        ["forecast_run_id"],
    )


def downgrade() -> None:
    op.drop_table("planning_forecast_run_lines")
    op.drop_table("planning_forecast_runs")
    op.drop_table("planning_lines")
    op.drop_table("planning_periods")
    op.drop_table("planning_plans")
    bind = op.get_bind()
    for enum_type in [
        planning_entry_method,
        planning_status,
        planning_scenario_type,
        planning_plan_type,
    ]:
        enum_type.drop(bind, checkfirst=True)
