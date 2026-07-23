from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.db.models.accounting import Account, AccountingPeriod, JournalEntry, JournalLine, PeriodLock
from app.db.models.auth import User
from app.db.models.documents import Document, DocumentLink
from app.db.models.enums import DocumentLinkEntityType, EntityType, JournalSourceType, JournalStatus, WorkflowStatus
from app.db.models.journal_recommendations import JournalRecommendationEntry, JournalRecommendationRun
from app.schemas.common import JournalEntryRead, JournalEvidenceRead, TrialBalanceRow
from app.schemas.requests import JournalEntryCreate, JournalEntryUpdate, JournalEvidenceLinkCreate


router = APIRouter(prefix="/companies/{company_id}/journals", tags=["ledger"])


def _load_journal_or_404(db: Session, company_id: UUID, journal_id: UUID) -> JournalEntry:
    journal = db.scalar(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.company_id == company_id, JournalEntry.id == journal_id)
    )
    if journal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return journal


def _load_document_or_404(db: Session, company_id: UUID, document_id: UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def _ensure_period_not_locked(db: Session, company_id: UUID, accounting_period_id: UUID) -> None:
    period = db.get(AccountingPeriod, accounting_period_id)
    if period is None or period.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accounting period not found")
    if period.status == WorkflowStatus.LOCKED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accounting period is locked")
    active_lock = db.scalar(
        select(PeriodLock)
        .where(PeriodLock.accounting_period_id == accounting_period_id, PeriodLock.unlocked_at.is_(None))
        .limit(1)
    )
    if active_lock is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accounting period is locked")


def _validate_journal_lines(db: Session, company_id: UUID, lines: list[JournalLine]) -> None:
    if len(lines) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Journal requires at least two lines")
    for index, line in enumerate(lines, start=1):
        is_valid_single_sided_line = (
            (line.debit_amount > Decimal("0.00") and line.credit_amount == Decimal("0.00"))
            or (line.credit_amount > Decimal("0.00") and line.debit_amount == Decimal("0.00"))
        )
        if not is_valid_single_sided_line:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Journal line {index} must have exactly one positive amount",
            )
    debit_total = sum((line.debit_amount for line in lines), Decimal("0.00"))
    credit_total = sum((line.credit_amount for line in lines), Decimal("0.00"))
    if debit_total != credit_total:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Journal is not balanced")
    account_ids = {line.account_id for line in lines}
    accounts = list(
        db.scalars(select(Account).where(Account.id.in_(account_ids), Account.company_id == company_id)).all()
    )
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Journal references invalid account ids")
    disallowed_accounts = [account.account_code for account in accounts if not account.allow_manual_posting]
    if disallowed_accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Journal references accounts that do not allow manual posting: {', '.join(sorted(disallowed_accounts))}",
        )


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


def _apply_journal_payload(journal: JournalEntry, payload: JournalEntryCreate, *, replace_lines: bool = True) -> None:
    journal.entry_date = payload.entry_date
    journal.accounting_period_id = payload.accounting_period_id
    journal.source_type = JournalSourceType(payload.source_type)
    journal.description = payload.description
    journal.reference = payload.reference
    if replace_lines:
        journal.lines.clear()
    for index, line in enumerate(payload.lines, start=1):
        journal.lines.append(
            JournalLine(
                line_number=index,
                account_id=line.account_id,
                description=line.description,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                tax_code_id=line.tax_code_id,
                reporting_category_id=line.reporting_category_id,
                source_document_reference=line.source_document_reference,
            )
        )


@router.get("", response_model=list[JournalEntryRead])
def list_journals(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[JournalEntry]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.company_id == company_id)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.entry_number.desc())
        ).all()
    )


