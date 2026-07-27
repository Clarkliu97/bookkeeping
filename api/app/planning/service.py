import csv
import io
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.audit.service import log_audit_event
from app.db.models.accounting import Account, AccountingPeriod
from app.db.models.companies import Company, CompanyConfigurationVersion
from app.db.models.enums import (
    AccountType,
    PlanningBudgetItemFrequency,
    PlanningEntryMethod,
    PlanningPlanType,
    PlanningScenarioType,
    PlanningStatus,
    SelfApprovalMode,
)
from app.db.models.planning import (
    PlanningBudgetItem,
    PlanningForecastRun,
    PlanningLine,
    PlanningPeriod,
    PlanningPlan,
)
from app.db.models.reference import ReportingCategory
from app.planning.periods import add_months, generate_fiscal_months
from app.planning.schemas import (
    PlanningAccountRead,
    PlanningApplyGrowthRequest,
    PlanningBudgetItemCreate,
    PlanningBudgetItemFloorRead,
    PlanningBudgetItemRead,
    PlanningBudgetItemUpdate,
    PlanningCloneRequest,
    PlanningCopyPriorActualsRequest,
    PlanningImportErrorRead,
    PlanningImportPreviewRead,
    PlanningLineBulkUpdate,
    PlanningLineInput,
    PlanningLineRead,
    PlanningFloorAdjustmentRead,
    PlanningPeriodRead,
    PlanningPlanCreate,
    PlanningPlanDetailRead,
    PlanningPlanRead,
    PlanningPlanUpdate,
    PlanningSpreadRequest,
    PlanningWarningRead,
)
from app.reports.service import _aggregate_accounts, _display_amount

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
PNL_ACCOUNT_TYPES = {
    AccountType.INCOME,
    AccountType.REVENUE,
    AccountType.OTHER_INCOME,
    AccountType.CONTRA_INCOME,
    AccountType.EXPENSE,
    AccountType.COST_OF_SALES,
    AccountType.OTHER_EXPENSE,
    AccountType.CONTRA_EXPENSE,
}
INCOME_ACCOUNT_TYPES = {
    AccountType.INCOME,
    AccountType.REVENUE,
    AccountType.OTHER_INCOME,
    AccountType.CONTRA_INCOME,
}
FREQUENCY_INTERVALS = {
    PlanningBudgetItemFrequency.ONE_OFF: None,
    PlanningBudgetItemFrequency.MONTHLY: 1,
    PlanningBudgetItemFrequency.QUARTERLY: 3,
    PlanningBudgetItemFrequency.HALF_YEARLY: 6,
    PlanningBudgetItemFrequency.ANNUALLY: 12,
}


def load_plan_or_404(db: Session, company_id: UUID, plan_id: UUID) -> PlanningPlan:
    plan = db.scalar(
        select(PlanningPlan).where(
            PlanningPlan.id == plan_id,
            PlanningPlan.company_id == company_id,
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planning plan not found")
    return plan


def _ensure_company_active(db: Session, company_id: UUID) -> None:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    if not company.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company is inactive")


def _ensure_draft(plan: PlanningPlan) -> None:
    if plan.status != PlanningStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft planning plans can be changed",
        )


def _ensure_revision(plan: PlanningPlan, revision: int) -> None:
    if plan.revision != revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Planning plan changed since it was loaded; current revision is {plan.revision}",
        )


def _periods_for_plan(db: Session, plan_id: UUID) -> list[PlanningPeriod]:
    return list(
        db.scalars(
            select(PlanningPeriod)
            .where(PlanningPeriod.planning_plan_id == plan_id)
            .order_by(PlanningPeriod.sequence_number.asc())
        ).all()
    )


def _validate_actual_through(
    plan_type: PlanningPlanType,
    actual_through_date: date | None,
    start_date: date,
    periods: list[PlanningPeriod] | list[tuple[int, str, date, date]],
) -> date | None:
    if plan_type == PlanningPlanType.BUDGET:
        return None
    cutoff = actual_through_date or start_date - timedelta(days=1)
    valid_dates = {start_date - timedelta(days=1)}
    for period in periods:
        valid_dates.add(period.end_date if isinstance(period, PlanningPeriod) else period[3])
    if cutoff not in valid_dates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forecast actual-through date must be the day before the year or a fiscal month end",
        )
    return cutoff


def _validate_baseline(
    db: Session,
    *,
    company_id: UUID,
    baseline_plan_id: UUID | None,
    start_date: date,
    end_date: date,
) -> PlanningPlan | None:
    if baseline_plan_id is None:
        return None
    baseline = load_plan_or_404(db, company_id, baseline_plan_id)
    if baseline.plan_type != PlanningPlanType.BUDGET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Baseline must be a budget plan"
        )
    if baseline.financial_year_start != start_date or baseline.financial_year_end != end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Baseline budget must use the same financial year",
        )
    return baseline


def list_plans(
    db: Session, company_id: UUID, *, include_archived: bool = False
) -> list[PlanningPlan]:
    query = select(PlanningPlan).where(PlanningPlan.company_id == company_id)
    if not include_archived:
        query = query.where(PlanningPlan.status != PlanningStatus.ARCHIVED)
    return list(
        db.scalars(
            query.order_by(
                PlanningPlan.financial_year_start.desc(),
                PlanningPlan.updated_at.desc(),
            )
        ).all()
    )


