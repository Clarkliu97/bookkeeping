import csv
import io
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit.service import log_audit_event
from app.db.models.accounting import Account, AccountingPeriod, JournalEntry, JournalLine, PeriodLock
from app.db.models.enums import (
    AccountType,
    DepreciationMethod,
    DepreciationRunStatus,
    EntityType,
    FixedAssetStatus,
    JournalSourceType,
    JournalStatus,
    WorkflowStatus,
)
from app.db.models.fixed_assets import DepreciationRun, DepreciationRunLine, FixedAsset, FixedAssetStatusHistory
from app.schemas.common import (
    DepreciationRunDetailRead,
    DepreciationRunRead,
    FixedAssetDetailRead,
    FixedAssetRead,
    FixedAssetRegisterRead,
)


ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")
FOUR_PLACES = Decimal("0.0001")


@dataclass(slots=True)
class AssetDepreciationAmounts:
    run_amount: Decimal
    accumulated_opening: Decimal
    accumulated_closing: Decimal
    carrying_opening: Decimal
    carrying_closing: Decimal


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _load_period_or_raise(db: Session, company_id: UUID, accounting_period_id: UUID) -> AccountingPeriod:
    period = db.get(AccountingPeriod, accounting_period_id)
    if period is None or period.company_id != company_id:
        raise ValueError("Accounting period not found")
    return period


def _ensure_period_not_locked(db: Session, company_id: UUID, accounting_period_id: UUID) -> None:
    period = _load_period_or_raise(db, company_id, accounting_period_id)
    if period.status == WorkflowStatus.LOCKED:
        raise ValueError("Accounting period is locked")
    active_lock = db.scalar(
        select(PeriodLock)
        .where(PeriodLock.accounting_period_id == accounting_period_id, PeriodLock.unlocked_at.is_(None))
        .limit(1)
    )
    if active_lock is not None:
        raise ValueError("Accounting period is locked")


def _next_entry_number(db: Session, company_id: UUID) -> str:
    latest_entry_number = db.scalar(
        select(JournalEntry.entry_number)
        .where(JournalEntry.company_id == company_id)
        .order_by(JournalEntry.entry_number.desc())
        .limit(1)
    )
    if not latest_entry_number:
        next_number = 1
    else:
        try:
            next_number = int(latest_entry_number.removeprefix("JE-")) + 1
        except ValueError:
            next_number = 1
    return f"JE-{next_number:06d}"


def _validate_accounts(db: Session, company_id: UUID, asset: FixedAsset) -> None:
    accounts = list(
        db.scalars(
            select(Account).where(
                Account.company_id == company_id,
                Account.id.in_(
                    [
                        asset.asset_account_id,
                        asset.accumulated_depreciation_account_id,
                        asset.depreciation_expense_account_id,
                    ]
                ),
            )
        ).all()
    )
    if len(accounts) != 3:
        raise ValueError("Fixed asset references invalid account ids")
    account_map = {account.id: account for account in accounts}
    if account_map[asset.asset_account_id].account_type not in {AccountType.ASSET, AccountType.CONTRA_ASSET}:
        raise ValueError("Asset account must be an asset account")
    if account_map[asset.accumulated_depreciation_account_id].account_type != AccountType.CONTRA_ASSET:
        raise ValueError("Accumulated depreciation account must be a contra asset account")
    if account_map[asset.depreciation_expense_account_id].account_type != AccountType.EXPENSE:
        raise ValueError("Depreciation expense account must be an expense account")


def _service_start(asset: FixedAsset) -> date:
    return max(asset.acquisition_date, asset.in_service_date)


def _service_end(asset: FixedAsset, as_of_date: date) -> date | None:
    end_date = as_of_date
    if asset.disposal_date is not None and asset.disposal_date < end_date:
        end_date = asset.disposal_date
    if end_date < _service_start(asset):
        return None
    return end_date


def _iter_month_segments(start_date: date, end_date: date):
    cursor = start_date.replace(day=1)
    while cursor <= end_date:
        days_in_month = monthrange(cursor.year, cursor.month)[1]
        month_start = cursor
        month_end = cursor.replace(day=days_in_month)
        segment_start = max(start_date, month_start)
        segment_end = min(end_date, month_end)
        if segment_start <= segment_end:
            active_days = Decimal((segment_end - segment_start).days + 1)
            yield segment_start, segment_end, active_days, Decimal(days_in_month)
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)


