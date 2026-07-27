from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import log_audit_event
from app.db.models.accounting import Account
from app.db.models.enums import AccountType
from app.db.models.planning import (
    PlanningForecastRun,
    PlanningForecastRunLine,
    PlanningLine,
    PlanningPeriod,
    PlanningPlan,
)
from app.planning.schemas import (
    PlanningComparisonItemRead,
    PlanningComparisonRead,
    PlanningForecastAccountRead,
    PlanningForecastMonthRead,
    PlanningForecastRunRead,
    PlanningWarningRead,
)
from app.planning.service import PNL_ACCOUNT_TYPES, ZERO, load_plan_or_404
from app.reports.service import _aggregate_accounts, _display_amount

CALCULATION_VERSION = "planning-pnl-v1"
FOUR_PLACES = Decimal("0.0001")
INCOME_TYPES = {
    AccountType.INCOME,
    AccountType.REVENUE,
    AccountType.OTHER_INCOME,
    AccountType.CONTRA_INCOME,
}
REVENUE_TYPES = {
    AccountType.INCOME,
    AccountType.REVENUE,
    AccountType.CONTRA_INCOME,
}
OTHER_INCOME_TYPES = {AccountType.OTHER_INCOME}
EXPENSE_TYPES = {
    AccountType.EXPENSE,
    AccountType.COST_OF_SALES,
    AccountType.OTHER_EXPENSE,
    AccountType.CONTRA_EXPENSE,
}
OPERATING_EXPENSE_TYPES = {AccountType.EXPENSE, AccountType.CONTRA_EXPENSE}
OTHER_EXPENSE_TYPES = {AccountType.OTHER_EXPENSE}


def _periods(db: Session, plan_id: UUID) -> list[PlanningPeriod]:
    return list(
        db.scalars(
            select(PlanningPeriod)
            .where(PlanningPeriod.planning_plan_id == plan_id)
            .order_by(PlanningPeriod.sequence_number.asc())
        ).all()
    )


def _lines(db: Session, plan_id: UUID) -> list[PlanningLine]:
    return list(
        db.scalars(select(PlanningLine).where(PlanningLine.planning_plan_id == plan_id)).all()
    )


def _validate_cutoff(plan: PlanningPlan, periods: list[PlanningPeriod], cutoff: date) -> None:
    valid = {plan.financial_year_start - timedelta(days=1), plan.financial_year_end}
    valid.update(period.end_date for period in periods)
    if cutoff not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forecast actual-through date must be the day before the year or a fiscal month end",
        )


def _variance_direction(account_type: AccountType, variance: Decimal) -> str:
    if variance == ZERO:
        return "on_budget"
    if account_type in INCOME_TYPES:
        return "favourable" if variance > ZERO else "unfavourable"
    return "favourable" if variance < ZERO else "unfavourable"


def _variance_percentage(variance: Decimal, budget: Decimal) -> Decimal | None:
    if budget == ZERO:
        return None
    return (variance / abs(budget) * Decimal(100)).quantize(
        FOUR_PLACES,
        rounding=ROUND_HALF_UP,
    )


def _statement_totals(
    account_totals: dict[UUID, Decimal],
    account_types: dict[UUID, AccountType],
) -> dict[str, Decimal]:
    revenue = sum(
        (
            amount
            for account_id, amount in account_totals.items()
            if account_types[account_id] in REVENUE_TYPES
        ),
        ZERO,
    )
    other_income = sum(
        (
            amount
            for account_id, amount in account_totals.items()
            if account_types[account_id] in OTHER_INCOME_TYPES
        ),
        ZERO,
    )
    cost_of_sales = sum(
        (
            amount
            for account_id, amount in account_totals.items()
            if account_types[account_id] == AccountType.COST_OF_SALES
        ),
        ZERO,
    )
    operating_expenses = sum(
        (
            amount
            for account_id, amount in account_totals.items()
            if account_types[account_id] in OPERATING_EXPENSE_TYPES
        ),
        ZERO,
    )
    other_expenses = sum(
        (
            amount
            for account_id, amount in account_totals.items()
            if account_types[account_id] in OTHER_EXPENSE_TYPES
        ),
        ZERO,
    )
    total_income = revenue + other_income
    total_expenses = cost_of_sales + operating_expenses + other_expenses
    gross_profit = revenue - cost_of_sales
    operating_profit = gross_profit - operating_expenses
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "gross_profit": gross_profit,
        "operating_profit": operating_profit,
        "net_profit": total_income - total_expenses,
    }


