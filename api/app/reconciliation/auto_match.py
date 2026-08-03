from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import combinations
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit.service import log_audit_event
from app.db.models.accounting import JournalEntry
from app.db.models.auth import User
from app.db.models.banking import BankAccount, BankImportRow
from app.db.models.enums import JournalStatus, ReconciliationItemStatus, ReconciliationSessionStatus
from app.db.models.reconciliation import ReconciliationItem, ReconciliationSession
from app.reconciliation.service import (
    ZERO,
    _existing_bank_allocation,
    _existing_journal_allocation,
    _money,
    bank_row_amount,
    create_match_group,
    journal_cash_amount,
)
from app.schemas.common import AutoReconciliationResult, ReconciliationMatchGroupRead
from app.schemas.requests import (
    AutoReconciliationRequest,
    ReconciliationBankAllocationCreate,
    ReconciliationJournalAllocationCreate,
    ReconciliationMatchGroupCreate,
)


LOCAL_BANK_POOL_LIMIT = 10
LOCAL_JOURNAL_POOL_LIMIT = 12


@dataclass(frozen=True)
class BankSource:
    item_id: UUID
    amount: Decimal
    transaction_date: date
    currency_code: str


@dataclass(frozen=True)
class JournalSource:
    journal_id: UUID
    amount: Decimal
    entry_date: date
    currency_code: str
    detail_line_amounts: tuple[Decimal, ...]


@dataclass(frozen=True)
class MatchCandidate:
    bank_sources: tuple[BankSource, ...]
    journal_sources: tuple[JournalSource, ...]
    bank_total: Decimal
    journal_total: Decimal
    difference: Decimal
    quality: tuple[int, int, int, int, int]

    @property
    def bank_ids(self) -> tuple[UUID, ...]:
        return tuple(source.item_id for source in self.bank_sources)

    @property
    def journal_ids(self) -> tuple[UUID, ...]:
        return tuple(source.journal_id for source in self.journal_sources)


def _days_apart(left: date, right: date) -> int:
    return abs((left - right).days)


def _money_cents(value: Decimal) -> int:
    return int((_money(value) * 100).to_integral_value())


def _date_metrics(
    banks: tuple[BankSource, ...], journals: tuple[JournalSource, ...]
) -> tuple[int, int]:
    gaps = [
        min(_days_apart(bank.transaction_date, journal.entry_date) for journal in journals)
        for bank in banks
    ]
    gaps.extend(
        min(_days_apart(journal.entry_date, bank.transaction_date) for bank in banks)
        for journal in journals
    )
    return max(gaps), sum(gaps)


def _component_match_count(
    banks: tuple[BankSource, ...],
    journals: tuple[JournalSource, ...],
    tolerance: Decimal,
) -> int:
    remaining_components = [
        amount for journal in journals for amount in journal.detail_line_amounts
    ]
    hits = 0
    for bank in sorted(banks, key=lambda source: (source.amount, str(source.item_id))):
        matching_index = next(
            (
                index
                for index, component in enumerate(remaining_components)
                if abs(abs(bank.amount) - component) <= tolerance
            ),
            None,
        )
        if matching_index is not None:
            hits += 1
            remaining_components.pop(matching_index)
    return hits


def _candidate(
    banks: tuple[BankSource, ...],
    journals: tuple[JournalSource, ...],
    payload: AutoReconciliationRequest,
) -> MatchCandidate | None:
    if not banks or not journals:
        return None
    if len({source.currency_code for source in (*banks, *journals)}) != 1:
        return None
    max_date_gap, total_date_gap = _date_metrics(banks, journals)
    if max_date_gap > payload.date_window_days:
        return None
    bank_total = _money(sum((source.amount for source in banks), ZERO))
    journal_total = _money(sum((source.amount for source in journals), ZERO))
    if bank_total == ZERO or journal_total == ZERO:
        return None
    difference = _money(bank_total - journal_total)
    if abs(difference) > payload.amount_tolerance:
        return None
    component_hits = _component_match_count(banks, journals, payload.amount_tolerance)
    quality = (
        abs(_money_cents(difference)),
        len(banks) + len(journals),
        max_date_gap,
        -component_hits,
        total_date_gap,
    )
    return MatchCandidate(
        bank_sources=banks,
        journal_sources=journals,
        bank_total=bank_total,
        journal_total=journal_total,
        difference=difference,
        quality=quality,
    )


