from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import log_audit_event
from app.db.models.accounting import AccountingPeriod, JournalEntry
from app.db.models.auth import User
from app.db.models.banking import BankAccount, BankImportRow
from app.db.models.enums import (
    BankImportRowStatus,
    JournalStatus,
    ReconciliationItemStatus,
    ReconciliationSessionStatus,
)
from app.db.models.reconciliation import (
    ReconciliationBankAllocation,
    ReconciliationItem,
    ReconciliationJournalAllocation,
    ReconciliationMatchGroup,
    ReconciliationSession,
)
from app.schemas.common import (
    ReconciliationBankAllocationRead,
    ReconciliationBankRowRead,
    ReconciliationJournalAllocationRead,
    ReconciliationJournalSummaryRead,
    ReconciliationMatchGroupRead,
)
from app.schemas.requests import ReconciliationMatchGroupCreate


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def bank_row_amount(row: BankImportRow) -> Decimal:
    return _money(row.credit_amount - row.debit_amount)


def journal_cash_amount(journal: JournalEntry, ledger_account_id: UUID) -> Decimal:
    return _money(
        sum(
            (
                line.debit_amount - line.credit_amount
                for line in journal.lines
                if line.account_id == ledger_account_id
            ),
            ZERO,
        )
    )


def _journal_summary(journal: JournalEntry) -> ReconciliationJournalSummaryRead:
    return ReconciliationJournalSummaryRead(
        id=journal.id,
        entry_number=journal.entry_number,
        entry_date=journal.entry_date,
        description=journal.description,
        reference=journal.reference,
        status=journal.status,
        debit_total=sum((line.debit_amount for line in journal.lines), ZERO),
        credit_total=sum((line.credit_amount for line in journal.lines), ZERO),
    )


def _bank_row_read(row: BankImportRow) -> ReconciliationBankRowRead:
    return ReconciliationBankRowRead(
        id=row.id,
        line_number=row.line_number,
        transaction_date=row.transaction_date,
        description=row.description,
        reference=row.reference,
        debit_amount=row.debit_amount,
        credit_amount=row.credit_amount,
        status=row.status,
    )


def load_match_group_or_404(
    db: Session,
    *,
    company_id: UUID,
    session_id: UUID,
    group_id: UUID,
) -> ReconciliationMatchGroup:
    group = db.get(ReconciliationMatchGroup, group_id)
    if (
        group is None
        or group.company_id != company_id
        or group.reconciliation_session_id != session_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reconciliation match group not found"
        )
    return group


def build_match_group_read(
    db: Session, group: ReconciliationMatchGroup
) -> ReconciliationMatchGroupRead:
    bank_reads: list[ReconciliationBankAllocationRead] = []
    bank_allocations = list(
        db.scalars(
            select(ReconciliationBankAllocation)
            .where(ReconciliationBankAllocation.reconciliation_match_group_id == group.id)
            .order_by(
                ReconciliationBankAllocation.created_at.asc(), ReconciliationBankAllocation.id.asc()
            )
        ).all()
    )
    for allocation in bank_allocations:
        item = db.get(ReconciliationItem, allocation.reconciliation_item_id)
        row = db.get(BankImportRow, item.bank_import_row_id) if item is not None else None
        if item is None or row is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reconciliation bank allocation source is unavailable",
            )
        bank_reads.append(
            ReconciliationBankAllocationRead(
                id=allocation.id,
                reconciliation_item_id=item.id,
                source_amount=allocation.source_amount,
                allocated_amount=allocation.allocated_amount,
                bank_row=_bank_row_read(row),
            )
        )

    journal_reads: list[ReconciliationJournalAllocationRead] = []
    journal_allocations = list(
        db.scalars(
            select(ReconciliationJournalAllocation)
            .where(ReconciliationJournalAllocation.reconciliation_match_group_id == group.id)
            .order_by(
                ReconciliationJournalAllocation.created_at.asc(),
                ReconciliationJournalAllocation.id.asc(),
            )
        ).all()
    )
    for allocation in journal_allocations:
        journal = db.get(JournalEntry, allocation.journal_entry_id)
        if journal is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reconciliation journal allocation source is unavailable",
            )
        journal_reads.append(
            ReconciliationJournalAllocationRead(
                id=allocation.id,
                journal_entry_id=journal.id,
                ledger_account_id=allocation.ledger_account_id,
                source_amount=allocation.source_amount,
                allocated_amount=allocation.allocated_amount,
                journal_entry=_journal_summary(journal),
            )
        )

    return ReconciliationMatchGroupRead(
        id=group.id,
        company_id=group.company_id,
        reconciliation_session_id=group.reconciliation_session_id,
        status=group.status,
        bank_total=group.bank_total,
        journal_total=group.journal_total,
        difference_amount=group.difference_amount,
        tolerance_amount=group.tolerance_amount,
        note=group.note,
        created_by_user_id=group.created_by_user_id,
        resolved_at=group.resolved_at,
        created_at=group.created_at,
        updated_at=group.updated_at,
        bank_allocations=bank_reads,
        journal_allocations=journal_reads,
    )


