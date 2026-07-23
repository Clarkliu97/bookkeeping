from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.db.models.auth import User
from app.db.models.documents import Document, DocumentLink
from app.db.models.enums import DocumentLinkEntityType, EntityType, JournalRecommendationStatus
from app.db.models.journal_recommendations import JournalRecommendationRun, JournalRecommendationRunDocument
from app.documents.service import store_document_bytes
from app.journal_recommendations.service import (
    PROMPT_VERSION,
    analyze_run,
    build_run_detail,
    ensure_supported_model,
    list_supported_models,
    reject_run,
    validate_analysis_mode,
    validate_new_files,
    normalize_media_type,
    accept_run,
)
from app.schemas.common import (
    JournalEntryRead,
    JournalRecommendationAcceptRead,
    JournalRecommendationDetailRead,
    JournalRecommendationModelRead,
    JournalRecommendationRunRead,
)
from app.schemas.requests import JournalRecommendationAcceptRequest


router = APIRouter(prefix="/companies/{company_id}/journal-recommendations", tags=["journal-recommendations"])


@router.get("/models", response_model=list[JournalRecommendationModelRead])
def list_journal_recommendation_models(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list_supported_models()


@router.get("", response_model=list[JournalRecommendationRunRead])
def list_recommendation_runs(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[JournalRecommendationRun]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(JournalRecommendationRun)
            .where(JournalRecommendationRun.company_id == company_id)
            .order_by(JournalRecommendationRun.created_at.desc())
        ).all()
    )


