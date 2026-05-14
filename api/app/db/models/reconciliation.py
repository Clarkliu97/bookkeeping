from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import ReconciliationItemStatus, ReconciliationSessionStatus
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class ReconciliationSession(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_sessions"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    bank_account_id: Mapped[str] = mapped_column(ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False)
    accounting_period_id: Mapped[str | None] = mapped_column(ForeignKey("accounting_periods.id", ondelete="SET NULL"))
    status: Mapped[ReconciliationSessionStatus] = mapped_column(
        Enum(ReconciliationSessionStatus),
        nullable=False,
    )
    started_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text)


class ReconciliationItem(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_items"
    __table_args__ = (
        UniqueConstraint(
            "reconciliation_session_id",
            "bank_import_row_id",
            name="uq_reconciliation_item_row_per_session",
        ),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    reconciliation_session_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    bank_import_row_id: Mapped[str] = mapped_column(
        ForeignKey("bank_import_rows.id", ondelete="CASCADE"),
        nullable=False,
    )
    matched_journal_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="SET NULL"))
    status: Mapped[ReconciliationItemStatus] = mapped_column(Enum(ReconciliationItemStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
