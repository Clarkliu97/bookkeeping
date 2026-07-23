from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.bank_imports.service import normalize_amount, parse_bank_csv_rows, parse_csv_date
from app.db.models.auth import User
from app.db.models.banking import BankAccount, BankImportRow, BankImportSession
from app.db.models.documents import Document
from app.db.models.enums import BankImportRowStatus, BankImportSessionStatus, EntityType
from app.db.models.reconciliation import ReconciliationItem
from app.documents.service import store_document_bytes
from app.schemas.common import BankAccountRead, BankImportRowRead, BankImportSessionRead
from app.schemas.requests import BankAccountCreate, BankAccountUpdate, BankImportSessionUpdate, PeriodActionRequest


router = APIRouter(prefix="/companies/{company_id}", tags=["bank-imports"])


def _load_bank_account_or_404(db: Session, company_id: UUID, bank_account_id: UUID) -> BankAccount:
    bank_account = db.get(BankAccount, bank_account_id)
    if bank_account is None or bank_account.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")
    return bank_account


def _load_bank_import_session_or_404(db: Session, company_id: UUID, session_id: UUID) -> BankImportSession:
    session = db.get(BankImportSession, session_id)
    if session is None or session.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank import session not found")
    return session


def _build_fingerprint(
    *,
    company_id: UUID,
    bank_account_id: UUID,
    transaction_date: str,
    description: str,
    reference: str | None,
    debit_amount: Decimal,
    credit_amount: Decimal,
) -> str:
    raw = "|".join(
        [
            str(company_id),
            str(bank_account_id),
            transaction_date,
            description.strip(),
            (reference or "").strip(),
            f"{debit_amount:.2f}",
            f"{credit_amount:.2f}",
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()


@router.get("/bank-accounts", response_model=list[BankAccountRead])
def list_bank_accounts(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BankAccount]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(BankAccount).where(BankAccount.company_id == company_id).order_by(BankAccount.name.asc())
        ).all()
    )