def _stable_candidate_key(candidate: MatchCandidate) -> tuple[object, ...]:
    return (
        candidate.quality,
        tuple(str(source_id) for source_id in candidate.bank_ids),
        tuple(str(source_id) for source_id in candidate.journal_ids),
    )


def _bank_subsets(
    sources: list[BankSource], max_group_size: int, date_window_days: int
) -> list[tuple[BankSource, ...]]:
    subsets: dict[tuple[str, ...], tuple[BankSource, ...]] = {}
    for anchor in sources:
        nearby = [
            source
            for source in sources
            if source.currency_code == anchor.currency_code
            and _days_apart(source.transaction_date, anchor.transaction_date) <= date_window_days
        ]
        nearby.sort(
            key=lambda source: (
                _days_apart(source.transaction_date, anchor.transaction_date),
                source.transaction_date,
                str(source.item_id),
            )
        )
        nearby = nearby[:LOCAL_BANK_POOL_LIMIT]
        if anchor not in nearby:
            nearby = [anchor, *nearby[: LOCAL_BANK_POOL_LIMIT - 1]]
        others = [source for source in nearby if source.item_id != anchor.item_id]
        for size in range(1, min(max_group_size, len(nearby)) + 1):
            for selected_others in combinations(others, size - 1):
                selected = tuple(
                    sorted((anchor, *selected_others), key=lambda source: str(source.item_id))
                )
                key = tuple(str(source.item_id) for source in selected)
                subsets[key] = selected
    return sorted(
        subsets.values(),
        key=lambda selected: (
            len(selected),
            min(source.transaction_date for source in selected),
            tuple(str(source.item_id) for source in selected),
        ),
    )


def _journal_pool(
    banks: tuple[BankSource, ...], journals: list[JournalSource]
) -> list[JournalSource]:
    bank_total = _money(sum((source.amount for source in banks), ZERO))
    bank_amounts = tuple(source.amount for source in banks)

    def component_gap(journal: JournalSource) -> Decimal:
        if not journal.detail_line_amounts:
            return abs(journal.amount - bank_total)
        return min(
            abs(component - bank_amount)
            for component in journal.detail_line_amounts
            for bank_amount in (abs(amount) for amount in bank_amounts)
        )

    eligible = [
        journal
        for journal in journals
        if journal.currency_code == banks[0].currency_code
    ]
    eligible.sort(
        key=lambda journal: (
            min(_days_apart(journal.entry_date, bank.transaction_date) for bank in banks),
            min(abs(journal.amount - bank_total), component_gap(journal)),
            journal.entry_date,
            str(journal.journal_id),
        )
    )
    return eligible[:LOCAL_JOURNAL_POOL_LIMIT]


def _generate_candidates(
    banks: list[BankSource],
    journals: list[JournalSource],
    payload: AutoReconciliationRequest,
) -> list[MatchCandidate]:
    candidates: dict[tuple[tuple[str, ...], tuple[str, ...]], MatchCandidate] = {}

    # Never pool-limit the ordinary one-to-one search.
    for bank in banks:
        for journal in journals:
            candidate = _candidate((bank,), (journal,), payload)
            if candidate is not None:
                candidates[((str(bank.item_id),), (str(journal.journal_id),))] = candidate

    for bank_subset in _bank_subsets(
        banks, payload.max_group_size, payload.date_window_days
    ):
        journal_pool = _journal_pool(bank_subset, journals)
        for journal_count in range(1, min(payload.max_group_size, len(journal_pool)) + 1):
            if len(bank_subset) == journal_count == 1:
                continue
            for selected_journals in combinations(journal_pool, journal_count):
                journal_subset = tuple(
                    sorted(selected_journals, key=lambda source: str(source.journal_id))
                )
                candidate = _candidate(bank_subset, journal_subset, payload)
                if candidate is None:
                    continue
                key = (
                    tuple(str(source.item_id) for source in bank_subset),
                    tuple(str(source.journal_id) for source in journal_subset),
                )
                candidates[key] = candidate
    return sorted(candidates.values(), key=_stable_candidate_key)