def create_plan(
    db: Session,
    *,
    company_id: UUID,
    payload: PlanningPlanCreate,
    acting_user_id: UUID,
    commit: bool = True,
) -> PlanningPlan:
    _ensure_company_active(db, company_id)
    try:
        generated_periods = generate_fiscal_months(
            payload.financial_year_start,
            payload.financial_year_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _validate_baseline(
        db,
        company_id=company_id,
        baseline_plan_id=payload.baseline_budget_plan_id,
        start_date=payload.financial_year_start,
        end_date=payload.financial_year_end,
    )
    actual_through = _validate_actual_through(
        payload.plan_type,
        payload.actual_through_date,
        payload.financial_year_start,
        generated_periods,
    )
    latest_version = db.scalar(
        select(func.max(PlanningPlan.version_number)).where(
            PlanningPlan.company_id == company_id,
            PlanningPlan.name == payload.name.strip(),
        )
    )
    plan = PlanningPlan(
        company_id=company_id,
        name=payload.name.strip(),
        plan_type=payload.plan_type,
        scenario_type=payload.scenario_type,
        scenario_label=payload.scenario_label.strip(),
        financial_year_start=payload.financial_year_start,
        financial_year_end=payload.financial_year_end,
        currency_code="AUD",
        version_number=int(latest_version or 0) + 1,
        revision=1,
        status=PlanningStatus.DRAFT,
        is_primary=False,
        baseline_budget_plan_id=payload.baseline_budget_plan_id,
        actual_through_date=actual_through,
        assumption_summary=payload.assumption_summary,
        preparer_note=payload.preparer_note,
        created_by_user_id=acting_user_id,
    )
    db.add(plan)
    db.flush()

    accounting_periods = {
        (item.start_date, item.end_date): item.id
        for item in db.scalars(
            select(AccountingPeriod).where(AccountingPeriod.company_id == company_id)
        ).all()
    }
    for sequence, label, period_start, period_end in generated_periods:
        db.add(
            PlanningPeriod(
                company_id=company_id,
                planning_plan_id=plan.id,
                sequence_number=sequence,
                period_label=label,
                start_date=period_start,
                end_date=period_end,
                accounting_period_id=accounting_periods.get((period_start, period_end)),
            )
        )
    db.flush()
    log_audit_event(
        db,
        company_id=company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action="planning_plan_created",
        summary=f"Created {plan.plan_type.value} {plan.name} v{plan.version_number}",
        after_state={
            "plan_type": plan.plan_type.value,
            "financial_year_start": plan.financial_year_start.isoformat(),
            "financial_year_end": plan.financial_year_end.isoformat(),
            "scenario": plan.scenario_label,
        },
    )
    if commit:
        db.commit()
        db.refresh(plan)
    return plan


def update_plan(
    db: Session,
    *,
    plan: PlanningPlan,
    payload: PlanningPlanUpdate,
    acting_user_id: UUID,
) -> PlanningPlan:
    _ensure_draft(plan)
    _ensure_revision(plan, payload.revision)
    periods = _periods_for_plan(db, plan.id)
    _validate_baseline(
        db,
        company_id=plan.company_id,
        baseline_plan_id=payload.baseline_budget_plan_id,
        start_date=plan.financial_year_start,
        end_date=plan.financial_year_end,
    )
    actual_through = _validate_actual_through(
        plan.plan_type,
        payload.actual_through_date,
        plan.financial_year_start,
        periods,
    )
    before = {
        "name": plan.name,
        "scenario_label": plan.scenario_label,
        "actual_through_date": plan.actual_through_date.isoformat()
        if plan.actual_through_date
        else None,
    }
    plan.name = payload.name.strip()
    plan.scenario_type = payload.scenario_type
    plan.scenario_label = payload.scenario_label.strip()
    plan.baseline_budget_plan_id = payload.baseline_budget_plan_id
    plan.actual_through_date = actual_through
    plan.assumption_summary = payload.assumption_summary
    plan.preparer_note = payload.preparer_note
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action="planning_plan_updated",
        summary=f"Updated planning plan {plan.name}",
        before_state=before,
        after_state={
            "name": plan.name,
            "scenario_label": plan.scenario_label,
            "actual_through_date": actual_through.isoformat() if actual_through else None,
        },
    )
    db.commit()
    db.refresh(plan)
    return plan


def _eligible_accounts(db: Session, company_id: UUID) -> list[tuple[Account, str | None]]:
    return list(
        db.execute(
            select(Account, ReportingCategory.code)
            .outerjoin(ReportingCategory, ReportingCategory.id == Account.reporting_category_id)
            .where(
                Account.company_id == company_id,
                Account.account_type.in_(PNL_ACCOUNT_TYPES),
            )
            .order_by(Account.account_code.asc())
        ).all()
    )


def _budget_items_for_plan(db: Session, plan_id: UUID) -> list[PlanningBudgetItem]:
    return list(
        db.scalars(
            select(PlanningBudgetItem)
            .where(PlanningBudgetItem.planning_plan_id == plan_id)
            .order_by(PlanningBudgetItem.created_at.asc(), PlanningBudgetItem.name.asc())
        ).all()
    )


def _budget_item_floor_map(
    db: Session,
    plan: PlanningPlan,
) -> dict[tuple[UUID, UUID], Decimal]:
    if plan.plan_type != PlanningPlanType.BUDGET:
        return {}
    periods = _periods_for_plan(db, plan.id)
    period_by_id = {period.id: period for period in periods}
    floor_map: dict[tuple[UUID, UUID], Decimal] = {}
    for item in _budget_items_for_plan(db, plan.id):
        start = period_by_id.get(item.start_period_id)
        end = period_by_id.get(item.end_period_id) if item.end_period_id else periods[-1]
        if start is None or end is None:
            continue
        interval = FREQUENCY_INTERVALS[item.occurrence_frequency]
        sequences = (
            [start.sequence_number]
            if interval is None
            else range(start.sequence_number, end.sequence_number + 1, interval)
        )
        for sequence in sequences:
            period = periods[sequence - 1]
            key = (item.account_id, period.id)
            floor_map[key] = (floor_map.get(key, ZERO) + Decimal(item.amount)).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
    return floor_map


