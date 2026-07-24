from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_approval_action, log_audit_event
from app.bas.service import (
    _refresh_line_results,
    build_bas_csv,
    build_bas_pdf,
    check_self_approval_block,
    create_bas_run,
    create_export_document,
    generate_bas_periods,
    maybe_lock_periods_for_policy,
    rebuild_bas_run,
)
from app.db.models.audit import ApprovalAction
from app.db.models.auth import User
from app.db.models.bas import (
    BasAdjustment,
    BasExport,
    BasLineResult,
    BasPeriod,
    BasReviewNote,
    BasRun,
)
from app.db.models.enums import (
    ApprovalActionType,
    BasExportFormat,
    BasPeriodStatus,
    BasRunStatus,
    EntityType,
)
from app.schemas.common import (
    ApprovalActionRead,
    BasAdjustmentRead,
    BasExportRead,
    BasPeriodRead,
    BasReviewNoteRead,
    BasRunDetailRead,
    BasRunRead,
)
from app.schemas.requests import (
    BasAdjustmentCreate,
    BasAdjustmentUpdate,
    BasPeriodGenerateRequest,
    BasPeriodUpdate,
    BasReviewNoteCreate,
    BasReviewNoteUpdate,
    BasRunCreate,
    BasRunUpdate,
    PeriodActionRequest,
)

router = APIRouter(prefix="/companies/{company_id}/bas", tags=["bas"])


def _load_bas_period_or_404(db: Session, company_id: UUID, bas_period_id: UUID) -> BasPeriod:
    bas_period = db.get(BasPeriod, bas_period_id)
    if bas_period is None or bas_period.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BAS period not found")
    return bas_period


def _load_bas_run_or_404(db: Session, company_id: UUID, bas_run_id: UUID) -> BasRun:
    bas_run = db.get(BasRun, bas_run_id)
    if bas_run is None or bas_run.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BAS run not found")
    return bas_run


def _load_bas_adjustment_or_404(db: Session, company_id: UUID, bas_run_id: UUID, adjustment_id: UUID) -> BasAdjustment:
    adjustment = db.get(BasAdjustment, adjustment_id)
    if adjustment is None or adjustment.company_id != company_id or adjustment.bas_run_id != bas_run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BAS adjustment not found")
    return adjustment


def _load_bas_review_note_or_404(db: Session, company_id: UUID, bas_run_id: UUID, review_note_id: UUID) -> BasReviewNote:
    review_note = db.get(BasReviewNote, review_note_id)
    if review_note is None or review_note.company_id != company_id or review_note.bas_run_id != bas_run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BAS review note not found")
    return review_note