def list_match_groups(
    db: Session, *, session: ReconciliationSession
) -> list[ReconciliationMatchGroupRead]:
    groups = list(
        db.scalars(
            select(ReconciliationMatchGroup)
            .where(ReconciliationMatchGroup.reconciliation_session_id == session.id)
            .order_by(
                ReconciliationMatchGroup.created_at.desc(), ReconciliationMatchGroup.id.desc()
            )
        ).all()
    )
    return [build_match_group_read(db, group) for group in groups]


def _existing_bank_allocation(db: Session, item: ReconciliationItem) -> Decimal:
    return _money(
        db.scalar(
            select(func.coalesce(func.sum(ReconciliationBankAllocation.allocated_amount), ZERO))
            .join(
                ReconciliationItem,
                ReconciliationItem.id == ReconciliationBankAllocation.reconciliation_item_id,
            )
            .join(
                ReconciliationMatchGroup,
                ReconciliationMatchGroup.id
                == ReconciliationBankAllocation.reconciliation_match_group_id,
            )
            .where(ReconciliationItem.bank_import_row_id == item.bank_import_row_id)
        )
        or ZERO
    )


def _existing_item_allocation(db: Session, item_id: UUID) -> Decimal:
    return _money(
        db.scalar(
            select(func.coalesce(func.sum(ReconciliationBankAllocation.allocated_amount), ZERO))
            .join(
                ReconciliationMatchGroup,
                ReconciliationMatchGroup.id
                == ReconciliationBankAllocation.reconciliation_match_group_id,
            )
            .where(ReconciliationBankAllocation.reconciliation_item_id == item_id)
        )
        or ZERO
    )


def _existing_journal_allocation(db: Session, journal_id: UUID, ledger_account_id: UUID) -> Decimal:
    return _money(
        db.scalar(
            select(
                func.coalesce(func.sum(ReconciliationJournalAllocation.allocated_amount), ZERO)
            )
            .join(
                ReconciliationMatchGroup,
                ReconciliationMatchGroup.id
                == ReconciliationJournalAllocation.reconciliation_match_group_id,
            )
            .where(
                ReconciliationJournalAllocation.journal_entry_id == journal_id,
                ReconciliationJournalAllocation.ledger_account_id == ledger_account_id,
            )
        )
        or ZERO
    )


def _resolve_allocation_amount(
    *,
    requested: Decimal | None,
    source: Decimal,
    already_allocated: Decimal,
    source_label: str,
) -> Decimal:
    remaining = _money(source - already_allocated)
    if remaining == ZERO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{source_label} is already fully allocated",
        )
    amount = remaining if requested is None else _money(requested)
    if amount == ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{source_label} allocation cannot be zero",
        )
    if (amount > ZERO) != (source > ZERO):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{source_label} allocation must have the same receipt/payment direction as its source",
        )
    if abs(amount) > abs(remaining):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{source_label} allocation exceeds the remaining unallocated amount",
        )
    return amount


def _period_for_group(db: Session, session: ReconciliationSession) -> AccountingPeriod | None:
    if session.accounting_period_id is None:
        return None
    period = db.get(AccountingPeriod, session.accounting_period_id)
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reconciliation accounting period is unavailable",
        )
    return period


