from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.db.models.accounting import AccountingPeriod, JournalEntry
from app.db.models.auth import User
from app.db.models.banking import BankAccount, BankImportRow, BankImportSession
from app.db.models.enums import (
    BankImportRowStatus,
    BankImportSessionStatus,
    EntityType,
    JournalStatus,
    ReconciliationItemStatus,
    ReconciliationSessionStatus,
)
from app.db.models.reconciliation import (
    ReconciliationBankAllocation,
    ReconciliationItem,
    ReconciliationMatchGroup,
    ReconciliationSession,
)
from app.reconciliation.auto_match import auto_reconcile_session
from app.reconciliation.service import (
    create_match_group,
    delete_match_group,
    list_match_groups,
    load_match_group_or_404,
)
from app.schemas.common import (
    AutoReconciliationResult,
    ReconciliationBankRowRead,
    ReconciliationItemRead,
    ReconciliationJournalSummaryRead,
    ReconciliationMatchGroupRead,
    ReconciliationSessionRead,
    ReconciliationSummary,
)
from app.schemas.requests import (
    AutoReconciliationRequest,
    PeriodActionRequest,
    ReconciliationMatchRequest,
    ReconciliationBankAllocationCreate,
    ReconciliationJournalAllocationCreate,
    ReconciliationMatchGroupCreate,
    ReconciliationSessionCreate,
    ReconciliationSessionUpdate,
)


router = APIRouter(
    prefix="/companies/{company_id}/reconciliation-sessions", tags=["reconciliation"]
)


def _load_session_or_404(db: Session, company_id: UUID, session_id: UUID) -> ReconciliationSession:
    session = db.get(ReconciliationSession, session_id)
    if session is None or session.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation session not found"
        )
    return session


def _load_item_or_404(
    db: Session, company_id: UUID, session_id: UUID, item_id: UUID
) -> ReconciliationItem:
    item = db.get(ReconciliationItem, item_id)
    if (
        item is None
        or item.company_id != company_id
        or item.reconciliation_session_id != session_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation item not found"
        )
    return item


def _period_for_session(db: Session, session: ReconciliationSession) -> AccountingPeriod | None:
    if session.accounting_period_id is None:
        return None
    period = db.get(AccountingPeriod, session.accounting_period_id)
    if period is None or period.company_id != session.company_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reconciliation accounting period is unavailable",
        )
    return period


def _bank_row_is_in_period(row: BankImportRow, period: AccountingPeriod | None) -> bool:
    return period is None or period.start_date <= row.transaction_date <= period.end_date


def _ensure_item_is_in_session_period(
    db: Session,
    session: ReconciliationSession,
    item: ReconciliationItem,
) -> BankImportRow:
    bank_row = db.get(BankImportRow, item.bank_import_row_id)
    if bank_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bank import row not found"
        )
    if not _bank_row_is_in_period(bank_row, _period_for_session(db, session)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank statement item is outside the reconciliation accounting period",
        )
    return bank_row


def _eligible_bank_rows(
    db: Session,
    *,
    company_id: UUID,
    bank_account_id: UUID,
    period: AccountingPeriod | None,
) -> list[BankImportRow]:
    statement = (
        select(BankImportRow)
        .join(BankImportSession, BankImportSession.id == BankImportRow.bank_import_session_id)
        .where(BankImportRow.company_id == company_id)
        .where(BankImportSession.bank_account_id == bank_account_id)
        .where(BankImportSession.status == BankImportSessionStatus.CONFIRMED)
        .where(BankImportRow.status == BankImportRowStatus.STAGED)
        .where(
            ~exists(
                select(ReconciliationItem.id)
                .join(
                    ReconciliationSession,
                    ReconciliationSession.id == ReconciliationItem.reconciliation_session_id,
                )
                .where(
                    ReconciliationItem.bank_import_row_id == BankImportRow.id,
                    ReconciliationSession.status == ReconciliationSessionStatus.IN_PROGRESS,
                )
            )
        )
    )
    if period is not None:
        statement = statement.where(
            BankImportRow.transaction_date >= period.start_date,
            BankImportRow.transaction_date <= period.end_date,
        )
    return list(
        db.scalars(
            statement.order_by(
                BankImportRow.transaction_date.asc(), BankImportRow.line_number.asc()
            )
        ).all()
    )