def _floor_reads(
    floor_map: dict[tuple[UUID, UUID], Decimal],
) -> list[PlanningBudgetItemFloorRead]:
    return [
        PlanningBudgetItemFloorRead(
            account_id=account_id,
            planning_period_id=period_id,
            amount=amount,
        )
        for (account_id, period_id), amount in floor_map.items()
    ]


def build_plan_detail(
    db: Session,
    plan: PlanningPlan,
    *,
    floor_adjustments: list[PlanningFloorAdjustmentRead] | None = None,
) -> PlanningPlanDetailRead:
    periods = _periods_for_plan(db, plan.id)
    budget_items = _budget_items_for_plan(db, plan.id)
    floor_map = _budget_item_floor_map(db, plan)
    lines = list(
        db.scalars(
            select(PlanningLine)
            .where(PlanningLine.planning_plan_id == plan.id)
            .order_by(
                PlanningLine.account_code_snapshot.asc(),
                PlanningLine.planning_period_id.asc(),
            )
        ).all()
    )
    account_rows = _eligible_accounts(db, plan.company_id)
    accounts = [
        PlanningAccountRead(
            id=account.id,
            account_code=account.account_code,
            account_name=account.name,
            account_type=account.account_type.value,
            reporting_category_code=category_code,
            is_active=account.is_active,
        )
        for account, category_code in account_rows
        if account.is_active or any(line.account_id == account.id for line in lines)
    ]
    warnings: list[PlanningWarningRead] = []
    planned_account_ids = {line.account_id for line in lines}
    for account, category_code in account_rows:
        if account.is_active and account.id not in planned_account_ids:
            warnings.append(
                PlanningWarningRead(
                    code="UNPLANNED_ACTIVE_ACCOUNT",
                    account_id=account.id,
                    message=f"{account.account_code} {account.name} has no planned values",
                )
            )
        if account.is_active and category_code is None:
            warnings.append(
                PlanningWarningRead(
                    code="MISSING_REPORTING_CATEGORY",
                    account_id=account.id,
                    message=f"{account.account_code} {account.name} has no reporting category",
                    severity="info",
                )
            )
        if not account.is_active and account.id in planned_account_ids:
            warnings.append(
                PlanningWarningRead(
                    code="INACTIVE_ACCOUNT_IN_PLAN",
                    account_id=account.id,
                    message=f"{account.account_code} {account.name} is inactive but remains in this plan",
                )
            )

    account_types = {account.id: account.account_type for account, _ in account_rows}
    income = sum(
        (
            line.amount
            for line in lines
            if account_types.get(line.account_id) in INCOME_ACCOUNT_TYPES
        ),
        ZERO,
    )
    expenses = sum(
        (
            line.amount
            for line in lines
            if account_types.get(line.account_id) not in INCOME_ACCOUNT_TYPES
        ),
        ZERO,
    )
    return PlanningPlanDetailRead(
        plan=PlanningPlanRead.model_validate(plan),
        periods=[PlanningPeriodRead.model_validate(period) for period in periods],
        lines=[PlanningLineRead.model_validate(line) for line in lines],
        budget_items=[PlanningBudgetItemRead.model_validate(item) for item in budget_items],
        budget_item_floors=_floor_reads(floor_map),
        floor_adjustments=floor_adjustments or [],
        accounts=accounts,
        warnings=warnings,
        annual_budget_income=income,
        annual_budget_expenses=expenses,
        annual_budget_net_profit=income - expenses,
        can_edit=plan.status == PlanningStatus.DRAFT,
    )


def _ensure_budget_plan(plan: PlanningPlan) -> None:
    if plan.plan_type != PlanningPlanType.BUDGET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget items can only be managed on budget plans",
        )


def _validate_budget_item_fields(
    db: Session,
    *,
    plan: PlanningPlan,
    account_id: UUID,
    start_period_id: UUID,
    end_period_id: UUID | None,
) -> None:
    account = db.get(Account, account_id)
    if account is None or account.company_id != plan.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Planning account not found"
        )
    if account.account_type not in PNL_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account {account.account_code} is not a profit-and-loss account",
        )
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account {account.account_code} is inactive",
        )
    period_map = {period.id: period for period in _periods_for_plan(db, plan.id)}
    start = period_map.get(start_period_id)
    end = period_map.get(end_period_id) if end_period_id else None
    if start is None or (end_period_id is not None and end is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget item start and end months must belong to the selected plan",
        )
    if end is not None and end.sequence_number < start.sequence_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget item end month cannot be before its start month",
        )


def _apply_budget_item_floors(
    db: Session,
    *,
    plan: PlanningPlan,
    acting_user_id: UUID,
) -> list[PlanningFloorAdjustmentRead]:
    floor_map = _budget_item_floor_map(db, plan)
    if not floor_map:
        return []
    existing = {
        (line.account_id, line.planning_period_id): line
        for line in db.scalars(
            select(PlanningLine).where(PlanningLine.planning_plan_id == plan.id)
        ).all()
    }
    account_rows = {
        account.id: (account, category_code)
        for account, category_code in _eligible_accounts(db, plan.company_id)
    }
    adjustments: list[PlanningFloorAdjustmentRead] = []
    for (account_id, period_id), minimum in floor_map.items():
        current = existing.get((account_id, period_id))
        requested = current.amount if current is not None else None
        if current is not None and current.amount >= minimum:
            continue
        account, category_code = account_rows[account_id]
        adjustments.append(
            PlanningFloorAdjustmentRead(
                account_id=account_id,
                planning_period_id=period_id,
                requested_amount=requested,
                applied_minimum=minimum,
            )
        )
        if current is None:
            db.add(
                PlanningLine(
                    company_id=plan.company_id,
                    planning_plan_id=plan.id,
                    planning_period_id=period_id,
                    account_id=account_id,
                    amount=minimum,
                    entry_method=PlanningEntryMethod.MANUAL,
                    note="Budget item minimum",
                    account_code_snapshot=account.account_code,
                    account_name_snapshot=account.name,
                    account_type_snapshot=account.account_type,
                    reporting_category_code_snapshot=category_code,
                    created_by_user_id=acting_user_id,
                    updated_by_user_id=acting_user_id,
                )
            )
        else:
            current.amount = minimum
            current.updated_by_user_id = acting_user_id
    return adjustments