@router.post("", response_model=JournalRecommendationDetailRead, status_code=201)
async def create_recommendation_run(
    company_id: UUID,
    files: list[UploadFile] | None = File(default=None),
    existing_document_ids: list[UUID] | None = Form(default=None),
    model: str = Form(default="gpt-5.4-mini"),
    user_context_note: str | None = Form(default=None),
    target_accounting_period_id: UUID | None = Form(default=None),
    analysis_mode: str = Form(default="multiple"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_company_permission(company_id, "can_prepare", db, current_user)
    chosen_model = ensure_supported_model(model)

    requested_document_ids = existing_document_ids or []
    if len(set(requested_document_ids)) != len(requested_document_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select each existing evidence document only once",
        )
    existing_documents: list[Document] = []
    for document_id in requested_document_ids:
        document = db.get(Document, document_id)
        if document is None or document.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Existing evidence document not found")
        existing_documents.append(document)

    file_payloads: list[tuple[UploadFile, bytes, str, int]] = []
    validation_payloads: list[tuple[str, str | None, int]] = [
        (document.original_filename, document.media_type, document.byte_size)
        for document in existing_documents
    ]
    for file in files or []:
        content = await file.read()
        validation_payloads.append((file.filename or "upload.bin", file.content_type, len(content)))
        file_payloads.append((file, content, file.filename or "upload.bin", len(content)))
    validate_new_files(validation_payloads)
    normalized_analysis_mode = validate_analysis_mode(analysis_mode, len(validation_payloads))

    run = JournalRecommendationRun(
        company_id=company_id,
        created_by_user_id=current_user.id,
        status=JournalRecommendationStatus.DRAFT,
        target_accounting_period_id=target_accounting_period_id,
        user_context_note=user_context_note,
        analysis_mode=normalized_analysis_mode,
        prompt_version=PROMPT_VERSION,
        provider_name="openai",
        provider_model=chosen_model.id,
    )
    db.add(run)
    db.flush()

    for index, document in enumerate(existing_documents, start=1):
        db.add(
            JournalRecommendationRunDocument(
                company_id=company_id,
                recommendation_run_id=run.id,
                document_id=document.id,
                display_order=index,
            )
        )
        db.add(
            DocumentLink(
                company_id=company_id,
                document_id=document.id,
                entity_type=DocumentLinkEntityType.JOURNAL_RECOMMENDATION_RUN,
                entity_id=str(run.id),
                note="Reused as AI-assisted journal recommendation evidence",
                linked_by_user_id=current_user.id,
            )
        )

    first_upload_order = len(existing_documents) + 1
    for index, (file, content, filename, _) in enumerate(file_payloads, start=first_upload_order):
        stored_filename, storage_path, checksum, byte_size = store_document_bytes(
            company_id=company_id,
            original_filename=filename,
            content=content,
        )
        document = Document(
            company_id=company_id,
            original_filename=filename,
            stored_filename=stored_filename,
            media_type=normalize_media_type(filename, file.content_type),
            byte_size=byte_size,
            checksum_sha256=checksum,
            storage_path=storage_path,
            uploaded_by_user_id=current_user.id,
        )
        db.add(document)
        db.flush()
        db.add(
            JournalRecommendationRunDocument(
                company_id=company_id,
                recommendation_run_id=run.id,
                document_id=document.id,
                display_order=index,
            )
        )
        db.add(
            DocumentLink(
                company_id=company_id,
                document_id=document.id,
                entity_type=DocumentLinkEntityType.JOURNAL_RECOMMENDATION_RUN,
                entity_id=str(run.id),
                note="Supports AI-assisted journal recommendation",
                linked_by_user_id=current_user.id,
            )
        )

    log_audit_event(
        db,
        action="journal-recommendation.created",
        summary="Created journal recommendation run",
        entity_type=EntityType.JOURNAL_RECOMMENDATION_RUN.value,
        entity_id=run.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        metadata={
            "provider": "openai",
            "model": chosen_model.id,
            "file_count": len(validation_payloads),
            "existing_document_count": len(existing_documents),
            "uploaded_document_count": len(file_payloads),
            "analysis_mode": normalized_analysis_mode,
        },
    )
    db.commit()
    return build_run_detail(db, company_id, run.id)


@router.get("/{run_id}", response_model=JournalRecommendationDetailRead)
def get_recommendation_run(
    company_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return build_run_detail(db, company_id, run_id)


@router.post("/{run_id}/analyze", response_model=JournalRecommendationDetailRead)
def analyze_recommendation_run(
    company_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_company_permission(company_id, "can_prepare", db, current_user)
    run = analyze_run(db, company_id=company_id, run_id=run_id)
    log_audit_event(
        db,
        action="journal-recommendation.analyzed",
        summary="Analyzed journal recommendation run",
        entity_type=EntityType.JOURNAL_RECOMMENDATION_RUN.value,
        entity_id=run.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        metadata={"provider": run.provider_name, "model": run.provider_model, "status": run.status.value},
    )
    db.commit()
    return build_run_detail(db, company_id, run_id)


@router.post("/{run_id}/accept", response_model=JournalRecommendationAcceptRead)
def accept_recommendation_run(
    company_id: UUID,
    run_id: UUID,
    payload: JournalRecommendationAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JournalRecommendationAcceptRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    journals = accept_run(
        db,
        company_id=company_id,
        run_id=run_id,
        created_by_user_id=current_user.id,
        accepted_proposal_ids=payload.accepted_proposal_ids,
    )
    log_audit_event(
        db,
        action="journal-recommendation.accepted",
        summary="Accepted journal recommendation into draft journal",
        entity_type=EntityType.JOURNAL_RECOMMENDATION_RUN.value,
        entity_id=run_id,
        actor_user_id=current_user.id,
        company_id=company_id,
        metadata={
            "accepted_journal_entry_ids": [str(journal.id) for journal in journals],
            "accepted_journal_count": len(journals),
            "accepted_proposal_count": len(payload.accepted_proposal_ids),
        },
    )
    db.commit()
    return JournalRecommendationAcceptRead(
        journals=[JournalEntryRead.model_validate(journal) for journal in journals]
    )


@router.post("/{run_id}/reject", response_model=JournalRecommendationDetailRead)
def reject_recommendation_run(
    company_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_company_permission(company_id, "can_prepare", db, current_user)
    run = reject_run(db, company_id=company_id, run_id=run_id)
    log_audit_event(
        db,
        action="journal-recommendation.rejected",
        summary="Rejected journal recommendation run",
        entity_type=EntityType.JOURNAL_RECOMMENDATION_RUN.value,
        entity_id=run.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    return build_run_detail(db, company_id, run_id)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recommendation_run(
    company_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    run = db.get(JournalRecommendationRun, run_id)
    if run is None or run.company_id != company_id:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if run.status == JournalRecommendationStatus.ACCEPTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accepted recommendation runs cannot be deleted")
    db.delete(run)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