def calculate_forecast(
    db: Session,
    *,
    plan: PlanningPlan,
    actual_through_date: date | None,
    acting_user_id: UUID,
    persist: bool,
) -> PlanningForecastRunRead:
    periods = _periods(db, plan.id)
    cutoff = (
        actual_through_date
        or plan.actual_through_date
        or plan.financial_year_start - timedelta(days=1)
    )
    _validate_cutoff(plan, periods, cutoff)

    baseline: PlanningPlan | None = None
    if plan.baseline_budget_plan_id is not None:
        baseline = load_plan_or_404(db, plan.company_id, plan.baseline_budget_plan_id)
        if (
            baseline.financial_year_start != plan.financial_year_start
            or baseline.financial_year_end != plan.financial_year_end
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Baseline budget uses a different financial year",
            )
    elif plan.plan_type.value == "budget":
        baseline = plan

    plan_lines = _lines(db, plan.id)
    baseline_lines = _lines(db, baseline.id) if baseline is not None else []
    baseline_periods = _periods(db, baseline.id) if baseline is not None else []
    baseline_sequence_by_id = {period.id: period.sequence_number for period in baseline_periods}
    plan_sequence_by_id = {period.id: period.sequence_number for period in periods}
    explicit_values = {
        (plan_sequence_by_id[line.planning_period_id], line.account_id): line.amount
        for line in plan_lines
    }
    budget_values = {
        (baseline_sequence_by_id[line.planning_period_id], line.account_id): line.amount
        for line in baseline_lines
    }

    account_ids = {line.account_id for line in plan_lines + baseline_lines}
    accounts = list(
        db.scalars(
            select(Account)
            .where(
                Account.company_id == plan.company_id,
                Account.account_type.in_(PNL_ACCOUNT_TYPES),
            )
            .order_by(Account.account_code.asc())
        ).all()
    )
    account_ids.update(account.id for account in accounts if account.is_active)
    account_map = {account.id: account for account in accounts}

    actual_values: dict[tuple[int, UUID], Decimal] = {}
    for period in periods:
        if period.end_date > cutoff:
            continue
        aggregates = _aggregate_accounts(
            db,
            company_id=plan.company_id,
            start_date=period.start_date,
            end_date=period.end_date,
            account_types=PNL_ACCOUNT_TYPES,
            include_draft=False,
            exclude_period_rollovers=True,
        )
        for aggregate in aggregates:
            account_ids.add(aggregate.account_id)
            actual_values[(period.sequence_number, aggregate.account_id)] = _display_amount(
                aggregate.account_type,
                aggregate.raw_balance,
            )

    warnings: list[PlanningWarningRead] = []
    rows: list[PlanningForecastAccountRead] = []
    persisted_months: list[
        tuple[Account, PlanningPeriod, Decimal, Decimal, Decimal, Decimal, str, str | None]
    ] = []
    annual_actual: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    annual_budget: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    annual_forecast: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    annual_projected: dict[UUID, Decimal] = defaultdict(lambda: ZERO)

    for account_id in sorted(
        account_ids,
        key=lambda item: account_map[item].account_code if item in account_map else str(item),
    ):
        account = account_map.get(account_id)
        if account is None:
            continue
        months: list[PlanningForecastMonthRead] = []
        for period in periods:
            key = (period.sequence_number, account_id)
            budget_amount = Decimal(budget_values.get(key, ZERO))
            actual_amount = Decimal(actual_values.get(key, ZERO))
            forecast_amount = ZERO
            warning_code: str | None = None
            if period.end_date <= cutoff:
                projected_amount = actual_amount
                value_source = "actual"
            else:
                if key in explicit_values:
                    forecast_amount = Decimal(explicit_values[key])
                    value_source = "forecast"
                elif key in budget_values:
                    forecast_amount = budget_amount
                    value_source = "budget_fallback"
                else:
                    forecast_amount = ZERO
                    value_source = "unplanned_zero"
                    warning_code = "UNPLANNED_FUTURE_PERIOD"
                    warnings.append(
                        PlanningWarningRead(
                            code=warning_code,
                            account_id=account_id,
                            planning_period_id=period.id,
                            message=(
                                f"{account.account_code} {account.name} has no value for "
                                f"{period.period_label}"
                            ),
                        )
                    )
                projected_amount = forecast_amount

            annual_actual[account_id] += actual_amount
            annual_budget[account_id] += budget_amount
            annual_forecast[account_id] += forecast_amount
            annual_projected[account_id] += projected_amount
            months.append(
                PlanningForecastMonthRead(
                    planning_period_id=period.id,
                    period_label=period.period_label,
                    start_date=period.start_date,
                    end_date=period.end_date,
                    actual_amount=actual_amount,
                    budget_amount=budget_amount,
                    forecast_amount=forecast_amount,
                    projected_amount=projected_amount,
                    value_source=value_source,
                    warning_code=warning_code,
                )
            )
            persisted_months.append(
                (
                    account,
                    period,
                    actual_amount,
                    budget_amount,
                    forecast_amount,
                    projected_amount,
                    value_source,
                    warning_code,
                )
            )

        variance = annual_projected[account_id] - annual_budget[account_id]
        rows.append(
            PlanningForecastAccountRead(
                account_id=account_id,
                account_code=account.account_code,
                account_name=account.name,
                account_type=account.account_type.value,
                actual_ytd=annual_actual[account_id],
                annual_budget=annual_budget[account_id],
                forecast_remaining=annual_forecast[account_id],
                projected_year_end=annual_projected[account_id],
                variance_amount=variance,
                variance_percentage=_variance_percentage(variance, annual_budget[account_id]),
                variance_direction=_variance_direction(account.account_type, variance),
                months=months,
            )
        )

    account_types = {account_id: account_map[account_id].account_type for account_id in account_ids}
    actual_totals = _statement_totals(annual_actual, account_types)
    budget_totals = _statement_totals(annual_budget, account_types)
    forecast_totals = _statement_totals(annual_forecast, account_types)
    projected_totals = _statement_totals(annual_projected, account_types)
    calculated_at = datetime.now(UTC)

    run_id: UUID | None = None
    if persist:
        run = PlanningForecastRun(
            company_id=plan.company_id,
            forecast_plan_id=plan.id,
            baseline_budget_plan_id=baseline.id if baseline is not None else None,
            actual_through_date=cutoff,
            ledger_calculated_at=calculated_at,
            generated_by_user_id=acting_user_id,
            calculation_version=CALCULATION_VERSION,
            warning_count=len(warnings),
            actual_total_income=actual_totals["total_income"],
            actual_total_expenses=actual_totals["total_expenses"],
            forecast_total_income=forecast_totals["total_income"],
            forecast_total_expenses=forecast_totals["total_expenses"],
            projected_total_income=projected_totals["total_income"],
            projected_total_expenses=projected_totals["total_expenses"],
            projected_net_profit=projected_totals["net_profit"],
            budget_net_profit=budget_totals["net_profit"],
            variance_to_budget=projected_totals["net_profit"] - budget_totals["net_profit"],
        )
        db.add(run)
        db.flush()
        run_id = run.id
        for (
            account,
            period,
            actual_amount,
            budget_amount,
            forecast_amount,
            projected_amount,
            value_source,
            warning_code,
        ) in persisted_months:
            variance = projected_amount - budget_amount
            db.add(
                PlanningForecastRunLine(
                    company_id=plan.company_id,
                    forecast_run_id=run.id,
                    planning_period_id=period.id,
                    account_id=account.id,
                    account_code_snapshot=account.account_code,
                    account_name_snapshot=account.name,
                    account_type_snapshot=account.account_type,
                    period_label_snapshot=period.period_label,
                    actual_amount=actual_amount,
                    budget_amount=budget_amount,
                    forecast_amount=forecast_amount,
                    projected_amount=projected_amount,
                    variance_amount=variance,
                    variance_percentage=_variance_percentage(variance, budget_amount),
                    variance_direction=_variance_direction(account.account_type, variance),
                    value_source=value_source,
                    warning_code=warning_code,
                )
            )
        log_audit_event(
            db,
            company_id=plan.company_id,
            actor_user_id=acting_user_id,
            entity_type="planning_forecast_run",
            entity_id=run.id,
            action="planning_forecast_calculated",
            summary=f"Calculated projected year-end P&L for {plan.name}",
            after_state={
                "actual_through_date": cutoff.isoformat(),
                "projected_net_profit": str(projected_totals["net_profit"]),
                "warning_count": len(warnings),
            },
        )
        db.commit()

    return PlanningForecastRunRead(
        id=run_id,
        company_id=plan.company_id,
        forecast_plan_id=plan.id,
        forecast_plan_name=plan.name,
        baseline_budget_plan_id=baseline.id if baseline is not None else None,
        actual_through_date=cutoff,
        ledger_calculated_at=calculated_at,
        calculation_version=CALCULATION_VERSION,
        warning_count=len(warnings),
        warnings=warnings,
        actual_total_income=actual_totals["total_income"],
        actual_total_expenses=actual_totals["total_expenses"],
        actual_net_profit=actual_totals["net_profit"],
        forecast_total_income=forecast_totals["total_income"],
        forecast_total_expenses=forecast_totals["total_expenses"],
        forecast_net_profit=forecast_totals["net_profit"],
        projected_total_income=projected_totals["total_income"],
        projected_total_expenses=projected_totals["total_expenses"],
        projected_gross_profit=projected_totals["gross_profit"],
        projected_operating_profit=projected_totals["operating_profit"],
        projected_net_profit=projected_totals["net_profit"],
        budget_total_income=budget_totals["total_income"],
        budget_total_expenses=budget_totals["total_expenses"],
        budget_gross_profit=budget_totals["gross_profit"],
        budget_operating_profit=budget_totals["operating_profit"],
        budget_net_profit=budget_totals["net_profit"],
        variance_to_budget=projected_totals["net_profit"] - budget_totals["net_profit"],
        rows=rows,
    )


