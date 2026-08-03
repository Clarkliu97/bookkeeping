from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import BankImportRowStatus, BankImportSessionStatus
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class BankAccount(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_bank_account_name"),)

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ledger_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    bsb: Mapped[str | None] = mapped_column(String(16))
    account_number_masked: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class BankImportSession(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bank_import_sessions"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    bank_account_id: Mapped[str] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    header_mapping: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[BankImportSessionStatus] = mapped_column(
        Enum(BankImportSessionStatus), nullable=False
    )
    imported_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class BankImportRow(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bank_import_rows"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    bank_import_session_id: Mapped[str] = mapped_column(
        ForeignKey("bank_import_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[BankImportRowStatus] = mapped_column(Enum(BankImportRowStatus), nullable=False)
