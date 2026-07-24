from __future__ import annotations

import csv
import io
from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.accounting_periods.service import create_period_earnings_rollover
from app.audit.service import log_approval_action, log_audit_event
from app.db.models.accounting import AccountingPeriod, JournalEntry, JournalLine, PeriodLock
from app.db.models.audit import ApprovalAction
from app.db.models.bas import (
    BasAdjustment,
    BasExport,
    BasLineResult,
    BasPeriod,
    BasReviewNote,
    BasRun,
)
from app.db.models.companies import CompanyConfigurationVersion
from app.db.models.documents import Document
from app.db.models.enums import (
    ApprovalActionType,
    BasExportFormat,
    BasPeriodStatus,
    BasRunStatus,
    EntityType,
    JournalStatus,
    PeriodLockPolicy,
    WorkflowStatus,
)
from app.db.models.reference import TaxCode
from app.documents.service import store_document_bytes

DISCLAIMER = (
    "Internal calculation support only. This report does not lodge anything with the ATO and "
    "should be reviewed before manual form entry or submission."
)


def _last_day_of_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def _end_of_period(start_date: date, frequency: str) -> date:
    def add_months(months_to_add: int) -> tuple[int, int]:
        month_index = (start_date.month - 1) + months_to_add
        year = start_date.year + month_index // 12
        month = (month_index % 12) + 1
        return year, month

    if frequency == "monthly":
        return date(
            start_date.year, start_date.month, _last_day_of_month(start_date.year, start_date.month)
        )
    if frequency == "quarterly":
        end_year, end_month = add_months(2)
        return date(end_year, end_month, _last_day_of_month(end_year, end_month))
    if frequency == "annually":
        end_year, end_month = add_months(11)
        return date(end_year, end_month, _last_day_of_month(end_year, end_month))
    return start_date


def _next_period_start(period_end: date) -> date:
    if period_end.month == 12:
        return date(period_end.year + 1, 1, 1)
    return date(period_end.year, period_end.month + 1, 1)


