from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.db.models.enums import (
    AccountType,
    EmploymentAssetStatus,
    EmploymentEngagementType,
    EmploymentReimbursementStatus,
    EmploymentStatus,
    EmploymentWorkerKind,
    RemunerationBasis,
    ReportingCategoryType,
    TaxInputOutputType,
    WorkRightsBasis,
    WorkRightsStatus,
)
from app.schemas.common import UserRead


class BootstrapUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    is_superuser: bool = False


class UpdateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_superuser: bool = False
    is_active: bool = True


class GrantCompanyAccessRequest(BaseModel):
    user_id: UUID
    can_prepare: bool = False
    can_review: bool = False
    can_approve: bool = False
    can_administer: bool = False


class CompanyAccessUpdateRequest(BaseModel):
    can_prepare: bool = False
    can_review: bool = False
    can_approve: bool = False
    can_administer: bool = False


class CompanyConfigurationCreate(BaseModel):
    effective_from: date
    effective_to: date | None = None
    gst_registered: bool
    bas_frequency: str
    bas_reporting_basis: str
    financial_year_start_month: int = Field(ge=1, le=12)
    financial_year_start_day: int = Field(ge=1, le=31)
    allow_self_approval: bool = False
    self_approval_mode: str
    period_lock_policy: str


class CompanyCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trading_name: str | None = None
    abn: str | None = None
    acn: str | None = None
    entity_type: str = Field(min_length=1, max_length=64)
    initial_configuration: CompanyConfigurationCreate


class CompanyUpdate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trading_name: str | None = None
    abn: str | None = None
    acn: str | None = None
    entity_type: str = Field(min_length=1, max_length=64)
    is_active: bool = True
    base_currency: str = Field(default="AUD", min_length=3, max_length=3)
    country_code: str = Field(default="AU", min_length=2, max_length=2)


class CompanyConfigurationUpdate(CompanyConfigurationCreate):
    pass


class ReportingCategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    is_active: bool = True
    category_type: ReportingCategoryType


class ReportingCategoryUpdate(ReportingCategoryCreate):
    pass


class TaxCodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    rate: Decimal
    is_gst_applicable: bool = True
    is_active: bool = True
    bas_label: str | None = None
    input_output_type: TaxInputOutputType


class TaxCodeUpdate(TaxCodeCreate):
    pass


class AccountCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    account_type: AccountType
    reporting_category_id: UUID | None = None
    default_tax_code_id: UUID | None = None
    is_active: bool = True
    allow_manual_posting: bool = True


class AccountUpdate(AccountCreate):
    pass


class AccountingPeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    period_type: str
    start_date: date
    end_date: date


class AccountingPeriodUpdate(AccountingPeriodCreate):
    pass


class EmploymentWorkerCreate(BaseModel):
    worker_code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    worker_kind: EmploymentWorkerKind
    date_of_birth: date | None = None
    primary_email: EmailStr | None = None
    primary_phone: str | None = Field(default=None, max_length=64)
    address_summary: str | None = None
    emergency_contact_summary: str | None = None
    privacy_note: str | None = None
    is_active: bool = True
    note: str | None = None


class EmploymentWorkerUpdate(EmploymentWorkerCreate):
    pass


class EmploymentEngagementCreate(BaseModel):
    engagement_type: EmploymentEngagementType
    employment_basis: str = Field(min_length=1, max_length=64)
    start_date: date
    expected_end_date: date | None = None
    actual_end_date: date | None = None
    department: str | None = Field(default=None, max_length=128)
    role_name: str = Field(min_length=1, max_length=255)
    manager_name: str | None = Field(default=None, max_length=255)
    primary_work_location: str | None = Field(default=None, max_length=255)
    pay_cycle_reference: str | None = Field(default=None, max_length=64)
    status: EmploymentStatus
    status_reason: str | None = None
    note: str | None = None


class EmploymentEngagementUpdate(EmploymentEngagementCreate):
    pass


