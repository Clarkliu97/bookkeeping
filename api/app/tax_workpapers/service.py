from __future__ import annotations

import io
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.accounting_periods.service import create_period_earnings_rollover
from app.audit.service import log_approval_action, log_audit_event
from app.bas.service import DISCLAIMER
from app.db.models.accounting import AccountingPeriod, PeriodLock
from app.db.models.audit import ApprovalAction
from app.db.models.bas import BasLineResult, BasPeriod, BasRun
from app.db.models.companies import CompanyConfigurationVersion
from app.db.models.documents import Document
from app.db.models.enums import (
    AccountingPeriodType,
    ApprovalActionType,
    BasRunStatus,
    EntityType,
    SelfApprovalMode,
    TaxWorkpaperExceptionStatus,
    TaxWorkpaperExportFormat,
    TaxWorkpaperNoteType,
    TaxWorkpaperStatus,
    WorkflowStatus,
)
from app.db.models.tax_workpapers import (
    TaxAdjustment,
    TaxWorkpaperExceptionItem,
    TaxWorkpaperExport,
    TaxWorkpaperNote,
    TaxWorkpaperPack,
)
from app.documents.service import store_document_bytes
from app.fixed_assets.service import build_fixed_asset_register
from app.reports.service import build_profit_and_loss_report
from app.schemas.common import (
    TaxWorkpaperAccountingProfitSchedule,
    TaxWorkpaperFixedAssetLine,
    TaxWorkpaperGstReconciliationLine,
    TaxWorkpaperPackDetailRead,
    TaxWorkpaperPackRead,
)

ZERO = Decimal("0.00")


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _configuration_for_date(
    db: Session, company_id: UUID, target_date: date
) -> CompanyConfigurationVersion | None:
    return db.scalar(
        select(CompanyConfigurationVersion)
        .where(CompanyConfigurationVersion.company_id == company_id)
        .where(CompanyConfigurationVersion.effective_from <= target_date)
        .where(
            (CompanyConfigurationVersion.effective_to.is_(None))
            | (CompanyConfigurationVersion.effective_to >= target_date)
        )
        .order_by(
            CompanyConfigurationVersion.effective_from.desc(),
            CompanyConfigurationVersion.version_number.desc(),
        )
        .limit(1)
    )


def _load_period_or_raise(
    db: Session, company_id: UUID, accounting_period_id: UUID
) -> AccountingPeriod:
    period = db.get(AccountingPeriod, accounting_period_id)
    if period is None or period.company_id != company_id:
        raise ValueError("Accounting period not found")
    return period


def _ensure_year_period(period: AccountingPeriod) -> None:
    if period.period_type != AccountingPeriodType.YEAR:
        raise ValueError("Tax workpaper packs require a year accounting period")


def _ensure_pack_editable(pack: TaxWorkpaperPack) -> None:
    if pack.status in {TaxWorkpaperStatus.APPROVED, TaxWorkpaperStatus.EXPORTED}:
        raise ValueError("Approved tax workpaper packs cannot be modified")


def _serialize_accounting_profit(company_id: UUID, db: Session, period: AccountingPeriod) -> dict:
    report = build_profit_and_loss_report(
        db,
        company_id=company_id,
        start_date=period.start_date,
        end_date=period.end_date,
    )
    return {
        "start_date": report.start_date.isoformat(),
        "end_date": report.end_date.isoformat(),
        "total_income": f"{report.total_income:.2f}",
        "total_expenses": f"{report.total_expenses:.2f}",
        "net_profit": f"{report.net_profit:.2f}",
    }


def _serialize_gst_reconciliation(
    company_id: UUID, db: Session, period: AccountingPeriod
) -> list[dict]:
    rows = db.execute(
        select(
            BasLineResult.label,
            func.coalesce(func.sum(BasLineResult.final_amount), 0).label("final_amount"),
            func.count(distinct(BasRun.id)).label("run_count"),
        )
        .join(BasRun, BasRun.id == BasLineResult.bas_run_id)
        .join(BasPeriod, BasPeriod.id == BasRun.bas_period_id)
        .where(BasRun.company_id == company_id)
        .where(BasRun.status.in_([BasRunStatus.APPROVED, BasRunStatus.EXPORTED]))
        .where(BasPeriod.start_date >= period.start_date)
        .where(BasPeriod.end_date <= period.end_date)
        .group_by(BasLineResult.label)
        .order_by(BasLineResult.label.asc())
    ).all()
    return [
        {
            "label": row.label,
            "final_amount": f"{Decimal(row.final_amount or ZERO):.2f}",
            "run_count": int(row.run_count),
        }
        for row in rows
    ]


