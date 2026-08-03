from datetime import datetime

from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import ReconciliationItemStatus, ReconciliationSessionStatus
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class ReconciliationSession(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_sessions"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    bank_account_id: Mapped[str] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    accounting_period_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="SET NULL")
    )
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

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    reconciliation_session_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    bank_import_row_id: Mapped[str] = mapped_column(
        ForeignKey("bank_import_rows.id", ondelete="CASCADE"),
        nullable=False,
    )
    matched_journal_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="SET NULL")
    )
    status: Mapped[ReconciliationItemStatus] = mapped_column(
        Enum(ReconciliationItemStatus), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReconciliationMatchGroup(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_match_groups"
    __table_args__ = (
        CheckConstraint(
            "tolerance_amount >= 0", name="ck_reconciliation_group_tolerance_nonnegative"
        ),
        Index("ix_recon_groups_company", "company_id"),
        Index("ix_recon_groups_session", "reconciliation_session_id"),
    )

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    reconciliation_session_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="matched")
    bank_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    journal_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    difference_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tolerance_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReconciliationBankAllocation(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_bank_allocations"
    __table_args__ = (
        UniqueConstraint(
            "reconciliation_match_group_id",
            "reconciliation_item_id",
            name="uq_reconciliation_group_bank_item",
        ),
        CheckConstraint("allocated_amount <> 0", name="ck_reconciliation_bank_allocation_nonzero"),
        Index("ix_recon_bank_alloc_group", "reconciliation_match_group_id"),
        Index("ix_recon_bank_alloc_item", "reconciliation_item_id"),
    )

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    reconciliation_match_group_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_match_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    reconciliation_item_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class ReconciliationJournalAllocation(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_journal_allocations"
    __table_args__ = (
        UniqueConstraint(
            "reconciliation_match_group_id",
            "journal_entry_id",
            name="uq_reconciliation_group_journal_entry",
        ),
        CheckConstraint(
            "allocated_amount <> 0", name="ck_reconciliation_journal_allocation_nonzero"
        ),
        Index("ix_recon_journal_alloc_group", "reconciliation_match_group_id"),
        Index("ix_recon_journal_alloc_journal", "journal_entry_id"),
    )

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    reconciliation_match_group_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_match_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    journal_entry_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ledger_account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
