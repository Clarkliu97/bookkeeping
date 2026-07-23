from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.db.models.accounting import Account
from app.db.models.auth import User
from app.db.models.documents import Document, DocumentLink
from app.db.models.employment import (
    EmploymentCompensationProfile,
    EmploymentEngagement,
    EmploymentIssuedAsset,
    EmploymentLeaveSnapshot,
    EmploymentReimbursementItem,
    EmploymentWorker,
    EmploymentWorkRightsRecord,
)
from app.db.models.enums import (
    DocumentLinkEntityType,
    EmploymentAssetStatus,
    EmploymentEngagementType,
    EmploymentStatus,
    EntityType,
)
from app.schemas.common import (
    EmploymentCompensationRead,
    EmploymentContractorReviewLineRead,
    EmploymentContractorReviewReportRead,
    EmploymentDashboardRead,
    EmploymentEngagementRead,
    EmploymentHeadcountLineRead,
    EmploymentHeadcountReportRead,
    EmploymentIssuedAssetRead,
    EmploymentLeaveLiabilityLineRead,
    EmploymentLeaveLiabilityReportRead,
    EmploymentLeaveSnapshotRead,
    EmploymentLinkedDocumentRead,
    EmploymentQueueItemRead,
    EmploymentReimbursementRead,
    EmploymentWorkerDetailRead,
    EmploymentWorkerRead,
    EmploymentWorkRightsRead,
    EmploymentWorkRightsReportLineRead,
    EmploymentWorkRightsReportRead,
)
from app.schemas.requests import (
    EmploymentCompensationUpdate,
    EmploymentEngagementCreate,
    EmploymentEngagementUpdate,
    EmploymentIssuedAssetCreate,
    EmploymentIssuedAssetUpdate,
    EmploymentLeaveSnapshotCreate,
    EmploymentLeaveSnapshotUpdate,
    EmploymentReimbursementCreate,
    EmploymentReimbursementUpdate,
    EmploymentWorkerCreate,
    EmploymentWorkerUpdate,
    EmploymentWorkRightsCreate,
    EmploymentWorkRightsUpdate,
)


router = APIRouter(prefix="/companies/{company_id}/employment", tags=["employment"])

ACTIVE_EMPLOYMENT_STATUSES = {
    EmploymentStatus.ACTIVE,
    EmploymentStatus.ACTIVE_WITH_RESTRICTIONS,
    EmploymentStatus.ON_PAID_LEAVE,
    EmploymentStatus.ON_UNPAID_LEAVE,
    EmploymentStatus.ON_NOTICE,
}
CONTRACTOR_ENGAGEMENT_TYPES = {
    EmploymentEngagementType.INDIVIDUAL_CONTRACTOR,
    EmploymentEngagementType.CONTRACTOR_ENTITY,
    EmploymentEngagementType.LABOUR_HIRE,
}


def _csv_response(filename: str, content: str) -> Response:
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_text(headers: list[str], rows: list[list[object | None]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return output.getvalue()


def _load_worker_or_404(db: Session, company_id: UUID, worker_id: UUID) -> EmploymentWorker:
    worker = db.get(EmploymentWorker, worker_id)
    if worker is None or worker.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment worker not found")
    return worker


def _load_engagement_or_404(db: Session, company_id: UUID, engagement_id: UUID) -> EmploymentEngagement:
    engagement = db.get(EmploymentEngagement, engagement_id)
    if engagement is None or engagement.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment engagement not found")
    return engagement


def _load_worker_engagement_or_400(
    db: Session,
    company_id: UUID,
    worker_id: UUID,
    engagement_id: UUID,
) -> EmploymentEngagement:
    engagement = _load_engagement_or_404(db, company_id, engagement_id)
    if engagement.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Engagement does not belong to the selected worker",
        )
    return engagement


def _validate_compensation_accounts(
    db: Session,
    company_id: UUID,
    *,
    expense_account_id: UUID | None,
    liability_account_id: UUID | None,
) -> None:
    for label, account_id in (
        ("Expense account", expense_account_id),
        ("Liability account", liability_account_id),
    ):
        if account_id is None:
            continue
        account = db.get(Account, account_id)
        if account is None or account.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} must belong to the selected company",
            )