def read_forecast_run(
    db: Session,
    *,
    company_id: UUID,
    run_id: UUID,
) -> PlanningForecastRunRead:
    run = db.scalar(
        select(PlanningForecastRun).where(
            PlanningForecastRun.id == run_id,
            PlanningForecastRun.company_id == company_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast run not found")
    plan = load_plan_or_404(db, company_id, run.forecast_plan_id)
    periods = _periods(db, plan.id)
    period_map = {period.id: period for period in periods}
    lines = list(
        db.scalars(
            select(PlanningForecastRunLine)
            .where(PlanningForecastRunLine.forecast_run_id == run.id)
            .order_by(
                PlanningForecastRunLine.account_code_snapshot.asc(),
                PlanningForecastRunLine.period_label_snapshot.asc(),
            )
        ).all()
    )
    grouped: dict[UUID, list[PlanningForecastRunLine]] = defaultdict(list)
    for line in lines:
        grouped[line.account_id].append(line)

    rows: list[PlanningForecastAccountRead] = []
    account_types: dict[UUID, AccountType] = {}
    annual_budget: dict[UUID, Decimal] = {}
    for account_id, account_lines in grouped.items():
        account_lines.sort(key=lambda item: period_map[item.planning_period_id].sequence_number)
        account_type = account_lines[0].account_type_snapshot
        account_types[account_id] = account_type
        actual = sum((line.actual_amount for line in account_lines), ZERO)
        budget = sum((line.budget_amount for line in account_lines), ZERO)
        forecast = sum((line.forecast_amount for line in account_lines), ZERO)
        projected = sum((line.projected_amount for line in account_lines), ZERO)
        annual_budget[account_id] = budget
        variance = projected - budget
        rows.append(
            PlanningForecastAccountRead(
                account_id=account_id,
                account_code=account_lines[0].account_code_snapshot,
                account_name=account_lines[0].account_name_snapshot,
                account_type=account_type.value,
                actual_ytd=actual,
                annual_budget=budget,
                forecast_remaining=forecast,
                projected_year_end=projected,
                variance_amount=variance,
                variance_percentage=_variance_percentage(variance, budget),
                variance_direction=_variance_direction(account_type, variance),
                months=[
                    PlanningForecastMonthRead(
                        planning_period_id=line.planning_period_id,
                        period_label=line.period_label_snapshot,
                        start_date=period_map[line.planning_period_id].start_date,
                        end_date=period_map[line.planning_period_id].end_date,
                        actual_amount=line.actual_amount,
                        budget_amount=line.budget_amount,
                        forecast_amount=line.forecast_amount,
                        projected_amount=line.projected_amount,
                        value_source=line.value_source,
                        warning_code=line.warning_code,
                    )
                    for line in account_lines
                ],
            )
        )
    budget_totals = _statement_totals(annual_budget, account_types)
    projected_by_account = {row.account_id: row.projected_year_end for row in rows}
    projected_totals = _statement_totals(projected_by_account, account_types)
    warnings = [
        PlanningWarningRead(
            code=line.warning_code,
            account_id=line.account_id,
            planning_period_id=line.planning_period_id,
            message=(
                f"{line.account_code_snapshot} {line.account_name_snapshot} has no value for "
                f"{line.period_label_snapshot}"
            ),
        )
        for line in lines
        if line.warning_code
    ]
    return PlanningForecastRunRead(
        id=run.id,
        company_id=run.company_id,
        forecast_plan_id=run.forecast_plan_id,
        forecast_plan_name=plan.name,
        baseline_budget_plan_id=run.baseline_budget_plan_id,
        actual_through_date=run.actual_through_date,
        ledger_calculated_at=run.ledger_calculated_at,
        calculation_version=run.calculation_version,
        warning_count=run.warning_count,
        warnings=warnings,
        actual_total_income=run.actual_total_income,
        actual_total_expenses=run.actual_total_expenses,
        actual_net_profit=run.actual_total_income - run.actual_total_expenses,
        forecast_total_income=run.forecast_total_income,
        forecast_total_expenses=run.forecast_total_expenses,
        forecast_net_profit=run.forecast_total_income - run.forecast_total_expenses,
        projected_total_income=run.projected_total_income,
        projected_total_expenses=run.projected_total_expenses,
        projected_gross_profit=projected_totals["gross_profit"],
        projected_operating_profit=projected_totals["operating_profit"],
        projected_net_profit=run.projected_net_profit,
        budget_total_income=budget_totals["total_income"],
        budget_total_expenses=budget_totals["total_expenses"],
        budget_gross_profit=budget_totals["gross_profit"],
        budget_operating_profit=budget_totals["operating_profit"],
        budget_net_profit=run.budget_net_profit or ZERO,
        variance_to_budget=run.variance_to_budget or ZERO,
        rows=rows,
    )


def compare_plans(
    db: Session,
    *,
    company_id: UUID,
    plan_ids: list[UUID],
    actual_through_date: date | None,
    acting_user_id: UUID,
) -> PlanningComparisonRead:
    plans = [load_plan_or_404(db, company_id, plan_id) for plan_id in plan_ids]
    first = plans[0]
    for plan in plans[1:]:
        if (
            plan.financial_year_start != first.financial_year_start
            or plan.financial_year_end != first.financial_year_end
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Comparison plans must use the same financial year",
            )
    items: list[PlanningComparisonItemRead] = []
    for plan in plans:
        result = calculate_forecast(
            db,
            plan=plan,
            actual_through_date=actual_through_date,
            acting_user_id=acting_user_id,
            persist=False,
        )
        items.append(
            PlanningComparisonItemRead(
                plan_id=plan.id,
                plan_name=plan.name,
                scenario_label=plan.scenario_label,
                actual_through_date=result.actual_through_date,
                projected_total_income=result.projected_total_income,
                projected_total_expenses=result.projected_total_expenses,
                projected_net_profit=result.projected_net_profit,
                budget_net_profit=result.budget_net_profit,
                variance_to_budget=result.variance_to_budget,
                warning_count=result.warning_count,
            )
        )
    return PlanningComparisonRead(
        financial_year_start=first.financial_year_start,
        financial_year_end=first.financial_year_end,
        items=items,
    )