def _serialize_fixed_asset_snapshot(
    company_id: UUID, db: Session, period: AccountingPeriod
) -> list[dict]:
    register = build_fixed_asset_register(db, company_id=company_id, as_of_date=period.end_date)
    return [
        {
            "asset_code": asset.asset_code,
            "asset_name": asset.name,
            "status": asset.status,
            "depreciation_method": asset.depreciation_method,
            "accumulated_depreciation": f"{asset.accumulated_depreciation:.2f}",
            "carrying_amount": f"{asset.carrying_amount:.2f}",
        }
        for asset in register.assets
    ]


def build_schedule_snapshot(db: Session, *, company_id: UUID, period: AccountingPeriod) -> dict:
    return {
        "accounting_profit_schedule": _serialize_accounting_profit(company_id, db, period),
        "gst_reconciliation_lines": _serialize_gst_reconciliation(company_id, db, period),
        "fixed_asset_lines": _serialize_fixed_asset_snapshot(company_id, db, period),
    }


def create_tax_workpaper_pack(
    db: Session, *, company_id: UUID, payload, generated_by_user_id: UUID
) -> TaxWorkpaperPack:
    period = _load_period_or_raise(db, company_id, payload.accounting_period_id)
    _ensure_year_period(period)
    existing = db.scalar(
        select(TaxWorkpaperPack).where(
            TaxWorkpaperPack.company_id == company_id,
            TaxWorkpaperPack.accounting_period_id == payload.accounting_period_id,
        )
    )
    if existing is not None:
        raise ValueError("A tax workpaper pack already exists for this accounting period")
    pack = TaxWorkpaperPack(
        company_id=company_id,
        accounting_period_id=payload.accounting_period_id,
        status=TaxWorkpaperStatus.DRAFT,
        schedule_snapshot=build_schedule_snapshot(db, company_id=company_id, period=period),
        generated_by_user_id=generated_by_user_id,
        note=payload.note,
    )
    db.add(pack)
    db.flush()
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.TAX_WORKPAPER_PACK,
        entity_id=pack.id,
        action_type=ApprovalActionType.PREPARED,
        prepared_by_user_id=generated_by_user_id,
        note="Tax workpaper pack generated",
    )
    log_audit_event(
        db,
        action="tax_workpaper_pack.generated",
        summary=f"Generated tax workpaper pack for period {period.start_date} to {period.end_date}",
        entity_type=EntityType.TAX_WORKPAPER_PACK.value,
        entity_id=pack.id,
        actor_user_id=generated_by_user_id,
        company_id=company_id,
    )
    return pack


def refresh_tax_workpaper_pack(
    db: Session, *, pack: TaxWorkpaperPack, payload, acting_user_id: UUID
) -> TaxWorkpaperPack:
    _ensure_pack_editable(pack)
    period = _load_period_or_raise(db, pack.company_id, payload.accounting_period_id)
    _ensure_year_period(period)
    existing = db.scalar(
        select(TaxWorkpaperPack).where(
            TaxWorkpaperPack.company_id == pack.company_id,
            TaxWorkpaperPack.accounting_period_id == payload.accounting_period_id,
            TaxWorkpaperPack.id != pack.id,
        )
    )
    if existing is not None:
        raise ValueError("A tax workpaper pack already exists for this accounting period")
    pack.accounting_period_id = payload.accounting_period_id
    pack.schedule_snapshot = build_schedule_snapshot(db, company_id=pack.company_id, period=period)
    pack.note = payload.note
    log_audit_event(
        db,
        action="tax_workpaper_pack.updated",
        summary=f"Updated tax workpaper pack {pack.id}",
        entity_type=EntityType.TAX_WORKPAPER_PACK.value,
        entity_id=pack.id,
        actor_user_id=acting_user_id,
        company_id=pack.company_id,
    )
    return pack


def _pack_accounting_profit(schedule_snapshot: dict) -> TaxWorkpaperAccountingProfitSchedule:
    return TaxWorkpaperAccountingProfitSchedule(**schedule_snapshot["accounting_profit_schedule"])