def list_budget_items(db: Session, plan: PlanningPlan) -> list[PlanningBudgetItem]:
    _ensure_budget_plan(plan)
    return _budget_items_for_plan(db, plan.id)


def load_budget_item_or_404(
    db: Session,
    *,
    plan: PlanningPlan,
    item_id: UUID,
) -> PlanningBudgetItem:
    item = db.scalar(
        select(PlanningBudgetItem).where(
            PlanningBudgetItem.id == item_id,
            PlanningBudgetItem.planning_plan_id == plan.id,
            PlanningBudgetItem.company_id == plan.company_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget item not found")
    return item


def create_budget_item(
    db: Session,
    *,
    plan: PlanningPlan,
    payload: PlanningBudgetItemCreate,
    acting_user_id: UUID,
) -> PlanningPlanDetailRead:
    _ensure_draft(plan)
    _ensure_budget_plan(plan)
    _ensure_revision(plan, payload.revision)
    _validate_budget_item_fields(
        db,
        plan=plan,
        account_id=payload.account_id,
        start_period_id=payload.start_period_id,
        end_period_id=payload.end_period_id,
    )
    item = PlanningBudgetItem(
        company_id=plan.company_id,
        planning_plan_id=plan.id,
        account_id=payload.account_id,
        name=payload.name.strip(),
        amount=Decimal(payload.amount).quantize(CENT, rounding=ROUND_HALF_UP),
        occurrence_frequency=payload.occurrence_frequency,
        start_period_id=payload.start_period_id,
        end_period_id=payload.end_period_id,
        note=payload.note,
        created_by_user_id=acting_user_id,
        updated_by_user_id=acting_user_id,
    )
    db.add(item)
    db.flush()
    adjustments = _apply_budget_item_floors(
        db,
        plan=plan,
        acting_user_id=acting_user_id,
    )
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_budget_item",
        entity_id=item.id,
        action="planning_budget_item_created",
        summary=f"Created budget item {item.name} in {plan.name}",
        after_state={
            "account_id": str(item.account_id),
            "amount": str(item.amount),
            "occurrence_frequency": item.occurrence_frequency.value,
            "start_period_id": str(item.start_period_id),
            "end_period_id": str(item.end_period_id) if item.end_period_id else None,
        },
        metadata={"floor_adjustment_count": len(adjustments)},
    )
    db.commit()
    db.refresh(plan)
    return build_plan_detail(db, plan, floor_adjustments=adjustments)


def update_budget_item(
    db: Session,
    *,
    plan: PlanningPlan,
    item: PlanningBudgetItem,
    payload: PlanningBudgetItemUpdate,
    acting_user_id: UUID,
) -> PlanningPlanDetailRead:
    _ensure_draft(plan)
    _ensure_budget_plan(plan)
    _ensure_revision(plan, payload.revision)
    _validate_budget_item_fields(
        db,
        plan=plan,
        account_id=payload.account_id,
        start_period_id=payload.start_period_id,
        end_period_id=payload.end_period_id,
    )
    before = {
        "name": item.name,
        "account_id": str(item.account_id),
        "amount": str(item.amount),
        "occurrence_frequency": item.occurrence_frequency.value,
        "start_period_id": str(item.start_period_id),
        "end_period_id": str(item.end_period_id) if item.end_period_id else None,
    }
    item.name = payload.name.strip()
    item.account_id = payload.account_id
    item.amount = Decimal(payload.amount).quantize(CENT, rounding=ROUND_HALF_UP)
    item.occurrence_frequency = payload.occurrence_frequency
    item.start_period_id = payload.start_period_id
    item.end_period_id = payload.end_period_id
    item.note = payload.note
    item.updated_by_user_id = acting_user_id
    db.flush()
    adjustments = _apply_budget_item_floors(
        db,
        plan=plan,
        acting_user_id=acting_user_id,
    )
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_budget_item",
        entity_id=item.id,
        action="planning_budget_item_updated",
        summary=f"Updated budget item {item.name} in {plan.name}",
        before_state=before,
        after_state={
            "name": item.name,
            "account_id": str(item.account_id),
            "amount": str(item.amount),
            "occurrence_frequency": item.occurrence_frequency.value,
            "start_period_id": str(item.start_period_id),
            "end_period_id": str(item.end_period_id) if item.end_period_id else None,
        },
        metadata={"floor_adjustment_count": len(adjustments)},
    )
    db.commit()
    db.refresh(plan)
    return build_plan_detail(db, plan, floor_adjustments=adjustments)


def delete_budget_item(
    db: Session,
    *,
    plan: PlanningPlan,
    item: PlanningBudgetItem,
    revision: int,
    acting_user_id: UUID,
) -> None:
    _ensure_draft(plan)
    _ensure_budget_plan(plan)
    _ensure_revision(plan, revision)
    item_id = item.id
    item_name = item.name
    item_state = {
        "account_id": str(item.account_id),
        "amount": str(item.amount),
        "occurrence_frequency": item.occurrence_frequency.value,
        "start_period_id": str(item.start_period_id),
        "end_period_id": str(item.end_period_id) if item.end_period_id else None,
    }
    db.delete(item)
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_budget_item",
        entity_id=item_id,
        action="planning_budget_item_deleted",
        summary=f"Deleted budget item {item_name} from {plan.name}",
        before_state=item_state,
    )
    db.commit()