def _ensure_bas_period_editable(db: Session, bas_period: BasPeriod) -> None:
    if bas_period.status == BasPeriodStatus.LOCKED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Locked BAS periods cannot be changed")
    if db.scalar(select(BasRun.id).where(BasRun.bas_period_id == bas_period.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="BAS periods with runs cannot be changed")


def _ensure_bas_run_editable(db: Session, bas_run: BasRun) -> None:
    if bas_run.status != BasRunStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft BAS runs can be changed")
    if db.scalar(select(BasExport.id).where(BasExport.bas_run_id == bas_run.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exported BAS runs cannot be changed")


def _bas_run_detail(db: Session, bas_run: BasRun) -> BasRunDetailRead:
    line_results = list(db.scalars(select(BasLineResult).where(BasLineResult.bas_run_id == bas_run.id)).all())
    adjustments = list(db.scalars(select(BasAdjustment).where(BasAdjustment.bas_run_id == bas_run.id)).all())
    review_notes = list(db.scalars(select(BasReviewNote).where(BasReviewNote.bas_run_id == bas_run.id)).all())
    exports = list(db.scalars(select(BasExport).where(BasExport.bas_run_id == bas_run.id)).all())
    return BasRunDetailRead(
        **BasRunRead.model_validate(bas_run).model_dump(),
        line_results=line_results,
        adjustments=adjustments,
        review_notes=review_notes,
        exports=exports,
    )


@router.get("/periods", response_model=list[BasPeriodRead])
def list_bas_periods(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BasPeriod]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(BasPeriod).where(BasPeriod.company_id == company_id).order_by(BasPeriod.start_date.desc())
        ).all()
    )


@router.post("/periods/generate", response_model=list[BasPeriodRead], status_code=201)
def generate_periods(
    company_id: UUID,
    payload: BasPeriodGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BasPeriod]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid BAS generation range")
    try:
        periods = generate_bas_periods(db, company_id=company_id, start_date=payload.start_date, end_date=payload.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return periods


@router.put("/periods/{bas_period_id}", response_model=BasPeriodRead)
def update_bas_period(
    company_id: UUID,
    bas_period_id: UUID,
    payload: BasPeriodUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasPeriod:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_period = _load_bas_period_or_404(db, company_id, bas_period_id)
    _ensure_bas_period_editable(db, bas_period)
    bas_period.note = payload.note
    db.commit()
    db.refresh(bas_period)
    return bas_period


@router.delete("/periods/{bas_period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bas_period(
    company_id: UUID,
    bas_period_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_period = _load_bas_period_or_404(db, company_id, bas_period_id)
    _ensure_bas_period_editable(db, bas_period)
    db.delete(bas_period)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/runs", response_model=BasRunDetailRead, status_code=201)
def generate_bas_run(
    company_id: UUID,
    payload: BasRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasRunDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_period = _load_bas_period_or_404(db, company_id, payload.bas_period_id)
    try:
        bas_run = create_bas_run(db, company_id=company_id, bas_period=bas_period, generated_by_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    log_audit_event(
        db,
        action="bas.run.generated",
        summary=f"Generated BAS run for period {bas_period.start_date} to {bas_period.end_date}",
        entity_type=EntityType.BAS_RUN.value,
        entity_id=bas_run.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    db.refresh(bas_run)
    return _bas_run_detail(db, bas_run)


@router.get("/runs/{bas_run_id}", response_model=BasRunDetailRead)
def get_bas_run(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasRunDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    return _bas_run_detail(db, bas_run)


@router.put("/runs/{bas_run_id}", response_model=BasRunDetailRead)
def update_bas_run(
    company_id: UUID,
    bas_run_id: UUID,
    payload: BasRunUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasRunDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    _ensure_bas_run_editable(db, bas_run)
    if db.scalar(
        select(BasReviewNote.id)
        .where(BasReviewNote.bas_run_id == bas_run.id, BasReviewNote.created_by_user_id.is_not(None))
        .limit(1)
    ) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="BAS runs with manual review notes cannot be rebuilt")
    bas_period = _load_bas_period_or_404(db, company_id, payload.bas_period_id)
    try:
        rebuild_bas_run(db, bas_run=bas_run, bas_period=bas_period, acting_user_id=current_user.id)
        _refresh_line_results(db, bas_run)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(bas_run)
    return _bas_run_detail(db, bas_run)


@router.delete("/runs/{bas_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bas_run(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    _ensure_bas_run_editable(db, bas_run)
    db.delete(bas_run)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/runs/{bas_run_id}/adjustments", response_model=list[BasAdjustmentRead])
def list_bas_adjustments(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BasAdjustment]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_bas_run_or_404(db, company_id, bas_run_id)
    return list(db.scalars(select(BasAdjustment).where(BasAdjustment.bas_run_id == bas_run_id)).all())


@router.post("/runs/{bas_run_id}/adjustments", response_model=BasRunDetailRead, status_code=201)
def add_bas_adjustment(
    company_id: UUID,
    bas_run_id: UUID,
    payload: BasAdjustmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasRunDetailRead:
    require_company_permission(company_id, "can_review", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    db.add(
        BasAdjustment(
            company_id=company_id,
            bas_run_id=bas_run_id,
            label=payload.label.upper(),
            amount=payload.amount,
            note=payload.note,
            created_by_user_id=current_user.id,
        )
    )
    db.flush()
    _refresh_line_results(db, bas_run)
    db.commit()
    db.refresh(bas_run)
    return _bas_run_detail(db, bas_run)


@router.put("/runs/{bas_run_id}/adjustments/{adjustment_id}", response_model=BasRunDetailRead)
def update_bas_adjustment(
    company_id: UUID,
    bas_run_id: UUID,
    adjustment_id: UUID,
    payload: BasAdjustmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasRunDetailRead:
    require_company_permission(company_id, "can_review", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    if bas_run.status not in {BasRunStatus.DRAFT, BasRunStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved BAS runs cannot be changed")
    adjustment = _load_bas_adjustment_or_404(db, company_id, bas_run_id, adjustment_id)
    adjustment.label = payload.label.upper()
    adjustment.amount = payload.amount
    adjustment.note = payload.note
    _refresh_line_results(db, bas_run)
    db.commit()
    db.refresh(bas_run)
    return _bas_run_detail(db, bas_run)


@router.delete("/runs/{bas_run_id}/adjustments/{adjustment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bas_adjustment(
    company_id: UUID,
    bas_run_id: UUID,
    adjustment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_review", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    if bas_run.status not in {BasRunStatus.DRAFT, BasRunStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved BAS runs cannot be changed")
    adjustment = _load_bas_adjustment_or_404(db, company_id, bas_run_id, adjustment_id)
    db.delete(adjustment)
    db.flush()
    _refresh_line_results(db, bas_run)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/runs/{bas_run_id}/review-notes", response_model=list[BasReviewNoteRead])
def list_bas_review_notes(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BasReviewNote]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_bas_run_or_404(db, company_id, bas_run_id)
    return list(db.scalars(select(BasReviewNote).where(BasReviewNote.bas_run_id == bas_run_id)).all())


@router.post("/runs/{bas_run_id}/review-notes", response_model=BasReviewNoteRead, status_code=201)
def add_bas_review_note(
    company_id: UUID,
    bas_run_id: UUID,
    payload: BasReviewNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasReviewNote:
    require_company_permission(company_id, "can_review", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    review_note = BasReviewNote(
        company_id=company_id,
        bas_run_id=bas_run_id,
        severity=payload.severity,
        message=payload.message,
        related_label=payload.related_label,
        created_by_user_id=current_user.id,
    )
    db.add(review_note)
    db.flush()
    bas_run.warning_count = len(
        list(db.scalars(select(BasReviewNote.id).where(BasReviewNote.bas_run_id == bas_run_id)).all())
    )
    db.commit()
    db.refresh(review_note)
    return review_note


@router.put("/runs/{bas_run_id}/review-notes/{review_note_id}", response_model=BasReviewNoteRead)
def update_bas_review_note(
    company_id: UUID,
    bas_run_id: UUID,
    review_note_id: UUID,
    payload: BasReviewNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasReviewNote:
    require_company_permission(company_id, "can_review", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    if bas_run.status not in {BasRunStatus.DRAFT, BasRunStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved BAS runs cannot be changed")
    review_note = _load_bas_review_note_or_404(db, company_id, bas_run_id, review_note_id)
    if review_note.created_by_user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Generated BAS warnings cannot be edited")
    review_note.severity = payload.severity
    review_note.message = payload.message
    review_note.related_label = payload.related_label
    db.commit()
    db.refresh(review_note)
    return review_note


@router.delete("/runs/{bas_run_id}/review-notes/{review_note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bas_review_note(
    company_id: UUID,
    bas_run_id: UUID,
    review_note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_review", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    if bas_run.status not in {BasRunStatus.DRAFT, BasRunStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved BAS runs cannot be changed")
    review_note = _load_bas_review_note_or_404(db, company_id, bas_run_id, review_note_id)
    if review_note.created_by_user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Generated BAS warnings cannot be removed")
    db.delete(review_note)
    db.flush()
    bas_run.warning_count = len(
        list(db.scalars(select(BasReviewNote.id).where(BasReviewNote.bas_run_id == bas_run_id)).all())
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/runs/{bas_run_id}/submit", response_model=BasRunRead)
def submit_bas_run(
    company_id: UUID,
    bas_run_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasRun:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    bas_run.status = BasRunStatus.REVIEW
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.BAS_RUN,
        entity_id=bas_run.id,
        action_type=ApprovalActionType.SUBMITTED_FOR_REVIEW,
        prepared_by_user_id=current_user.id,
        note=payload.note,
    )
    db.commit()
    db.refresh(bas_run)
    return bas_run


@router.post("/runs/{bas_run_id}/approve", response_model=BasRunRead)
def approve_bas_run(
    company_id: UUID,
    bas_run_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasRun:
    require_company_permission(company_id, "can_approve", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    try:
        check_self_approval_block(db, bas_run=bas_run, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    bas_run.status = BasRunStatus.APPROVED
    bas_run.approved_by_user_id = current_user.id
    bas_run.approved_at = date.today()
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.BAS_RUN,
        entity_id=bas_run.id,
        action_type=ApprovalActionType.APPROVED,
        approved_by_user_id=current_user.id,
        note=payload.note,
    )
    try:
        maybe_lock_periods_for_policy(
            db, bas_run=bas_run, acting_user_id=current_user.id, on_export=False
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(bas_run)
    return bas_run


@router.get("/runs/{bas_run_id}/approval-actions", response_model=list[ApprovalActionRead])
def bas_approval_actions(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApprovalAction]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_bas_run_or_404(db, company_id, bas_run_id)
    return list(
        db.scalars(
            select(ApprovalAction)
            .where(ApprovalAction.entity_id == str(bas_run_id))
            .order_by(ApprovalAction.created_at.asc())
        ).all()
    )


@router.get("/runs/{bas_run_id}/exports", response_model=list[BasExportRead])
def list_bas_exports(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BasExport]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_bas_run_or_404(db, company_id, bas_run_id)
    return list(db.scalars(select(BasExport).where(BasExport.bas_run_id == bas_run_id)).all())


@router.post("/runs/{bas_run_id}/exports/csv", response_model=BasExportRead, status_code=201)
def export_bas_csv(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasExport:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    if bas_run.status not in {BasRunStatus.APPROVED, BasRunStatus.EXPORTED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="BAS run must be approved before export")
    detail = _bas_run_detail(db, bas_run)
    export = create_export_document(
        db,
        company_id=company_id,
        bas_run_id=bas_run.id,
        exported_by_user_id=current_user.id,
        filename=f"bas-{bas_run.id}.csv",
        media_type="text/csv",
        content=build_bas_csv(bas_run, detail.line_results, detail.review_notes),
        export_format=BasExportFormat.CSV,
    )
    bas_run.status = BasRunStatus.EXPORTED
    try:
        maybe_lock_periods_for_policy(
            db, bas_run=bas_run, acting_user_id=current_user.id, on_export=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(export)
    return export


@router.post("/runs/{bas_run_id}/exports/pdf", response_model=BasExportRead, status_code=201)
def export_bas_pdf(
    company_id: UUID,
    bas_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BasExport:
    require_company_permission(company_id, "can_prepare", db, current_user)
    bas_run = _load_bas_run_or_404(db, company_id, bas_run_id)
    if bas_run.status not in {BasRunStatus.APPROVED, BasRunStatus.EXPORTED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="BAS run must be approved before export")
    detail = _bas_run_detail(db, bas_run)
    export = create_export_document(
        db,
        company_id=company_id,
        bas_run_id=bas_run.id,
        exported_by_user_id=current_user.id,
        filename=f"bas-{bas_run.id}.pdf",
        media_type="application/pdf",
        content=build_bas_pdf(bas_run, detail.line_results, detail.review_notes),
        export_format=BasExportFormat.PDF,
    )
    bas_run.status = BasRunStatus.EXPORTED
    try:
        maybe_lock_periods_for_policy(
            db, bas_run=bas_run, acting_user_id=current_user.id, on_export=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(export)
    return export