def _pack_gst_lines(schedule_snapshot: dict) -> list[TaxWorkpaperGstReconciliationLine]:
    return [
        TaxWorkpaperGstReconciliationLine(**item)
        for item in schedule_snapshot.get("gst_reconciliation_lines", [])
    ]


def _pack_fixed_asset_lines(schedule_snapshot: dict) -> list[TaxWorkpaperFixedAssetLine]:
    return [
        TaxWorkpaperFixedAssetLine(**item)
        for item in schedule_snapshot.get("fixed_asset_lines", [])
    ]


def build_tax_workpaper_pack_detail(
    db: Session, pack: TaxWorkpaperPack
) -> TaxWorkpaperPackDetailRead:
    adjustments = list(
        db.scalars(
            select(TaxAdjustment).where(TaxAdjustment.tax_workpaper_pack_id == pack.id)
        ).all()
    )
    notes = list(
        db.scalars(
            select(TaxWorkpaperNote)
            .where(TaxWorkpaperNote.tax_workpaper_pack_id == pack.id)
            .order_by(TaxWorkpaperNote.created_at.asc())
        ).all()
    )
    exceptions = list(
        db.scalars(
            select(TaxWorkpaperExceptionItem)
            .where(TaxWorkpaperExceptionItem.tax_workpaper_pack_id == pack.id)
            .order_by(TaxWorkpaperExceptionItem.created_at.asc())
        ).all()
    )
    exports = list(
        db.scalars(
            select(TaxWorkpaperExport)
            .where(TaxWorkpaperExport.tax_workpaper_pack_id == pack.id)
            .order_by(TaxWorkpaperExport.created_at.asc())
        ).all()
    )
    accounting_profit_schedule = _pack_accounting_profit(pack.schedule_snapshot)
    total_adjustments = _quantize(sum((adjustment.amount for adjustment in adjustments), ZERO))
    taxable_income = _quantize(accounting_profit_schedule.net_profit + total_adjustments)
    return TaxWorkpaperPackDetailRead(
        **TaxWorkpaperPackRead.model_validate(pack).model_dump(),
        accounting_profit_schedule=accounting_profit_schedule,
        gst_reconciliation_lines=_pack_gst_lines(pack.schedule_snapshot),
        fixed_asset_lines=_pack_fixed_asset_lines(pack.schedule_snapshot),
        total_adjustments=total_adjustments,
        taxable_income=taxable_income,
        tax_adjustments=adjustments,
        review_notes=[note for note in notes if note.note_type == TaxWorkpaperNoteType.REVIEW],
        sign_off_notes=[note for note in notes if note.note_type == TaxWorkpaperNoteType.SIGN_OFF],
        exception_items=exceptions,
        exports=exports,
    )


def add_tax_adjustment(
    db: Session, *, pack: TaxWorkpaperPack, payload, acting_user_id: UUID
) -> TaxWorkpaperPackDetailRead:
    _ensure_pack_editable(pack)
    db.add(
        TaxAdjustment(
            company_id=pack.company_id,
            tax_workpaper_pack_id=pack.id,
            label=payload.label,
            amount=payload.amount,
            note=payload.note,
            created_by_user_id=acting_user_id,
        )
    )
    db.flush()
    return build_tax_workpaper_pack_detail(db, pack)


def add_tax_note(
    db: Session, *, pack: TaxWorkpaperPack, payload, acting_user_id: UUID
) -> TaxWorkpaperNote:
    _ensure_pack_editable(pack)
    note = TaxWorkpaperNote(
        company_id=pack.company_id,
        tax_workpaper_pack_id=pack.id,
        note_type=TaxWorkpaperNoteType(payload.note_type),
        message=payload.message,
        created_by_user_id=acting_user_id,
    )
    db.add(note)
    return note


def add_exception_item(
    db: Session, *, pack: TaxWorkpaperPack, payload, acting_user_id: UUID
) -> TaxWorkpaperExceptionItem:
    _ensure_pack_editable(pack)
    exception_item = TaxWorkpaperExceptionItem(
        company_id=pack.company_id,
        tax_workpaper_pack_id=pack.id,
        severity=payload.severity,
        message=payload.message,
        status=TaxWorkpaperExceptionStatus.OPEN,
        created_by_user_id=acting_user_id,
    )
    db.add(exception_item)
    return exception_item