def _load_work_rights_or_404(db: Session, company_id: UUID, record_id: UUID) -> EmploymentWorkRightsRecord:
    record = db.get(EmploymentWorkRightsRecord, record_id)
    if record is None or record.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work-rights record not found")
    return record


def _load_compensation_or_404(db: Session, company_id: UUID, compensation_id: UUID) -> EmploymentCompensationProfile:
    profile = db.get(EmploymentCompensationProfile, compensation_id)
    if profile is None or profile.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compensation profile not found")
    return profile


def _load_leave_snapshot_or_404(db: Session, company_id: UUID, snapshot_id: UUID) -> EmploymentLeaveSnapshot:
    snapshot = db.get(EmploymentLeaveSnapshot, snapshot_id)
    if snapshot is None or snapshot.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave snapshot not found")
    return snapshot


def _load_reimbursement_or_404(db: Session, company_id: UUID, reimbursement_id: UUID) -> EmploymentReimbursementItem:
    item = db.get(EmploymentReimbursementItem, reimbursement_id)
    if item is None or item.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reimbursement support item not found")
    return item


def _load_issued_asset_or_404(db: Session, company_id: UUID, asset_id: UUID) -> EmploymentIssuedAsset:
    item = db.get(EmploymentIssuedAsset, asset_id)
    if item is None or item.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issued asset record not found")
    return item


def _linked_documents_for_worker(db: Session, company_id: UUID, worker_id: UUID) -> list[EmploymentLinkedDocumentRead]:
    rows = db.execute(
        select(DocumentLink, Document)
        .join(Document, Document.id == DocumentLink.document_id)
        .where(
            DocumentLink.company_id == company_id,
            DocumentLink.entity_type == DocumentLinkEntityType.EMPLOYMENT_WORKER,
            DocumentLink.entity_id == str(worker_id),
        )
        .order_by(DocumentLink.created_at.desc())
    ).all()
    return [
        EmploymentLinkedDocumentRead(
            link_id=link.id,
            document_id=document.id,
            original_filename=document.original_filename,
            media_type=document.media_type,
            byte_size=document.byte_size,
            note=link.note,
            linked_at=link.created_at,
        )
        for link, document in rows
    ]


def _build_worker_detail(db: Session, worker: EmploymentWorker) -> EmploymentWorkerDetailRead:
    engagements = list(
        db.scalars(
            select(EmploymentEngagement)
            .where(EmploymentEngagement.worker_id == worker.id)
            .order_by(EmploymentEngagement.start_date.desc(), EmploymentEngagement.created_at.desc())
        ).all()
    )
    engagement_ids = [item.id for item in engagements]
    work_rights = list(
        db.scalars(
            select(EmploymentWorkRightsRecord)
            .where(EmploymentWorkRightsRecord.worker_id == worker.id)
            .order_by(EmploymentWorkRightsRecord.created_at.desc())
        ).all()
    )
    compensation_profiles = list(
        db.scalars(
            select(EmploymentCompensationProfile)
            .where(EmploymentCompensationProfile.engagement_id.in_(engagement_ids) if engagement_ids else False)
            .order_by(EmploymentCompensationProfile.created_at.desc())
        ).all()
    ) if engagement_ids else []
    leave_snapshots = list(
        db.scalars(
            select(EmploymentLeaveSnapshot)
            .where(EmploymentLeaveSnapshot.engagement_id.in_(engagement_ids) if engagement_ids else False)
            .order_by(EmploymentLeaveSnapshot.snapshot_date.desc(), EmploymentLeaveSnapshot.created_at.desc())
        ).all()
    ) if engagement_ids else []
    reimbursements = list(
        db.scalars(
            select(EmploymentReimbursementItem)
            .where(EmploymentReimbursementItem.worker_id == worker.id)
            .order_by(EmploymentReimbursementItem.reimbursement_date.desc(), EmploymentReimbursementItem.created_at.desc())
        ).all()
    )
    issued_assets = list(
        db.scalars(
            select(EmploymentIssuedAsset)
            .where(EmploymentIssuedAsset.worker_id == worker.id)
            .order_by(EmploymentIssuedAsset.assigned_on.desc(), EmploymentIssuedAsset.created_at.desc())
        ).all()
    )

    return EmploymentWorkerDetailRead(
        **EmploymentWorkerRead.model_validate(worker).model_dump(mode="python"),
        engagements=[EmploymentEngagementRead.model_validate(item) for item in engagements],
        work_rights_records=[EmploymentWorkRightsRead.model_validate(item) for item in work_rights],
        compensation_profiles=[EmploymentCompensationRead.model_validate(item) for item in compensation_profiles],
        leave_snapshots=[EmploymentLeaveSnapshotRead.model_validate(item) for item in leave_snapshots],
        reimbursements=[EmploymentReimbursementRead.model_validate(item) for item in reimbursements],
        issued_assets=[EmploymentIssuedAssetRead.model_validate(item) for item in issued_assets],
        linked_documents=_linked_documents_for_worker(db, worker.company_id, worker.id),
    )


