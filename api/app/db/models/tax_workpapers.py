from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import (
    TaxWorkpaperExceptionStatus,
    TaxWorkpaperExportFormat,
    TaxWorkpaperNoteType,
    TaxWorkpaperStatus,
)
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class TaxWorkpaperPack(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tax_workpaper_packs"
    __table_args__ = (
        UniqueConstraint("company_id", "accounting_period_id", name="uq_tax_workpaper_pack_period"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    accounting_period_id: Mapped[str] = mapped_column(ForeignKey("accounting_periods.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[TaxWorkpaperStatus] = mapped_column(Enum(TaxWorkpaperStatus), nullable=False)
    schedule_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)


class TaxAdjustment(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tax_adjustments"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    tax_workpaper_pack_id: Mapped[str] = mapped_column(
        ForeignKey("tax_workpaper_packs.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class TaxWorkpaperNote(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tax_workpaper_notes"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    tax_workpaper_pack_id: Mapped[str] = mapped_column(
        ForeignKey("tax_workpaper_packs.id", ondelete="CASCADE"),
        nullable=False,
    )
    note_type: Mapped[TaxWorkpaperNoteType] = mapped_column(Enum(TaxWorkpaperNoteType), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class TaxWorkpaperExceptionItem(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tax_workpaper_exception_items"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    tax_workpaper_pack_id: Mapped[str] = mapped_column(
        ForeignKey("tax_workpaper_packs.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaxWorkpaperExceptionStatus] = mapped_column(
        Enum(TaxWorkpaperExceptionStatus),
        nullable=False,
        default=TaxWorkpaperExceptionStatus.OPEN,
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class TaxWorkpaperExport(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tax_workpaper_exports"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    tax_workpaper_pack_id: Mapped[str] = mapped_column(
        ForeignKey("tax_workpaper_packs.id", ondelete="CASCADE"),
        nullable=False,
    )
    format: Mapped[TaxWorkpaperExportFormat] = mapped_column(Enum(TaxWorkpaperExportFormat), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    exported_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)