def _upsert_lines(
    db: Session,
    *,
    plan: PlanningPlan,
    line_inputs: list[PlanningLineInput],
    acting_user_id: UUID,
) -> tuple[int, int, list[PlanningFloorAdjustmentRead]]:
    period_ids = {period.id for period in _periods_for_plan(db, plan.id)}
    requested_period_ids = {item.planning_period_id for item in line_inputs}
    if not requested_period_ids.issubset(period_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Every planning period must belong to the selected plan",
        )
    account_ids = {item.account_id for item in line_inputs}
    account_rows = list(
        db.execute(
            select(Account, ReportingCategory.code)
            .outerjoin(ReportingCategory, ReportingCategory.id == Account.reporting_category_id)
            .where(Account.id.in_(account_ids))
        ).all()
    )
    account_map = {account.id: (account, category_code) for account, category_code in account_rows}
    if len(account_map) != len(account_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Planning account not found"
        )
    for account, _ in account_map.values():
        if account.company_id != plan.company_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Planning account not found"
            )
        if account.account_type not in PNL_ACCOUNT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account {account.account_code} is not a profit-and-loss account",
            )
        if not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Account {account.account_code} is inactive",
            )

    existing = {
        (line.account_id, line.planning_period_id): line
        for line in db.scalars(
            select(PlanningLine).where(
                PlanningLine.planning_plan_id == plan.id,
                PlanningLine.account_id.in_(account_ids),
                PlanningLine.planning_period_id.in_(requested_period_ids),
            )
        ).all()
    }
    changed = 0
    deleted_count = 0
    floor_map = _budget_item_floor_map(db, plan)
    floor_adjustments: list[PlanningFloorAdjustmentRead] = []
    for item in line_inputs:
        key = (item.account_id, item.planning_period_id)
        current = existing.get(key)
        requested_amount = (
            Decimal(item.amount).quantize(CENT, rounding=ROUND_HALF_UP)
            if item.amount is not None
            else None
        )
        minimum = floor_map.get(key)
        amount = requested_amount
        if minimum is not None and (amount is None or amount < minimum):
            floor_adjustments.append(
                PlanningFloorAdjustmentRead(
                    account_id=item.account_id,
                    planning_period_id=item.planning_period_id,
                    requested_amount=requested_amount,
                    applied_minimum=minimum,
                )
            )
            amount = minimum
        if amount is None:
            if current is not None:
                db.delete(current)
                changed += 1
                deleted_count += 1
            continue
        account, category_code = account_map[item.account_id]
        if current is None:
            db.add(
                PlanningLine(
                    company_id=plan.company_id,
                    planning_plan_id=plan.id,
                    planning_period_id=item.planning_period_id,
                    account_id=item.account_id,
                    amount=amount,
                    entry_method=item.entry_method,
                    note=item.note,
                    account_code_snapshot=account.account_code,
                    account_name_snapshot=account.name,
                    account_type_snapshot=account.account_type,
                    reporting_category_code_snapshot=category_code,
                    created_by_user_id=acting_user_id,
                    updated_by_user_id=acting_user_id,
                )
            )
            changed += 1
        elif (
            current.amount != amount
            or current.entry_method != item.entry_method
            or current.note != item.note
        ):
            current.amount = amount
            current.entry_method = item.entry_method
            current.note = item.note
            current.updated_by_user_id = acting_user_id
            changed += 1
    return changed, deleted_count, floor_adjustments


def bulk_update_lines(
    db: Session,
    *,
    plan: PlanningPlan,
    payload: PlanningLineBulkUpdate,
    acting_user_id: UUID,
) -> PlanningPlanDetailRead:
    _ensure_draft(plan)
    _ensure_revision(plan, payload.revision)
    changed, deleted_count, floor_adjustments = _upsert_lines(
        db,
        plan=plan,
        line_inputs=payload.lines,
        acting_user_id=acting_user_id,
    )
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action="planning_lines_bulk_updated",
        summary=f"Updated {changed} planning values in {plan.name}",
        metadata={
            "submitted_line_count": len(payload.lines),
            "changed_line_count": changed,
            "deleted_line_count": deleted_count,
            "floor_adjustment_count": len(floor_adjustments),
        },
    )
    db.commit()
    db.refresh(plan)
    return build_plan_detail(db, plan, floor_adjustments=floor_adjustments)


def spread_annual_amount(
    db: Session,
    *,
    plan: PlanningPlan,
    payload: PlanningSpreadRequest,
    acting_user_id: UUID,
) -> PlanningPlanDetailRead:
    _ensure_draft(plan)
    _ensure_revision(plan, payload.revision)
    periods = _periods_for_plan(db, plan.id)
    selected = periods
    if payload.period_ids is not None:
        selected_ids = set(payload.period_ids)
        selected = [period for period in periods if period.id in selected_ids]
        if len(selected) != len(selected_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Every selected spread period must belong to the plan",
            )
    if not selected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one period"
        )

    annual_amount = Decimal(payload.annual_amount).quantize(CENT, rounding=ROUND_HALF_UP)
    if payload.percentages is not None:
        if len(payload.percentages) != len(selected):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom percentages must match the selected periods",
            )
        percentages = [Decimal(value) for value in payload.percentages]
        if sum(percentages, ZERO).quantize(Decimal("0.0001")) != Decimal("100.0000"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom percentages must total 100",
            )
        amounts = [
            (annual_amount * percentage / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
            for percentage in percentages
        ]
    else:
        equal = (annual_amount / Decimal(len(selected))).quantize(CENT, rounding=ROUND_HALF_UP)
        amounts = [equal for _ in selected]
    amounts[-1] += annual_amount - sum(amounts, ZERO)

    inputs = [
        PlanningLineInput(
            planning_period_id=period.id,
            account_id=payload.account_id,
            amount=amount,
            entry_method=PlanningEntryMethod.ANNUAL_SPREAD,
            note=payload.note,
        )
        for period, amount in zip(selected, amounts, strict=True)
    ]
    changed, _, floor_adjustments = _upsert_lines(
        db,
        plan=plan,
        line_inputs=inputs,
        acting_user_id=acting_user_id,
    )
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action="planning_annual_amount_spread",
        summary=f"Spread {annual_amount} across {len(selected)} periods in {plan.name}",
        metadata={
            "changed_line_count": changed,
            "account_id": str(payload.account_id),
            "floor_adjustment_count": len(floor_adjustments),
        },
    )
    db.commit()
    db.refresh(plan)
    return build_plan_detail(db, plan, floor_adjustments=floor_adjustments)


