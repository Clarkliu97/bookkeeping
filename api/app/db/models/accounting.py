from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import AccountType, AccountingPeriodType, JournalSourceType, JournalStatus, WorkflowStatus
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class Account(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("company_id", "account_code", name="uq_account_code"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    reporting_category_id: Mapped[str | None] = mapped_column(ForeignKey("reporting_categories.id"))
    default_tax_code_id: Mapped[str | None] = mapped_column(ForeignKey("tax_codes.id"))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    allow_manual_posting: Mapped[bool] = mapped_column(nullable=False, default=True)


class AccountingPeriod(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "start_date", "end_date", name="uq_accounting_period_range"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    period_type: Mapped[AccountingPeriodType] = mapped_column(Enum(AccountingPeriodType), nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), nullable=False)


class PeriodLock(PrimaryKeyMixin, Base):
    __tablename__ = "period_locks"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    accounting_period_id: Mapped[str] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    lock_reason: Mapped[str] = mapped_column(Text, nullable=False)
    locked_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(nullable=False)
    unlocked_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    unlocked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    unlock_reason: Mapped[str | None] = mapped_column(Text)


class JournalEntry(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("company_id", "entry_number", name="uq_journal_entry_number"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    entry_number: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_date: Mapped[date] = mapped_column(nullable=False)
    accounting_period_id: Mapped[str] = mapped_column(ForeignKey("accounting_periods.id"), nullable=False)
    status: Mapped[JournalStatus] = mapped_column(Enum(JournalStatus), nullable=False)
    source_type: Mapped[JournalSourceType] = mapped_column(Enum(JournalSourceType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")
    posted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    posted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reversal_of_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id"))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="journal_entry",
        cascade="all, delete-orphan",
    )


class JournalLine(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        UniqueConstraint("journal_entry_id", "line_number", name="uq_journal_line_number"),
        CheckConstraint(
            "((debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0))",
            name="ck_journal_line_single_sided_amount",
        ),
    )

    journal_entry_id: Mapped[str] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    tax_code_id: Mapped[str | None] = mapped_column(ForeignKey("tax_codes.id"))
    reporting_category_id: Mapped[str | None] = mapped_column(ForeignKey("reporting_categories.id"))
    source_document_reference: Mapped[str | None] = mapped_column(String(255))

    journal_entry: Mapped[JournalEntry] = relationship(back_populates="lines")