def _queue_item(worker: EmploymentWorker, title: str, status: str, due_date: date | None, detail: str | None, engagement_id: UUID | None = None) -> EmploymentQueueItemRead:
    return EmploymentQueueItemRead(
        worker_id=worker.id,
        worker_name=worker.display_name,
        engagement_id=engagement_id,
        title=title,
        status=status,
        due_date=due_date,
        detail=detail,
    )


def _build_dashboard(db: Session, company_id: UUID) -> EmploymentDashboardRead:
    today = date.today()
    warning_date = today + timedelta(days=30)
    workers = list(db.scalars(select(EmploymentWorker).where(EmploymentWorker.company_id == company_id).order_by(EmploymentWorker.display_name.asc())).all())
    worker_by_id = {worker.id: worker for worker in workers}
    engagements = list(db.scalars(select(EmploymentEngagement).where(EmploymentEngagement.company_id == company_id)).all())
    work_rights_records = list(db.scalars(select(EmploymentWorkRightsRecord).where(EmploymentWorkRightsRecord.company_id == company_id)).all())
    issued_assets = list(db.scalars(select(EmploymentIssuedAsset).where(EmploymentIssuedAsset.company_id == company_id)).all())
    linked_worker_ids = {
        UUID(link.entity_id)
        for link in db.scalars(
            select(DocumentLink)
            .where(
                DocumentLink.company_id == company_id,
                DocumentLink.entity_type == DocumentLinkEntityType.EMPLOYMENT_WORKER,
            )
        ).all()
    }

    onboarding_items = [
        _queue_item(
            worker_by_id[engagement.worker_id],
            title=engagement.role_name,
            status=engagement.status.value,
            due_date=engagement.start_date,
            detail=engagement.note or engagement.status_reason,
            engagement_id=engagement.id,
        )
        for engagement in engagements
        if engagement.worker_id in worker_by_id and engagement.status in {EmploymentStatus.DRAFT, EmploymentStatus.ONBOARDING}
    ]

    work_rights_due_items: list[EmploymentQueueItemRead] = []
    for record in work_rights_records:
        worker = worker_by_id.get(record.worker_id)
        if worker is None:
            continue
        due_date = record.next_review_due_at or record.visa_expiry_date
        if record.review_status.value in {"pending_evidence", "pending_review", "expired", "blocked_pending_review"} or (due_date is not None and due_date <= warning_date):
            work_rights_due_items.append(
                _queue_item(
                    worker,
                    title=record.visa_label or record.work_rights_basis.value.replace("_", " "),
                    status=record.review_status.value,
                    due_date=due_date,
                    detail=record.hours_restriction_summary or record.work_condition_summary,
                    engagement_id=record.engagement_id,
                )
            )

    open_assets_by_worker: dict[UUID, list[EmploymentIssuedAsset]] = {}
    for item in issued_assets:
        if item.status != EmploymentAssetStatus.RETURNED:
            open_assets_by_worker.setdefault(item.worker_id, []).append(item)
    finalization_items = []
    for engagement in engagements:
        if engagement.status != EmploymentStatus.ENDED:
            continue
        worker = worker_by_id.get(engagement.worker_id)
        if worker is None:
            continue
        assets = open_assets_by_worker.get(worker.id, [])
        if assets:
            finalization_items.append(
                _queue_item(
                    worker,
                    title=engagement.role_name,
                    status=engagement.status.value,
                    due_date=engagement.actual_end_date,
                    detail=f"{len(assets)} issued asset(s) still open",
                    engagement_id=engagement.id,
                )
            )

    return EmploymentDashboardRead(
        total_workers=len(workers),
        active_engagements=sum(1 for item in engagements if item.status in ACTIVE_EMPLOYMENT_STATUSES),
        onboarding_count=len(onboarding_items),
        expiring_work_rights_count=len(work_rights_due_items),
        missing_document_count=sum(1 for worker in workers if worker.is_active and worker.id not in linked_worker_ids),
        onboarding_items=onboarding_items[:10],
        work_rights_due_items=work_rights_due_items[:10],
        finalization_items=finalization_items[:10],
    )