def _add_eligible_items(
    db: Session,
    *,
    session: ReconciliationSession,
    period: AccountingPeriod | None,
) -> None:
    for row in _eligible_bank_rows(
        db,
        company_id=session.company_id,
        bank_account_id=session.bank_account_id,
        period=period,
    ):
        db.add(
            ReconciliationItem(
                company_id=session.company_id,
                reconciliation_session_id=session.id,
                bank_import_row_id=row.id,
                status=ReconciliationItemStatus.UNMATCHED,
            )
        )


def _journal_summary(journal: JournalEntry | None) -> ReconciliationJournalSummaryRead | None:
    if journal is None:
        return None
    debit_total = sum((line.debit_amount for line in journal.lines), Decimal("0"))
    credit_total = sum((line.credit_amount for line in journal.lines), Decimal("0"))
    return ReconciliationJournalSummaryRead(
        id=journal.id,
        entry_number=journal.entry_number,
        entry_date=journal.entry_date,
        description=journal.description,
        reference=journal.reference,
        status=journal.status,
        debit_total=debit_total,
        credit_total=credit_total,
    )


def _item_read(db: Session, item: ReconciliationItem) -> ReconciliationItemRead:
    bank_row = db.get(BankImportRow, item.bank_import_row_id)
    matched_journal = (
        db.get(JournalEntry, item.matched_journal_entry_id)
        if item.matched_journal_entry_id
        else None
    )
    return ReconciliationItemRead(
        id=item.id,
        company_id=item.company_id,
        reconciliation_session_id=item.reconciliation_session_id,
        bank_import_row_id=item.bank_import_row_id,
        matched_journal_entry_id=item.matched_journal_entry_id,
        status=item.status,
        note=item.note,
        resolved_by_user_id=item.resolved_by_user_id,
        resolved_at=item.resolved_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        bank_row=(
            ReconciliationBankRowRead(
                id=bank_row.id,
                line_number=bank_row.line_number,
                transaction_date=bank_row.transaction_date,
                description=bank_row.description,
                reference=bank_row.reference,
                debit_amount=bank_row.debit_amount,
                credit_amount=bank_row.credit_amount,
                status=bank_row.status,
            )
            if bank_row is not None
            else None
        ),
        matched_journal_entry=_journal_summary(matched_journal),
    )


@router.get("", response_model=list[ReconciliationSessionRead])
def list_reconciliation_sessions(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReconciliationSession]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(ReconciliationSession)
            .where(ReconciliationSession.company_id == company_id)
            .order_by(ReconciliationSession.created_at.desc())
        ).all()
    )


@router.post("", response_model=ReconciliationSessionRead, status_code=201)
def create_reconciliation_session(
    company_id: UUID,
    payload: ReconciliationSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationSession:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bank_account = db.get(BankAccount, payload.bank_account_id)
    if bank_account is None or bank_account.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")
    if not bank_account.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bank account is inactive")
    period = None
    if payload.accounting_period_id is not None:
        period = db.get(AccountingPeriod, payload.accounting_period_id)
        if period is None or period.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Accounting period not found"
            )

    session = ReconciliationSession(
        company_id=company_id,
        bank_account_id=payload.bank_account_id,
        accounting_period_id=payload.accounting_period_id,
        status=ReconciliationSessionStatus.IN_PROGRESS,
        started_by_user_id=current_user.id,
        note=payload.note,
    )
    db.add(session)
    db.flush()

    _add_eligible_items(db, session=session, period=period)
    db.commit()
    db.refresh(session)
    return session