def _straight_line_to_date(asset: FixedAsset, as_of_date: date) -> Decimal:
    service_end = _service_end(asset, as_of_date)
    if service_end is None:
        return ZERO
    depreciable_base = asset.cost_amount - asset.salvage_value
    monthly_amount = depreciable_base / Decimal(asset.useful_life_months)
    total = ZERO
    for _, _, active_days, days_in_month in _iter_month_segments(_service_start(asset), service_end):
        total += monthly_amount * (active_days / days_in_month)
    return _quantize(min(depreciable_base, total))


def _diminishing_value_to_date(asset: FixedAsset, as_of_date: date) -> Decimal:
    service_end = _service_end(asset, as_of_date)
    if service_end is None:
        return ZERO
    if asset.diminishing_value_rate is None:
        raise ValueError("Diminishing value assets require an annual depreciation rate")
    carrying_amount = asset.cost_amount
    annual_rate = asset.diminishing_value_rate.quantize(FOUR_PLACES)
    for _, _, active_days, days_in_month in _iter_month_segments(_service_start(asset), service_end):
        depreciable_carrying = max(carrying_amount - asset.salvage_value, ZERO)
        if depreciable_carrying == ZERO:
            break
        monthly_amount = depreciable_carrying * annual_rate / Decimal("12")
        segment_amount = monthly_amount * (active_days / days_in_month)
        segment_amount = min(depreciable_carrying, segment_amount)
        carrying_amount -= segment_amount
    return _quantize(asset.cost_amount - carrying_amount)


def accumulated_depreciation_to_date(asset: FixedAsset, as_of_date: date) -> Decimal:
    if as_of_date < _service_start(asset):
        return ZERO
    if asset.depreciation_method == DepreciationMethod.STRAIGHT_LINE:
        return _straight_line_to_date(asset, as_of_date)
    if asset.depreciation_method == DepreciationMethod.DIMINISHING_VALUE:
        return _diminishing_value_to_date(asset, as_of_date)
    raise ValueError("Unsupported depreciation method")


def calculate_asset_depreciation(asset: FixedAsset, start_date: date, end_date: date) -> AssetDepreciationAmounts:
    previous_day = start_date - timedelta(days=1)
    accumulated_opening = accumulated_depreciation_to_date(asset, previous_day)
    accumulated_closing = accumulated_depreciation_to_date(asset, end_date)
    carrying_opening = _quantize(asset.cost_amount - accumulated_opening)
    carrying_closing = _quantize(asset.cost_amount - accumulated_closing)
    return AssetDepreciationAmounts(
        run_amount=_quantize(accumulated_closing - accumulated_opening),
        accumulated_opening=accumulated_opening,
        accumulated_closing=accumulated_closing,
        carrying_opening=carrying_opening,
        carrying_closing=carrying_closing,
    )


def build_fixed_asset_detail(asset: FixedAsset, *, as_of_date: date, history: list[FixedAssetStatusHistory]) -> FixedAssetDetailRead:
    accumulated = accumulated_depreciation_to_date(asset, as_of_date)
    return FixedAssetDetailRead(
        **FixedAssetRead.model_validate(asset).model_dump(),
        accumulated_depreciation=accumulated,
        carrying_amount=_quantize(asset.cost_amount - accumulated),
        history=history,
    )


def build_fixed_asset_register(db: Session, *, company_id: UUID, as_of_date: date) -> FixedAssetRegisterRead:
    assets = list(
        db.scalars(
            select(FixedAsset)
            .where(FixedAsset.company_id == company_id)
            .order_by(FixedAsset.asset_code.asc())
        ).all()
    )
    histories = list(
        db.scalars(
            select(FixedAssetStatusHistory)
            .where(FixedAssetStatusHistory.company_id == company_id)
            .order_by(FixedAssetStatusHistory.effective_date.asc(), FixedAssetStatusHistory.created_at.asc())
        ).all()
    )
    by_asset: dict[UUID, list[FixedAssetStatusHistory]] = {}
    for history in histories:
        by_asset.setdefault(history.fixed_asset_id, []).append(history)
    return FixedAssetRegisterRead(
        as_of_date=as_of_date,
        assets=[build_fixed_asset_detail(asset, as_of_date=as_of_date, history=by_asset.get(asset.id, [])) for asset in assets],
    )


