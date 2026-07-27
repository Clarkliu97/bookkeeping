from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import (
    PlanningBudgetItemFrequency,
    PlanningEntryMethod,
    PlanningPlanType,
    PlanningScenarioType,
    PlanningStatus,
)


class PlanningORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PlanningPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    plan_type: PlanningPlanType
    scenario_type: PlanningScenarioType = PlanningScenarioType.BASELINE
    scenario_label: str = Field(default="Baseline", min_length=1, max_length=120)
    financial_year_start: date
    financial_year_end: date
    baseline_budget_plan_id: UUID | None = None
    actual_through_date: date | None = None
    assumption_summary: str | None = None
    preparer_note: str | None = None


class PlanningPlanUpdate(BaseModel):
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=160)
    scenario_type: PlanningScenarioType
    scenario_label: str = Field(min_length=1, max_length=120)
    baseline_budget_plan_id: UUID | None = None
    actual_through_date: date | None = None
    assumption_summary: str | None = None
    preparer_note: str | None = None


class PlanningLineInput(BaseModel):
    planning_period_id: UUID
    account_id: UUID
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    entry_method: PlanningEntryMethod = PlanningEntryMethod.MANUAL
    note: str | None = None


class PlanningLineBulkUpdate(BaseModel):
    revision: int = Field(ge=1)
    lines: list[PlanningLineInput] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_account_periods(self):
        keys = [(line.account_id, line.planning_period_id) for line in self.lines]
        if len(keys) != len(set(keys)):
            raise ValueError("Each account and planning period may appear only once")
        return self


class PlanningSpreadRequest(BaseModel):
    revision: int = Field(ge=1)
    account_id: UUID
    annual_amount: Decimal = Field(max_digits=18, decimal_places=2)
    period_ids: list[UUID] | None = None
    percentages: list[Decimal] | None = None
    note: str | None = None


class PlanningCopyPriorActualsRequest(BaseModel):
    revision: int = Field(ge=1)
    growth_percentage: Decimal = Field(default=Decimal("0.00"), ge=-1000, le=1000)
    note: str | None = None


class PlanningApplyGrowthRequest(BaseModel):
    revision: int = Field(ge=1)
    growth_percentage: Decimal = Field(ge=-1000, le=1000)
    account_ids: list[UUID] | None = None
    planning_period_ids: list[UUID] | None = None
    note: str | None = None


class PlanningBudgetItemCreate(BaseModel):
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=160)
    account_id: UUID
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    occurrence_frequency: PlanningBudgetItemFrequency
    start_period_id: UUID
    end_period_id: UUID | None = None
    note: str | None = None


class PlanningBudgetItemUpdate(PlanningBudgetItemCreate):
    pass


class PlanningCloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    plan_type: PlanningPlanType | None = None
    scenario_type: PlanningScenarioType | None = None
    scenario_label: str | None = Field(default=None, min_length=1, max_length=120)
    baseline_budget_plan_id: UUID | None = None
    actual_through_date: date | None = None
    preparer_note: str | None = None


class PlanningActionRequest(BaseModel):
    note: str | None = None


class PlanningCalculateRequest(BaseModel):
    actual_through_date: date | None = None
    persist: bool = True


class PlanningComparisonRequest(BaseModel):
    plan_ids: list[UUID] = Field(min_length=2, max_length=4)
    actual_through_date: date | None = None

    @model_validator(mode="after")
    def unique_plans(self):
        if len(self.plan_ids) != len(set(self.plan_ids)):
            raise ValueError("Comparison plans must be unique")
        return self


class PlanningPlanRead(PlanningORMModel):
    id: UUID
    company_id: UUID
    name: str
    plan_type: PlanningPlanType
    scenario_type: PlanningScenarioType
    scenario_label: str
    financial_year_start: date
    financial_year_end: date
    currency_code: str
    version_number: int
    revision: int
    status: PlanningStatus
    is_primary: bool
    source_plan_id: UUID | None
    baseline_budget_plan_id: UUID | None
    actual_through_date: date | None
    assumption_summary: str | None
    preparer_note: str | None
    review_note: str | None
    created_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    locked_by_user_id: UUID | None
    locked_at: datetime | None
    archived_by_user_id: UUID | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PlanningPeriodRead(PlanningORMModel):
    id: UUID
    sequence_number: int
    period_label: str
    start_date: date
    end_date: date
    accounting_period_id: UUID | None


class PlanningLineRead(PlanningORMModel):
    id: UUID
    planning_period_id: UUID
    account_id: UUID
    amount: Decimal
    entry_method: PlanningEntryMethod
    note: str | None
    account_code_snapshot: str
    account_name_snapshot: str
    account_type_snapshot: str
    reporting_category_code_snapshot: str | None
    updated_at: datetime


