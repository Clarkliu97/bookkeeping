from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import BasFrequency, BasReportingBasis, PeriodLockPolicy, SelfApprovalMode
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


if TYPE_CHECKING:
    from app.db.models.auth import UserCompanyAccess


class Company(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(255))
    abn: Mapped[str | None] = mapped_column(String(32))
    acn: Mapped[str | None] = mapped_column(String(32))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD")
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="AU")

    configuration_versions: Mapped[list["CompanyConfigurationVersion"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    user_accesses: Mapped[list["UserCompanyAccess"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )


class CompanyConfigurationVersion(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company_configuration_versions"
    __table_args__ = (UniqueConstraint("company_id", "version_number", name="uq_company_config_version"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(nullable=False)
    effective_to: Mapped[date | None] = mapped_column(nullable=True)
    gst_registered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    bas_frequency: Mapped[BasFrequency] = mapped_column(Enum(BasFrequency), nullable=False)
    bas_reporting_basis: Mapped[BasReportingBasis] = mapped_column(
        Enum(BasReportingBasis),
        nullable=False,
    )
    financial_year_start_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    financial_year_start_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    allow_self_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    self_approval_mode: Mapped[SelfApprovalMode] = mapped_column(
        Enum(SelfApprovalMode),
        nullable=False,
        default=SelfApprovalMode.WARN,
    )
    period_lock_policy: Mapped[PeriodLockPolicy] = mapped_column(
        Enum(PeriodLockPolicy),
        nullable=False,
        default=PeriodLockPolicy.AFTER_APPROVAL,
    )
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    company: Mapped[Company] = relationship(back_populates="configuration_versions")