def create_fixed_asset(db: Session, *, company_id: UUID, payload, created_by_user_id: UUID) -> FixedAsset:
    if payload.in_service_date < payload.acquisition_date:
        raise ValueError("In-service date cannot be earlier than acquisition date")
    asset = FixedAsset(
        company_id=company_id,
        asset_code=payload.asset_code,
        name=payload.name,
        description=payload.description,
        acquisition_date=payload.acquisition_date,
        in_service_date=payload.in_service_date,
        cost_amount=payload.cost_amount,
        salvage_value=payload.salvage_value,
        useful_life_months=payload.useful_life_months,
        depreciation_method=DepreciationMethod(payload.depreciation_method),
        diminishing_value_rate=payload.diminishing_value_rate,
        asset_account_id=payload.asset_account_id,
        accumulated_depreciation_account_id=payload.accumulated_depreciation_account_id,
        depreciation_expense_account_id=payload.depreciation_expense_account_id,
        acquisition_reference=payload.acquisition_reference,
        note=payload.note,
        created_by_user_id=created_by_user_id,
        status=FixedAssetStatus.ACTIVE,
    )
    _validate_accounts(db, company_id, asset)
    db.add(asset)
    db.flush()
    db.add(
        FixedAssetStatusHistory(
            company_id=company_id,
            fixed_asset_id=asset.id,
            from_status=None,
            to_status=FixedAssetStatus.ACTIVE,
            effective_date=asset.in_service_date,
            note="Asset created",
            changed_by_user_id=created_by_user_id,
        )
    )
    log_audit_event(
        db,
        action="fixed_asset.created",
        summary=f"Created fixed asset {asset.asset_code}",
        entity_type=EntityType.FIXED_ASSET.value,
        entity_id=asset.id,
        actor_user_id=created_by_user_id,
        company_id=company_id,
    )
    return asset


def update_fixed_asset(db: Session, *, asset: FixedAsset, payload, acting_user_id: UUID) -> FixedAsset:
    if asset.status != FixedAssetStatus.ACTIVE:
        raise ValueError("Only active fixed assets can be updated")
    if payload.in_service_date < payload.acquisition_date:
        raise ValueError("In-service date cannot be earlier than acquisition date")

    asset.asset_code = payload.asset_code
    asset.name = payload.name
    asset.description = payload.description
    asset.acquisition_date = payload.acquisition_date
    asset.in_service_date = payload.in_service_date
    asset.cost_amount = payload.cost_amount
    asset.salvage_value = payload.salvage_value
    asset.useful_life_months = payload.useful_life_months
    asset.depreciation_method = DepreciationMethod(payload.depreciation_method)
    asset.diminishing_value_rate = payload.diminishing_value_rate
    asset.asset_account_id = payload.asset_account_id
    asset.accumulated_depreciation_account_id = payload.accumulated_depreciation_account_id
    asset.depreciation_expense_account_id = payload.depreciation_expense_account_id
    asset.acquisition_reference = payload.acquisition_reference
    asset.note = payload.note
    _validate_accounts(db, asset.company_id, asset)
    log_audit_event(
        db,
        action="fixed_asset.updated",
        summary=f"Updated fixed asset {asset.asset_code}",
        entity_type=EntityType.FIXED_ASSET.value,
        entity_id=asset.id,
        actor_user_id=acting_user_id,
        company_id=asset.company_id,
    )
    return asset


def dispose_fixed_asset(db: Session, *, asset: FixedAsset, payload, acting_user_id: UUID) -> FixedAsset:
    if asset.status == FixedAssetStatus.DISPOSED:
        raise ValueError("Fixed asset is already disposed")
    if payload.disposal_date < asset.in_service_date:
        raise ValueError("Disposal date cannot be earlier than in-service date")
    asset.status = FixedAssetStatus.DISPOSED
    asset.disposal_date = payload.disposal_date
    asset.disposal_reference = payload.disposal_reference
    asset.disposal_note = payload.disposal_note
    asset.disposal_proceeds = payload.disposal_proceeds
    db.add(
        FixedAssetStatusHistory(
            company_id=asset.company_id,
            fixed_asset_id=asset.id,
            from_status=FixedAssetStatus.ACTIVE,
            to_status=FixedAssetStatus.DISPOSED,
            effective_date=payload.disposal_date,
            note=payload.disposal_note,
            changed_by_user_id=acting_user_id,
        )
    )
    log_audit_event(
        db,
        action="fixed_asset.disposed",
        summary=f"Disposed fixed asset {asset.asset_code}",
        entity_type=EntityType.FIXED_ASSET.value,
        entity_id=asset.id,
        actor_user_id=acting_user_id,
        company_id=asset.company_id,
    )
    return asset


