from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import BasExportFormat, BasPeriodStatus, BasRunStatus
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class BasPeriod(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bas_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "start_date", "end_date", name="uq_bas_period_range"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[BasPeriodStatus] = mapped_column(Enum(BasPeriodStatus), nullable=False)
    configuration_version_id: Mapped[str] = mapped_column(
        ForeignKey("company_configuration_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text)


class BasRun(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bas_runs"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    bas_period_id: Mapped[str] = mapped_column(ForeignKey("bas_periods.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[BasRunStatus] = mapped_column(Enum(BasRunStatus), nullable=False)
    configuration_version_id: Mapped[str] = mapped_column(
        ForeignKey("company_configuration_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    configuration_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[date | None] = mapped_column(Date)
    warning_count: Mapped[int] = mapped_column(nullable=False, default=0)


class BasLineResult(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bas_line_results"
    __table_args__ = (UniqueConstraint("bas_run_id", "label", name="uq_bas_run_label"),)

    bas_run_id: Mapped[str] = mapped_column(ForeignKey("bas_runs.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    system_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    adjustment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    final_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    detail_count: Mapped[int] = mapped_column(nullable=False, default=0)


class BasAdjustment(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bas_adjustments"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    bas_run_id: Mapped[str] = mapped_column(ForeignKey("bas_runs.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class BasReviewNote(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bas_review_notes"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    bas_run_id: Mapped[str] = mapped_column(ForeignKey("bas_runs.id", ondelete="CASCADE"), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_label: Mapped[str | None] = mapped_column(String(32))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class BasExport(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bas_exports"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    bas_run_id: Mapped[str] = mapped_column(ForeignKey("bas_runs.id", ondelete="CASCADE"), nullable=False)
    format: Mapped[BasExportFormat] = mapped_column(Enum(BasExportFormat), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    exported_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)