@router.post("", response_model=JournalEntryRead, status_code=201)
def create_journal(
    company_id: UUID,
    payload: JournalEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEntry:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _ensure_period_not_locked(db, company_id, payload.accounting_period_id)
    journal = JournalEntry(
        company_id=company_id,
        entry_number=_next_entry_number(db, company_id),
        entry_date=payload.entry_date,
        accounting_period_id=payload.accounting_period_id,
        status=JournalStatus.DRAFT,
        source_type=JournalSourceType(payload.source_type),
        description=payload.description,
        reference=payload.reference,
        created_by_user_id=current_user.id,
    )
    _apply_journal_payload(journal, payload, replace_lines=False)
    _validate_journal_lines(db, company_id, journal.lines)
    db.add(journal)
    db.commit()
    db.refresh(journal)
    return _load_journal_or_404(db, company_id, journal.id)


@router.put("/{journal_id}", response_model=JournalEntryRead)
def update_journal(
    company_id: UUID,
    journal_id: UUID,
    payload: JournalEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEntry:
    require_company_permission(company_id, "can_prepare", db, current_user)
    journal = _load_journal_or_404(db, company_id, journal_id)
    if journal.status != JournalStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft journals can be updated")
    _ensure_period_not_locked(db, company_id, payload.accounting_period_id)
    before_state = JournalEntryRead.model_validate(journal).model_dump(mode="json")
    journal.lines.clear()
    db.flush()
    _apply_journal_payload(journal, payload, replace_lines=False)
    _validate_journal_lines(db, company_id, journal.lines)
    db.flush()
    log_audit_event(
        db,
        action="journal.updated",
        summary=f"Updated journal {journal.entry_number}",
        entity_type=EntityType.JOURNAL_ENTRY.value,
        entity_id=journal.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=JournalEntryRead.model_validate(journal).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(journal)
    return _load_journal_or_404(db, company_id, journal.id)


@router.delete("/{journal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal(
    company_id: UUID,
    journal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    journal = _load_journal_or_404(db, company_id, journal_id)
    if journal.status != JournalStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft journals can be deleted")
    log_audit_event(
        db,
        action="journal.deleted",
        summary=f"Deleted journal {journal.entry_number}",
        entity_type=EntityType.JOURNAL_ENTRY.value,
        entity_id=journal.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=JournalEntryRead.model_validate(journal).model_dump(mode="json"),
    )

    # Keep recommendation history while allowing accepted draft journals to be deleted.
    recommendation_entry_run_ids = select(JournalRecommendationEntry.recommendation_run_id).where(
        JournalRecommendationEntry.accepted_journal_entry_id == journal.id
    )
    recommendation_runs = list(
        db.scalars(
            select(JournalRecommendationRun).where(
                JournalRecommendationRun.company_id == company_id,
                (
                    (JournalRecommendationRun.accepted_journal_entry_id == journal.id)
                    | (JournalRecommendationRun.target_journal_entry_id == journal.id)
                    | JournalRecommendationRun.id.in_(recommendation_entry_run_ids)
                ),
            )
        ).all()
    )
    recommendation_entries = list(
        db.scalars(
            select(JournalRecommendationEntry).where(
                JournalRecommendationEntry.accepted_journal_entry_id == journal.id
            )
        ).all()
    )
    for entry in recommendation_entries:
        entry.accepted_journal_entry_id = None
    for run in recommendation_runs:
        if run.accepted_journal_entry_id == journal.id:
            run.accepted_journal_entry_id = None
        if run.target_journal_entry_id == journal.id:
            run.target_journal_entry_id = None

    # Document links use a polymorphic string key, so remove direct journal links explicitly.
    evidence_links = list(
        db.scalars(
            select(DocumentLink).where(
                DocumentLink.company_id == company_id,
                DocumentLink.entity_type == DocumentLinkEntityType.JOURNAL_ENTRY,
                DocumentLink.entity_id == str(journal.id),
            )
        ).all()
    )
    for link in evidence_links:
        db.delete(link)

    db.delete(journal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{journal_id}/post", response_model=JournalEntryRead)
def post_journal(
    company_id: UUID,
    journal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEntry:
    require_company_permission(company_id, "can_prepare", db, current_user)
    journal = _load_journal_or_404(db, company_id, journal_id)
    _ensure_period_not_locked(db, company_id, journal.accounting_period_id)
    _validate_journal_lines(db, company_id, journal.lines)
    journal.status = JournalStatus.POSTED
    journal.posted_by_user_id = current_user.id
    journal.posted_at = datetime.now(timezone.utc)
    log_audit_event(
        db,
        action="journal.posted",
        summary=f"Posted journal {journal.entry_number}",
        entity_type=EntityType.JOURNAL_ENTRY.value,
        entity_id=journal.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    db.refresh(journal)
    return _load_journal_or_404(db, company_id, journal.id)


@router.post("/{journal_id}/reverse", response_model=JournalEntryRead, status_code=201)
def reverse_journal(
    company_id: UUID,
    journal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEntry:
    require_company_permission(company_id, "can_prepare", db, current_user)
    journal = _load_journal_or_404(db, company_id, journal_id)
    if journal.status != JournalStatus.POSTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only posted journals can be reversed")
    _ensure_period_not_locked(db, company_id, journal.accounting_period_id)
    reversal = JournalEntry(
        company_id=company_id,
        entry_number=_next_entry_number(db, company_id),
        entry_date=journal.entry_date,
        accounting_period_id=journal.accounting_period_id,
        status=JournalStatus.POSTED,
        source_type=JournalSourceType.ADJUSTMENT,
        description=f"Reversal of {journal.entry_number}",
        reference=journal.reference,
        created_by_user_id=current_user.id,
        posted_by_user_id=current_user.id,
        posted_at=datetime.now(timezone.utc),
        reversal_of_entry_id=journal.id,
    )
    for index, line in enumerate(journal.lines, start=1):
        reversal.lines.append(
            JournalLine(
                line_number=index,
                account_id=line.account_id,
                description=line.description,
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                tax_code_id=line.tax_code_id,
                reporting_category_id=line.reporting_category_id,
                source_document_reference=line.source_document_reference,
            )
        )
    journal.status = JournalStatus.REVERSED
    db.add(reversal)
    log_audit_event(
        db,
        action="journal.reversed",
        summary=f"Reversed journal {journal.entry_number}",
        entity_type=EntityType.JOURNAL_ENTRY.value,
        entity_id=journal.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    db.refresh(reversal)
    return _load_journal_or_404(db, company_id, reversal.id)


@router.get("/{journal_id}/documents", response_model=list[JournalEvidenceRead])
def list_journal_evidence(
    company_id: UUID,
    journal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[JournalEvidenceRead]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_journal_or_404(db, company_id, journal_id)
    rows = db.execute(
        select(DocumentLink, Document)
        .join(Document, Document.id == DocumentLink.document_id)
        .where(DocumentLink.company_id == company_id)
        .where(DocumentLink.entity_type == DocumentLinkEntityType.JOURNAL_ENTRY)
        .where(DocumentLink.entity_id == str(journal_id))
        .order_by(DocumentLink.created_at.desc(), Document.created_at.desc())
    ).all()
    return [
        JournalEvidenceRead(
            link_id=link.id,
            document_id=document.id,
            original_filename=document.original_filename,
            media_type=document.media_type,
            byte_size=document.byte_size,
            uploaded_by_user_id=document.uploaded_by_user_id,
            document_created_at=document.created_at,
            note=link.note,
            linked_by_user_id=link.linked_by_user_id,
            linked_at=link.created_at,
        )
        for link, document in rows
    ]


@router.post("/{journal_id}/documents/{document_id}", response_model=JournalEvidenceRead, status_code=201)
def link_document_to_journal(
    company_id: UUID,
    journal_id: UUID,
    document_id: UUID,
    payload: JournalEvidenceLinkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalEvidenceRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    journal = _load_journal_or_404(db, company_id, journal_id)
    document = _load_document_or_404(db, company_id, document_id)
    existing_link = db.scalar(
        select(DocumentLink)
        .where(DocumentLink.company_id == company_id)
        .where(DocumentLink.document_id == document_id)
        .where(DocumentLink.entity_type == DocumentLinkEntityType.JOURNAL_ENTRY)
        .where(DocumentLink.entity_id == str(journal_id))
        .limit(1)
    )
    if existing_link is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is already linked to this journal")
    link = DocumentLink(
        company_id=company_id,
        document_id=document_id,
        entity_type=DocumentLinkEntityType.JOURNAL_ENTRY,
        entity_id=str(journal_id),
        note=payload.note,
        linked_by_user_id=current_user.id,
    )
    db.add(link)
    db.flush()
    log_audit_event(
        db,
        action="journal.evidence_linked",
        summary=f"Linked document {document.original_filename} to journal {journal.entry_number}",
        entity_type=EntityType.JOURNAL_ENTRY.value,
        entity_id=journal.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        metadata={"document_id": str(document.id), "note": payload.note} if payload.note else {"document_id": str(document.id)},
    )
    db.commit()
    db.refresh(link)
    return JournalEvidenceRead(
        link_id=link.id,
        document_id=document.id,
        original_filename=document.original_filename,
        media_type=document.media_type,
        byte_size=document.byte_size,
        uploaded_by_user_id=document.uploaded_by_user_id,
        document_created_at=document.created_at,
        note=link.note,
        linked_by_user_id=link.linked_by_user_id,
        linked_at=link.created_at,
    )


@router.delete("/{journal_id}/documents/{document_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_document_from_journal(
    company_id: UUID,
    journal_id: UUID,
    document_id: UUID,
    link_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    journal = _load_journal_or_404(db, company_id, journal_id)
    document = _load_document_or_404(db, company_id, document_id)
    link = db.get(DocumentLink, link_id)
    if (
        link is None
        or link.company_id != company_id
        or str(link.document_id) != str(document_id)
        or link.entity_type != DocumentLinkEntityType.JOURNAL_ENTRY
        or link.entity_id != str(journal_id)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal evidence link not found")
    log_audit_event(
        db,
        action="journal.evidence_unlinked",
        summary=f"Unlinked document {document.original_filename} from journal {journal.entry_number}",
        entity_type=EntityType.JOURNAL_ENTRY.value,
        entity_id=journal.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        metadata={"document_id": str(document.id), "link_id": str(link.id)},
    )
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/trial-balance", response_model=list[TrialBalanceRow])
def trial_balance(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TrialBalanceRow]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    query = (
        select(
            Account.id,
            Account.account_code,
            Account.name,
            func.coalesce(func.sum(JournalLine.debit_amount), 0).label("debit_total"),
            func.coalesce(func.sum(JournalLine.credit_amount), 0).label("credit_total"),
            (
                func.coalesce(func.sum(JournalLine.debit_amount), 0)
                - func.coalesce(func.sum(JournalLine.credit_amount), 0)
            ).label("balance"),
        )
        .join(JournalLine, JournalLine.account_id == Account.id, isouter=True)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id, isouter=True)
        .where(Account.company_id == company_id)
        .where((JournalEntry.status == JournalStatus.POSTED) | (JournalEntry.status.is_(None)))
        .group_by(Account.id, Account.account_code, Account.name)
        .order_by(Account.account_code.asc())
    )
    rows = db.execute(query).all()
    return [
        TrialBalanceRow(
            account_id=row.id,
            account_code=row.account_code,
            account_name=row.name,
            debit_total=row.debit_total,
            credit_total=row.credit_total,
            balance=row.balance,
        )
        for row in rows
    ]
