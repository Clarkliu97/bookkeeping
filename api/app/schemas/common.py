from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRead(ORMModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CompanyAccessRead(ORMModel):
    user_id: UUID
    company_id: UUID
    can_prepare: bool
    can_review: bool
    can_approve: bool
    can_administer: bool
    created_at: datetime
    updated_at: datetime


class RoleRead(ORMModel):
    id: UUID
    code: str
    name: str
    description: str | None


class CompanyRead(ORMModel):
    id: UUID
    legal_name: str
    trading_name: str | None
    abn: str | None
    acn: str | None
    entity_type: str
    is_active: bool
    base_currency: str
    country_code: str
    created_at: datetime
    updated_at: datetime


class ConfigurationVersionRead(ORMModel):
    id: UUID
    company_id: UUID
    version_number: int
    effective_from: date
    effective_to: date | None
    gst_registered: bool
    bas_frequency: str
    bas_reporting_basis: str
    financial_year_start_month: int
    financial_year_start_day: int
    allow_self_approval: bool
    self_approval_mode: str
    period_lock_policy: str
    created_by_user_id: UUID
    created_at: datetime


class ReportingCategoryRead(ORMModel):
    id: UUID
    company_id: UUID | None
    code: str
    name: str
    is_active: bool
    category_type: str


class TaxCodeRead(ORMModel):
    id: UUID
    company_id: UUID | None
    code: str
    name: str
    description: str | None
    rate: Decimal
    is_gst_applicable: bool
    is_active: bool
    bas_label: str | None
    input_output_type: str


class AccountRead(ORMModel):
    id: UUID
    company_id: UUID
    account_code: str
    name: str
    account_type: str
    reporting_category_id: UUID | None
    default_tax_code_id: UUID | None
    is_active: bool
    allow_manual_posting: bool
    created_at: datetime
    updated_at: datetime


class AccountingPeriodRead(ORMModel):
    id: UUID
    company_id: UUID
    name: str
    period_type: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    updated_at: datetime


class EmploymentWorkerRead(ORMModel):
    id: UUID
    company_id: UUID
    worker_code: str
    display_name: str
    legal_name: str | None
    worker_kind: str
    date_of_birth: date | None
    primary_email: str | None
    primary_phone: str | None
    address_summary: str | None
    emergency_contact_summary: str | None
    privacy_note: str | None
    is_active: bool
    note: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmploymentEngagementRead(ORMModel):
    id: UUID
    company_id: UUID
    worker_id: UUID
    engagement_type: str
    employment_basis: str
    start_date: date
    expected_end_date: date | None
    actual_end_date: date | None
    department: str | None
    role_name: str
    manager_name: str | None
    primary_work_location: str | None
    pay_cycle_reference: str | None
    status: str
    status_reason: str | None
    note: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmploymentWorkRightsRead(ORMModel):
    id: UUID
    company_id: UUID
    worker_id: UUID
    engagement_id: UUID | None
    work_rights_basis: str
    review_status: str
    visa_subclass: str | None
    visa_label: str | None
    visa_grant_date: date | None
    visa_expiry_date: date | None
    work_condition_summary: str | None
    hours_restriction_summary: str | None
    sponsorship_required: bool
    sponsoring_entity_note: str | None
    vevo_checked_at: datetime | None
    next_review_due_at: date | None
    reviewer_user_id: UUID | None
    review_note: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmploymentCompensationRead(ORMModel):
    id: UUID
    company_id: UUID
    engagement_id: UUID
    remuneration_basis: str
    expected_base_amount: Decimal | None
    tax_profile: str | None
    superannuation_category: str | None
    workers_comp_category: str | None
    payroll_tax_in_scope: bool
    leave_profile: str | None
    reimbursement_allowed: bool
    asset_issue_allowed: bool
    expense_account_id: UUID | None
    liability_account_id: UUID | None
    tfn_declaration_received: bool
    super_choice_received: bool
    abn_provided: bool
    gst_registered_known: bool
    note: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmploymentLeaveSnapshotRead(ORMModel):
    id: UUID
    company_id: UUID
    engagement_id: UUID
    snapshot_date: date
    annual_leave_hours: Decimal
    personal_leave_hours: Decimal
    long_service_leave_hours: Decimal
    leave_value_amount: Decimal
    current_lsl_value_amount: Decimal
    non_current_lsl_value_amount: Decimal
    note: str | None
    reviewed_by_user_id: UUID | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmploymentReimbursementRead(ORMModel):
    id: UUID
    company_id: UUID
    worker_id: UUID
    engagement_id: UUID | None
    reimbursement_date: date
    description: str
    amount: Decimal
    status: str
    note: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmploymentIssuedAssetRead(ORMModel):
    id: UUID
    company_id: UUID
    worker_id: UUID
    engagement_id: UUID | None
    asset_name: str
    asset_type: str | None
    serial_number: str | None
    assigned_on: date
    due_back_on: date | None
    returned_on: date | None
    status: str
    note: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmploymentLinkedDocumentRead(BaseModel):
    link_id: UUID
    document_id: UUID
    original_filename: str
    media_type: str | None
    byte_size: int
    note: str | None
    linked_at: datetime


class EmploymentQueueItemRead(BaseModel):
    worker_id: UUID
    worker_name: str
    engagement_id: UUID | None
    title: str
    status: str
    due_date: date | None
    detail: str | None


class EmploymentDashboardRead(BaseModel):
    total_workers: int
    active_engagements: int
    onboarding_count: int
    expiring_work_rights_count: int
    missing_document_count: int
    onboarding_items: list[EmploymentQueueItemRead]
    work_rights_due_items: list[EmploymentQueueItemRead]
    finalization_items: list[EmploymentQueueItemRead]


class EmploymentWorkerDetailRead(EmploymentWorkerRead):
    engagements: list[EmploymentEngagementRead]
    work_rights_records: list[EmploymentWorkRightsRead]
    compensation_profiles: list[EmploymentCompensationRead]
    leave_snapshots: list[EmploymentLeaveSnapshotRead]
    reimbursements: list[EmploymentReimbursementRead]
    issued_assets: list[EmploymentIssuedAssetRead]
    linked_documents: list[EmploymentLinkedDocumentRead]


class EmploymentHeadcountLineRead(BaseModel):
    worker_id: UUID
    worker_name: str
    worker_kind: str
    engagement_id: UUID
    engagement_type: str
    status: str
    department: str | None
    role_name: str
    start_date: date
    expected_end_date: date | None
    actual_end_date: date | None


class EmploymentHeadcountReportRead(BaseModel):
    generated_at: datetime
    total_workers: int
    active_engagements: int
    contractor_engagements: int
    rows: list[EmploymentHeadcountLineRead]


class EmploymentWorkRightsReportLineRead(BaseModel):
    worker_id: UUID
    worker_name: str
    engagement_id: UUID | None
    review_status: str
    work_rights_basis: str
    visa_label: str | None
    visa_expiry_date: date | None
    next_review_due_at: date | None
    restriction_summary: str | None


class EmploymentWorkRightsReportRead(BaseModel):
    generated_at: datetime
    rows: list[EmploymentWorkRightsReportLineRead]


class EmploymentLeaveLiabilityLineRead(BaseModel):
    worker_id: UUID
    worker_name: str
    engagement_id: UUID
    engagement_status: str
    snapshot_date: date
    annual_leave_hours: Decimal
    long_service_leave_hours: Decimal
    leave_value_amount: Decimal
    current_lsl_value_amount: Decimal
    non_current_lsl_value_amount: Decimal


class EmploymentLeaveLiabilityReportRead(BaseModel):
    generated_at: datetime
    rows: list[EmploymentLeaveLiabilityLineRead]


class EmploymentContractorReviewLineRead(BaseModel):
    worker_id: UUID
    worker_name: str
    engagement_id: UUID
    engagement_type: str
    status: str
    remuneration_basis: str | None
    abn_provided: bool | None
    gst_registered_known: bool | None
    payroll_tax_in_scope: bool | None
    note: str | None


class EmploymentContractorReviewReportRead(BaseModel):
    generated_at: datetime
    rows: list[EmploymentContractorReviewLineRead]


class ApprovalActionRead(ORMModel):
    id: UUID
    company_id: UUID
    entity_type: str
    entity_id: str
    action_type: str
    prepared_by_user_id: UUID | None
    approved_by_user_id: UUID | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class JournalLineRead(ORMModel):
    id: UUID
    journal_entry_id: UUID
    line_number: int
    account_id: UUID
    description: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    tax_code_id: UUID | None
    reporting_category_id: UUID | None
    source_document_reference: str | None
    created_at: datetime
    updated_at: datetime


class JournalEntryRead(ORMModel):
    id: UUID
    company_id: UUID
    entry_number: str
    entry_date: date
    accounting_period_id: UUID
    status: str
    source_type: str
    description: str
    reference: str | None
    currency_code: str
    posted_at: datetime | None
    posted_by_user_id: UUID | None
    reversal_of_entry_id: UUID | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    lines: list[JournalLineRead]


class TrialBalanceRow(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal


class FinancialReportLine(BaseModel):
    account_id: UUID | None = None
    account_code: str
    account_name: str
    account_type: str
    amount: Decimal


class TrialBalanceReportRead(BaseModel):
    start_date: date | None
    end_date: date | None
    rows: list[TrialBalanceRow]


class ProfitAndLossReportRead(BaseModel):
    start_date: date
    end_date: date
    income_lines: list[FinancialReportLine]
    expense_lines: list[FinancialReportLine]
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal


class BalanceSheetReportRead(BaseModel):
    as_of_date: date
    asset_lines: list[FinancialReportLine]
    liability_lines: list[FinancialReportLine]
    equity_lines: list[FinancialReportLine]
    current_earnings: FinancialReportLine
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    total_liabilities_and_equity: Decimal


class GeneralLedgerEntryRead(BaseModel):
    journal_entry_id: UUID
    entry_number: str
    journal_status: str
    entry_date: date
    line_number: int
    journal_description: str
    line_description: str | None
    reference: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    running_balance: Decimal


class GeneralLedgerAccountRead(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    opening_balance: Decimal
    closing_balance: Decimal
    entries: list[GeneralLedgerEntryRead]


class GeneralLedgerReportRead(BaseModel):
    start_date: date
    end_date: date
    accounts: list[GeneralLedgerAccountRead]


class FixedAssetStatusHistoryRead(ORMModel):
    id: UUID
    company_id: UUID
    fixed_asset_id: UUID
    from_status: str | None
    to_status: str
    effective_date: date
    note: str | None
    changed_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class FixedAssetRead(ORMModel):
    id: UUID
    company_id: UUID
    asset_code: str
    name: str
    description: str | None
    acquisition_date: date
    in_service_date: date
    cost_amount: Decimal
    salvage_value: Decimal
    useful_life_months: int
    depreciation_method: str
    diminishing_value_rate: Decimal | None
    asset_account_id: UUID
    accumulated_depreciation_account_id: UUID
    depreciation_expense_account_id: UUID
    status: str
    disposal_date: date | None
    disposal_reference: str | None
    disposal_note: str | None
    disposal_proceeds: Decimal | None
    acquisition_reference: str | None
    note: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class FixedAssetScheduleLine(BaseModel):
    fixed_asset_id: UUID
    asset_code: str
    asset_name: str
    status: str
    depreciation_method: str
    run_amount: Decimal
    accumulated_depreciation_opening: Decimal
    accumulated_depreciation_closing: Decimal
    carrying_amount_opening: Decimal
    carrying_amount_closing: Decimal


class FixedAssetDetailRead(FixedAssetRead):
    accumulated_depreciation: Decimal
    carrying_amount: Decimal
    history: list[FixedAssetStatusHistoryRead]


class DepreciationRunLineRead(ORMModel):
    id: UUID
    depreciation_run_id: UUID
    fixed_asset_id: UUID
    depreciation_amount: Decimal
    accumulated_depreciation_opening: Decimal
    accumulated_depreciation_closing: Decimal
    carrying_amount_opening: Decimal
    carrying_amount_closing: Decimal
    created_at: datetime
    updated_at: datetime


class DepreciationRunRead(ORMModel):
    id: UUID
    company_id: UUID
    accounting_period_id: UUID
    start_date: date
    end_date: date
    status: str
    journal_entry_id: UUID | None
    generated_by_user_id: UUID
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class DepreciationRunDetailRead(DepreciationRunRead):
    total_depreciation_amount: Decimal
    lines: list[DepreciationRunLineRead]


class FixedAssetRegisterRead(BaseModel):
    as_of_date: date
    assets: list[FixedAssetDetailRead]


class TaxWorkpaperAccountingProfitSchedule(BaseModel):
    start_date: date
    end_date: date
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal


class TaxWorkpaperGstReconciliationLine(BaseModel):
    label: str
    final_amount: Decimal
    run_count: int


class TaxWorkpaperFixedAssetLine(BaseModel):
    asset_code: str
    asset_name: str
    status: str
    depreciation_method: str
    accumulated_depreciation: Decimal
    carrying_amount: Decimal


class TaxAdjustmentRead(ORMModel):
    id: UUID
    company_id: UUID
    tax_workpaper_pack_id: UUID
    label: str
    amount: Decimal
    note: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class TaxWorkpaperNoteRead(ORMModel):
    id: UUID
    company_id: UUID
    tax_workpaper_pack_id: UUID
    note_type: str
    message: str
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class TaxWorkpaperExceptionItemRead(ORMModel):
    id: UUID
    company_id: UUID
    tax_workpaper_pack_id: UUID
    severity: str
    message: str
    status: str
    resolution_note: str | None
    created_by_user_id: UUID | None
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaxWorkpaperExportRead(ORMModel):
    id: UUID
    company_id: UUID
    tax_workpaper_pack_id: UUID
    format: str
    document_id: UUID
    exported_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class TaxWorkpaperPackRead(ORMModel):
    id: UUID
    company_id: UUID
    accounting_period_id: UUID
    status: str
    schedule_snapshot: dict
    generated_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: date | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class TaxWorkpaperPackDetailRead(TaxWorkpaperPackRead):
    accounting_profit_schedule: TaxWorkpaperAccountingProfitSchedule
    gst_reconciliation_lines: list[TaxWorkpaperGstReconciliationLine]
    fixed_asset_lines: list[TaxWorkpaperFixedAssetLine]
    total_adjustments: Decimal
    taxable_income: Decimal
    tax_adjustments: list[TaxAdjustmentRead]
    review_notes: list[TaxWorkpaperNoteRead]
    sign_off_notes: list[TaxWorkpaperNoteRead]
    exception_items: list[TaxWorkpaperExceptionItemRead]
    exports: list[TaxWorkpaperExportRead]



class DocumentRead(ORMModel):
    id: UUID
    company_id: UUID
    original_filename: str
    stored_filename: str
    media_type: str | None
    byte_size: int
    checksum_sha256: str
    storage_path: str
    uploaded_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class DocumentLinkRead(ORMModel):
    id: UUID
    company_id: UUID
    document_id: UUID
    entity_type: str
    entity_id: str
    note: str | None
    linked_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class JournalEvidenceRead(BaseModel):
    link_id: UUID
    document_id: UUID
    original_filename: str
    media_type: str | None
    byte_size: int
    uploaded_by_user_id: UUID
    document_created_at: datetime
    note: str | None
    linked_by_user_id: UUID
    linked_at: datetime


class JournalRecommendationModelRead(BaseModel):
    id: str
    label: str
    provider: str
    supports_vision: bool
    reasoning_effort: str | None
    input_cost_per_million_tokens_usd: Decimal
    output_cost_per_million_tokens_usd: Decimal
    estimated_cost_per_1000_calls_usd: Decimal
    estimated_input_tokens_per_call: int
    estimated_output_tokens_per_call: int
    pricing_note: str
    max_file_count: int
    max_file_size_bytes: int
    max_total_size_bytes: int


class JournalRecommendationRunRead(ORMModel):
    id: UUID
    company_id: UUID
    created_by_user_id: UUID
    status: str
    extracted_entry_date: date | None = None
    target_accounting_period_id: UUID | None
    target_journal_entry_id: UUID | None
    accepted_journal_entry_id: UUID | None
    user_context_note: str | None
    analysis_mode: str
    prompt_version: str
    provider_name: str
    provider_model: str
    analysis_summary: str | None
    confidence_summary: str | None
    warning_text: str | None
    failure_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JournalRecommendationRunDocumentRead(BaseModel):
    id: UUID
    document_id: UUID
    display_order: int
    original_filename: str
    media_type: str | None
    byte_size: int
    created_at: datetime


class JournalRecommendationLineRead(ORMModel):
    id: UUID
    recommendation_run_id: UUID
    recommendation_entry_id: UUID | None
    line_number: int
    description: str | None
    explanation: str | None
    suggested_account_id: UUID | None
    suggested_account_code: str | None
    suggested_tax_code_id: UUID | None
    suggested_tax_code_code: str | None
    suggested_reporting_category_id: UUID | None
    suggested_reporting_category_code: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    created_at: datetime
    updated_at: datetime


class JournalRecommendationProposalRead(ORMModel):
    id: UUID
    recommendation_run_id: UUID
    proposal_type: str
    status: str
    suggested_code: str
    suggested_name: str
    suggested_attributes_json: dict | None
    rationale: str | None
    created_entity_id: str | None
    created_at: datetime
    updated_at: datetime


class JournalRecommendationEntryRead(ORMModel):
    id: UUID
    recommendation_run_id: UUID
    sequence_number: int
    summary: str
    entry_date: date | None
    vendor_name: str | None
    total_amount: Decimal | None
    gst_amount: Decimal | None
    currency_code: str
    recommended_description: str
    recommended_reference: str | None
    confidence_summary: str | None
    warning_text: str | None
    accepted_journal_entry_id: UUID | None
    documents: list[JournalRecommendationRunDocumentRead] = []
    lines: list[JournalRecommendationLineRead] = []
    created_at: datetime
    updated_at: datetime


class JournalRecommendationSearchSourceRead(BaseModel):
    title: str | None = None
    url: str
    domain: str | None = None


class JournalRecommendationDetailRead(JournalRecommendationRunRead):
    documents: list[JournalRecommendationRunDocumentRead]
    lines: list[JournalRecommendationLineRead]
    entries: list[JournalRecommendationEntryRead] = []
    proposals: list[JournalRecommendationProposalRead]
    search_sources: list[JournalRecommendationSearchSourceRead] = []


class JournalRecommendationAcceptRead(BaseModel):
    journals: list[JournalEntryRead]


class BankAccountRead(ORMModel):
    id: UUID
    company_id: UUID
    name: str
    bank_name: str | None
    bsb: str | None
    account_number_masked: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BankImportRowRead(ORMModel):
    id: UUID
    company_id: UUID
    bank_import_session_id: UUID
    line_number: int
    transaction_date: date
    description: str
    reference: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    currency_code: str
    raw_data: dict
    fingerprint: str
    status: str
    created_at: datetime
    updated_at: datetime


class BankImportSessionRead(ORMModel):
    id: UUID
    company_id: UUID
    bank_account_id: UUID
    uploaded_document_id: UUID | None
    original_filename: str
    header_mapping: dict | None
    status: str
    imported_by_user_id: UUID
    imported_at: datetime
    note: str | None
    created_at: datetime
    updated_at: datetime


class ReconciliationBankRowRead(ORMModel):
    id: UUID
    line_number: int
    transaction_date: date
    description: str
    reference: str | None
    debit_amount: Decimal
    credit_amount: Decimal
    status: str


class ReconciliationJournalSummaryRead(BaseModel):
    id: UUID
    entry_number: str
    entry_date: date
    description: str
    reference: str | None
    status: str
    debit_total: Decimal
    credit_total: Decimal


class ReconciliationItemRead(ORMModel):
    id: UUID
    company_id: UUID
    reconciliation_session_id: UUID
    bank_import_row_id: UUID
    matched_journal_entry_id: UUID | None
    status: str
    note: str | None
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    bank_row: ReconciliationBankRowRead | None = None
    matched_journal_entry: ReconciliationJournalSummaryRead | None = None


class ReconciliationSessionRead(ORMModel):
    id: UUID
    company_id: UUID
    bank_account_id: UUID
    accounting_period_id: UUID | None
    status: str
    started_by_user_id: UUID
    completed_at: datetime | None
    note: str | None
    created_at: datetime
    updated_at: datetime

    bank_row: ReconciliationBankRowRead | None = None
    matched_journal_entry: ReconciliationJournalSummaryRead | None = None


class ReconciliationSummary(BaseModel):
    total_items: int
    unmatched_items: int
    matched_items: int
    ignored_items: int


class BasPeriodRead(ORMModel):
    id: UUID
    company_id: UUID
    start_date: date
    end_date: date
    status: str
    configuration_version_id: UUID
    note: str | None
    created_at: datetime
    updated_at: datetime


class BasLineResultRead(ORMModel):
    id: UUID
    bas_run_id: UUID
    label: str
    system_amount: Decimal
    adjustment_amount: Decimal
    final_amount: Decimal
    detail_count: int
    created_at: datetime
    updated_at: datetime


class BasAdjustmentRead(ORMModel):
    id: UUID
    company_id: UUID
    bas_run_id: UUID
    label: str
    amount: Decimal
    note: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class BasReviewNoteRead(ORMModel):
    id: UUID
    company_id: UUID
    bas_run_id: UUID
    severity: str
    message: str
    related_label: str | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class BasExportRead(ORMModel):
    id: UUID
    company_id: UUID
    bas_run_id: UUID
    format: str
    document_id: UUID
    exported_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class BasRunRead(ORMModel):
    id: UUID
    company_id: UUID
    bas_period_id: UUID
    status: str
    configuration_version_id: UUID
    configuration_snapshot: dict
    generated_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: date | None
    warning_count: int
    created_at: datetime
    updated_at: datetime


class BasRunDetailRead(BasRunRead):
    line_results: list[BasLineResultRead]
    adjustments: list[BasAdjustmentRead]
    review_notes: list[BasReviewNoteRead]
    exports: list[BasExportRead]
