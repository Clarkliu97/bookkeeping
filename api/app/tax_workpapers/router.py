from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.db.models.audit import ApprovalAction
from app.db.models.auth import User
from app.db.models.enums import TaxWorkpaperExceptionStatus, TaxWorkpaperExportFormat, TaxWorkpaperStatus
from app.db.models.tax_workpapers import (
    TaxAdjustment,
    TaxWorkpaperExceptionItem,
    TaxWorkpaperExport,
    TaxWorkpaperNote,
    TaxWorkpaperPack,
)
from app.schemas.common import (
    ApprovalActionRead,
    TaxAdjustmentRead,
    TaxWorkpaperExceptionItemRead,
    TaxWorkpaperExportRead,
    TaxWorkpaperNoteRead,
    TaxWorkpaperPackDetailRead,
    TaxWorkpaperPackRead,
)
from app.schemas.requests import (
    PeriodActionRequest,
    TaxWorkpaperAdjustmentCreate,
    TaxWorkpaperAdjustmentUpdate,
    TaxWorkpaperExceptionCreate,
    TaxWorkpaperExceptionUpdate,
    TaxWorkpaperExceptionResolveRequest,
    TaxWorkpaperNoteCreate,
    TaxWorkpaperNoteUpdate,
    TaxWorkpaperPackCreate,
    TaxWorkpaperPackUpdate,
)
from app.tax_workpapers.service import (
    add_exception_item,
    add_tax_adjustment,
    add_tax_note,
    approve_tax_workpaper_pack,
    build_tax_workpaper_pack_detail,
    build_tax_workpaper_pdf,
    create_tax_workpaper_export,
    create_tax_workpaper_pack,
    refresh_tax_workpaper_pack,
    resolve_exception_item,
    submit_tax_workpaper_pack,
)


router = APIRouter(prefix="/companies/{company_id}/tax-workpapers", tags=["tax_workpapers"])


def _load_pack_or_404(db: Session, company_id: UUID, pack_id: UUID) -> TaxWorkpaperPack:
    pack = db.get(TaxWorkpaperPack, pack_id)
    if pack is None or pack.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax workpaper pack not found")
    return pack


def _load_exception_or_404(
    db: Session,
    company_id: UUID,
    pack_id: UUID,
    exception_id: UUID,
) -> TaxWorkpaperExceptionItem:
    exception_item = db.get(TaxWorkpaperExceptionItem, exception_id)
    if exception_item is None or exception_item.company_id != company_id or exception_item.tax_workpaper_pack_id != pack_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax workpaper exception not found")
    return exception_item


def _load_adjustment_or_404(db: Session, company_id: UUID, pack_id: UUID, adjustment_id: UUID) -> TaxAdjustment:
    adjustment = db.get(TaxAdjustment, adjustment_id)
    if adjustment is None or adjustment.company_id != company_id or adjustment.tax_workpaper_pack_id != pack_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax adjustment not found")
    return adjustment


def _load_note_or_404(db: Session, company_id: UUID, pack_id: UUID, note_id: UUID) -> TaxWorkpaperNote:
    note = db.get(TaxWorkpaperNote, note_id)
    if note is None or note.company_id != company_id or note.tax_workpaper_pack_id != pack_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax workpaper note not found")
    return note


def _ensure_pack_refreshable(db: Session, pack: TaxWorkpaperPack) -> None:
    if pack.status != TaxWorkpaperStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft tax workpaper packs can be rebuilt")
    dependent_queries = (
        select(TaxAdjustment.id).where(TaxAdjustment.tax_workpaper_pack_id == pack.id).limit(1),
        select(TaxWorkpaperNote.id).where(TaxWorkpaperNote.tax_workpaper_pack_id == pack.id).limit(1),
        select(TaxWorkpaperExceptionItem.id).where(TaxWorkpaperExceptionItem.tax_workpaper_pack_id == pack.id).limit(1),
        select(TaxWorkpaperExport.id).where(TaxWorkpaperExport.tax_workpaper_pack_id == pack.id).limit(1),
    )
    if any(db.scalar(query) is not None for query in dependent_queries):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tax workpaper packs with dependent records cannot be rebuilt",
        )


@router.get("/packs", response_model=list[TaxWorkpaperPackRead])
def list_packs(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxWorkpaperPack]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(TaxWorkpaperPack)
            .where(TaxWorkpaperPack.company_id == company_id)
            .order_by(TaxWorkpaperPack.created_at.desc())
        ).all()
    )