def create_match_group(
    db: Session,
    *,
    session: ReconciliationSession,
    payload: ReconciliationMatchGroupCreate,
    acting_user: User,
    commit: bool = True,
) -> ReconciliationMatchGroupRead:
    if session.status == ReconciliationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed reconciliation sessions cannot be changed",
        )
    bank_account = db.get(BankAccount, session.bank_account_id)
    if bank_account is None or bank_account.ledger_account_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Link the bank account to its ledger cash account before creating grouped matches",
        )
    if len({allocation.reconciliation_item_id for allocation in payload.bank_allocations}) != len(
        payload.bank_allocations
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A statement item can appear only once in a match group",
        )
    if len({allocation.journal_entry_id for allocation in payload.journal_allocations}) != len(
        payload.journal_allocations
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A journal can appear only once in a match group",
        )

    period = _period_for_group(db, session)
    bank_sources: list[tuple[ReconciliationItem, BankImportRow, Decimal, Decimal]] = []
    bank_currencies: set[str] = set()
    for requested in payload.bank_allocations:
        item = db.scalar(
            select(ReconciliationItem)
            .where(ReconciliationItem.id == requested.reconciliation_item_id)
            .with_for_update()
        )
        if (
            item is None
            or item.company_id != session.company_id
            or item.reconciliation_session_id != session.id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reconciliation statement item not found",
            )
        if item.status == ReconciliationItemStatus.IGNORED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ignored statement items cannot be allocated",
            )
        row = db.scalar(
            select(BankImportRow)
            .where(BankImportRow.id == item.bank_import_row_id)
            .with_for_update()
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank statement item source is unavailable",
            )
        if period is not None and not (
            period.start_date <= row.transaction_date <= period.end_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bank statement item is outside the reconciliation accounting period",
            )
        source = bank_row_amount(row)
        amount = _resolve_allocation_amount(
            requested=requested.allocated_amount,
            source=source,
            already_allocated=_existing_bank_allocation(db, item),
            source_label=f"Statement item {row.line_number}",
        )
        bank_sources.append((item, row, source, amount))
        bank_currencies.add(row.currency_code)

    journal_sources: list[tuple[JournalEntry, Decimal, Decimal]] = []
    journal_currencies: set[str] = set()
    for requested in payload.journal_allocations:
        journal = db.scalar(
            select(JournalEntry)
            .where(JournalEntry.id == requested.journal_entry_id)
            .with_for_update()
        )
        if (
            journal is None
            or journal.company_id != session.company_id
            or journal.status != JournalStatus.POSTED
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Posted journal entry is required"
            )
        if period is not None and (
            journal.accounting_period_id != period.id
            or not (period.start_date <= journal.entry_date <= period.end_date)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Posted journal entry is outside the reconciliation accounting period",
            )
        source = journal_cash_amount(journal, bank_account.ledger_account_id)
        if source == ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Journal {journal.entry_number} has no movement in the linked ledger cash account",
            )
        amount = _resolve_allocation_amount(
            requested=requested.allocated_amount,
            source=source,
            already_allocated=_existing_journal_allocation(
                db, journal.id, bank_account.ledger_account_id
            ),
            source_label=f"Journal {journal.entry_number}",
        )
        journal_sources.append((journal, source, amount))
        journal_currencies.add(journal.currency_code)

    if len(bank_currencies | journal_currencies) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grouped reconciliation sources must use one currency",
        )
    bank_total = _money(sum((amount for _, _, _, amount in bank_sources), ZERO))
    journal_total = _money(sum((amount for _, _, amount in journal_sources), ZERO))
    difference = _money(bank_total - journal_total)
    tolerance = _money(payload.tolerance_amount)
    if abs(difference) > tolerance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Grouped reconciliation is outside tolerance",
                "bank_total": str(bank_total),
                "journal_total": str(journal_total),
                "difference_amount": str(difference),
                "tolerance_amount": str(tolerance),
            },
        )
    note = payload.note.strip() if payload.note else None
    if difference != ZERO and not note:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A note is required when accepting a tolerance difference",
        )

    now = datetime.now(timezone.utc)
    group = ReconciliationMatchGroup(
        company_id=session.company_id,
        reconciliation_session_id=session.id,
        status="matched",
        bank_total=bank_total,
        journal_total=journal_total,
        difference_amount=difference,
        tolerance_amount=tolerance,
        note=note,
        created_by_user_id=acting_user.id,
        resolved_at=now,
    )
    db.add(group)
    db.flush()
    for item, _row, source, amount in bank_sources:
        db.add(
            ReconciliationBankAllocation(
                company_id=session.company_id,
                reconciliation_match_group_id=group.id,
                reconciliation_item_id=item.id,
                source_amount=source,
                allocated_amount=amount,
            )
        )
    for journal, source, amount in journal_sources:
        db.add(
            ReconciliationJournalAllocation(
                company_id=session.company_id,
                reconciliation_match_group_id=group.id,
                journal_entry_id=journal.id,
                ledger_account_id=bank_account.ledger_account_id,
                source_amount=source,
                allocated_amount=amount,
            )
        )
    db.flush()

    one_to_one_journal_id = (
        journal_sources[0][0].id if len(bank_sources) == len(journal_sources) == 1 else None
    )
    for item, row, source, amount in bank_sources:
        allocated = _existing_item_allocation(db, item.id)
        if allocated == source:
            item.status = ReconciliationItemStatus.MATCHED
            item.matched_journal_entry_id = one_to_one_journal_id if amount == source else None
            item.resolved_by_user_id = acting_user.id
            item.resolved_at = now
            row.status = BankImportRowStatus.MATCHED
        else:
            item.status = ReconciliationItemStatus.UNMATCHED
            item.matched_journal_entry_id = None
            item.resolved_by_user_id = None
            item.resolved_at = None
            row.status = BankImportRowStatus.STAGED

    log_audit_event(
        db,
        action="reconciliation.group_matched",
        summary=f"Matched {len(bank_sources)} statement items to {len(journal_sources)} journals",
        entity_type="reconciliation_match_group",
        entity_id=group.id,
        actor_user_id=acting_user.id,
        company_id=session.company_id,
        metadata={
            "bank_total": str(bank_total),
            "journal_total": str(journal_total),
            "difference_amount": str(difference),
            "tolerance_amount": str(tolerance),
        },
    )
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(group)
    return build_match_group_read(db, group)


