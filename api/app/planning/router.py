from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.db.models.auth import User
from app.db.models.companies import Company
from app.db.models.planning import PlanningForecastRun
from app.planning.calculations import calculate_forecast, compare_plans, read_forecast_run
from app.planning.exports import build_forecast_csv, build_forecast_pdf, build_plan_csv
from app.planning.schemas import (
    PlanningActionRequest,
    PlanningApplyGrowthRequest,
    PlanningBudgetItemCreate,
    PlanningBudgetItemRead,
    PlanningBudgetItemUpdate,
    PlanningCalculateRequest,
    PlanningCloneRequest,
    PlanningComparisonRead,
    PlanningComparisonRequest,
    PlanningCopyPriorActualsRequest,
    PlanningForecastRunRead,
    PlanningForecastRunSummaryRead,
    PlanningImportPreviewRead,
    PlanningLineBulkUpdate,
    PlanningPlanCreate,
    PlanningPlanDetailRead,
    PlanningPlanRead,
    PlanningPlanUpdate,
    PlanningSpreadRequest,
)
from app.planning.service import (
    apply_growth,
    approve_plan,
    archive_plan,
    build_plan_detail,
    bulk_update_lines,
    clone_plan,
    commit_csv_import,
    copy_prior_actuals,
    create_budget_item,
    create_plan,
    delete_budget_item,
    delete_draft_plan,
    list_budget_items,
    list_plans,
    load_budget_item_or_404,
    load_plan_or_404,
    lock_plan,
    preview_csv_import,
    reject_plan,
    review_plan,
    spread_annual_amount,
    submit_plan,
    update_budget_item,
    update_plan,
)

router = APIRouter(prefix="/companies/{company_id}/planning", tags=["planning"])