@router.put("/{session_id}", response_model=ReconciliationSessionRead)
def update_reconciliation_session(
    company_id: UUID,
    session_id: UUID,
    payload: ReconciliationSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationSession:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    if session.status == ReconciliationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed reconciliation sessions cannot be updated",
        )
    period = None
    if payload.accounting_period_id is not None:
        period = db.get(AccountingPeriod, payload.accounting_period_id)
        if period is None or period.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Accounting period not found"
            )
    if session.accounting_period_id != payload.accounting_period_id:
        resolved_item_count = (
            db.scalar(
                select(func.count())
                .select_from(ReconciliationItem)
                .where(
                    ReconciliationItem.reconciliation_session_id == session.id,
                    ReconciliationItem.status != ReconciliationItemStatus.UNMATCHED,
                )
            )
            or 0
        )
        match_group_count = (
            db.scalar(
                select(func.count())
                .select_from(ReconciliationMatchGroup)
                .where(ReconciliationMatchGroup.reconciliation_session_id == session.id)
            )
            or 0
        )
        if resolved_item_count or match_group_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Accounting period cannot be changed after reconciliation items are resolved",
            )
        existing_items = list(
            db.scalars(
                select(ReconciliationItem).where(
                    ReconciliationItem.reconciliation_session_id == session.id
                )
            ).all()
        )
        for item in existing_items:
            db.delete(item)
        db.flush()
        session.accounting_period_id = payload.accounting_period_id
        _add_eligible_items(db, session=session, period=period)
    session.note = payload.note
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reconciliation_session(
    company_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    if session.status == ReconciliationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed reconciliation sessions cannot be deleted",
        )
    items = list(
        db.scalars(
            select(ReconciliationItem).where(
                ReconciliationItem.reconciliation_session_id == session.id
            )
        ).all()
    )
    for item in items:
        bank_row = db.get(BankImportRow, item.bank_import_row_id)
        if bank_row is not None:
            bank_row.status = BankImportRowStatus.STAGED
    db.delete(session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/items", response_model=list[ReconciliationItemRead])
def list_reconciliation_items(
    company_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReconciliationItemRead]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    period = _period_for_session(db, session)
    statement = (
        select(ReconciliationItem)
        .join(BankImportRow, BankImportRow.id == ReconciliationItem.bank_import_row_id)
        .where(ReconciliationItem.reconciliation_session_id == session_id)
    )
    if period is not None:
        statement = statement.where(
            BankImportRow.transaction_date >= period.start_date,
            BankImportRow.transaction_date <= period.end_date,
        )
    items = list(
        db.scalars(
            statement.order_by(
                BankImportRow.transaction_date.asc(),
                BankImportRow.line_number.asc(),
                ReconciliationItem.id.asc(),
            )
        ).all()
    )
    return [_item_read(db, item) for item in items]


@router.get("/{session_id}/match-groups", response_model=list[ReconciliationMatchGroupRead])
def list_reconciliation_match_groups(
    company_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReconciliationMatchGroupRead]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    return list_match_groups(db, session=session)


@router.post(
    "/{session_id}/match-groups", response_model=ReconciliationMatchGroupRead, status_code=201
)
def create_reconciliation_match_group(
    company_id: UUID,
    session_id: UUID,
    payload: ReconciliationMatchGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationMatchGroupRead:
    require_company_permission(company_id, "can_review", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    return create_match_group(db, session=session, payload=payload, acting_user=current_user)


@router.post("/{session_id}/auto-reconcile", response_model=AutoReconciliationResult)
def auto_reconcile(
    company_id: UUID,
    session_id: UUID,
    payload: AutoReconciliationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AutoReconciliationResult:
    require_company_permission(company_id, "can_review", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    return auto_reconcile_session(
        db,
        session=session,
        payload=payload,
        acting_user=current_user,
    )


@router.delete("/{session_id}/match-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reconciliation_match_group(
    company_id: UUID,
    session_id: UUID,
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_review", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    group = load_match_group_or_404(
        db,
        company_id=company_id,
        session_id=session_id,
        group_id=group_id,
    )
    delete_match_group(db, session=session, group=group, acting_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{session_id}/items/{item_id}/match", response_model=ReconciliationItemRead)
def match_reconciliation_item(
    company_id: UUID,
    session_id: UUID,
    item_id: UUID,
    payload: ReconciliationMatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationItemRead:
    require_company_permission(company_id, "can_review", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    if session.status == ReconciliationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed reconciliation sessions cannot be changed",
        )
    item = _load_item_or_404(db, company_id, session_id, item_id)
    bank_row = _ensure_item_is_in_session_period(db, session, item)
    journal = db.get(JournalEntry, payload.matched_journal_entry_id)
    if (
        journal is None
        or journal.company_id != company_id
        or journal.status != JournalStatus.POSTED
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Posted journal entry is required"
        )
    period = _period_for_session(db, session)
    if period is not None and (
        journal.accounting_period_id != period.id
        or journal.entry_date < period.start_date
        or journal.entry_date > period.end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Posted journal entry is outside the reconciliation accounting period",
        )
    bank_account = db.get(BankAccount, session.bank_account_id)
    if bank_account is not None and bank_account.ledger_account_id is not None:
        create_match_group(
            db,
            session=session,
            payload=ReconciliationMatchGroupCreate(
                bank_allocations=[
                    ReconciliationBankAllocationCreate(reconciliation_item_id=item.id)
                ],
                journal_allocations=[
                    ReconciliationJournalAllocationCreate(journal_entry_id=journal.id)
                ],
                note=payload.note,
            ),
            acting_user=current_user,
        )
        db.refresh(item)
        return _item_read(db, item)
    item.matched_journal_entry_id = journal.id
    item.status = ReconciliationItemStatus.MATCHED
    item.note = payload.note
    item.resolved_by_user_id = current_user.id
    item.resolved_at = datetime.now(timezone.utc)
    bank_row.status = BankImportRowStatus.MATCHED
    db.commit()
    db.refresh(item)
    return _item_read(db, item)


@router.post("/{session_id}/items/{item_id}/ignore", response_model=ReconciliationItemRead)
def ignore_reconciliation_item(
    company_id: UUID,
    session_id: UUID,
    item_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationItemRead:
    require_company_permission(company_id, "can_review", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    if session.status == ReconciliationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed reconciliation sessions cannot be changed",
        )
    item = _load_item_or_404(db, company_id, session_id, item_id)
    has_allocations = db.scalar(
        select(
            exists().where(
                ReconciliationBankAllocation.reconciliation_item_id == item.id,
                ReconciliationBankAllocation.reconciliation_match_group_id
                == ReconciliationMatchGroup.id,
            )
        )
    )
    if has_allocations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unmatch the item's reconciliation groups before ignoring it",
        )
    bank_row = _ensure_item_is_in_session_period(db, session, item)
    item.status = ReconciliationItemStatus.IGNORED
    item.note = payload.note or payload.reason
    item.resolved_by_user_id = current_user.id
    item.resolved_at = datetime.now(timezone.utc)
    bank_row.status = BankImportRowStatus.IGNORED
    db.commit()
    db.refresh(item)
    return _item_read(db, item)


@router.get("/{session_id}/summary", response_model=ReconciliationSummary)
def reconciliation_summary(
    company_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationSummary:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    period = _period_for_session(db, session)

    def count_items(item_status: ReconciliationItemStatus | None = None) -> int:
        statement = (
            select(func.count())
            .select_from(ReconciliationItem)
            .join(BankImportRow, BankImportRow.id == ReconciliationItem.bank_import_row_id)
            .where(ReconciliationItem.reconciliation_session_id == session_id)
        )
        if period is not None:
            statement = statement.where(
                BankImportRow.transaction_date >= period.start_date,
                BankImportRow.transaction_date <= period.end_date,
            )
        if item_status is not None:
            statement = statement.where(ReconciliationItem.status == item_status)
        return db.scalar(statement) or 0

    total_items = count_items()
    matched_items = count_items(ReconciliationItemStatus.MATCHED)
    ignored_items = count_items(ReconciliationItemStatus.IGNORED)
    unmatched_items = total_items - matched_items - ignored_items
    return ReconciliationSummary(
        total_items=total_items,
        unmatched_items=unmatched_items,
        matched_items=matched_items,
        ignored_items=ignored_items,
    )


@router.post("/{session_id}/complete", response_model=ReconciliationSessionRead)
def complete_reconciliation_session(
    company_id: UUID,
    session_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationSession:
    require_company_permission(company_id, "can_review", db, current_user)
    session = _load_session_or_404(db, company_id, session_id)
    summary = reconciliation_summary(company_id, session_id, current_user, db)
    if summary.unmatched_items > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unmatched reconciliation items remain"
        )
    session.status = ReconciliationSessionStatus.COMPLETED
    session.completed_at = datetime.now(timezone.utc)
    if payload.note:
        session.note = payload.note
    log_audit_event(
        db,
        action="reconciliation.completed",
        summary=f"Completed reconciliation session {session_id}",
        entity_type=EntityType.COMPANY.value,
        entity_id=session.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    db.refresh(session)
    return session