def resolve_exception_item(
    db: Session,
    *,
    pack: TaxWorkpaperPack,
    exception_item: TaxWorkpaperExceptionItem,
    resolution_note: str,
    acting_user_id: UUID,
) -> TaxWorkpaperExceptionItem:
    _ensure_pack_editable(pack)
    exception_item.status = TaxWorkpaperExceptionStatus.RESOLVED
    exception_item.resolution_note = resolution_note
    exception_item.resolved_by_user_id = acting_user_id
    exception_item.resolved_at = datetime.now(timezone.utc)
    return exception_item


def submit_tax_workpaper_pack(
    db: Session, *, pack: TaxWorkpaperPack, acting_user_id: UUID, note: str | None
) -> TaxWorkpaperPack:
    _ensure_pack_editable(pack)
    pack.status = TaxWorkpaperStatus.REVIEW
    log_approval_action(
        db,
        company_id=pack.company_id,
        entity_type=EntityType.TAX_WORKPAPER_PACK,
        entity_id=pack.id,
        action_type=ApprovalActionType.SUBMITTED_FOR_REVIEW,
        prepared_by_user_id=acting_user_id,
        note=note,
    )
    return pack


def _check_self_approval_block(
    db: Session, *, pack: TaxWorkpaperPack, acting_user_id: UUID
) -> None:
    period = db.get(AccountingPeriod, pack.accounting_period_id)
    if period is None:
        return
    configuration = _configuration_for_date(db, pack.company_id, period.end_date)
    if configuration is None or configuration.self_approval_mode != SelfApprovalMode.BLOCK:
        return
    submitted_action = db.scalar(
        select(ApprovalAction)
        .where(
            ApprovalAction.entity_id == str(pack.id),
            ApprovalAction.action_type == ApprovalActionType.SUBMITTED_FOR_REVIEW,
        )
        .order_by(ApprovalAction.created_at.desc())
        .limit(1)
    )
    if submitted_action is not None and submitted_action.prepared_by_user_id == acting_user_id:
        raise ValueError("Company policy blocks self-approval for this tax workpaper pack")


def _lock_year_period(db: Session, *, pack: TaxWorkpaperPack, acting_user_id: UUID) -> None:
    period = db.get(AccountingPeriod, pack.accounting_period_id)
    if period is None:
        return
    if period.status == WorkflowStatus.LOCKED:
        return
    active_lock = db.scalar(
        select(PeriodLock)
        .where(PeriodLock.accounting_period_id == period.id, PeriodLock.unlocked_at.is_(None))
        .limit(1)
    )
    if active_lock is None:
        create_period_earnings_rollover(
            db,
            period=period,
            actor_user_id=acting_user_id,
        )
        db.add(
            PeriodLock(
                company_id=pack.company_id,
                accounting_period_id=period.id,
                lock_reason=f"Locked by annual tax workpaper pack {pack.id}",
                locked_by_user_id=acting_user_id,
                locked_at=datetime.now(timezone.utc),
            )
        )
    period.status = WorkflowStatus.LOCKED


def approve_tax_workpaper_pack(
    db: Session, *, pack: TaxWorkpaperPack, acting_user_id: UUID, note: str | None
) -> TaxWorkpaperPack:
    _check_self_approval_block(db, pack=pack, acting_user_id=acting_user_id)
    pack.status = TaxWorkpaperStatus.APPROVED
    pack.approved_by_user_id = acting_user_id
    pack.approved_at = date.today()
    log_approval_action(
        db,
        company_id=pack.company_id,
        entity_type=EntityType.TAX_WORKPAPER_PACK,
        entity_id=pack.id,
        action_type=ApprovalActionType.APPROVED,
        approved_by_user_id=acting_user_id,
        note=note,
    )
    _lock_year_period(db, pack=pack, acting_user_id=acting_user_id)
    return pack