def copy_prior_actuals(
    db: Session,
    *,
    plan: PlanningPlan,
    payload: PlanningCopyPriorActualsRequest,
    acting_user_id: UUID,
) -> PlanningPlanDetailRead:
    _ensure_draft(plan)
    _ensure_revision(plan, payload.revision)
    factor = Decimal("1.00") + Decimal(payload.growth_percentage) / Decimal(100)
    inputs: list[PlanningLineInput] = []
    for period in _periods_for_plan(db, plan.id):
        source_start = add_months(period.start_date, -12)
        source_end = add_months(period.end_date + timedelta(days=1), -12) - timedelta(days=1)
        aggregates = _aggregate_accounts(
            db,
            company_id=plan.company_id,
            start_date=source_start,
            end_date=source_end,
            account_types=PNL_ACCOUNT_TYPES,
            include_draft=False,
            exclude_period_rollovers=True,
        )
        for aggregate in aggregates:
            amount = (
                _display_amount(aggregate.account_type, aggregate.raw_balance) * factor
            ).quantize(
                CENT,
                rounding=ROUND_HALF_UP,
            )
            inputs.append(
                PlanningLineInput(
                    planning_period_id=period.id,
                    account_id=aggregate.account_id,
                    amount=amount,
                    entry_method=PlanningEntryMethod.PRIOR_ACTUAL,
                    note=payload.note,
                )
            )
    if not inputs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No posted prior-year P&L actuals were found",
        )
    changed, _, floor_adjustments = _upsert_lines(
        db,
        plan=plan,
        line_inputs=inputs,
        acting_user_id=acting_user_id,
    )
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action="planning_prior_actuals_copied",
        summary=f"Copied prior-year actuals into {plan.name}",
        metadata={
            "growth_percentage": str(payload.growth_percentage),
            "changed_line_count": changed,
            "floor_adjustment_count": len(floor_adjustments),
        },
    )
    db.commit()
    db.refresh(plan)
    return build_plan_detail(db, plan, floor_adjustments=floor_adjustments)


def apply_growth(
    db: Session,
    *,
    plan: PlanningPlan,
    payload: PlanningApplyGrowthRequest,
    acting_user_id: UUID,
) -> PlanningPlanDetailRead:
    _ensure_draft(plan)
    _ensure_revision(plan, payload.revision)
    query = select(PlanningLine).where(PlanningLine.planning_plan_id == plan.id)
    if payload.account_ids:
        query = query.where(PlanningLine.account_id.in_(set(payload.account_ids)))
    if payload.planning_period_ids:
        query = query.where(PlanningLine.planning_period_id.in_(set(payload.planning_period_ids)))
    lines = list(db.scalars(query).all())
    if not lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No planning values matched the growth selection",
        )
    factor = Decimal("1.00") + Decimal(payload.growth_percentage) / Decimal(100)
    for line in lines:
        line.amount = (line.amount * factor).quantize(CENT, rounding=ROUND_HALF_UP)
        line.entry_method = PlanningEntryMethod.GROWTH_RATE
        line.note = payload.note or line.note
        line.updated_by_user_id = acting_user_id
    floor_adjustments = _apply_budget_item_floors(
        db,
        plan=plan,
        acting_user_id=acting_user_id,
    )
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action="planning_growth_applied",
        summary=f"Applied {payload.growth_percentage}% growth to {len(lines)} values in {plan.name}",
        metadata={
            "growth_percentage": str(payload.growth_percentage),
            "line_count": len(lines),
            "floor_adjustment_count": len(floor_adjustments),
        },
    )
    db.commit()
    db.refresh(plan)
    return build_plan_detail(db, plan, floor_adjustments=floor_adjustments)


def preview_csv_import(
    db: Session,
    *,
    plan: PlanningPlan,
    content: bytes,
) -> PlanningImportPreviewRead:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planning CSV must be UTF-8 encoded",
        ) from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {"account_code", "period_start", "amount"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planning CSV requires account_code, period_start, and amount columns",
        )
    accounts_by_code = {
        account.account_code: account
        for account, _ in _eligible_accounts(db, plan.company_id)
        if account.is_active
    }
    periods_by_start = {
        period.start_date.isoformat(): period for period in _periods_for_plan(db, plan.id)
    }
    lines: list[PlanningLineInput] = []
    errors: list[PlanningImportErrorRead] = []
    seen: set[tuple[UUID, UUID]] = set()
    for row_number, row in enumerate(reader, start=2):
        account = accounts_by_code.get((row.get("account_code") or "").strip())
        period = periods_by_start.get((row.get("period_start") or "").strip())
        if account is None:
            errors.append(
                PlanningImportErrorRead(
                    row_number=row_number, message="Unknown or inactive account code"
                )
            )
            continue
        if period is None:
            errors.append(
                PlanningImportErrorRead(
                    row_number=row_number, message="Period start is outside this plan"
                )
            )
            continue
        key = (account.id, period.id)
        if key in seen:
            errors.append(
                PlanningImportErrorRead(
                    row_number=row_number, message="Duplicate account and period"
                )
            )
            continue
        try:
            amount = Decimal((row.get("amount") or "").replace(",", "")).quantize(
                CENT,
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, ValueError):
            errors.append(
                PlanningImportErrorRead(
                    row_number=row_number, message="Amount is not a valid decimal"
                )
            )
            continue
        seen.add(key)
        lines.append(
            PlanningLineInput(
                planning_period_id=period.id,
                account_id=account.id,
                amount=amount,
                entry_method=PlanningEntryMethod.CSV_IMPORT,
                note=(row.get("note") or "").strip() or None,
            )
        )
    return PlanningImportPreviewRead(valid_rows=len(lines), lines=lines, errors=errors)