@router.post("/packs", response_model=TaxWorkpaperPackDetailRead, status_code=201)
def generate_pack(
    company_id: UUID,
    payload: TaxWorkpaperPackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperPackDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    try:
        pack = create_tax_workpaper_pack(db, company_id=company_id, payload=payload, generated_by_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(pack)
    return build_tax_workpaper_pack_detail(db, pack)


@router.put("/packs/{pack_id}", response_model=TaxWorkpaperPackDetailRead)
def update_pack(
    company_id: UUID,
    pack_id: UUID,
    payload: TaxWorkpaperPackUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperPackDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    _ensure_pack_refreshable(db, pack)
    try:
        refresh_tax_workpaper_pack(db, pack=pack, payload=payload, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(pack)
    return build_tax_workpaper_pack_detail(db, pack)


@router.delete("/packs/{pack_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pack(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status != TaxWorkpaperStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft tax workpaper packs can be deleted")
    db.delete(pack)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/packs/{pack_id}", response_model=TaxWorkpaperPackDetailRead)
def get_pack(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperPackDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    return build_tax_workpaper_pack_detail(db, pack)


@router.get("/packs/{pack_id}/adjustments", response_model=list[TaxAdjustmentRead])
def list_adjustments(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxAdjustment]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_pack_or_404(db, company_id, pack_id)
    return list(
        db.scalars(
            select(TaxAdjustment)
            .where(TaxAdjustment.tax_workpaper_pack_id == pack_id)
            .order_by(TaxAdjustment.created_at.asc())
        ).all()
    )


@router.post("/packs/{pack_id}/adjustments", response_model=TaxWorkpaperPackDetailRead, status_code=201)
def create_adjustment(
    company_id: UUID,
    pack_id: UUID,
    payload: TaxWorkpaperAdjustmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperPackDetailRead:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    try:
        detail = add_tax_adjustment(db, pack=pack, payload=payload, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return detail


@router.put("/packs/{pack_id}/adjustments/{adjustment_id}", response_model=TaxWorkpaperPackDetailRead)
def update_adjustment(
    company_id: UUID,
    pack_id: UUID,
    adjustment_id: UUID,
    payload: TaxWorkpaperAdjustmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperPackDetailRead:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status not in {TaxWorkpaperStatus.DRAFT, TaxWorkpaperStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved tax workpaper packs cannot be changed")
    adjustment = _load_adjustment_or_404(db, company_id, pack_id, adjustment_id)
    adjustment.label = payload.label
    adjustment.amount = payload.amount
    adjustment.note = payload.note
    db.commit()
    return build_tax_workpaper_pack_detail(db, pack)


@router.delete("/packs/{pack_id}/adjustments/{adjustment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_adjustment(
    company_id: UUID,
    pack_id: UUID,
    adjustment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status not in {TaxWorkpaperStatus.DRAFT, TaxWorkpaperStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved tax workpaper packs cannot be changed")
    adjustment = _load_adjustment_or_404(db, company_id, pack_id, adjustment_id)
    db.delete(adjustment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/packs/{pack_id}/notes", response_model=list[TaxWorkpaperNoteRead])
def list_notes(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxWorkpaperNote]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_pack_or_404(db, company_id, pack_id)
    return list(
        db.scalars(
            select(TaxWorkpaperNote)
            .where(TaxWorkpaperNote.tax_workpaper_pack_id == pack_id)
            .order_by(TaxWorkpaperNote.created_at.asc())
        ).all()
    )


@router.post("/packs/{pack_id}/notes", response_model=TaxWorkpaperNoteRead, status_code=201)
def create_note(
    company_id: UUID,
    pack_id: UUID,
    payload: TaxWorkpaperNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperNote:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    try:
        note = add_tax_note(db, pack=pack, payload=payload, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(note)
    return note


@router.put("/packs/{pack_id}/notes/{note_id}", response_model=TaxWorkpaperNoteRead)
def update_note(
    company_id: UUID,
    pack_id: UUID,
    note_id: UUID,
    payload: TaxWorkpaperNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperNote:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status not in {TaxWorkpaperStatus.DRAFT, TaxWorkpaperStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved tax workpaper packs cannot be changed")
    note = _load_note_or_404(db, company_id, pack_id, note_id)
    note.note_type = payload.note_type
    note.message = payload.message
    db.commit()
    db.refresh(note)
    return note


@router.delete("/packs/{pack_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    company_id: UUID,
    pack_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status not in {TaxWorkpaperStatus.DRAFT, TaxWorkpaperStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved tax workpaper packs cannot be changed")
    note = _load_note_or_404(db, company_id, pack_id, note_id)
    db.delete(note)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/packs/{pack_id}/exceptions", response_model=list[TaxWorkpaperExceptionItemRead])
def list_exceptions(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxWorkpaperExceptionItem]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_pack_or_404(db, company_id, pack_id)
    return list(
        db.scalars(
            select(TaxWorkpaperExceptionItem)
            .where(TaxWorkpaperExceptionItem.tax_workpaper_pack_id == pack_id)
            .order_by(TaxWorkpaperExceptionItem.created_at.asc())
        ).all()
    )


@router.post("/packs/{pack_id}/exceptions", response_model=TaxWorkpaperExceptionItemRead, status_code=201)
def create_exception(
    company_id: UUID,
    pack_id: UUID,
    payload: TaxWorkpaperExceptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperExceptionItem:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    try:
        exception_item = add_exception_item(db, pack=pack, payload=payload, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(exception_item)
    return exception_item


@router.put("/packs/{pack_id}/exceptions/{exception_id}", response_model=TaxWorkpaperExceptionItemRead)
def update_exception(
    company_id: UUID,
    pack_id: UUID,
    exception_id: UUID,
    payload: TaxWorkpaperExceptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperExceptionItem:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status not in {TaxWorkpaperStatus.DRAFT, TaxWorkpaperStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved tax workpaper packs cannot be changed")
    exception_item = _load_exception_or_404(db, company_id, pack_id, exception_id)
    if exception_item.status != TaxWorkpaperExceptionStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resolved exceptions cannot be edited")
    exception_item.severity = payload.severity
    exception_item.message = payload.message
    db.commit()
    db.refresh(exception_item)
    return exception_item


@router.delete("/packs/{pack_id}/exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exception(
    company_id: UUID,
    pack_id: UUID,
    exception_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status not in {TaxWorkpaperStatus.DRAFT, TaxWorkpaperStatus.REVIEW}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved tax workpaper packs cannot be changed")
    exception_item = _load_exception_or_404(db, company_id, pack_id, exception_id)
    db.delete(exception_item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/packs/{pack_id}/exceptions/{exception_id}/resolve", response_model=TaxWorkpaperExceptionItemRead)
def resolve_exception(
    company_id: UUID,
    pack_id: UUID,
    exception_id: UUID,
    payload: TaxWorkpaperExceptionResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperExceptionItem:
    require_company_permission(company_id, "can_review", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    exception_item = _load_exception_or_404(db, company_id, pack_id, exception_id)
    try:
        resolve_exception_item(
            db,
            pack=pack,
            exception_item=exception_item,
            resolution_note=payload.note,
            acting_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(exception_item)
    return exception_item


@router.post("/packs/{pack_id}/submit", response_model=TaxWorkpaperPackRead)
def submit_pack(
    company_id: UUID,
    pack_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperPack:
    require_company_permission(company_id, "can_prepare", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    try:
        submit_tax_workpaper_pack(db, pack=pack, acting_user_id=current_user.id, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(pack)
    return pack


@router.post("/packs/{pack_id}/approve", response_model=TaxWorkpaperPackRead)
def approve_pack(
    company_id: UUID,
    pack_id: UUID,
    payload: PeriodActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperPack:
    require_company_permission(company_id, "can_approve", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    try:
        approve_tax_workpaper_pack(db, pack=pack, acting_user_id=current_user.id, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(pack)
    return pack


@router.get("/packs/{pack_id}/approval-actions", response_model=list[ApprovalActionRead])
def list_approval_actions(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApprovalAction]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_pack_or_404(db, company_id, pack_id)
    return list(
        db.scalars(
            select(ApprovalAction)
            .where(ApprovalAction.entity_id == str(pack_id))
            .order_by(ApprovalAction.created_at.asc())
        ).all()
    )


@router.get("/packs/{pack_id}/exports", response_model=list[TaxWorkpaperExportRead])
def list_exports(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxWorkpaperExport]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_pack_or_404(db, company_id, pack_id)
    return list(
        db.scalars(
            select(TaxWorkpaperExport)
            .where(TaxWorkpaperExport.tax_workpaper_pack_id == pack_id)
            .order_by(TaxWorkpaperExport.created_at.asc())
        ).all()
    )


@router.post("/packs/{pack_id}/exports/pdf", response_model=TaxWorkpaperExportRead, status_code=201)
def export_pdf(
    company_id: UUID,
    pack_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxWorkpaperExport:
    require_company_permission(company_id, "can_prepare", db, current_user)
    pack = _load_pack_or_404(db, company_id, pack_id)
    if pack.status not in {TaxWorkpaperStatus.APPROVED, TaxWorkpaperStatus.EXPORTED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tax workpaper pack must be approved before export")
    detail = build_tax_workpaper_pack_detail(db, pack)
    export = create_tax_workpaper_export(
        db,
        company_id=company_id,
        pack_id=pack.id,
        exported_by_user_id=current_user.id,
        filename=f"tax-workpaper-pack-{pack.id}.pdf",
        media_type="application/pdf",
        content=build_tax_workpaper_pdf(pack, detail),
        export_format=TaxWorkpaperExportFormat.PDF,
    )
    pack.status = TaxWorkpaperStatus.EXPORTED
    db.commit()
    db.refresh(export)
    return export