def build_tax_workpaper_pdf(pack: TaxWorkpaperPack, detail: TaxWorkpaperPackDetailRead) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    cursor_y = height - 50

    def ensure_space(lines: int = 1) -> None:
        nonlocal cursor_y
        if cursor_y < 70 + (lines * 14):
            pdf.showPage()
            cursor_y = height - 50
            pdf.setFont("Helvetica", 10)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, cursor_y, "Company Tax Workpaper Pack")
    cursor_y -= 22
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, cursor_y, f"Pack ID: {pack.id}")
    cursor_y -= 14
    pdf.drawString(
        50,
        cursor_y,
        f"Period: {detail.accounting_profit_schedule.start_date} to {detail.accounting_profit_schedule.end_date}",
    )
    cursor_y -= 16
    pdf.drawString(50, cursor_y, DISCLAIMER)
    cursor_y -= 22

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, cursor_y, "Accounting Profit Support")
    cursor_y -= 18
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        50, cursor_y, f"Total income: {detail.accounting_profit_schedule.total_income:.2f}"
    )
    cursor_y -= 14
    pdf.drawString(
        50, cursor_y, f"Total expenses: {detail.accounting_profit_schedule.total_expenses:.2f}"
    )
    cursor_y -= 14
    pdf.drawString(
        50, cursor_y, f"Accounting profit: {detail.accounting_profit_schedule.net_profit:.2f}"
    )
    cursor_y -= 14
    pdf.drawString(50, cursor_y, f"Tax adjustments: {detail.total_adjustments:.2f}")
    cursor_y -= 14
    pdf.drawString(50, cursor_y, f"Taxable income support: {detail.taxable_income:.2f}")
    cursor_y -= 24

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, cursor_y, "GST Reconciliation Support")
    cursor_y -= 18
    pdf.setFont("Helvetica", 10)
    if not detail.gst_reconciliation_lines:
        pdf.drawString(50, cursor_y, "No approved BAS totals in this financial year.")
        cursor_y -= 14
    else:
        for line in detail.gst_reconciliation_lines:
            ensure_space()
            pdf.drawString(
                50,
                cursor_y,
                f"{line.label}: {line.final_amount:.2f} across {line.run_count} BAS runs",
            )
            cursor_y -= 14
    cursor_y -= 10

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, cursor_y, "Fixed Asset Support")
    cursor_y -= 18
    pdf.setFont("Helvetica", 10)
    if not detail.fixed_asset_lines:
        pdf.drawString(50, cursor_y, "No fixed assets recorded.")
        cursor_y -= 14
    else:
        for line in detail.fixed_asset_lines:
            ensure_space()
            pdf.drawString(
                50,
                cursor_y,
                f"{line.asset_code} {line.asset_name}: accumulated {line.accumulated_depreciation:.2f}, carrying {line.carrying_amount:.2f}",
            )
            cursor_y -= 14
    cursor_y -= 10

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, cursor_y, "Review Notes and Exceptions")
    cursor_y -= 18
    pdf.setFont("Helvetica", 10)
    notes = detail.review_notes + detail.sign_off_notes
    if not notes and not detail.exception_items:
        pdf.drawString(50, cursor_y, "No notes or exceptions recorded.")
        cursor_y -= 14
    else:
        for note in notes:
            ensure_space()
            pdf.drawString(50, cursor_y, f"{note.note_type.upper()}: {note.message}")
            cursor_y -= 14
        for item in detail.exception_items:
            ensure_space()
            pdf.drawString(
                50, cursor_y, f"{item.status.upper()} {item.severity.upper()}: {item.message}"
            )
            cursor_y -= 14

    pdf.save()
    return buffer.getvalue()


def create_tax_workpaper_export(
    db: Session,
    *,
    company_id: UUID,
    pack_id: UUID,
    exported_by_user_id: UUID,
    filename: str,
    media_type: str,
    content: bytes,
    export_format: TaxWorkpaperExportFormat,
) -> TaxWorkpaperExport:
    stored_filename, storage_path, checksum, byte_size = store_document_bytes(
        company_id=company_id,
        original_filename=filename,
        content=content,
    )
    document = Document(
        company_id=company_id,
        original_filename=filename,
        stored_filename=stored_filename,
        media_type=media_type,
        byte_size=byte_size,
        checksum_sha256=checksum,
        storage_path=storage_path,
        uploaded_by_user_id=exported_by_user_id,
    )
    db.add(document)
    db.flush()
    export = TaxWorkpaperExport(
        company_id=company_id,
        tax_workpaper_pack_id=pack_id,
        format=export_format,
        document_id=document.id,
        exported_by_user_id=exported_by_user_id,
    )
    db.add(export)
    return export