def delete_match_group(
    db: Session,
    *,
    session: ReconciliationSession,
    group: ReconciliationMatchGroup,
    acting_user: User,
) -> None:
    if session.status == ReconciliationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed reconciliation sessions cannot be changed",
        )
    group_bank_allocations = list(
        db.scalars(
            select(ReconciliationBankAllocation).where(
                ReconciliationBankAllocation.reconciliation_match_group_id == group.id
            )
        ).all()
    )
    remaining_by_item_id: dict[UUID, Decimal] = {}
    for allocation in group_bank_allocations:
        item = db.get(ReconciliationItem, allocation.reconciliation_item_id)
        if item is not None:
            remaining_by_item_id[item.id] = _money(
                _existing_item_allocation(db, item.id) - allocation.allocated_amount
            )
    group_snapshot = build_match_group_read(db, group).model_dump(mode="json")
    db.delete(group)
    db.flush()
    for item_id, allocated in remaining_by_item_id.items():
        item = db.get(ReconciliationItem, item_id)
        if item is None:
            continue
        row = db.get(BankImportRow, item.bank_import_row_id)
        source = bank_row_amount(row) if row is not None else ZERO
        if source != ZERO and allocated == source:
            item.status = ReconciliationItemStatus.MATCHED
            if row is not None:
                row.status = BankImportRowStatus.MATCHED
        else:
            item.status = ReconciliationItemStatus.UNMATCHED
            item.matched_journal_entry_id = None
            item.resolved_by_user_id = None
            item.resolved_at = None
            if row is not None:
                row.status = BankImportRowStatus.STAGED
    log_audit_event(
        db,
        action="reconciliation.group_unmatched",
        summary=f"Removed grouped reconciliation {group.id}",
        entity_type="reconciliation_match_group",
        entity_id=group.id,
        actor_user_id=acting_user.id,
        company_id=session.company_id,
        before_state=group_snapshot,
    )
    db.commit()