def _download(content: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


def _company_or_404(db: Session, company_id: UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("/plans", response_model=list[PlanningPlanRead])
def get_plans(
    company_id: UUID,
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list_plans(db, company_id, include_archived=include_archived)


@router.post("/plans", response_model=PlanningPlanRead, status_code=201)
def post_plan(
    company_id: UUID,
    payload: PlanningPlanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return create_plan(
        db,
        company_id=company_id,
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.get("/plans/{plan_id}", response_model=PlanningPlanDetailRead)
def get_plan(
    company_id: UUID,
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return build_plan_detail(db, load_plan_or_404(db, company_id, plan_id))


@router.put("/plans/{plan_id}", response_model=PlanningPlanRead)
def put_plan(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return update_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(
    company_id: UUID,
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    delete_draft_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        acting_user_id=current_user.id,
    )
    return Response(status_code=204)


@router.get("/plans/{plan_id}/budget-items", response_model=list[PlanningBudgetItemRead])
def get_budget_items(
    company_id: UUID,
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list_budget_items(db, load_plan_or_404(db, company_id, plan_id))


@router.post(
    "/plans/{plan_id}/budget-items",
    response_model=PlanningPlanDetailRead,
    status_code=201,
)
def post_budget_item(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningBudgetItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return create_budget_item(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.put(
    "/plans/{plan_id}/budget-items/{item_id}",
    response_model=PlanningPlanDetailRead,
)
def put_budget_item(
    company_id: UUID,
    plan_id: UUID,
    item_id: UUID,
    payload: PlanningBudgetItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    plan = load_plan_or_404(db, company_id, plan_id)
    return update_budget_item(
        db,
        plan=plan,
        item=load_budget_item_or_404(db, plan=plan, item_id=item_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.delete("/plans/{plan_id}/budget-items/{item_id}", status_code=204)
def delete_budget_item_route(
    company_id: UUID,
    plan_id: UUID,
    item_id: UUID,
    revision: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    plan = load_plan_or_404(db, company_id, plan_id)
    delete_budget_item(
        db,
        plan=plan,
        item=load_budget_item_or_404(db, plan=plan, item_id=item_id),
        revision=revision,
        acting_user_id=current_user.id,
    )
    return Response(status_code=204)


@router.put("/plans/{plan_id}/lines/bulk", response_model=PlanningPlanDetailRead)
def put_lines(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningLineBulkUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return bulk_update_lines(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.post("/plans/{plan_id}/spread", response_model=PlanningPlanDetailRead)
def post_spread(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningSpreadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return spread_annual_amount(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.post("/plans/{plan_id}/copy-prior-actuals", response_model=PlanningPlanDetailRead)
def post_copy_prior_actuals(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningCopyPriorActualsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return copy_prior_actuals(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.post("/plans/{plan_id}/apply-growth", response_model=PlanningPlanDetailRead)
def post_apply_growth(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningApplyGrowthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return apply_growth(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.post("/plans/{plan_id}/imports/preview", response_model=PlanningImportPreviewRead)
async def post_import_preview(
    company_id: UUID,
    plan_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    plan = load_plan_or_404(db, company_id, plan_id)
    content = await file.read()
    return preview_csv_import(db, plan=plan, content=content)


@router.post("/plans/{plan_id}/imports/commit", response_model=PlanningPlanDetailRead)
async def post_import_commit(
    company_id: UUID,
    plan_id: UUID,
    revision: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    plan = load_plan_or_404(db, company_id, plan_id)
    content = await file.read()
    return commit_csv_import(
        db,
        plan=plan,
        revision=revision,
        content=content,
        acting_user_id=current_user.id,
    )


@router.post("/plans/{plan_id}/clone", response_model=PlanningPlanRead, status_code=201)
def post_clone(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningCloneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return clone_plan(
        db,
        source=load_plan_or_404(db, company_id, plan_id),
        payload=payload,
        acting_user_id=current_user.id,
    )


@router.post("/plans/{plan_id}/submit", response_model=PlanningPlanRead)
def post_submit(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return submit_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        acting_user_id=current_user.id,
        note=payload.note,
    )


@router.post("/plans/{plan_id}/review", response_model=PlanningPlanRead)
def post_review(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_review", db, current_user)
    return review_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        acting_user_id=current_user.id,
        note=payload.note,
    )


@router.post("/plans/{plan_id}/reject", response_model=PlanningPlanRead)
def post_reject(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_review", db, current_user)
    return reject_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        acting_user_id=current_user.id,
        note=payload.note,
    )


@router.post("/plans/{plan_id}/approve", response_model=PlanningPlanRead)
def post_approve(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_approve", db, current_user)
    return approve_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        acting_user_id=current_user.id,
        note=payload.note,
    )


@router.post("/plans/{plan_id}/lock", response_model=PlanningPlanRead)
def post_lock(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_approve", db, current_user)
    return lock_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        acting_user_id=current_user.id,
        note=payload.note,
    )


@router.post("/plans/{plan_id}/archive", response_model=PlanningPlanRead)
def post_archive(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_administer", db, current_user)
    return archive_plan(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        acting_user_id=current_user.id,
        note=payload.note,
    )


@router.post("/plans/{plan_id}/calculate", response_model=PlanningForecastRunRead)
def post_calculate(
    company_id: UUID,
    plan_id: UUID,
    payload: PlanningCalculateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return calculate_forecast(
        db,
        plan=load_plan_or_404(db, company_id, plan_id),
        actual_through_date=payload.actual_through_date,
        acting_user_id=current_user.id,
        persist=payload.persist,
    )


@router.get("/forecast-runs", response_model=list[PlanningForecastRunSummaryRead])
def get_forecast_runs(
    company_id: UUID,
    plan_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    query = select(PlanningForecastRun).where(PlanningForecastRun.company_id == company_id)
    if plan_id is not None:
        load_plan_or_404(db, company_id, plan_id)
        query = query.where(PlanningForecastRun.forecast_plan_id == plan_id)
    return list(db.scalars(query.order_by(PlanningForecastRun.created_at.desc()).limit(100)).all())


@router.get("/forecast-runs/{run_id}", response_model=PlanningForecastRunRead)
def get_forecast_run(
    company_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return read_forecast_run(db, company_id=company_id, run_id=run_id)


@router.post("/comparisons", response_model=PlanningComparisonRead)
def post_comparison(
    company_id: UUID,
    payload: PlanningComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return compare_plans(
        db,
        company_id=company_id,
        plan_ids=payload.plan_ids,
        actual_through_date=payload.actual_through_date,
        acting_user_id=current_user.id,
    )


@router.get("/plans/{plan_id}/export/csv")
def export_plan_csv(
    company_id: UUID,
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    detail = build_plan_detail(db, load_plan_or_404(db, company_id, plan_id))
    return _download(build_plan_csv(detail), "budget-plan.csv", "text/csv")


@router.get("/plans/{plan_id}/export/pdf")
def export_plan_pdf(
    company_id: UUID,
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    plan = load_plan_or_404(db, company_id, plan_id)
    detail = build_plan_detail(db, plan)
    report = calculate_forecast(
        db,
        plan=plan,
        actual_through_date=plan.actual_through_date,
        acting_user_id=current_user.id,
        persist=False,
    )
    return _download(
        build_forecast_pdf(
            _company_or_404(db, company_id),
            report,
            plan_detail=detail,
        ),
        "budget-plan.pdf",
        "application/pdf",
    )


@router.get("/forecast-runs/{run_id}/export/csv")
def export_run_csv(
    company_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    return _download(
        build_forecast_csv(read_forecast_run(db, company_id=company_id, run_id=run_id)),
        "forecast-run.csv",
        "text/csv",
    )


@router.get("/forecast-runs/{run_id}/export/pdf")
def export_run_pdf(
    company_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_company_permission(company_id, "can_prepare", db, current_user)
    report = read_forecast_run(db, company_id=company_id, run_id=run_id)
    return _download(
        build_forecast_pdf(_company_or_404(db, company_id), report),
        "forecast-run.pdf",
        "application/pdf",
    )