class PlanningBudgetItemRead(PlanningORMModel):
    id: UUID
    company_id: UUID
    planning_plan_id: UUID
    account_id: UUID
    name: str
    amount: Decimal
    occurrence_frequency: PlanningBudgetItemFrequency
    start_period_id: UUID
    end_period_id: UUID | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class PlanningBudgetItemFloorRead(BaseModel):
    account_id: UUID
    planning_period_id: UUID
    amount: Decimal


class PlanningFloorAdjustmentRead(BaseModel):
    account_id: UUID
    planning_period_id: UUID
    requested_amount: Decimal | None
    applied_minimum: Decimal


class PlanningAccountRead(BaseModel):
    id: UUID
    account_code: str
    account_name: str
    account_type: str
    reporting_category_code: str | None
    is_active: bool


class PlanningWarningRead(BaseModel):
    code: str
    message: str
    account_id: UUID | None = None
    planning_period_id: UUID | None = None
    severity: str = "warning"


class PlanningImportErrorRead(BaseModel):
    row_number: int
    message: str


class PlanningImportPreviewRead(BaseModel):
    valid_rows: int
    lines: list[PlanningLineInput]
    errors: list[PlanningImportErrorRead]


class PlanningPlanDetailRead(BaseModel):
    plan: PlanningPlanRead
    periods: list[PlanningPeriodRead]
    lines: list[PlanningLineRead]
    budget_items: list[PlanningBudgetItemRead] = Field(default_factory=list)
    budget_item_floors: list[PlanningBudgetItemFloorRead] = Field(default_factory=list)
    floor_adjustments: list[PlanningFloorAdjustmentRead] = Field(default_factory=list)
    accounts: list[PlanningAccountRead]
    warnings: list[PlanningWarningRead]
    annual_budget_income: Decimal
    annual_budget_expenses: Decimal
    annual_budget_net_profit: Decimal
    can_edit: bool


class PlanningForecastMonthRead(BaseModel):
    planning_period_id: UUID
    period_label: str
    start_date: date
    end_date: date
    actual_amount: Decimal
    budget_amount: Decimal
    forecast_amount: Decimal
    projected_amount: Decimal
    value_source: str
    warning_code: str | None = None


class PlanningForecastAccountRead(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    actual_ytd: Decimal
    annual_budget: Decimal
    forecast_remaining: Decimal
    projected_year_end: Decimal
    variance_amount: Decimal
    variance_percentage: Decimal | None
    variance_direction: str
    months: list[PlanningForecastMonthRead]


class PlanningForecastRunRead(BaseModel):
    id: UUID | None
    company_id: UUID
    forecast_plan_id: UUID
    forecast_plan_name: str
    baseline_budget_plan_id: UUID | None
    actual_through_date: date
    ledger_calculated_at: datetime
    calculation_version: str
    warning_count: int
    warnings: list[PlanningWarningRead]
    actual_total_income: Decimal
    actual_total_expenses: Decimal
    actual_net_profit: Decimal
    forecast_total_income: Decimal
    forecast_total_expenses: Decimal
    forecast_net_profit: Decimal
    projected_total_income: Decimal
    projected_total_expenses: Decimal
    projected_gross_profit: Decimal
    projected_operating_profit: Decimal
    projected_net_profit: Decimal
    budget_total_income: Decimal
    budget_total_expenses: Decimal
    budget_gross_profit: Decimal
    budget_operating_profit: Decimal
    budget_net_profit: Decimal
    variance_to_budget: Decimal
    rows: list[PlanningForecastAccountRead]


class PlanningForecastRunSummaryRead(PlanningORMModel):
    id: UUID
    forecast_plan_id: UUID
    baseline_budget_plan_id: UUID | None
    actual_through_date: date
    ledger_calculated_at: datetime
    warning_count: int
    projected_total_income: Decimal
    projected_total_expenses: Decimal
    projected_net_profit: Decimal
    budget_net_profit: Decimal | None
    variance_to_budget: Decimal | None
    created_at: datetime


class PlanningComparisonItemRead(BaseModel):
    plan_id: UUID
    plan_name: str
    scenario_label: str
    actual_through_date: date
    projected_total_income: Decimal
    projected_total_expenses: Decimal
    projected_net_profit: Decimal
    budget_net_profit: Decimal
    variance_to_budget: Decimal
    warning_count: int


class PlanningComparisonRead(BaseModel):
    financial_year_start: date
    financial_year_end: date
    items: list[PlanningComparisonItemRead]
