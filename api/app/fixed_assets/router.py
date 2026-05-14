from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.db.models.auth import User
from app.db.models.enums import DepreciationRunStatus, EntityType, FixedAssetStatus
from app.db.models.fixed_assets import DepreciationRun, DepreciationRunLine, FixedAsset, FixedAssetStatusHistory
from app.fixed_assets.service import (
    build_depreciation_run_csv,
    build_depreciation_run_detail,
    build_fixed_asset_detail,
    build_fixed_asset_register,
    create_depreciation_run,
    create_fixed_asset,
    dispose_fixed_asset,
    post_depreciation_run,
    rebuild_depreciation_run,
    update_fixed_asset,
)
from app.schemas.common import DepreciationRunDetailRead, DepreciationRunRead, FixedAssetDetailRead, FixedAssetRead, FixedAssetRegisterRead
from app.schemas.requests import DepreciationRunCreate, DepreciationRunUpdate, FixedAssetCreate, FixedAssetDisposeRequest, FixedAssetUpdate


router = APIRouter(prefix="/companies/{company_id}/fixed-assets", tags=["fixed_assets"])


def _csv_response(filename: str, content: bytes) -> Response:
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _load_asset_or_404(db: Session, company_id: UUID, asset_id: UUID) -> FixedAsset:
    asset = db.get(FixedAsset, asset_id)
    if asset is None or asset.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fixed asset not found")
    return asset


def _load_run_or_404(db: Session, company_id: UUID, depreciation_run_id: UUID) -> DepreciationRun:
    depreciation_run = db.get(DepreciationRun, depreciation_run_id)
    if depreciation_run is None or depreciation_run.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depreciation run not found")
    return depreciation_run


def _asset_detail(db: Session, asset: FixedAsset, as_of_date: date | None = None) -> FixedAssetDetailRead:
    effective_date = as_of_date or date.today()
    history = list(
        db.scalars(
            select(FixedAssetStatusHistory)
            .where(FixedAssetStatusHistory.fixed_asset_id == asset.id)
            .order_by(FixedAssetStatusHistory.effective_date.asc(), FixedAssetStatusHistory.created_at.asc())
        ).all()
    )
    return build_fixed_asset_detail(asset, as_of_date=effective_date, history=history)