def _build_headcount_report(db: Session, company_id: UUID) -> EmploymentHeadcountReportRead:
    workers = {item.id: item for item in db.scalars(select(EmploymentWorker).where(EmploymentWorker.company_id == company_id)).all()}
    engagements = list(
        db.scalars(
            select(EmploymentEngagement)
            .where(EmploymentEngagement.company_id == company_id)
            .order_by(EmploymentEngagement.start_date.desc(), EmploymentEngagement.created_at.desc())
        ).all()
    )
    rows = [
        EmploymentHeadcountLineRead(
            worker_id=worker.id,
            worker_name=worker.display_name,
            worker_kind=worker.worker_kind.value,
            engagement_id=engagement.id,
            engagement_type=engagement.engagement_type.value,
            status=engagement.status.value,
            department=engagement.department,
            role_name=engagement.role_name,
            start_date=engagement.start_date,
            expected_end_date=engagement.expected_end_date,
            actual_end_date=engagement.actual_end_date,
        )
        for engagement in engagements
        if (worker := workers.get(engagement.worker_id)) is not None
    ]
    return EmploymentHeadcountReportRead(
        generated_at=datetime.now(timezone.utc),
        total_workers=len(workers),
        active_engagements=sum(1 for item in engagements if item.status in ACTIVE_EMPLOYMENT_STATUSES),
        contractor_engagements=sum(1 for item in engagements if item.engagement_type in CONTRACTOR_ENGAGEMENT_TYPES),
        rows=rows,
    )


def _build_work_rights_report(db: Session, company_id: UUID) -> EmploymentWorkRightsReportRead:
    workers = {item.id: item for item in db.scalars(select(EmploymentWorker).where(EmploymentWorker.company_id == company_id)).all()}
    records = list(
        db.scalars(
            select(EmploymentWorkRightsRecord)
            .where(EmploymentWorkRightsRecord.company_id == company_id)
            .order_by(EmploymentWorkRightsRecord.next_review_due_at.asc(), EmploymentWorkRightsRecord.visa_expiry_date.asc())
        ).all()
    )
    return EmploymentWorkRightsReportRead(
        generated_at=datetime.now(timezone.utc),
        rows=[
            EmploymentWorkRightsReportLineRead(
                worker_id=worker.id,
                worker_name=worker.display_name,
                engagement_id=record.engagement_id,
                review_status=record.review_status.value,
                work_rights_basis=record.work_rights_basis.value,
                visa_label=record.visa_label,
                visa_expiry_date=record.visa_expiry_date,
                next_review_due_at=record.next_review_due_at,
                restriction_summary=record.hours_restriction_summary or record.work_condition_summary,
            )
            for record in records
            if (worker := workers.get(record.worker_id)) is not None
        ],
    )


