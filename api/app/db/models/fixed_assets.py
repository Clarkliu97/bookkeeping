from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import DepreciationMethod, DepreciationRunStatus, FixedAssetStatus
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class FixedAsset(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fixed_assets"
    __table_args__ = (
        UniqueConstraint("company_id", "asset_code", name="uq_fixed_asset_code"),
        CheckConstraint("cost_amount > 0", name="ck_fixed_asset_positive_cost"),
        CheckConstraint("salvage_value >= 0", name="ck_fixed_asset_non_negative_salvage"),
        CheckConstraint("salvage_value <= cost_amount", name="ck_fixed_asset_salvage_lte_cost"),
        CheckConstraint("useful_life_months > 0", name="ck_fixed_asset_useful_life_positive"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    asset_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    acquisition_date: Mapped[date] = mapped_column(nullable=False)
    in_service_date: Mapped[date] = mapped_column(nullable=False)
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    depreciation_method: Mapped[DepreciationMethod] = mapped_column(Enum(DepreciationMethod), nullable=False)
    diminishing_value_rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    asset_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    accumulated_depreciation_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    depreciation_expense_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    status: Mapped[FixedAssetStatus] = mapped_column(Enum(FixedAssetStatus), nullable=False, default=FixedAssetStatus.ACTIVE)
    disposal_date: Mapped[date | None] = mapped_column(nullable=True)
    disposal_reference: Mapped[str | None] = mapped_column(String(128))
    disposal_note: Mapped[str | None] = mapped_column(Text)
    disposal_proceeds: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    acquisition_reference: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    status_history: Mapped[list["FixedAssetStatusHistory"]] = relationship(
        back_populates="fixed_asset",
        cascade="all, delete-orphan",
    )
    run_lines: Mapped[list["DepreciationRunLine"]] = relationship(back_populates="fixed_asset")


class FixedAssetStatusHistory(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fixed_asset_status_history"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    fixed_asset_id: Mapped[str] = mapped_column(ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[FixedAssetStatus | None] = mapped_column(Enum(FixedAssetStatus))
    to_status: Mapped[FixedAssetStatus] = mapped_column(Enum(FixedAssetStatus), nullable=False)
    effective_date: Mapped[date] = mapped_column(nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    changed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    fixed_asset: Mapped[FixedAsset] = relationship(back_populates="status_history")


class DepreciationRun(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "depreciation_runs"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "accounting_period_id",
            "start_date",
            "end_date",
            name="uq_depreciation_run_range",
        ),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    accounting_period_id: Mapped[str] = mapped_column(ForeignKey("accounting_periods.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[DepreciationRunStatus] = mapped_column(Enum(DepreciationRunStatus), nullable=False)
    journal_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id"))
    generated_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    posted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["DepreciationRunLine"]] = relationship(
        back_populates="depreciation_run",
        cascade="all, delete-orphan",
    )


class DepreciationRunLine(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "depreciation_run_lines"
    __table_args__ = (UniqueConstraint("depreciation_run_id", "fixed_asset_id", name="uq_depreciation_run_asset"),)

    depreciation_run_id: Mapped[str] = mapped_column(
        ForeignKey("depreciation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    fixed_asset_id: Mapped[str] = mapped_column(ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False)
    depreciation_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    accumulated_depreciation_opening: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    accumulated_depreciation_closing: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    carrying_amount_opening: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    carrying_amount_closing: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    depreciation_run: Mapped[DepreciationRun] = relationship(back_populates="lines")
    fixed_asset: Mapped[FixedAsset] = relationship(back_populates="run_lines")