@router.get("", response_model=FixedAssetRegisterRead)
def list_fixed_assets(
    company_id: UUID,
    as_of_date: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FixedAssetRegisterRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return build_fixed_asset_register(db, company_id=company_id, as_of_date=as_of_date or date.today())


@router.post("", response_model=FixedAssetRead, status_code=201)
def create_asset(
    company_id: UUID,
    payload: FixedAssetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FixedAsset:
    require_company_permission(company_id, "can_prepare", db, current_user)
    try:
        asset = create_fixed_asset(db, company_id=company_id, payload=payload, created_by_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/depreciation-runs", response_model=list[DepreciationRunRead])
def list_depreciation_runs(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DepreciationRun]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(DepreciationRun)
            .where(DepreciationRun.company_id == company_id)
            .order_by(DepreciationRun.end_date.desc(), DepreciationRun.created_at.desc())
        ).all()
    )


@router.post("/depreciation-runs", response_model=DepreciationRunDetailRead, status_code=201)
def generate_depreciation_run(
    company_id: UUID,
    payload: DepreciationRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DepreciationRunDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    try:
        depreciation_run = create_depreciation_run(
            db,
            company_id=company_id,
            payload=payload,
            generated_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(depreciation_run)
    return build_depreciation_run_detail(db, depreciation_run)


@router.get("/depreciation-runs/{depreciation_run_id}", response_model=DepreciationRunDetailRead)
def get_depreciation_run(
    company_id: UUID,
    depreciation_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DepreciationRunDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    depreciation_run = _load_run_or_404(db, company_id, depreciation_run_id)
    return build_depreciation_run_detail(db, depreciation_run)


@router.put("/depreciation-runs/{depreciation_run_id}", response_model=DepreciationRunDetailRead)
def update_depreciation_run(
    company_id: UUID,
    depreciation_run_id: UUID,
    payload: DepreciationRunUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DepreciationRunDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    depreciation_run = _load_run_or_404(db, company_id, depreciation_run_id)
    try:
        rebuild_depreciation_run(db, depreciation_run=depreciation_run, payload=payload, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(depreciation_run)
    return build_depreciation_run_detail(db, depreciation_run)


@router.delete("/depreciation-runs/{depreciation_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_depreciation_run(
    company_id: UUID,
    depreciation_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    depreciation_run = _load_run_or_404(db, company_id, depreciation_run_id)
    if depreciation_run.status != DepreciationRunStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft depreciation runs can be deleted")
    log_audit_event(
        db,
        action="depreciation_run.deleted",
        summary=f"Deleted depreciation run {depreciation_run.id}",
        entity_type=EntityType.DEPRECIATION_RUN.value,
        entity_id=depreciation_run.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.delete(depreciation_run)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/depreciation-runs/{depreciation_run_id}/post", response_model=DepreciationRunDetailRead)
def post_run(
    company_id: UUID,
    depreciation_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DepreciationRunDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    depreciation_run = _load_run_or_404(db, company_id, depreciation_run_id)
    try:
        post_depreciation_run(db, depreciation_run=depreciation_run, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(depreciation_run)
    return build_depreciation_run_detail(db, depreciation_run)


@router.get("/depreciation-runs/{depreciation_run_id}/export")
def export_depreciation_run(
    company_id: UUID,
    depreciation_run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    depreciation_run = _load_run_or_404(db, company_id, depreciation_run_id)
    content = build_depreciation_run_csv(db, depreciation_run)
    return _csv_response(
        filename=f"depreciation-run-{depreciation_run.start_date.isoformat()}-{depreciation_run.end_date.isoformat()}.csv",
        content=content,
    )


@router.get("/{asset_id}", response_model=FixedAssetDetailRead)
def get_fixed_asset(
    company_id: UUID,
    asset_id: UUID,
    as_of_date: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FixedAssetDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    asset = _load_asset_or_404(db, company_id, asset_id)
    return _asset_detail(db, asset, as_of_date)


@router.put("/{asset_id}", response_model=FixedAssetRead)
def update_asset(
    company_id: UUID,
    asset_id: UUID,
    payload: FixedAssetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FixedAsset:
    require_company_permission(company_id, "can_prepare", db, current_user)
    asset = _load_asset_or_404(db, company_id, asset_id)
    if asset.status != FixedAssetStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only active fixed assets can be updated")
    if db.scalar(select(DepreciationRunLine.id).where(DepreciationRunLine.fixed_asset_id == asset.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fixed assets with depreciation history cannot be updated")
    try:
        update_fixed_asset(db, asset=asset, payload=payload, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    company_id: UUID,
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    asset = _load_asset_or_404(db, company_id, asset_id)
    if asset.status != FixedAssetStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only active fixed assets can be deleted")
    if db.scalar(select(DepreciationRunLine.id).where(DepreciationRunLine.fixed_asset_id == asset.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fixed assets with depreciation history cannot be deleted")
    log_audit_event(
        db,
        action="fixed_asset.deleted",
        summary=f"Deleted fixed asset {asset.asset_code}",
        entity_type=EntityType.FIXED_ASSET.value,
        entity_id=asset.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.delete(asset)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{asset_id}/dispose", response_model=FixedAssetDetailRead)
def dispose_asset(
    company_id: UUID,
    asset_id: UUID,
    payload: FixedAssetDisposeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FixedAssetDetailRead:
    require_company_permission(company_id, "can_review", db, current_user)
    asset = _load_asset_or_404(db, company_id, asset_id)
    try:
        dispose_fixed_asset(db, asset=asset, payload=payload, acting_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(asset)
    return _asset_detail(db, asset, payload.disposal_date)