@router.post("/bank-accounts", response_model=BankAccountRead, status_code=201)
def create_bank_account(
    company_id: UUID,
    payload: BankAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BankAccount:
    require_company_permission(company_id, "can_administer", db, current_user)
    bank_account = BankAccount(company_id=company_id, **payload.model_dump())
    db.add(bank_account)
    db.commit()
    db.refresh(bank_account)
    return bank_account


@router.put("/bank-accounts/{bank_account_id}", response_model=BankAccountRead)
def update_bank_account(
    company_id: UUID,
    bank_account_id: UUID,
    payload: BankAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BankAccount:
    require_company_permission(company_id, "can_administer", db, current_user)
    bank_account = _load_bank_account_or_404(db, company_id, bank_account_id)
    bank_account.name = payload.name
    bank_account.bank_name = payload.bank_name
    bank_account.bsb = payload.bsb
    bank_account.account_number_masked = payload.account_number_masked
    bank_account.is_active = payload.is_active
    db.commit()
    db.refresh(bank_account)
    return bank_account


@router.delete("/bank-accounts/{bank_account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_account(
    company_id: UUID,
    bank_account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    bank_account = _load_bank_account_or_404(db, company_id, bank_account_id)
    bank_account.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/bank-imports", response_model=list[BankImportSessionRead])
def list_bank_import_sessions(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BankImportSession]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(BankImportSession)
            .where(BankImportSession.company_id == company_id)
            .order_by(BankImportSession.imported_at.desc())
        ).all()
    )


@router.post("/bank-imports/upload", response_model=BankImportSessionRead, status_code=201)
async def upload_bank_csv(
    company_id: UUID,
    bank_account_id: UUID = Form(...),
    file: UploadFile = File(...),
    date_column: str = Form(default="date"),
    description_column: str = Form(default="description"),
    debit_column: str = Form(default="debit"),
    credit_column: str = Form(default="credit"),
    reference_column: str | None = Form(default="reference"),
    note: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BankImportSession:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_bank_account_or_404(db, company_id, bank_account_id)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded CSV is empty")

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must be UTF-8 encoded") from exc

    try:
        csv_rows = parse_bank_csv_rows(
            decoded,
            date_column=date_column,
            description_column=description_column,
            debit_column=debit_column,
            credit_column=credit_column,
            reference_column=reference_column,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    parsed_rows: list[dict] = []
    for line_number, row in enumerate(csv_rows, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            transaction_date = parse_csv_date(row.get(date_column, ""))
            debit_amount = normalize_amount(row.get(debit_column, ""))
            credit_amount = normalize_amount(row.get(credit_column, ""))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Row {line_number}: {exc}") from exc
        description = (row.get(description_column) or "").strip()
        if not description:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Row {line_number}: description is required")
        reference = (row.get(reference_column) or "").strip() if reference_column else None
        parsed_rows.append(
            {
                "line_number": line_number,
                "transaction_date": transaction_date,
                "description": description,
                "reference": reference or None,
                "debit_amount": debit_amount,
                "credit_amount": credit_amount,
                "raw_data": row,
            }
        )
    if not parsed_rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV contains no data rows")

    stored_filename, storage_path, checksum, byte_size = store_document_bytes(
        company_id=company_id,
        original_filename=file.filename or "bank-import.csv",
        content=content,
    )
    document = Document(
        company_id=company_id,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        media_type=file.content_type or "text/csv",
        byte_size=byte_size,
        checksum_sha256=checksum,
        storage_path=storage_path,
        uploaded_by_user_id=current_user.id,
    )
    db.add(document)
    db.flush()

    session = BankImportSession(
        company_id=company_id,
        bank_account_id=bank_account_id,
        uploaded_document_id=document.id,
        original_filename=file.filename or "bank-import.csv",
        header_mapping={
            "date": date_column,
            "description": description_column,
            "debit": debit_column,
            "credit": credit_column,
            "reference": reference_column,
        },
        status=BankImportSessionStatus.STAGED,
        imported_by_user_id=current_user.id,
        imported_at=datetime.now(timezone.utc),
        note=note,
    )
    db.add(session)
    db.flush()

    for row in parsed_rows:
        fingerprint = _build_fingerprint(
            company_id=company_id,
            bank_account_id=bank_account_id,
            transaction_date=row["transaction_date"].isoformat(),
            description=row["description"],
            reference=row["reference"],
            debit_amount=row["debit_amount"],
            credit_amount=row["credit_amount"],
        )
        duplicate_exists = db.scalar(
            select(BankImportRow.id).where(
                BankImportRow.company_id == company_id,
                BankImportRow.fingerprint == fingerprint,
            )
        )
        db.add(
            BankImportRow(
                company_id=company_id,
                bank_import_session_id=session.id,
                line_number=row["line_number"],
                transaction_date=row["transaction_date"],
                description=row["description"],
                reference=row["reference"],
                debit_amount=row["debit_amount"],
                credit_amount=row["credit_amount"],
                raw_data=row["raw_data"],
                fingerprint=fingerprint,
                status=BankImportRowStatus.DUPLICATE if duplicate_exists else BankImportRowStatus.STAGED,
            )
        )

    log_audit_event(
        db,
        action="bank-import.uploaded",
        summary=f"Uploaded bank import {session.original_filename}",
        entity_type=EntityType.COMPANY.value,
        entity_id=session.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    db.refresh(session)
    return session


@router.get("/bank-imports/{session_id}/rows", response_model=list[BankImportRowRead])
def list_bank_import_rows(
    company_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BankImportRow]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = db.get(BankImportSession, session_id)
    if session is None or session.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank import session not found")
    return list(
        db.scalars(
            select(BankImportRow)
            .where(BankImportRow.bank_import_session_id == session_id)
            .order_by(BankImportRow.line_number.asc())
        ).all()
    )


@router.post("/bank-imports/{session_id}/confirm", response_model=BankImportSessionRead)
def confirm_bank_import(
    company_id: UUID,
    session_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BankImportSession:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_bank_import_session_or_404(db, company_id, session_id)
    session.status = BankImportSessionStatus.CONFIRMED
    if payload.note:
        session.note = payload.note
    db.commit()
    db.refresh(session)
    return session


@router.put("/bank-imports/{session_id}", response_model=BankImportSessionRead)
def update_bank_import_session(
    company_id: UUID,
    session_id: UUID,
    payload: BankImportSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BankImportSession:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_bank_import_session_or_404(db, company_id, session_id)
    if session.status != BankImportSessionStatus.STAGED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only staged bank imports can be updated")
    session.note = payload.note
    db.commit()
    db.refresh(session)
    return session


@router.delete("/bank-imports/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_import_session(
    company_id: UUID,
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    session = _load_bank_import_session_or_404(db, company_id, session_id)
    if session.status != BankImportSessionStatus.STAGED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only staged bank imports can be deleted")
    if db.scalar(
        select(ReconciliationItem.id)
        .join(BankImportRow, BankImportRow.id == ReconciliationItem.bank_import_row_id)
        .where(BankImportRow.bank_import_session_id == session.id)
        .limit(1)
    ) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bank import session is already used in reconciliation")
    db.delete(session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