def build_depreciation_run_detail(db: Session, depreciation_run: DepreciationRun) -> DepreciationRunDetailRead:
    lines = list(
        db.scalars(
            select(DepreciationRunLine)
            .where(DepreciationRunLine.depreciation_run_id == depreciation_run.id)
            .order_by(DepreciationRunLine.fixed_asset_id.asc())
        ).all()
    )
    total = sum((line.depreciation_amount for line in lines), ZERO)
    return DepreciationRunDetailRead(
        **DepreciationRunRead.model_validate(depreciation_run).model_dump(),
        total_depreciation_amount=_quantize(total),
        lines=lines,
    )


def _populate_depreciation_run_lines(
    db: Session,
    *,
    depreciation_run: DepreciationRun,
    company_id: UUID,
    start_date: date,
    end_date: date,
) -> None:
    assets = list(
        db.scalars(
            select(FixedAsset)
            .where(FixedAsset.company_id == company_id)
            .order_by(FixedAsset.asset_code.asc())
        ).all()
    )
    depreciation_run.lines.clear()
    db.flush()
    for asset in assets:
        amounts = calculate_asset_depreciation(asset, start_date, end_date)
        if amounts.run_amount <= ZERO:
            continue
        depreciation_run.lines.append(
            DepreciationRunLine(
                fixed_asset_id=asset.id,
                depreciation_amount=amounts.run_amount,
                accumulated_depreciation_opening=amounts.accumulated_opening,
                accumulated_depreciation_closing=amounts.accumulated_closing,
                carrying_amount_opening=amounts.carrying_opening,
                carrying_amount_closing=amounts.carrying_closing,
            )
        )
    if not depreciation_run.lines:
        raise ValueError("No depreciable assets found for the selected period")