def _configuration_for_date(
    db: Session, company_id: UUID, target_date: date
) -> CompanyConfigurationVersion:
    configuration = db.scalar(
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
    if configuration is None:
        raise ValueError("No company configuration exists for the requested BAS period start date")
    return configuration


def _configuration_snapshot(configuration: CompanyConfigurationVersion) -> dict:
    return {
        "version_number": configuration.version_number,
        "effective_from": configuration.effective_from.isoformat(),
        "effective_to": configuration.effective_to.isoformat()
        if configuration.effective_to
        else None,
        "gst_registered": configuration.gst_registered,
        "bas_frequency": configuration.bas_frequency.value,
        "bas_reporting_basis": configuration.bas_reporting_basis.value,
        "financial_year_start_month": configuration.financial_year_start_month,
        "financial_year_start_day": configuration.financial_year_start_day,
        "allow_self_approval": configuration.allow_self_approval,
        "self_approval_mode": configuration.self_approval_mode.value,
        "period_lock_policy": configuration.period_lock_policy.value,
    }


def generate_bas_periods(
    db: Session, *, company_id: UUID, start_date: date, end_date: date
) -> list[BasPeriod]:
    periods: list[BasPeriod] = []
    current_start = start_date
    while current_start <= end_date:
        configuration = _configuration_for_date(db, company_id, current_start)
        current_end = _end_of_period(current_start, configuration.bas_frequency.value)
        if current_end > end_date:
            current_end = end_date
        existing = db.scalar(
            select(BasPeriod).where(
                BasPeriod.company_id == company_id,
                BasPeriod.start_date == current_start,
                BasPeriod.end_date == current_end,
            )
        )
        if existing is not None:
            periods.append(existing)
            current_start = _next_period_start(current_end)
            continue
        period = BasPeriod(
            company_id=company_id,
            start_date=current_start,
            end_date=current_end,
            status=BasPeriodStatus.GENERATED,
            configuration_version_id=configuration.id,
        )
        db.add(period)
        db.flush()
        periods.append(period)
        current_start = _next_period_start(current_end)
    return periods


def _amount_for_line(line: JournalLine) -> Decimal:
    debit_amount = line.debit_amount or Decimal("0.00")
    credit_amount = line.credit_amount or Decimal("0.00")
    return abs(Decimal(debit_amount) - Decimal(credit_amount))


def _refresh_line_results(db: Session, bas_run: BasRun) -> None:
    adjustments = list(
        db.scalars(select(BasAdjustment).where(BasAdjustment.bas_run_id == bas_run.id)).all()
    )
    adjustment_totals: dict[str, Decimal] = {}
    for adjustment in adjustments:
        adjustment_totals[adjustment.label] = (
            adjustment_totals.get(adjustment.label, Decimal("0.00")) + adjustment.amount
        )

    line_results = list(
        db.scalars(select(BasLineResult).where(BasLineResult.bas_run_id == bas_run.id)).all()
    )
    existing_by_label = {line_result.label: line_result for line_result in line_results}
    for label, adjustment_total in adjustment_totals.items():
        if label not in existing_by_label:
            missing_line_result = BasLineResult(
                bas_run_id=bas_run.id,
                label=label,
                system_amount=Decimal("0.00"),
                adjustment_amount=Decimal("0.00"),
                final_amount=Decimal("0.00"),
                detail_count=0,
            )
            db.add(missing_line_result)
            line_results.append(missing_line_result)
            existing_by_label[label] = missing_line_result
    for line_result in line_results:
        line_result.adjustment_amount = adjustment_totals.get(line_result.label, Decimal("0.00"))
        line_result.final_amount = line_result.system_amount + line_result.adjustment_amount


def _bas_lines_and_warnings(
    db: Session, company_id: UUID, bas_period: BasPeriod
) -> tuple[dict[str, dict[str, Decimal | int]], list[BasReviewNote]]:
    lines = db.execute(
        select(JournalLine, JournalEntry, TaxCode)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .outerjoin(TaxCode, TaxCode.id == JournalLine.tax_code_id)
        .where(JournalEntry.company_id == company_id)
        .where(JournalEntry.status == JournalStatus.POSTED)
        .where(JournalEntry.entry_date >= bas_period.start_date)
        .where(JournalEntry.entry_date <= bas_period.end_date)
    ).all()

    totals: dict[str, dict[str, Decimal | int]] = {}
    review_notes: list[BasReviewNote] = []
    for journal_line, _, tax_code in lines:
        if journal_line.tax_code_id is None:
            review_notes.append(
                BasReviewNote(
                    company_id=company_id,
                    bas_run_id=None,  # type: ignore[arg-type]
                    severity="warning",
                    message=f"Journal line {journal_line.id} has no tax code and was excluded from BAS totals.",
                    related_label=None,
                    created_by_user_id=None,
                )
            )
            continue
        if tax_code is None:
            continue
        if not tax_code.is_gst_applicable:
            continue
        if not tax_code.bas_label:
            review_notes.append(
                BasReviewNote(
                    company_id=company_id,
                    bas_run_id=None,  # type: ignore[arg-type]
                    severity="warning",
                    message=f"Tax code {tax_code.code} has no BAS label mapping.",
                    related_label=None,
                    created_by_user_id=None,
                )
            )
            continue
        label = tax_code.bas_label.upper()
        amount = _amount_for_line(journal_line)
        bucket = totals.setdefault(label, {"system_amount": Decimal("0.00"), "detail_count": 0})
        bucket["system_amount"] = Decimal(bucket["system_amount"]) + amount
        bucket["detail_count"] = int(bucket["detail_count"]) + 1
    return totals, review_notes


def create_bas_run(
    db: Session, *, company_id: UUID, bas_period: BasPeriod, generated_by_user_id: UUID
) -> BasRun:
    configuration = db.get(CompanyConfigurationVersion, bas_period.configuration_version_id)
    if configuration is None:
        raise ValueError("BAS period has no valid configuration reference")

    bas_run = BasRun(
        company_id=company_id,
        bas_period_id=bas_period.id,
        status=BasRunStatus.DRAFT,
        configuration_version_id=configuration.id,
        configuration_snapshot=_configuration_snapshot(configuration),
        generated_by_user_id=generated_by_user_id,
        warning_count=0,
    )
    db.add(bas_run)
    db.flush()

    totals, warnings = _bas_lines_and_warnings(db, company_id, bas_period)
    for label, values in totals.items():
        system_amount = Decimal(values["system_amount"]).quantize(Decimal("0.01"))
        db.add(
            BasLineResult(
                bas_run_id=bas_run.id,
                label=label,
                system_amount=system_amount,
                adjustment_amount=Decimal("0.00"),
                final_amount=system_amount,
                detail_count=int(values["detail_count"]),
            )
        )
    for warning in warnings:
        warning.bas_run_id = bas_run.id
        db.add(warning)
    bas_run.warning_count = len(warnings)
    log_approval_action(
        db,
        company_id=company_id,
        entity_type=EntityType.BAS_RUN,
        entity_id=bas_run.id,
        action_type=ApprovalActionType.PREPARED,
        prepared_by_user_id=generated_by_user_id,
        note="BAS run generated",
    )
    return bas_run


def rebuild_bas_run(
    db: Session, *, bas_run: BasRun, bas_period: BasPeriod, acting_user_id: UUID
) -> BasRun:
    configuration = db.get(CompanyConfigurationVersion, bas_period.configuration_version_id)
    if configuration is None:
        raise ValueError("BAS period has no valid configuration reference")

    bas_run.bas_period_id = bas_period.id
    bas_run.configuration_version_id = configuration.id
    bas_run.configuration_snapshot = _configuration_snapshot(configuration)
    db.execute(delete(BasLineResult).where(BasLineResult.bas_run_id == bas_run.id))
    db.execute(delete(BasReviewNote).where(BasReviewNote.bas_run_id == bas_run.id))
    db.flush()

    totals, warnings = _bas_lines_and_warnings(db, bas_run.company_id, bas_period)
    for label, values in totals.items():
        system_amount = Decimal(values["system_amount"]).quantize(Decimal("0.01"))
        db.add(
            BasLineResult(
                bas_run_id=bas_run.id,
                label=label,
                system_amount=system_amount,
                adjustment_amount=Decimal("0.00"),
                final_amount=system_amount,
                detail_count=int(values["detail_count"]),
            )
        )
    for warning in warnings:
        warning.bas_run_id = bas_run.id
        db.add(warning)
    bas_run.warning_count = len(warnings)
    log_audit_event(
        db,
        action="bas.run.updated",
        summary=f"Updated BAS run {bas_run.id}",
        entity_type=EntityType.BAS_RUN.value,
        entity_id=bas_run.id,
        actor_user_id=acting_user_id,
        company_id=bas_run.company_id,
    )
    return bas_run


def check_self_approval_block(db: Session, *, bas_run: BasRun, acting_user_id: UUID) -> None:
    configuration = db.get(CompanyConfigurationVersion, bas_run.configuration_version_id)
    if configuration is None:
        return
    submitted_action = db.scalar(
        select(ApprovalAction)
        .where(
            ApprovalAction.entity_id == str(bas_run.id),
            ApprovalAction.action_type == ApprovalActionType.SUBMITTED_FOR_REVIEW,
        )
        .order_by(ApprovalAction.created_at.desc())
        .limit(1)
    )
    if submitted_action is None or submitted_action.prepared_by_user_id != acting_user_id:
        return
    if configuration.self_approval_mode.value == "block":
        raise ValueError("Company policy blocks self-approval for this BAS run")


def _lock_periods_for_bas(
    db: Session, *, company_id: UUID, bas_period: BasPeriod, acting_user_id: UUID
) -> None:
    periods = list(
        db.scalars(
            select(AccountingPeriod)
            .where(AccountingPeriod.company_id == company_id)
            .where(AccountingPeriod.start_date >= bas_period.start_date)
            .where(AccountingPeriod.end_date <= bas_period.end_date)
        ).all()
    )
    for accounting_period in periods:
        if accounting_period.status == WorkflowStatus.LOCKED:
            continue
        active_lock = db.scalar(
            select(PeriodLock)
            .where(PeriodLock.accounting_period_id == accounting_period.id)
            .where(PeriodLock.unlocked_at.is_(None))
            .limit(1)
        )
        if active_lock is not None:
            continue
        create_period_earnings_rollover(
            db,
            period=accounting_period,
            actor_user_id=acting_user_id,
        )
        accounting_period.status = WorkflowStatus.LOCKED
        db.add(
            PeriodLock(
                company_id=company_id,
                accounting_period_id=accounting_period.id,
                lock_reason=f"Locked by BAS period {bas_period.start_date} to {bas_period.end_date}",
                locked_by_user_id=acting_user_id,
                locked_at=datetime.now(timezone.utc),
            )
        )


def maybe_lock_periods_for_policy(
    db: Session, *, bas_run: BasRun, acting_user_id: UUID, on_export: bool = False
) -> None:
    configuration = db.get(CompanyConfigurationVersion, bas_run.configuration_version_id)
    bas_period = db.get(BasPeriod, bas_run.bas_period_id)
    if configuration is None or bas_period is None:
        return
    if configuration.period_lock_policy == PeriodLockPolicy.AFTER_APPROVAL and not on_export:
        _lock_periods_for_bas(
            db, company_id=bas_run.company_id, bas_period=bas_period, acting_user_id=acting_user_id
        )
        bas_period.status = BasPeriodStatus.LOCKED
    if configuration.period_lock_policy == PeriodLockPolicy.AFTER_EXPORT and on_export:
        _lock_periods_for_bas(
            db, company_id=bas_run.company_id, bas_period=bas_period, acting_user_id=acting_user_id
        )
        bas_period.status = BasPeriodStatus.LOCKED


def build_bas_csv(
    bas_run: BasRun, line_results: list[BasLineResult], review_notes: list[BasReviewNote]
) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["BAS Label", "System Amount", "Adjustment Amount", "Final Amount", "Detail Count"]
    )
    for line in sorted(line_results, key=lambda item: item.label):
        writer.writerow(
            [
                line.label,
                f"{line.system_amount:.2f}",
                f"{line.adjustment_amount:.2f}",
                f"{line.final_amount:.2f}",
                line.detail_count,
            ]
        )
    writer.writerow([])
    writer.writerow(["Warnings"])
    for note in review_notes:
        writer.writerow([note.severity, note.related_label or "", note.message])
    writer.writerow([])
    writer.writerow([DISCLAIMER])
    return output.getvalue().encode("utf-8")