class EmploymentWorkRightsCreate(BaseModel):
    engagement_id: UUID | None = None
    work_rights_basis: WorkRightsBasis
    review_status: WorkRightsStatus
    visa_subclass: str | None = Field(default=None, max_length=64)
    visa_label: str | None = Field(default=None, max_length=255)
    visa_grant_date: date | None = None
    visa_expiry_date: date | None = None
    work_condition_summary: str | None = None
    hours_restriction_summary: str | None = None
    sponsorship_required: bool = False
    sponsoring_entity_note: str | None = None
    vevo_checked_at: date | None = None
    next_review_due_at: date | None = None
    reviewer_user_id: UUID | None = None
    review_note: str | None = None


class EmploymentWorkRightsUpdate(EmploymentWorkRightsCreate):
    pass


class EmploymentCompensationCreate(BaseModel):
    remuneration_basis: RemunerationBasis
    expected_base_amount: Decimal | None = None
    tax_profile: str | None = Field(default=None, max_length=64)
    superannuation_category: str | None = Field(default=None, max_length=64)
    workers_comp_category: str | None = Field(default=None, max_length=64)
    payroll_tax_in_scope: bool = False
    leave_profile: str | None = Field(default=None, max_length=64)
    reimbursement_allowed: bool = False
    asset_issue_allowed: bool = False
    expense_account_id: UUID | None = None
    liability_account_id: UUID | None = None
    tfn_declaration_received: bool = False
    super_choice_received: bool = False
    abn_provided: bool = False
    gst_registered_known: bool = False
    note: str | None = None


class EmploymentCompensationUpdate(EmploymentCompensationCreate):
    pass


class EmploymentLeaveSnapshotCreate(BaseModel):
    snapshot_date: date
    annual_leave_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    personal_leave_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    long_service_leave_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    leave_value_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    current_lsl_value_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    non_current_lsl_value_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    note: str | None = None
    reviewed_by_user_id: UUID | None = None


class EmploymentLeaveSnapshotUpdate(EmploymentLeaveSnapshotCreate):
    pass


class EmploymentReimbursementCreate(BaseModel):
    engagement_id: UUID | None = None
    reimbursement_date: date
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(ge=Decimal("0.00"))
    status: EmploymentReimbursementStatus
    note: str | None = None


class EmploymentReimbursementUpdate(EmploymentReimbursementCreate):
    pass


class EmploymentIssuedAssetCreate(BaseModel):
    engagement_id: UUID | None = None
    asset_name: str = Field(min_length=1, max_length=255)
    asset_type: str | None = Field(default=None, max_length=64)
    serial_number: str | None = Field(default=None, max_length=128)
    assigned_on: date
    due_back_on: date | None = None
    returned_on: date | None = None
    status: EmploymentAssetStatus
    note: str | None = None


class EmploymentIssuedAssetUpdate(EmploymentIssuedAssetCreate):
    pass


class PeriodActionRequest(BaseModel):
    note: str | None = None
    reason: str | None = None


class JournalLineCreate(BaseModel):
    account_id: UUID
    description: str | None = None
    debit_amount: Decimal = Decimal("0.00")
    credit_amount: Decimal = Decimal("0.00")
    tax_code_id: UUID | None = None
    reporting_category_id: UUID | None = None
    source_document_reference: str | None = None


class JournalEntryCreate(BaseModel):
    entry_date: date
    accounting_period_id: UUID
    source_type: str
    description: str = Field(min_length=1)
    reference: str | None = None
    lines: list[JournalLineCreate] = Field(min_length=2)


class JournalEntryUpdate(JournalEntryCreate):
    pass


class JournalRecommendationAcceptRequest(BaseModel):
    accepted_proposal_ids: list[UUID] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class BootstrapResponse(BaseModel):
    user: UserRead
    access_token: str
    token_type: str = "bearer"


class DocumentLinkCreate(BaseModel):
    entity_type: str
    entity_id: UUID
    note: str | None = None


