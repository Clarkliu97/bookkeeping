from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
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
from app.db.models.reconciliation import ReconciliationItem, ReconciliationSession
from app.schemas.common import (
    ReconciliationBankRowRead,
    ReconciliationItemRead,
    ReconciliationJournalSummaryRead,
    ReconciliationSessionRead,
    ReconciliationSummary,
)
from app.schemas.requests import (
    PeriodActionRequest,
    ReconciliationMatchRequest,
    ReconciliationSessionCreate,
    ReconciliationSessionUpdate,
)


router = APIRouter(prefix="/companies/{company_id}/reconciliation-sessions", tags=["reconciliation"])


def _load_session_or_404(db: Session, company_id: UUID, session_id: UUID) -> ReconciliationSession:
    session = db.get(ReconciliationSession, session_id)
    if session is None or session.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation session not found")
    return session


def _load_item_or_404(db: Session, company_id: UUID, session_id: UUID, item_id: UUID) -> ReconciliationItem:
    item = db.get(ReconciliationItem, item_id)
    if item is None or item.company_id != company_id or item.reconciliation_session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation item not found")
    return item


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
    matched_journal = db.get(JournalEntry, item.matched_journal_entry_id) if item.matched_journal_entry_id else None
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
    if payload.accounting_period_id is not None:
        period = db.get(AccountingPeriod, payload.accounting_period_id)
        if period is None or period.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accounting period not found")

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

    rows = list(
        db.scalars(
            select(BankImportRow)
            .join(BankImportSession, BankImportSession.id == BankImportRow.bank_import_session_id)
            .where(BankImportRow.company_id == company_id)
            .where(BankImportSession.bank_account_id == payload.bank_account_id)
            .where(BankImportSession.status == BankImportSessionStatus.CONFIRMED)
            .where(BankImportRow.status == BankImportRowStatus.STAGED)
            .order_by(BankImportRow.transaction_date.asc(), BankImportRow.line_number.asc())
        ).all()
    )
    for row in rows:
        db.add(
            ReconciliationItem(
                company_id=company_id,
                reconciliation_session_id=session.id,
                bank_import_row_id=row.id,
                status=ReconciliationItemStatus.UNMATCHED,
            )
        )
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Completed reconciliation sessions cannot be updated")
    if payload.accounting_period_id is not None:
        period = db.get(AccountingPeriod, payload.accounting_period_id)
        if period is None or period.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accounting period not found")
    session.accounting_period_id = payload.accounting_period_id
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Completed reconciliation sessions cannot be deleted")
    items = list(
        db.scalars(select(ReconciliationItem).where(ReconciliationItem.reconciliation_session_id == session.id)).all()
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
    _load_session_or_404(db, company_id, session_id)
    items = list(
        db.scalars(
            select(ReconciliationItem)
            .join(BankImportRow, BankImportRow.id == ReconciliationItem.bank_import_row_id)
            .where(ReconciliationItem.reconciliation_session_id == session_id)
            .order_by(
                BankImportRow.transaction_date.asc(),
                BankImportRow.line_number.asc(),
                ReconciliationItem.id.asc(),
            )
        ).all()
    )
    return [_item_read(db, item) for item in items]


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
    item = _load_item_or_404(db, company_id, session_id, item_id)
    journal = db.get(JournalEntry, payload.matched_journal_entry_id)
    if journal is None or journal.company_id != company_id or journal.status != JournalStatus.POSTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Posted journal entry is required")
    bank_row = db.get(BankImportRow, item.bank_import_row_id)
    if bank_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank import row not found")
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
    item = _load_item_or_404(db, company_id, session_id, item_id)
    bank_row = db.get(BankImportRow, item.bank_import_row_id)
    if bank_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank import row not found")
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
    _load_session_or_404(db, company_id, session_id)
    total_items = db.scalar(
        select(func.count()).select_from(ReconciliationItem).where(ReconciliationItem.reconciliation_session_id == session_id)
    ) or 0
    matched_items = db.scalar(
        select(func.count())
        .select_from(ReconciliationItem)
        .where(
            ReconciliationItem.reconciliation_session_id == session_id,
            ReconciliationItem.status == ReconciliationItemStatus.MATCHED,
        )
    ) or 0
    ignored_items = db.scalar(
        select(func.count())
        .select_from(ReconciliationItem)
        .where(
            ReconciliationItem.reconciliation_session_id == session_id,
            ReconciliationItem.status == ReconciliationItemStatus.IGNORED,
        )
    ) or 0
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unmatched reconciliation items remain")
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