def _build_leave_liability_report(db: Session, company_id: UUID) -> EmploymentLeaveLiabilityReportRead:
    workers = {item.id: item for item in db.scalars(select(EmploymentWorker).where(EmploymentWorker.company_id == company_id)).all()}
    engagements = {item.id: item for item in db.scalars(select(EmploymentEngagement).where(EmploymentEngagement.company_id == company_id)).all()}
    snapshots = list(
        db.scalars(
            select(EmploymentLeaveSnapshot)
            .where(EmploymentLeaveSnapshot.company_id == company_id)
            .order_by(EmploymentLeaveSnapshot.snapshot_date.desc(), EmploymentLeaveSnapshot.created_at.desc())
        ).all()
    )
    latest_by_engagement: dict[UUID, EmploymentLeaveSnapshot] = {}
    for snapshot in snapshots:
        latest_by_engagement.setdefault(snapshot.engagement_id, snapshot)
    rows = []
    for engagement_id, snapshot in latest_by_engagement.items():
        engagement = engagements.get(engagement_id)
        if engagement is None:
            continue
        worker = workers.get(engagement.worker_id)
        if worker is None:
            continue
        rows.append(
            EmploymentLeaveLiabilityLineRead(
                worker_id=worker.id,
                worker_name=worker.display_name,
                engagement_id=engagement.id,
                engagement_status=engagement.status.value,
                snapshot_date=snapshot.snapshot_date,
                annual_leave_hours=snapshot.annual_leave_hours,
                long_service_leave_hours=snapshot.long_service_leave_hours,
                leave_value_amount=snapshot.leave_value_amount,
                current_lsl_value_amount=snapshot.current_lsl_value_amount,
                non_current_lsl_value_amount=snapshot.non_current_lsl_value_amount,
            )
        )
    return EmploymentLeaveLiabilityReportRead(generated_at=datetime.now(timezone.utc), rows=rows)


def _build_contractor_review_report(db: Session, company_id: UUID) -> EmploymentContractorReviewReportRead:
    workers = {item.id: item for item in db.scalars(select(EmploymentWorker).where(EmploymentWorker.company_id == company_id)).all()}
    engagements = list(
        db.scalars(
            select(EmploymentEngagement)
            .where(EmploymentEngagement.company_id == company_id, EmploymentEngagement.engagement_type.in_(CONTRACTOR_ENGAGEMENT_TYPES))
            .order_by(EmploymentEngagement.start_date.desc(), EmploymentEngagement.created_at.desc())
        ).all()
    )
    compensation_by_engagement = {
        item.engagement_id: item
        for item in db.scalars(select(EmploymentCompensationProfile).where(EmploymentCompensationProfile.company_id == company_id)).all()
    }
    rows = []
    for engagement in engagements:
        worker = workers.get(engagement.worker_id)
        if worker is None:
            continue
        compensation = compensation_by_engagement.get(engagement.id)
        rows.append(
            EmploymentContractorReviewLineRead(
                worker_id=worker.id,
                worker_name=worker.display_name,
                engagement_id=engagement.id,
                engagement_type=engagement.engagement_type.value,
                status=engagement.status.value,
                remuneration_basis=compensation.remuneration_basis.value if compensation else None,
                abn_provided=compensation.abn_provided if compensation else None,
                gst_registered_known=compensation.gst_registered_known if compensation else None,
                payroll_tax_in_scope=compensation.payroll_tax_in_scope if compensation else None,
                note=compensation.note if compensation and compensation.note else engagement.note,
            )
        )
    return EmploymentContractorReviewReportRead(generated_at=datetime.now(timezone.utc), rows=rows)


@router.get("/dashboard", response_model=EmploymentDashboardRead)
def get_employment_dashboard(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentDashboardRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return _build_dashboard(db, company_id)


@router.get("/workers", response_model=list[EmploymentWorkerRead])
def list_workers(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmploymentWorker]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(EmploymentWorker)
            .where(EmploymentWorker.company_id == company_id)
            .order_by(EmploymentWorker.is_active.desc(), EmploymentWorker.display_name.asc())
        ).all()
    )