def _ambiguous_source_ids(
    candidates: list[MatchCandidate], *, bank_side: bool
) -> set[UUID]:
    by_source: dict[UUID, list[MatchCandidate]] = {}
    for candidate in candidates:
        source_ids = candidate.bank_ids if bank_side else candidate.journal_ids
        for source_id in source_ids:
            by_source.setdefault(source_id, []).append(candidate)

    ambiguous: set[UUID] = set()
    for source_id, source_candidates in by_source.items():
        best_quality = min(candidate.quality for candidate in source_candidates)
        best_matches = {
            (candidate.bank_ids, candidate.journal_ids)
            for candidate in source_candidates
            if candidate.quality == best_quality
        }
        if len(best_matches) > 1:
            ambiguous.add(source_id)
    return ambiguous


def _select_candidates(
    candidates: list[MatchCandidate],
) -> tuple[list[MatchCandidate], set[UUID]]:
    ambiguous_bank_ids = _ambiguous_source_ids(candidates, bank_side=True)
    ambiguous_journal_ids = _ambiguous_source_ids(candidates, bank_side=False)
    ambiguous_statement_ids = set(ambiguous_bank_ids)
    for candidate in candidates:
        if any(source_id in ambiguous_journal_ids for source_id in candidate.journal_ids):
            ambiguous_statement_ids.update(candidate.bank_ids)
    selected: list[MatchCandidate] = []
    used_bank_ids: set[UUID] = set()
    used_journal_ids: set[UUID] = set()
    for candidate in candidates:
        if any(source_id in ambiguous_bank_ids for source_id in candidate.bank_ids):
            continue
        if any(source_id in ambiguous_journal_ids for source_id in candidate.journal_ids):
            continue
        if any(source_id in used_bank_ids for source_id in candidate.bank_ids):
            continue
        if any(source_id in used_journal_ids for source_id in candidate.journal_ids):
            continue
        selected.append(candidate)
        used_bank_ids.update(candidate.bank_ids)
        used_journal_ids.update(candidate.journal_ids)
    return selected, ambiguous_statement_ids


def _load_sources(
    db: Session,
    *,
    session: ReconciliationSession,
    ledger_account_id: UUID,
) -> tuple[list[BankSource], list[JournalSource]]:
    items = list(
        db.scalars(
            select(ReconciliationItem)
            .where(
                ReconciliationItem.reconciliation_session_id == session.id,
                ReconciliationItem.status == ReconciliationItemStatus.UNMATCHED,
            )
            .order_by(ReconciliationItem.id.asc())
        ).all()
    )
    banks: list[BankSource] = []
    for item in items:
        row = db.get(BankImportRow, item.bank_import_row_id)
        if row is None:
            continue
        source = bank_row_amount(row)
        remaining = _money(source - _existing_bank_allocation(db, item))
        if remaining == ZERO or (remaining > ZERO) != (source > ZERO):
            continue
        banks.append(
            BankSource(
                item_id=item.id,
                amount=remaining,
                transaction_date=row.transaction_date,
                currency_code=row.currency_code,
            )
        )

    journal_statement = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(
            JournalEntry.company_id == session.company_id,
            JournalEntry.status == JournalStatus.POSTED,
        )
    )
    if session.accounting_period_id is not None:
        journal_statement = journal_statement.where(
            JournalEntry.accounting_period_id == session.accounting_period_id
        )
    journals: list[JournalSource] = []
    for journal in db.scalars(
        journal_statement.order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc())
    ).all():
        source = journal_cash_amount(journal, ledger_account_id)
        if source == ZERO:
            continue
        remaining = _money(
            source - _existing_journal_allocation(db, journal.id, ledger_account_id)
        )
        if remaining == ZERO or (remaining > ZERO) != (source > ZERO):
            continue
        line_amounts = tuple(
            abs(_money(line.debit_amount - line.credit_amount))
            for line in journal.lines
            if _money(line.debit_amount - line.credit_amount) != ZERO
        )
        journals.append(
            JournalSource(
                journal_id=journal.id,
                amount=remaining,
                entry_date=journal.entry_date,
                currency_code=journal.currency_code,
                detail_line_amounts=line_amounts,
            )
        )
    return banks, journals


