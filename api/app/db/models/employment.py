from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    EmploymentAssetStatus,
    EmploymentEngagementType,
    EmploymentReimbursementStatus,
    EmploymentStatus,
    EmploymentWorkerKind,
    RemunerationBasis,
    WorkRightsBasis,
    WorkRightsStatus,
)
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class EmploymentWorker(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_workers"
    __table_args__ = (UniqueConstraint("company_id", "worker_code", name="uq_employment_worker_code"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    worker_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    worker_kind: Mapped[EmploymentWorkerKind] = mapped_column(Enum(EmploymentWorkerKind), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(320))
    primary_phone: Mapped[str | None] = mapped_column(String(64))
    address_summary: Mapped[str | None] = mapped_column(Text)
    emergency_contact_summary: Mapped[str | None] = mapped_column(Text)
    privacy_note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    engagements: Mapped[list["EmploymentEngagement"]] = relationship(back_populates="worker", cascade="all, delete-orphan")
    work_rights_records: Mapped[list["EmploymentWorkRightsRecord"]] = relationship(back_populates="worker", cascade="all, delete-orphan")
    reimbursements: Mapped[list["EmploymentReimbursementItem"]] = relationship(back_populates="worker", cascade="all, delete-orphan")
    issued_assets: Mapped[list["EmploymentIssuedAsset"]] = relationship(back_populates="worker", cascade="all, delete-orphan")


class EmploymentEngagement(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_engagements"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    worker_id: Mapped[str] = mapped_column(ForeignKey("employment_workers.id", ondelete="CASCADE"), nullable=False)
    engagement_type: Mapped[EmploymentEngagementType] = mapped_column(Enum(EmploymentEngagementType), nullable=False)
    employment_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    expected_end_date: Mapped[date | None] = mapped_column(nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(nullable=True)
    department: Mapped[str | None] = mapped_column(String(128))
    role_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manager_name: Mapped[str | None] = mapped_column(String(255))
    primary_work_location: Mapped[str | None] = mapped_column(String(255))
    pay_cycle_reference: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[EmploymentStatus] = mapped_column(Enum(EmploymentStatus), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    worker: Mapped[EmploymentWorker] = relationship(back_populates="engagements")
    work_rights_records: Mapped[list["EmploymentWorkRightsRecord"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    compensation_profiles: Mapped[list["EmploymentCompensationProfile"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    leave_snapshots: Mapped[list["EmploymentLeaveSnapshot"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")


class EmploymentWorkRightsRecord(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_work_rights_records"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    worker_id: Mapped[str] = mapped_column(ForeignKey("employment_workers.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[str | None] = mapped_column(ForeignKey("employment_engagements.id", ondelete="CASCADE"))
    work_rights_basis: Mapped[WorkRightsBasis] = mapped_column(Enum(WorkRightsBasis), nullable=False)
    review_status: Mapped[WorkRightsStatus] = mapped_column(Enum(WorkRightsStatus), nullable=False)
    visa_subclass: Mapped[str | None] = mapped_column(String(64))
    visa_label: Mapped[str | None] = mapped_column(String(255))
    visa_grant_date: Mapped[date | None] = mapped_column(nullable=True)
    visa_expiry_date: Mapped[date | None] = mapped_column(nullable=True)
    work_condition_summary: Mapped[str | None] = mapped_column(Text)
    hours_restriction_summary: Mapped[str | None] = mapped_column(Text)
    sponsorship_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sponsoring_entity_note: Mapped[str | None] = mapped_column(Text)
    vevo_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_review_due_at: Mapped[date | None] = mapped_column(nullable=True)
    reviewer_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    worker: Mapped[EmploymentWorker] = relationship(back_populates="work_rights_records")
    engagement: Mapped[EmploymentEngagement | None] = relationship(back_populates="work_rights_records")


class EmploymentCompensationProfile(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_compensation_profiles"
    __table_args__ = (UniqueConstraint("engagement_id", name="uq_employment_compensation_engagement"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("employment_engagements.id", ondelete="CASCADE"), nullable=False)
    remuneration_basis: Mapped[RemunerationBasis] = mapped_column(Enum(RemunerationBasis), nullable=False)
    expected_base_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax_profile: Mapped[str | None] = mapped_column(String(64))
    superannuation_category: Mapped[str | None] = mapped_column(String(64))
    workers_comp_category: Mapped[str | None] = mapped_column(String(64))
    payroll_tax_in_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    leave_profile: Mapped[str | None] = mapped_column(String(64))
    reimbursement_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asset_issue_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expense_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    liability_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    tfn_declaration_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    super_choice_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abn_provided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gst_registered_known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    engagement: Mapped[EmploymentEngagement] = relationship(back_populates="compensation_profiles")


class EmploymentLeaveSnapshot(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_leave_snapshots"
    __table_args__ = (
        UniqueConstraint("engagement_id", "snapshot_date", name="uq_employment_leave_snapshot_date"),
        CheckConstraint("annual_leave_hours >= 0", name="ck_employment_leave_annual_non_negative"),
        CheckConstraint("personal_leave_hours >= 0", name="ck_employment_leave_personal_non_negative"),
        CheckConstraint("long_service_leave_hours >= 0", name="ck_employment_leave_lsl_non_negative"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("employment_engagements.id", ondelete="CASCADE"), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(nullable=False)
    annual_leave_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    personal_leave_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    long_service_leave_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    leave_value_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    current_lsl_value_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    non_current_lsl_value_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    engagement: Mapped[EmploymentEngagement] = relationship(back_populates="leave_snapshots")


class EmploymentReimbursementItem(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_reimbursement_items"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_employment_reimbursement_amount_non_negative"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    worker_id: Mapped[str] = mapped_column(ForeignKey("employment_workers.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[str | None] = mapped_column(ForeignKey("employment_engagements.id", ondelete="SET NULL"))
    reimbursement_date: Mapped[date] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[EmploymentReimbursementStatus] = mapped_column(Enum(EmploymentReimbursementStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    worker: Mapped[EmploymentWorker] = relationship(back_populates="reimbursements")


class EmploymentIssuedAsset(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employment_issued_assets"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    worker_id: Mapped[str] = mapped_column(ForeignKey("employment_workers.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[str | None] = mapped_column(ForeignKey("employment_engagements.id", ondelete="SET NULL"))
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str | None] = mapped_column(String(64))
    serial_number: Mapped[str | None] = mapped_column(String(128))
    assigned_on: Mapped[date] = mapped_column(nullable=False)
    due_back_on: Mapped[date | None] = mapped_column(nullable=True)
    returned_on: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[EmploymentAssetStatus] = mapped_column(Enum(EmploymentAssetStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    worker: Mapped[EmploymentWorker] = relationship(back_populates="issued_assets")