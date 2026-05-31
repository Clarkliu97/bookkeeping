from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.db.models.accounting import AccountingPeriod, JournalEntry
from app.db.models.auth import User
from app.db.models.bas import BasExport
from app.db.models.documents import Document, DocumentLink
from app.db.models.employment import EmploymentWorker
from app.db.models.enums import DocumentLinkEntityType, EntityType
from app.db.models.reconciliation import ReconciliationItem
from app.documents.service import resolve_document_path, store_document_bytes
from app.db.models.banking import BankImportRow, BankImportSession
from app.db.models.tax_workpapers import TaxWorkpaperExport
from app.db.models.journal_recommendations import JournalRecommendationRun
from app.schemas.common import DocumentLinkRead, DocumentRead
from app.schemas.requests import DocumentLinkCreate, DocumentLinkUpdate, DocumentUpdate


router = APIRouter(prefix="/companies/{company_id}/documents", tags=["documents"])


def _load_document_or_404(db: Session, company_id: UUID, document_id: UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def _load_document_link_or_404(db: Session, company_id: UUID, document_id: UUID, link_id: UUID) -> DocumentLink:
    link = db.get(DocumentLink, link_id)
    if link is None or link.company_id != company_id or link.document_id != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document link not found")
    return link


def _validate_link_target(db: Session, company_id: UUID, entity_type: DocumentLinkEntityType, entity_id: UUID) -> None:
    entity_map = {
        DocumentLinkEntityType.JOURNAL_ENTRY: JournalEntry,
        DocumentLinkEntityType.JOURNAL_RECOMMENDATION_RUN: JournalRecommendationRun,
        DocumentLinkEntityType.BANK_IMPORT_SESSION: BankImportSession,
        DocumentLinkEntityType.BANK_IMPORT_ROW: BankImportRow,
        DocumentLinkEntityType.RECONCILIATION_ITEM: ReconciliationItem,
        DocumentLinkEntityType.ACCOUNTING_PERIOD: AccountingPeriod,
        DocumentLinkEntityType.EMPLOYMENT_WORKER: EmploymentWorker,
    }
    model = entity_map[entity_type]
    instance = db.get(model, entity_id)
    if instance is None or getattr(instance, "company_id", None) != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link target not found")


@router.get("", response_model=list[DocumentRead])
def list_documents(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(Document).where(Document.company_id == company_id).order_by(Document.created_at.desc())
        ).all()
    )


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    company_id: UUID,
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_company_permission(company_id, "can_prepare", db, current_user)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    stored_filename, storage_path, checksum, byte_size = store_document_bytes(
        company_id=company_id,
        original_filename=file.filename or "upload.bin",
        content=content,
    )
    document = Document(
        company_id=company_id,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        media_type=file.content_type,
        byte_size=byte_size,
        checksum_sha256=checksum,
        storage_path=storage_path,
        uploaded_by_user_id=current_user.id,
    )
    db.add(document)
    db.flush()
    log_audit_event(
        db,
        action="document.uploaded",
        summary=f"Uploaded document {document.original_filename}",
        entity_type=EntityType.COMPANY.value,
        entity_id=document.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        metadata={"note": note} if note else None,
    )
    db.commit()
    db.refresh(document)
    return document


@router.post("/{document_id}/links", response_model=DocumentLinkRead, status_code=201)
def link_document(
    company_id: UUID,
    document_id: UUID,
    payload: DocumentLinkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentLink:
    require_company_permission(company_id, "can_prepare", db, current_user)
    document = db.get(Document, document_id)
    if document is None or document.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    entity_type = DocumentLinkEntityType(payload.entity_type)
    _validate_link_target(db, company_id, entity_type, payload.entity_id)
    link = DocumentLink(
        company_id=company_id,
        document_id=document_id,
        entity_type=entity_type,
        entity_id=str(payload.entity_id),
        note=payload.note,
        linked_by_user_id=current_user.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.put("/{document_id}", response_model=DocumentRead)
def update_document(
    company_id: UUID,
    document_id: UUID,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    require_company_permission(company_id, "can_prepare", db, current_user)
    document = _load_document_or_404(db, company_id, document_id)
    before_state = DocumentRead.model_validate(document).model_dump(mode="json")
    document.original_filename = payload.original_filename
    document.media_type = payload.media_type
    log_audit_event(
        db,
        action="document.updated",
        summary=f"Updated document {document.original_filename}",
        entity_type=EntityType.COMPANY.value,
        entity_id=document.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=DocumentRead.model_validate(document).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    company_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    document = _load_document_or_404(db, company_id, document_id)
    if db.scalar(select(DocumentLink.id).where(DocumentLink.document_id == document.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is linked to other records")
    if db.scalar(select(BankImportSession.id).where(BankImportSession.uploaded_document_id == document.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is attached to a bank import session")
    if db.scalar(select(BasExport.id).where(BasExport.document_id == document.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is attached to a BAS export")
    if db.scalar(select(TaxWorkpaperExport.id).where(TaxWorkpaperExport.document_id == document.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is attached to a tax workpaper export")
    log_audit_event(
        db,
        action="document.deleted",
        summary=f"Deleted document {document.original_filename}",
        entity_type=EntityType.COMPANY.value,
        entity_id=document.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=DocumentRead.model_validate(document).model_dump(mode="json"),
    )
    path = resolve_document_path(document.storage_path)
    if path.exists():
        path.unlink()
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{document_id}/links/{link_id}", response_model=DocumentLinkRead)
def update_document_link(
    company_id: UUID,
    document_id: UUID,
    link_id: UUID,
    payload: DocumentLinkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentLink:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_document_or_404(db, company_id, document_id)
    link = _load_document_link_or_404(db, company_id, document_id, link_id)
    entity_type = DocumentLinkEntityType(payload.entity_type)
    _validate_link_target(db, company_id, entity_type, payload.entity_id)
    link.entity_type = entity_type
    link.entity_id = str(payload.entity_id)
    link.note = payload.note
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{document_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_link(
    company_id: UUID,
    document_id: UUID,
    link_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_document_or_404(db, company_id, document_id)
    link = _load_document_link_or_404(db, company_id, document_id, link_id)
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/links", response_model=list[DocumentLinkRead])
def list_document_links(
    company_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentLink]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(DocumentLink)
            .where(DocumentLink.company_id == company_id, DocumentLink.document_id == document_id)
            .order_by(DocumentLink.created_at.asc())
        ).all()
    )


@router.get("/{document_id}/download")
def download_document(
    company_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    require_company_permission(company_id, "can_prepare", db, current_user)
    document = _load_document_or_404(db, company_id, document_id)
    path = resolve_document_path(document.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file is missing")
    return FileResponse(path=path, filename=document.original_filename, media_type=document.media_type)