def create_depreciation_run(db: Session, *, company_id: UUID, payload, generated_by_user_id: UUID) -> DepreciationRun:
    if payload.start_date > payload.end_date:
        raise ValueError("Invalid depreciation run range")
    period = _load_period_or_raise(db, company_id, payload.accounting_period_id)
    if payload.start_date < period.start_date or payload.end_date > period.end_date:
        raise ValueError("Depreciation run range must fall within the accounting period")
    depreciation_run = DepreciationRun(
        company_id=company_id,
        accounting_period_id=payload.accounting_period_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=DepreciationRunStatus.DRAFT,
        generated_by_user_id=generated_by_user_id,
        note=payload.note,
    )
    db.add(depreciation_run)
    db.flush()
    _populate_depreciation_run_lines(
        db,
        depreciation_run=depreciation_run,
        company_id=company_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_audit_event(
        db,
        action="depreciation_run.generated",
        summary=f"Generated depreciation run for {payload.start_date} to {payload.end_date}",
        entity_type=EntityType.DEPRECIATION_RUN.value,
        entity_id=depreciation_run.id,
        actor_user_id=generated_by_user_id,
        company_id=company_id,
    )
    return depreciation_run


def rebuild_depreciation_run(db: Session, *, depreciation_run: DepreciationRun, payload, acting_user_id: UUID) -> DepreciationRun:
    if depreciation_run.status != DepreciationRunStatus.DRAFT:
        raise ValueError("Only draft depreciation runs can be updated")
    if depreciation_run.journal_entry_id is not None:
        raise ValueError("Posted depreciation runs cannot be updated")
    if payload.start_date > payload.end_date:
        raise ValueError("Invalid depreciation run range")
    period = _load_period_or_raise(db, depreciation_run.company_id, payload.accounting_period_id)
    if payload.start_date < period.start_date or payload.end_date > period.end_date:
        raise ValueError("Depreciation run range must fall within the accounting period")

    depreciation_run.accounting_period_id = payload.accounting_period_id
    depreciation_run.start_date = payload.start_date
    depreciation_run.end_date = payload.end_date
    depreciation_run.note = payload.note
    _populate_depreciation_run_lines(
        db,
        depreciation_run=depreciation_run,
        company_id=depreciation_run.company_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    log_audit_event(
        db,
        action="depreciation_run.updated",
        summary=f"Updated depreciation run {depreciation_run.id}",
        entity_type=EntityType.DEPRECIATION_RUN.value,
        entity_id=depreciation_run.id,
        actor_user_id=acting_user_id,
        company_id=depreciation_run.company_id,
    )
    return depreciation_run


def post_depreciation_run(db: Session, *, depreciation_run: DepreciationRun, acting_user_id: UUID) -> DepreciationRun:
    if depreciation_run.status != DepreciationRunStatus.DRAFT:
        raise ValueError("Only draft depreciation runs can be posted")
    _ensure_period_not_locked(db, depreciation_run.company_id, depreciation_run.accounting_period_id)
    lines = list(
        db.scalars(
            select(DepreciationRunLine)
            .options(selectinload(DepreciationRunLine.fixed_asset))
            .where(DepreciationRunLine.depreciation_run_id == depreciation_run.id)
        ).all()
    )
    expense_totals: dict[UUID, Decimal] = {}
    contra_totals: dict[UUID, Decimal] = {}
    for line in lines:
        asset = line.fixed_asset
        expense_totals[asset.depreciation_expense_account_id] = expense_totals.get(asset.depreciation_expense_account_id, ZERO) + line.depreciation_amount
        contra_totals[asset.accumulated_depreciation_account_id] = contra_totals.get(asset.accumulated_depreciation_account_id, ZERO) + line.depreciation_amount
    journal = JournalEntry(
        company_id=depreciation_run.company_id,
        entry_number=_next_entry_number(db, depreciation_run.company_id),
        entry_date=depreciation_run.end_date,
        accounting_period_id=depreciation_run.accounting_period_id,
        status=JournalStatus.POSTED,
        source_type=JournalSourceType.DEPRECIATION,
        description=f"Depreciation run {depreciation_run.start_date} to {depreciation_run.end_date}",
        reference=f"DEP-{depreciation_run.start_date.isoformat()}-{depreciation_run.end_date.isoformat()}",
        created_by_user_id=acting_user_id,
        posted_by_user_id=acting_user_id,
        posted_at=datetime.now(timezone.utc),
    )
    line_number = 1
    for account_id, amount in sorted(expense_totals.items(), key=lambda item: str(item[0])):
        journal.lines.append(
            JournalLine(
                line_number=line_number,
                account_id=account_id,
                description="Depreciation expense",
                debit_amount=_quantize(amount),
                credit_amount=ZERO,
            )
        )
        line_number += 1
    for account_id, amount in sorted(contra_totals.items(), key=lambda item: str(item[0])):
        journal.lines.append(
            JournalLine(
                line_number=line_number,
                account_id=account_id,
                description="Accumulated depreciation",
                debit_amount=ZERO,
                credit_amount=_quantize(amount),
            )
        )
        line_number += 1
    db.add(journal)
    db.flush()
    depreciation_run.status = DepreciationRunStatus.POSTED
    depreciation_run.journal_entry_id = journal.id
    depreciation_run.posted_by_user_id = acting_user_id
    depreciation_run.posted_at = journal.posted_at
    log_audit_event(
        db,
        action="depreciation_run.posted",
        summary=f"Posted depreciation run ending {depreciation_run.end_date}",
        entity_type=EntityType.DEPRECIATION_RUN.value,
        entity_id=depreciation_run.id,
        actor_user_id=acting_user_id,
        company_id=depreciation_run.company_id,
    )
    return depreciation_run


def build_depreciation_run_csv(db: Session, depreciation_run: DepreciationRun) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Asset Code",
            "Asset Name",
            "Run Amount",
            "Accumulated Opening",
            "Accumulated Closing",
            "Carrying Opening",
            "Carrying Closing",
        ]
    )
    lines = list(
        db.execute(
            select(
                FixedAsset.asset_code,
                FixedAsset.name,
                DepreciationRunLine.depreciation_amount,
                DepreciationRunLine.accumulated_depreciation_opening,
                DepreciationRunLine.accumulated_depreciation_closing,
                DepreciationRunLine.carrying_amount_opening,
                DepreciationRunLine.carrying_amount_closing,
            )
            .join(FixedAsset, FixedAsset.id == DepreciationRunLine.fixed_asset_id)
            .where(DepreciationRunLine.depreciation_run_id == depreciation_run.id)
            .order_by(FixedAsset.asset_code.asc())
        ).all()
    )
    for line in lines:
        writer.writerow(
            [
                line.asset_code,
                line.name,
                f"{line.depreciation_amount:.2f}",
                f"{line.accumulated_depreciation_opening:.2f}",
                f"{line.accumulated_depreciation_closing:.2f}",
                f"{line.carrying_amount_opening:.2f}",
                f"{line.carrying_amount_closing:.2f}",
            ]
        )
    return output.getvalue().encode("utf-8")
