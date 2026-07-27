from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    AccountType,
    PlanningBudgetItemFrequency,
    PlanningEntryMethod,
    PlanningPlanType,
    PlanningScenarioType,
    PlanningStatus,
)
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class PlanningPlan(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_plans"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            "version_number",
            name="uq_planning_plan_name_version",
        ),
        CheckConstraint(
            "financial_year_end >= financial_year_start",
            name="ck_planning_plan_financial_year",
        ),
        CheckConstraint("version_number > 0", name="ck_planning_plan_version_positive"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_type: Mapped[PlanningPlanType] = mapped_column(Enum(PlanningPlanType), nullable=False)
    scenario_type: Mapped[PlanningScenarioType] = mapped_column(
        Enum(PlanningScenarioType),
        nullable=False,
    )
    scenario_label: Mapped[str] = mapped_column(String(120), nullable=False)
    financial_year_start: Mapped[date] = mapped_column(Date, nullable=False)
    financial_year_end: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[PlanningStatus] = mapped_column(
        Enum(PlanningStatus),
        nullable=False,
        default=PlanningStatus.DRAFT,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_plan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("planning_plans.id", ondelete="RESTRICT"),
    )
    baseline_budget_plan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("planning_plans.id", ondelete="RESTRICT"),
    )
    actual_through_date: Mapped[date | None] = mapped_column(Date)
    assumption_summary: Mapped[str | None] = mapped_column(Text)
    preparer_note: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    periods: Mapped[list["PlanningPeriod"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanningPeriod.sequence_number",
    )
    lines: Mapped[list["PlanningLine"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    budget_items: Mapped[list["PlanningBudgetItem"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class PlanningPeriod(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_periods"
    __table_args__ = (
        UniqueConstraint(
            "planning_plan_id",
            "sequence_number",
            name="uq_planning_period_sequence",
        ),
        UniqueConstraint(
            "planning_plan_id",
            "start_date",
            "end_date",
            name="uq_planning_period_range",
        ),
        CheckConstraint(
            "sequence_number >= 1 AND sequence_number <= 12",
            name="ck_planning_period_sequence",
        ),
        CheckConstraint("end_date >= start_date", name="ck_planning_period_dates"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planning_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_label: Mapped[str] = mapped_column(String(40), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    accounting_period_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="SET NULL"),
    )

    plan: Mapped[PlanningPlan] = relationship(back_populates="periods")


class PlanningLine(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_lines"
    __table_args__ = (
        UniqueConstraint(
            "planning_plan_id",
            "planning_period_id",
            "account_id",
            name="uq_planning_line_account_period",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planning_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planning_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    entry_method: Mapped[PlanningEntryMethod] = mapped_column(
        Enum(PlanningEntryMethod),
        nullable=False,
        default=PlanningEntryMethod.MANUAL,
    )
    note: Mapped[str | None] = mapped_column(Text)
    account_code_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    account_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type_snapshot: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    reporting_category_code_snapshot: Mapped[str | None] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    plan: Mapped[PlanningPlan] = relationship(back_populates="lines")


class PlanningBudgetItem(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_budget_items"

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planning_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    occurrence_frequency: Mapped[PlanningBudgetItemFrequency] = mapped_column(
        Enum(PlanningBudgetItemFrequency),
        nullable=False,
    )
    start_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    end_period_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("planning_periods.id", ondelete="RESTRICT"),
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    plan: Mapped[PlanningPlan] = relationship(back_populates="budget_items")


class PlanningForecastRun(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_forecast_runs"

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    forecast_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    baseline_budget_plan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("planning_plans.id", ondelete="RESTRICT"),
    )
    actual_through_date: Mapped[date] = mapped_column(Date, nullable=False)
    ledger_calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_total_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    actual_total_expenses: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    forecast_total_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    forecast_total_expenses: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    projected_total_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    projected_total_expenses: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    projected_net_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    budget_net_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    variance_to_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    lines: Mapped[list["PlanningForecastRunLine"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class PlanningForecastRunLine(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_forecast_run_lines"
    __table_args__ = (
        UniqueConstraint(
            "forecast_run_id",
            "planning_period_id",
            "account_id",
            name="uq_planning_forecast_run_line",
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    forecast_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planning_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_periods.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_code_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    account_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type_snapshot: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    period_label_snapshot: Mapped[str] = mapped_column(String(40), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    forecast_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    projected_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    variance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    variance_percentage: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    variance_direction: Mapped[str] = mapped_column(String(24), nullable=False)
    value_source: Mapped[str] = mapped_column(String(24), nullable=False)
    warning_code: Mapped[str | None] = mapped_column(String(64))

    run: Mapped[PlanningForecastRun] = relationship(back_populates="lines")