class JournalEvidenceLinkCreate(BaseModel):
    note: str | None = None


class DocumentUpdate(BaseModel):
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: str | None = Field(default=None, max_length=255)


class DocumentLinkUpdate(DocumentLinkCreate):
    pass


class BankAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    bank_name: str | None = Field(default=None, max_length=120)
    bsb: str | None = Field(default=None, max_length=16)
    account_number_masked: str | None = Field(default=None, max_length=32)
    is_active: bool = True


class BankAccountUpdate(BankAccountCreate):
    pass


class BankImportSessionUpdate(BaseModel):
    note: str | None = None


class ReconciliationSessionCreate(BaseModel):
    bank_account_id: UUID
    accounting_period_id: UUID | None = None
    note: str | None = None


class ReconciliationSessionUpdate(BaseModel):
    accounting_period_id: UUID | None = None
    note: str | None = None


class ReconciliationMatchRequest(BaseModel):
    matched_journal_entry_id: UUID
    note: str | None = None


class BasPeriodGenerateRequest(BaseModel):
    start_date: date
    end_date: date


class BasRunCreate(BaseModel):
    bas_period_id: UUID


class BasPeriodUpdate(BaseModel):
    note: str | None = None


class BasRunUpdate(BasRunCreate):
    pass


class BasAdjustmentCreate(BaseModel):
    label: str = Field(min_length=1, max_length=32)
    amount: Decimal
    note: str = Field(min_length=1)


class BasAdjustmentUpdate(BasAdjustmentCreate):
    pass


class BasReviewNoteCreate(BaseModel):
    severity: str = Field(min_length=1, max_length=16)
    message: str = Field(min_length=1)
    related_label: str | None = Field(default=None, max_length=32)


class BasReviewNoteUpdate(BasReviewNoteCreate):
    pass


class FixedAssetCreate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    acquisition_date: date
    in_service_date: date
    cost_amount: Decimal = Field(gt=Decimal("0.00"))
    salvage_value: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    useful_life_months: int = Field(ge=1, le=600)
    depreciation_method: str
    diminishing_value_rate: Decimal | None = Field(default=None, gt=Decimal("0.00"), le=Decimal("1.00"))
    asset_account_id: UUID
    accumulated_depreciation_account_id: UUID
    depreciation_expense_account_id: UUID
    acquisition_reference: str | None = Field(default=None, max_length=128)
    note: str | None = None


class FixedAssetUpdate(FixedAssetCreate):
    pass


class FixedAssetDisposeRequest(BaseModel):
    disposal_date: date
    disposal_reference: str | None = Field(default=None, max_length=128)
    disposal_note: str | None = None
    disposal_proceeds: Decimal | None = Field(default=None, ge=Decimal("0.00"))


class DepreciationRunCreate(BaseModel):
    accounting_period_id: UUID
    start_date: date
    end_date: date
    note: str | None = None


class DepreciationRunUpdate(DepreciationRunCreate):
    pass


class TaxWorkpaperPackCreate(BaseModel):
    accounting_period_id: UUID
    note: str | None = None


class TaxWorkpaperPackUpdate(TaxWorkpaperPackCreate):
    pass


class TaxWorkpaperAdjustmentCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    amount: Decimal
    note: str = Field(min_length=1)


class TaxWorkpaperAdjustmentUpdate(TaxWorkpaperAdjustmentCreate):
    pass


class TaxWorkpaperNoteCreate(BaseModel):
    note_type: str
    message: str = Field(min_length=1)


class TaxWorkpaperNoteUpdate(TaxWorkpaperNoteCreate):
    pass


class TaxWorkpaperExceptionCreate(BaseModel):
    severity: str = Field(min_length=1, max_length=16)
    message: str = Field(min_length=1)


class TaxWorkpaperExceptionUpdate(TaxWorkpaperExceptionCreate):
    pass


class TaxWorkpaperExceptionResolveRequest(BaseModel):
    note: str = Field(min_length=1)