def auto_reconcile_session(
    db: Session,
    *,
    session: ReconciliationSession,
    payload: AutoReconciliationRequest,
    acting_user: User,
) -> AutoReconciliationResult:
    if session.status == ReconciliationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed reconciliation sessions cannot be changed",
        )
    bank_account = db.get(BankAccount, session.bank_account_id)
    if bank_account is None or bank_account.ledger_account_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Link the bank account to its ledger cash account before auto-reconciling",
        )

    banks, journals = _load_sources(
        db,
        session=session,
        ledger_account_id=bank_account.ledger_account_id,
    )
    candidates = _generate_candidates(banks, journals, payload)
    selected, ambiguous_statement_ids = _select_candidates(candidates)
    created_groups: list[ReconciliationMatchGroupRead] = []
    matched_bank_ids: set[UUID] = set()
    try:
        for candidate in selected:
            note = (
                "Auto reconciliation: "
                f"amount tolerance {payload.amount_tolerance}; "
                f"date window {payload.date_window_days} day(s)."
            )
            created_groups.append(
                create_match_group(
                    db,
                    session=session,
                    payload=ReconciliationMatchGroupCreate(
                        bank_allocations=[
                            ReconciliationBankAllocationCreate(
                                reconciliation_item_id=source.item_id,
                                allocated_amount=source.amount,
                            )
                            for source in candidate.bank_sources
                        ],
                        journal_allocations=[
                            ReconciliationJournalAllocationCreate(
                                journal_entry_id=source.journal_id,
                                allocated_amount=source.amount,
                            )
                            for source in candidate.journal_sources
                        ],
                        tolerance_amount=payload.amount_tolerance,
                        note=note,
                    ),
                    acting_user=acting_user,
                    commit=False,
                )
            )
            matched_bank_ids.update(candidate.bank_ids)

        unmatched_ids = [source.item_id for source in banks if source.item_id not in matched_bank_ids]
        log_audit_event(
            db,
            action="reconciliation.auto_reconciled",
            summary=(
                f"Auto-reconciled {len(matched_bank_ids)} of {len(banks)} statement items "
                f"into {len(created_groups)} groups"
            ),
            entity_type="reconciliation_session",
            entity_id=session.id,
            actor_user_id=acting_user.id,
            company_id=session.company_id,
            metadata={
                "amount_tolerance": str(payload.amount_tolerance),
                "date_window_days": payload.date_window_days,
                "max_group_size": payload.max_group_size,
                "candidate_count": len(candidates),
                "ambiguous_statement_item_count": len(ambiguous_statement_ids),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return AutoReconciliationResult(
        considered_statement_items=len(banks),
        matched_statement_items=len(matched_bank_ids),
        created_group_count=len(created_groups),
        unmatched_statement_item_ids=unmatched_ids,
        ambiguous_statement_item_ids=sorted(ambiguous_statement_ids, key=str),
        amount_tolerance=payload.amount_tolerance,
        date_window_days=payload.date_window_days,
        max_group_size=payload.max_group_size,
        groups=created_groups,
    )
