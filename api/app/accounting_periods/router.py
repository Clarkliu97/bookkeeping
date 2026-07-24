from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting_periods.service import (
    create_period_earnings_rollover,
    void_period_earnings_rollover,
)
from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_approval_action, log_audit_event
from app.db.models.accounting import AccountingPeriod, JournalEntry, PeriodLock
from app.db.models.audit import ApprovalAction
from app.db.models.auth import User
from app.db.models.companies import CompanyConfigurationVersion
from app.db.models.enums import AccountingPeriodType, ApprovalActionType, EntityType, WorkflowStatus
from app.db.models.fixed_assets import DepreciationRun
from app.db.models.reconciliation import ReconciliationSession
from app.db.models.tax_workpapers import TaxWorkpaperPack
from app.schemas.common import AccountingPeriodRead
from app.schemas.requests import AccountingPeriodCreate, AccountingPeriodUpdate, PeriodActionRequest

router = APIRouter(prefix="/companies/{company_id}/periods", tags=["accounting-periods"])


def _latest_configuration(db: Session, company_id: UUID) -> CompanyConfigurationVersion:
    configuration = db.scalar(
        select(CompanyConfigurationVersion)
        .where(CompanyConfigurationVersion.company_id == company_id)
        .order_by(CompanyConfigurationVersion.version_number.desc())
        .limit(1)
    )
    if configuration is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Company configuration is required"
        )
    return configuration


def _load_period_or_404(db: Session, company_id: UUID, period_id: UUID) -> AccountingPeriod:
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.company_id == company_id,
            AccountingPeriod.id == period_id,
        )
    )
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Accounting period not found"
        )
    return period


def _ensure_period_editable(db: Session, period: AccountingPeriod) -> None:
    if period.status != WorkflowStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft periods can be changed"
        )
    active_lock = db.scalar(
        select(PeriodLock)
        .where(PeriodLock.accounting_period_id == period.id, PeriodLock.unlocked_at.is_(None))
        .limit(1)
    )
    if active_lock is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Accounting period is locked"
        )


def _ensure_period_has_no_dependents(db: Session, period: AccountingPeriod) -> None:
    dependent_queries = (
        (
            select(JournalEntry.id).where(JournalEntry.accounting_period_id == period.id).limit(1),
            "Period has journal entries",
        ),
        (
            select(DepreciationRun.id)
            .where(DepreciationRun.accounting_period_id == period.id)
            .limit(1),
            "Period has depreciation runs",
        ),
        (
            select(TaxWorkpaperPack.id)
            .where(TaxWorkpaperPack.accounting_period_id == period.id)
            .limit(1),
            "Period has tax workpaper packs",
        ),
        (
            select(ReconciliationSession.id)
            .where(ReconciliationSession.accounting_period_id == period.id)
            .limit(1),
            "Period is referenced by reconciliation sessions",
        ),
    )
    for query, detail in dependent_queries:
        if db.scalar(query) is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _check_self_approval(
    db: Session,
    *,
    company_id: UUID,
    prepared_by_user_id: UUID,
    acting_user_id: UUID,
) -> None:
    configuration = _latest_configuration(db, company_id)
    if prepared_by_user_id != acting_user_id:
        return
    if configuration.self_approval_mode.value == "block":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company policy blocks self-approval for this action",
        )


@router.get("", response_model=list[AccountingPeriodRead])
def list_periods(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AccountingPeriod]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(AccountingPeriod)
            .where(AccountingPeriod.company_id == company_id)
            .order_by(AccountingPeriod.start_date.desc())
        ).all()
    )


@router.post("", response_model=AccountingPeriodRead, status_code=201)
def create_period(
    company_id: UUID,
    payload: AccountingPeriodCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountingPeriod:
    require_company_permission(company_id, "can_administer", db, current_user)
    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Period dates are invalid"
        )
    period = AccountingPeriod(
        company_id=company_id,
        name=payload.name,
        period_type=AccountingPeriodType(payload.period_type),
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=WorkflowStatus.DRAFT,
    )
    db.add(period)
    db.flush()
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.ACCOUNTING_PERIOD,
        entity_id=period.id,
        action_type=ApprovalActionType.PREPARED,
        prepared_by_user_id=current_user.id,
        note="Accounting period created",
    )
    db.commit()
    db.refresh(period)
    return period