def commit_csv_import(
    db: Session,
    *,
    plan: PlanningPlan,
    revision: int,
    content: bytes,
    acting_user_id: UUID,
) -> PlanningPlanDetailRead:
    _ensure_draft(plan)
    _ensure_revision(plan, revision)
    preview = preview_csv_import(db, plan=plan, content=content)
    if preview.errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Planning CSV contains validation errors",
                "errors": [error.model_dump() for error in preview.errors],
            },
        )
    if not preview.lines:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Planning CSV is empty")
    changed, _, floor_adjustments = _upsert_lines(
        db,
        plan=plan,
        line_inputs=preview.lines,
        acting_user_id=acting_user_id,
    )
    plan.revision += 1
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action="planning_csv_imported",
        summary=f"Imported {changed} planning values into {plan.name}",
        metadata={
            "valid_rows": preview.valid_rows,
            "changed_line_count": changed,
            "floor_adjustment_count": len(floor_adjustments),
        },
    )
    db.commit()
    db.refresh(plan)
    return build_plan_detail(db, plan, floor_adjustments=floor_adjustments)


def clone_plan(
    db: Session,
    *,
    source: PlanningPlan,
    payload: PlanningCloneRequest,
    acting_user_id: UUID,
) -> PlanningPlan:
    target_type = payload.plan_type or source.plan_type
    target_scenario = payload.scenario_type or source.scenario_type
    baseline_id = payload.baseline_budget_plan_id
    if target_type == PlanningPlanType.FORECAST and baseline_id is None:
        baseline_id = (
            source.id
            if source.plan_type == PlanningPlanType.BUDGET
            else source.baseline_budget_plan_id
        )
    created = create_plan(
        db,
        company_id=source.company_id,
        payload=PlanningPlanCreate(
            name=payload.name,
            plan_type=target_type,
            scenario_type=target_scenario,
            scenario_label=payload.scenario_label or source.scenario_label,
            financial_year_start=source.financial_year_start,
            financial_year_end=source.financial_year_end,
            baseline_budget_plan_id=baseline_id,
            actual_through_date=payload.actual_through_date,
            assumption_summary=source.assumption_summary,
            preparer_note=payload.preparer_note,
        ),
        acting_user_id=acting_user_id,
        commit=False,
    )
    source_periods = _periods_for_plan(db, source.id)
    target_periods = _periods_for_plan(db, created.id)
    target_by_sequence = {period.sequence_number: period for period in target_periods}
    source_sequence = {period.id: period.sequence_number for period in source_periods}
    source_lines = list(
        db.scalars(select(PlanningLine).where(PlanningLine.planning_plan_id == source.id)).all()
    )
    for line in source_lines:
        db.add(
            PlanningLine(
                company_id=created.company_id,
                planning_plan_id=created.id,
                planning_period_id=target_by_sequence[source_sequence[line.planning_period_id]].id,
                account_id=line.account_id,
                amount=line.amount,
                entry_method=(
                    PlanningEntryMethod.PRIOR_BUDGET
                    if source.plan_type == PlanningPlanType.BUDGET
                    else line.entry_method
                ),
                note=line.note,
                account_code_snapshot=line.account_code_snapshot,
                account_name_snapshot=line.account_name_snapshot,
                account_type_snapshot=line.account_type_snapshot,
                reporting_category_code_snapshot=line.reporting_category_code_snapshot,
                created_by_user_id=acting_user_id,
                updated_by_user_id=acting_user_id,
            )
        )
    cloned_item_count = 0
    if source.plan_type == PlanningPlanType.BUDGET and target_type == PlanningPlanType.BUDGET:
        for item in _budget_items_for_plan(db, source.id):
            db.add(
                PlanningBudgetItem(
                    company_id=created.company_id,
                    planning_plan_id=created.id,
                    account_id=item.account_id,
                    name=item.name,
                    amount=item.amount,
                    occurrence_frequency=item.occurrence_frequency,
                    start_period_id=target_by_sequence[source_sequence[item.start_period_id]].id,
                    end_period_id=(
                        target_by_sequence[source_sequence[item.end_period_id]].id
                        if item.end_period_id
                        else None
                    ),
                    note=item.note,
                    created_by_user_id=acting_user_id,
                    updated_by_user_id=acting_user_id,
                )
            )
            cloned_item_count += 1
        db.flush()
        _apply_budget_item_floors(
            db,
            plan=created,
            acting_user_id=acting_user_id,
        )
    created.source_plan_id = source.id
    created.revision += 1
    log_audit_event(
        db,
        company_id=source.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=created.id,
        action="planning_plan_cloned",
        summary=f"Cloned {source.name} into {created.name}",
        metadata={
            "source_plan_id": str(source.id),
            "line_count": len(source_lines),
            "budget_item_count": cloned_item_count,
        },
    )
    db.commit()
    db.refresh(created)
    return created


