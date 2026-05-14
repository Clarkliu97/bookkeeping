from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.db.models.auth import User
from app.reports.service import (
    build_balance_sheet_csv,
    build_balance_sheet_report,
    build_general_ledger_csv,
    build_general_ledger_report,
    build_profit_and_loss_csv,
    build_profit_and_loss_report,
    build_trial_balance_csv,
    build_trial_balance_report,
)
from app.schemas.common import (
    BalanceSheetReportRead,
    GeneralLedgerReportRead,
    ProfitAndLossReportRead,
    TrialBalanceReportRead,
)


router = APIRouter(prefix="/companies/{company_id}/reports", tags=["reports"])


def _csv_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _validate_date_range(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report date range is invalid")


@router.get("/trial-balance", response_model=TrialBalanceReportRead)
def trial_balance_report(
    company_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrialBalanceReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    if start_date is not None and end_date is not None:
        _validate_date_range(start_date, end_date)
    return build_trial_balance_report(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        include_draft=include_draft,
    )


@router.get("/trial-balance/export")
def export_trial_balance_report(
    company_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    if start_date is not None and end_date is not None:
        _validate_date_range(start_date, end_date)
    report = build_trial_balance_report(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        include_draft=include_draft,
    )
    return _csv_response(build_trial_balance_csv(report), "trial-balance.csv")


@router.get("/profit-and-loss", response_model=ProfitAndLossReportRead)
def profit_and_loss_report(
    company_id: UUID,
    start_date: date,
    end_date: date,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfitAndLossReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _validate_date_range(start_date, end_date)
    return build_profit_and_loss_report(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        include_draft=include_draft,
    )


@router.get("/profit-and-loss/export")
def export_profit_and_loss_report(
    company_id: UUID,
    start_date: date,
    end_date: date,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _validate_date_range(start_date, end_date)
    report = build_profit_and_loss_report(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        include_draft=include_draft,
    )
    return _csv_response(build_profit_and_loss_csv(report), "profit-and-loss.csv")


@router.get("/balance-sheet", response_model=BalanceSheetReportRead)
def balance_sheet_report(
    company_id: UUID,
    as_of_date: date,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BalanceSheetReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return build_balance_sheet_report(
        db,
        company_id=company_id,
        as_of_date=as_of_date,
        include_draft=include_draft,
    )


@router.get("/balance-sheet/export")
def export_balance_sheet_report(
    company_id: UUID,
    as_of_date: date,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    report = build_balance_sheet_report(
        db,
        company_id=company_id,
        as_of_date=as_of_date,
        include_draft=include_draft,
    )
    return _csv_response(build_balance_sheet_csv(report), "balance-sheet.csv")


@router.get("/general-ledger", response_model=GeneralLedgerReportRead)
def general_ledger_report(
    company_id: UUID,
    start_date: date,
    end_date: date,
    account_id: UUID | None = None,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneralLedgerReportRead:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _validate_date_range(start_date, end_date)
    return build_general_ledger_report(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        include_draft=include_draft,
    )


@router.get("/general-ledger/export")
def export_general_ledger_report(
    company_id: UUID,
    start_date: date,
    end_date: date,
    account_id: UUID | None = None,
    include_draft: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_prepare", db, current_user)
    _validate_date_range(start_date, end_date)
    report = build_general_ledger_report(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        include_draft=include_draft,
    )
    return _csv_response(build_general_ledger_csv(report), "general-ledger.csv")