def build_bas_pdf(
    bas_run: BasRun, line_results: list[BasLineResult], review_notes: list[BasReviewNote]
) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    cursor_y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, cursor_y, "BAS Review Pack")
    cursor_y -= 24
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, cursor_y, f"Run ID: {bas_run.id}")
    cursor_y -= 16
    pdf.drawString(50, cursor_y, DISCLAIMER)
    cursor_y -= 24
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, cursor_y, "Line Results")
    cursor_y -= 18
    pdf.setFont("Helvetica", 10)
    for line in sorted(line_results, key=lambda item: item.label):
        pdf.drawString(
            50,
            cursor_y,
            f"{line.label}: final {line.final_amount:.2f} (system {line.system_amount:.2f}, adj {line.adjustment_amount:.2f})",
        )
        cursor_y -= 14
        if cursor_y < 70:
            pdf.showPage()
            cursor_y = height - 50
            pdf.setFont("Helvetica", 10)
    cursor_y -= 10
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, cursor_y, "Warnings and Review Notes")
    cursor_y -= 18
    pdf.setFont("Helvetica", 10)
    if not review_notes:
        pdf.drawString(50, cursor_y, "No review warnings recorded.")
    else:
        for note in review_notes:
            pdf.drawString(50, cursor_y, f"{note.severity.upper()}: {note.message}")
            cursor_y -= 14
            if cursor_y < 70:
                pdf.showPage()
                cursor_y = height - 50
                pdf.setFont("Helvetica", 10)
    pdf.save()
    return buffer.getvalue()


def create_export_document(
    db: Session,
    *,
    company_id: UUID,
    bas_run_id: UUID,
    exported_by_user_id: UUID,
    filename: str,
    media_type: str,
    content: bytes,
    export_format: BasExportFormat,
) -> BasExport:
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
    export = BasExport(
        company_id=company_id,
        bas_run_id=bas_run_id,
        format=export_format,
        document_id=document.id,
        exported_by_user_id=exported_by_user_id,
    )
    db.add(export)
    return export