def submit_plan(
    db: Session, *, plan: PlanningPlan, acting_user_id: UUID, note: str | None
) -> PlanningPlan:
    _ensure_draft(plan)
    if (
        db.scalar(select(PlanningLine.id).where(PlanningLine.planning_plan_id == plan.id).limit(1))
        is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add at least one planning value before submitting",
        )
    plan.status = PlanningStatus.IN_REVIEW
    plan.preparer_note = note or plan.preparer_note
    plan.revision += 1
    _audit_status(db, plan, acting_user_id, "planning_plan_submitted", note)
    db.commit()
    db.refresh(plan)
    return plan


def review_plan(
    db: Session, *, plan: PlanningPlan, acting_user_id: UUID, note: str | None
) -> PlanningPlan:
    if plan.status != PlanningStatus.IN_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan is not in review")
    plan.reviewed_by_user_id = acting_user_id
    plan.reviewed_at = datetime.now(UTC)
    plan.review_note = note
    plan.revision += 1
    _audit_status(db, plan, acting_user_id, "planning_plan_reviewed", note)
    db.commit()
    db.refresh(plan)
    return plan


def reject_plan(
    db: Session, *, plan: PlanningPlan, acting_user_id: UUID, note: str | None
) -> PlanningPlan:
    if plan.status != PlanningStatus.IN_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan is not in review")
    if not note:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Rejection note is required"
        )
    plan.status = PlanningStatus.DRAFT
    plan.reviewed_by_user_id = acting_user_id
    plan.reviewed_at = datetime.now(UTC)
    plan.review_note = note
    plan.revision += 1
    _audit_status(db, plan, acting_user_id, "planning_plan_rejected", note)
    db.commit()
    db.refresh(plan)
    return plan


def approve_plan(
    db: Session, *, plan: PlanningPlan, acting_user_id: UUID, note: str | None
) -> PlanningPlan:
    if plan.status != PlanningStatus.IN_REVIEW:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan is not in review")
    configuration = db.scalar(
        select(CompanyConfigurationVersion)
        .where(CompanyConfigurationVersion.company_id == plan.company_id)
        .order_by(CompanyConfigurationVersion.version_number.desc())
        .limit(1)
    )
    if (
        configuration is not None
        and configuration.self_approval_mode == SelfApprovalMode.BLOCK
        and plan.created_by_user_id == acting_user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company policy blocks self-approval for this action",
        )
    if (
        plan.plan_type == PlanningPlanType.BUDGET
        and plan.scenario_type == PlanningScenarioType.BASELINE
    ):
        db.execute(
            update(PlanningPlan)
            .where(
                PlanningPlan.company_id == plan.company_id,
                PlanningPlan.financial_year_start == plan.financial_year_start,
                PlanningPlan.financial_year_end == plan.financial_year_end,
                PlanningPlan.plan_type == PlanningPlanType.BUDGET,
                PlanningPlan.scenario_type == PlanningScenarioType.BASELINE,
                PlanningPlan.id != plan.id,
            )
            .values(is_primary=False)
        )
        plan.is_primary = True
    plan.status = PlanningStatus.APPROVED
    plan.approved_by_user_id = acting_user_id
    plan.approved_at = datetime.now(UTC)
    if note:
        plan.review_note = note
    plan.revision += 1
    _audit_status(db, plan, acting_user_id, "planning_plan_approved", note)
    db.commit()
    db.refresh(plan)
    return plan


def lock_plan(
    db: Session, *, plan: PlanningPlan, acting_user_id: UUID, note: str | None
) -> PlanningPlan:
    if plan.status != PlanningStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only approved plans can be locked"
        )
    plan.status = PlanningStatus.LOCKED
    plan.locked_by_user_id = acting_user_id
    plan.locked_at = datetime.now(UTC)
    plan.revision += 1
    _audit_status(db, plan, acting_user_id, "planning_plan_locked", note)
    db.commit()
    db.refresh(plan)
    return plan


def archive_plan(
    db: Session, *, plan: PlanningPlan, acting_user_id: UUID, note: str | None
) -> PlanningPlan:
    if plan.status == PlanningStatus.ARCHIVED:
        return plan
    plan.status = PlanningStatus.ARCHIVED
    plan.is_primary = False
    plan.archived_by_user_id = acting_user_id
    plan.archived_at = datetime.now(UTC)
    plan.revision += 1
    _audit_status(db, plan, acting_user_id, "planning_plan_archived", note)
    db.commit()
    db.refresh(plan)
    return plan


def delete_draft_plan(db: Session, *, plan: PlanningPlan, acting_user_id: UUID) -> None:
    _ensure_draft(plan)
    if (
        db.scalar(
            select(PlanningForecastRun.id)
            .where(PlanningForecastRun.forecast_plan_id == plan.id)
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan has forecast runs")
    if (
        db.scalar(
            select(PlanningPlan.id)
            .where(
                (PlanningPlan.source_plan_id == plan.id)
                | (PlanningPlan.baseline_budget_plan_id == plan.id)
            )
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Plan is referenced by another plan"
        )
    plan_id = plan.id
    name = plan.name
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan_id,
        action="planning_plan_deleted",
        summary=f"Deleted draft planning plan {name}",
    )
    db.delete(plan)
    db.commit()


def _audit_status(
    db: Session,
    plan: PlanningPlan,
    acting_user_id: UUID,
    action: str,
    note: str | None,
) -> None:
    log_audit_event(
        db,
        company_id=plan.company_id,
        actor_user_id=acting_user_id,
        entity_type="planning_plan",
        entity_id=plan.id,
        action=action,
        summary=f"{action.replace('_', ' ').title()}: {plan.name}",
        after_state={"status": plan.status.value, "revision": plan.revision},
        metadata={"note": note} if note else None,
    )