@router.post("/workers", response_model=EmploymentWorkerRead, status_code=201)
def create_worker(
    company_id: UUID,
    payload: EmploymentWorkerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentWorker:
    require_company_permission(company_id, "can_prepare", db, current_user)
    worker = EmploymentWorker(company_id=company_id, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(worker)
    db.flush()
    log_audit_event(
        db,
        action="employment.worker.created",
        summary=f"Created worker {worker.display_name}",
        entity_type=EntityType.EMPLOYMENT_WORKER.value,
        entity_id=worker.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        after_state=EmploymentWorkerRead.model_validate(worker).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(worker)
    return worker


@router.get("/workers/{worker_id}", response_model=EmploymentWorkerDetailRead)
def get_worker_detail(
    company_id: UUID,
    worker_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentWorkerDetailRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    worker = _load_worker_or_404(db, company_id, worker_id)
    return _build_worker_detail(db, worker)


@router.put("/workers/{worker_id}", response_model=EmploymentWorkerRead)
def update_worker(
    company_id: UUID,
    worker_id: UUID,
    payload: EmploymentWorkerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentWorker:
    require_company_permission(company_id, "can_prepare", db, current_user)
    worker = _load_worker_or_404(db, company_id, worker_id)
    before_state = EmploymentWorkerRead.model_validate(worker).model_dump(mode="json")
    for key, value in payload.model_dump().items():
        setattr(worker, key, value)
    log_audit_event(
        db,
        action="employment.worker.updated",
        summary=f"Updated worker {worker.display_name}",
        entity_type=EntityType.EMPLOYMENT_WORKER.value,
        entity_id=worker.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=EmploymentWorkerRead.model_validate(worker).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(worker)
    return worker


@router.post("/workers/{worker_id}/engagements", response_model=EmploymentEngagementRead, status_code=201)
def create_engagement(
    company_id: UUID,
    worker_id: UUID,
    payload: EmploymentEngagementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentEngagement:
    require_company_permission(company_id, "can_prepare", db, current_user)
    worker = _load_worker_or_404(db, company_id, worker_id)
    engagement = EmploymentEngagement(company_id=company_id, worker_id=worker.id, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    return engagement


@router.put("/engagements/{engagement_id}", response_model=EmploymentEngagementRead)
def update_engagement(
    company_id: UUID,
    engagement_id: UUID,
    payload: EmploymentEngagementUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentEngagement:
    require_company_permission(company_id, "can_prepare", db, current_user)
    engagement = _load_engagement_or_404(db, company_id, engagement_id)
    for key, value in payload.model_dump().items():
        setattr(engagement, key, value)
    db.commit()
    db.refresh(engagement)
    return engagement


@router.delete("/engagements/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_engagement(
    company_id: UUID,
    engagement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    engagement = _load_engagement_or_404(db, company_id, engagement_id)
    db.delete(engagement)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/workers/{worker_id}/work-rights", response_model=EmploymentWorkRightsRead, status_code=201)
def create_work_rights_record(
    company_id: UUID,
    worker_id: UUID,
    payload: EmploymentWorkRightsCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentWorkRightsRecord:
    require_company_permission(company_id, "can_prepare", db, current_user)
    worker = _load_worker_or_404(db, company_id, worker_id)
    if payload.engagement_id:
        _load_worker_engagement_or_400(db, company_id, worker.id, payload.engagement_id)
    payload_data = payload.model_dump()
    vevo_checked_at = payload_data.pop("vevo_checked_at")
    record = EmploymentWorkRightsRecord(
        company_id=company_id,
        worker_id=worker.id,
        created_by_user_id=current_user.id,
        vevo_checked_at=datetime.combine(vevo_checked_at, datetime.min.time(), tzinfo=timezone.utc) if vevo_checked_at else None,
        **payload_data,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/work-rights/{record_id}", response_model=EmploymentWorkRightsRead)
def update_work_rights_record(
    company_id: UUID,
    record_id: UUID,
    payload: EmploymentWorkRightsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentWorkRightsRecord:
    require_company_permission(company_id, "can_prepare", db, current_user)
    record = _load_work_rights_or_404(db, company_id, record_id)
    if payload.engagement_id:
        _load_worker_engagement_or_400(db, company_id, record.worker_id, payload.engagement_id)
    payload_data = payload.model_dump()
    vevo_checked_at = payload_data.pop("vevo_checked_at")
    for key, value in payload_data.items():
        setattr(record, key, value)
    record.vevo_checked_at = datetime.combine(vevo_checked_at, datetime.min.time(), tzinfo=timezone.utc) if vevo_checked_at else None
    db.commit()
    db.refresh(record)
    return record


@router.delete("/work-rights/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_rights_record(
    company_id: UUID,
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    record = _load_work_rights_or_404(db, company_id, record_id)
    db.delete(record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/engagements/{engagement_id}/compensation", response_model=EmploymentCompensationRead)
def upsert_compensation_profile(
    company_id: UUID,
    engagement_id: UUID,
    payload: EmploymentCompensationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentCompensationProfile:
    require_company_permission(company_id, "can_prepare", db, current_user)
    engagement = _load_engagement_or_404(db, company_id, engagement_id)
    _validate_compensation_accounts(
        db,
        company_id,
        expense_account_id=payload.expense_account_id,
        liability_account_id=payload.liability_account_id,
    )
    profile = db.scalar(select(EmploymentCompensationProfile).where(EmploymentCompensationProfile.engagement_id == engagement.id).limit(1))
    if profile is None:
        profile = EmploymentCompensationProfile(company_id=company_id, engagement_id=engagement.id, created_by_user_id=current_user.id, **payload.model_dump())
        db.add(profile)
    else:
        for key, value in payload.model_dump().items():
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/compensation/{compensation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_compensation_profile(
    company_id: UUID,
    compensation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    profile = _load_compensation_or_404(db, company_id, compensation_id)
    db.delete(profile)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/engagements/{engagement_id}/leave-snapshots", response_model=EmploymentLeaveSnapshotRead, status_code=201)
def create_leave_snapshot(
    company_id: UUID,
    engagement_id: UUID,
    payload: EmploymentLeaveSnapshotCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentLeaveSnapshot:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _load_engagement_or_404(db, company_id, engagement_id)
    snapshot = EmploymentLeaveSnapshot(company_id=company_id, engagement_id=engagement_id, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.put("/leave-snapshots/{snapshot_id}", response_model=EmploymentLeaveSnapshotRead)
def update_leave_snapshot(
    company_id: UUID,
    snapshot_id: UUID,
    payload: EmploymentLeaveSnapshotUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentLeaveSnapshot:
    require_company_permission(company_id, "can_prepare", db, current_user)
    snapshot = _load_leave_snapshot_or_404(db, company_id, snapshot_id)
    for key, value in payload.model_dump().items():
        setattr(snapshot, key, value)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.delete("/leave-snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave_snapshot(
    company_id: UUID,
    snapshot_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    snapshot = _load_leave_snapshot_or_404(db, company_id, snapshot_id)
    db.delete(snapshot)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/workers/{worker_id}/reimbursements", response_model=EmploymentReimbursementRead, status_code=201)
def create_reimbursement_item(
    company_id: UUID,
    worker_id: UUID,
    payload: EmploymentReimbursementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentReimbursementItem:
    require_company_permission(company_id, "can_prepare", db, current_user)
    worker = _load_worker_or_404(db, company_id, worker_id)
    if payload.engagement_id:
        _load_worker_engagement_or_400(db, company_id, worker.id, payload.engagement_id)
    item = EmploymentReimbursementItem(company_id=company_id, worker_id=worker.id, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/reimbursements/{reimbursement_id}", response_model=EmploymentReimbursementRead)
def update_reimbursement_item(
    company_id: UUID,
    reimbursement_id: UUID,
    payload: EmploymentReimbursementUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentReimbursementItem:
    require_company_permission(company_id, "can_prepare", db, current_user)
    item = _load_reimbursement_or_404(db, company_id, reimbursement_id)
    if payload.engagement_id:
        _load_worker_engagement_or_400(db, company_id, item.worker_id, payload.engagement_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/reimbursements/{reimbursement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reimbursement_item(
    company_id: UUID,
    reimbursement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    item = _load_reimbursement_or_404(db, company_id, reimbursement_id)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/workers/{worker_id}/issued-assets", response_model=EmploymentIssuedAssetRead, status_code=201)
def create_issued_asset(
    company_id: UUID,
    worker_id: UUID,
    payload: EmploymentIssuedAssetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentIssuedAsset:
    require_company_permission(company_id, "can_prepare", db, current_user)
    worker = _load_worker_or_404(db, company_id, worker_id)
    if payload.engagement_id:
        _load_worker_engagement_or_400(db, company_id, worker.id, payload.engagement_id)
    item = EmploymentIssuedAsset(company_id=company_id, worker_id=worker.id, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/issued-assets/{asset_id}", response_model=EmploymentIssuedAssetRead)
def update_issued_asset(
    company_id: UUID,
    asset_id: UUID,
    payload: EmploymentIssuedAssetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentIssuedAsset:
    require_company_permission(company_id, "can_prepare", db, current_user)
    item = _load_issued_asset_or_404(db, company_id, asset_id)
    if payload.engagement_id:
        _load_worker_engagement_or_400(db, company_id, item.worker_id, payload.engagement_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/issued-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_issued_asset(
    company_id: UUID,
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    item = _load_issued_asset_or_404(db, company_id, asset_id)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reports/headcount", response_model=EmploymentHeadcountReportRead)
def get_headcount_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentHeadcountReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return _build_headcount_report(db, company_id)


@router.get("/reports/headcount/export")
def export_headcount_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    report = _build_headcount_report(db, company_id)
    return _csv_response(
        "employment-headcount.csv",
        _csv_text(
            ["worker_name", "worker_kind", "engagement_type", "status", "department", "role_name", "start_date", "expected_end_date", "actual_end_date"],
            [[row.worker_name, row.worker_kind, row.engagement_type, row.status, row.department, row.role_name, row.start_date, row.expected_end_date, row.actual_end_date] for row in report.rows],
        ),
    )


@router.get("/reports/work-rights", response_model=EmploymentWorkRightsReportRead)
def get_work_rights_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentWorkRightsReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return _build_work_rights_report(db, company_id)


@router.get("/reports/work-rights/export")
def export_work_rights_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    report = _build_work_rights_report(db, company_id)
    return _csv_response(
        "employment-work-rights.csv",
        _csv_text(
            ["worker_name", "review_status", "work_rights_basis", "visa_label", "visa_expiry_date", "next_review_due_at", "restriction_summary"],
            [[row.worker_name, row.review_status, row.work_rights_basis, row.visa_label, row.visa_expiry_date, row.next_review_due_at, row.restriction_summary] for row in report.rows],
        ),
    )


@router.get("/reports/leave-liability-support", response_model=EmploymentLeaveLiabilityReportRead)
def get_leave_liability_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentLeaveLiabilityReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return _build_leave_liability_report(db, company_id)


@router.get("/reports/leave-liability-support/export")
def export_leave_liability_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    report = _build_leave_liability_report(db, company_id)
    return _csv_response(
        "employment-leave-liability-support.csv",
        _csv_text(
            ["worker_name", "engagement_status", "snapshot_date", "annual_leave_hours", "long_service_leave_hours", "leave_value_amount", "current_lsl_value_amount", "non_current_lsl_value_amount"],
            [[row.worker_name, row.engagement_status, row.snapshot_date, row.annual_leave_hours, row.long_service_leave_hours, row.leave_value_amount, row.current_lsl_value_amount, row.non_current_lsl_value_amount] for row in report.rows],
        ),
    )


@router.get("/reports/contractor-review", response_model=EmploymentContractorReviewReportRead)
def get_contractor_review_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmploymentContractorReviewReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return _build_contractor_review_report(db, company_id)


@router.get("/reports/contractor-review/export")
def export_contractor_review_report(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    report = _build_contractor_review_report(db, company_id)
    return _csv_response(
        "employment-contractor-review.csv",
        _csv_text(
            ["worker_name", "engagement_type", "status", "remuneration_basis", "abn_provided", "gst_registered_known", "payroll_tax_in_scope", "note"],
            [[row.worker_name, row.engagement_type, row.status, row.remuneration_basis, row.abn_provided, row.gst_registered_known, row.payroll_tax_in_scope, row.note] for row in report.rows],
        ),
    )