@router.put("/{period_id}", response_model=AccountingPeriodRead)
def update_period(
    company_id: UUID,
    period_id: UUID,
    payload: AccountingPeriodUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountingPeriod:
    require_company_permission(company_id, "can_administer", db, current_user)
    period = _load_period_or_404(db, company_id, period_id)
    _ensure_period_editable(db, period)
    _ensure_period_has_no_dependents(db, period)
    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Period dates are invalid"
        )
    before_state = AccountingPeriodRead.model_validate(period).model_dump(mode="json")
    period.name = payload.name
    period.period_type = AccountingPeriodType(payload.period_type)
    period.start_date = payload.start_date
    period.end_date = payload.end_date
    log_audit_event(
        db,
        action="accounting_period.updated",
        summary=f"Updated accounting period {period.name}",
        entity_type=EntityType.ACCOUNTING_PERIOD.value,
        entity_id=period.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=AccountingPeriodRead.model_validate(period).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(period)
    return period


@router.delete("/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_period(
    company_id: UUID,
    period_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    period = _load_period_or_404(db, company_id, period_id)
    _ensure_period_editable(db, period)
    _ensure_period_has_no_dependents(db, period)
    log_audit_event(
        db,
        action="accounting_period.deleted",
        summary=f"Deleted accounting period {period.name}",
        entity_type=EntityType.ACCOUNTING_PERIOD.value,
        entity_id=period.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=AccountingPeriodRead.model_validate(period).model_dump(mode="json"),
    )
    db.delete(period)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{period_id}/submit", response_model=AccountingPeriodRead)
def submit_period_for_review(
    company_id: UUID,
    period_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountingPeriod:
    require_company_permission(company_id, "can_prepare", db, current_user)
    period = _load_period_or_404(db, company_id, period_id)
    period.status = WorkflowStatus.IN_REVIEW
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.ACCOUNTING_PERIOD,
        entity_id=period.id,
        action_type=ApprovalActionType.SUBMITTED_FOR_REVIEW,
        prepared_by_user_id=current_user.id,
        note=payload.note,
    )
    db.commit()
    db.refresh(period)
    return period


@router.post("/{period_id}/approve", response_model=AccountingPeriodRead)
def approve_period(
    company_id: UUID,
    period_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountingPeriod:
    require_company_permission(company_id, "can_approve", db, current_user)
    period = _load_period_or_404(db, company_id, period_id)
    prepared_action = db.scalar(
        select(ApprovalAction)
        .where(
            ApprovalAction.entity_id == str(period.id),
            ApprovalAction.action_type == ApprovalActionType.SUBMITTED_FOR_REVIEW,
        )
        .order_by(ApprovalAction.created_at.desc())
        .limit(1)
    )
    if prepared_action is not None and prepared_action.prepared_by_user_id is not None:
        _check_self_approval(
            db,
            company_id=company_id,
            prepared_by_user_id=prepared_action.prepared_by_user_id,
            acting_user_id=current_user.id,
        )
    period.status = WorkflowStatus.APPROVED
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.ACCOUNTING_PERIOD,
        entity_id=period.id,
        action_type=ApprovalActionType.APPROVED,
        approved_by_user_id=current_user.id,
        note=payload.note,
    )
    db.commit()
    db.refresh(period)
    return period


@router.post("/{period_id}/lock", response_model=AccountingPeriodRead)
def lock_period(
    company_id: UUID,
    period_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountingPeriod:
    require_company_permission(company_id, "can_administer", db, current_user)
    period = db.scalar(
        select(AccountingPeriod)
        .where(AccountingPeriod.company_id == company_id, AccountingPeriod.id == period_id)
        .with_for_update()
    )
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Accounting period not found"
        )
    period_was_locked = period.status == WorkflowStatus.LOCKED
    try:
        create_period_earnings_rollover(
            db,
            period=period,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if period_was_locked:
        db.commit()
        db.refresh(period)
        return period
    period.status = WorkflowStatus.LOCKED
    db.add(
        PeriodLock(
            company_id=company_id,
            accounting_period_id=period.id,
            lock_reason=payload.reason or "Locked by administrator",
            locked_by_user_id=current_user.id,
            locked_at=datetime.now(timezone.utc),
        )
    )
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.ACCOUNTING_PERIOD,
        entity_id=period.id,
        action_type=ApprovalActionType.LOCKED,
        approved_by_user_id=current_user.id,
        note=payload.reason,
    )
    db.commit()
    db.refresh(period)
    return period


@router.post("/{period_id}/unlock", response_model=AccountingPeriodRead)
def unlock_period(
    company_id: UUID,
    period_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountingPeriod:
    require_company_permission(company_id, "can_administer", db, current_user)
    period = _load_period_or_404(db, company_id, period_id)
    lock_record = db.scalar(
        select(PeriodLock)
        .where(PeriodLock.accounting_period_id == period.id, PeriodLock.unlocked_at.is_(None))
        .order_by(PeriodLock.locked_at.desc())
        .limit(1)
    )
    if lock_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Period is not currently locked"
        )
    void_period_earnings_rollover(
        db,
        period=period,
        actor_user_id=current_user.id,
    )
    lock_record.unlocked_by_user_id = current_user.id
    lock_record.unlocked_at = datetime.now(timezone.utc)
    lock_record.unlock_reason = payload.reason or payload.note
    period.status = WorkflowStatus.APPROVED
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.ACCOUNTING_PERIOD,
        entity_id=period.id,
        action_type=ApprovalActionType.UNLOCKED,
        approved_by_user_id=current_user.id,
        note=payload.reason,
    )
    db.commit()
    db.refresh(period)
    return period
