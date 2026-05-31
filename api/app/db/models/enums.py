from enum import StrEnum


class EntityType(StrEnum):
    COMPANY = "company"
    COMPANY_CONFIGURATION = "company_configuration"
    ACCOUNT = "account"
    ACCOUNTING_PERIOD = "accounting_period"
    JOURNAL_ENTRY = "journal_entry"
    JOURNAL_RECOMMENDATION_RUN = "journal_recommendation_run"
    BAS_RUN = "bas_run"
    EMPLOYMENT_WORKER = "employment_worker"
    FIXED_ASSET = "fixed_asset"
    DEPRECIATION_RUN = "depreciation_run"
    TAX_WORKPAPER_PACK = "tax_workpaper_pack"


class SelfApprovalMode(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


class PeriodLockPolicy(StrEnum):
    MANUAL_ONLY = "manual_only"
    AFTER_APPROVAL = "after_approval"
    AFTER_EXPORT = "after_export"


class BasFrequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    OTHER = "other"


class BasReportingBasis(StrEnum):
    CASH = "cash"
    ACCRUAL = "accrual"


class ReportingCategoryType(StrEnum):
    PNL = "pnl"
    BALANCE_SHEET = "balance_sheet"
    GST = "gst"
    BAS = "bas"
    TAX_SUPPORT = "tax_support"
    OTHER = "other"


class TaxInputOutputType(StrEnum):
    INPUT_TAXED = "input_taxed"
    OUTPUT_TAXED = "output_taxed"
    GST_FREE = "gst_free"
    INPUT_TAX_CREDIT = "input_tax_credit"
    NONE = "none"


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    REVENUE = "revenue"
    EXPENSE = "expense"
    COST_OF_SALES = "cost_of_sales"
    OTHER_INCOME = "other_income"
    OTHER_EXPENSE = "other_expense"
    NON_POSTING = "non_posting"
    CONTRA_ASSET = "contra_asset"
    CONTRA_LIABILITY = "contra_liability"
    CONTRA_INCOME = "contra_income"
    CONTRA_EXPENSE = "contra_expense"


class AccountingPeriodType(StrEnum):
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    LOCKED = "locked"


class JournalStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"
    VOIDED = "voided"


class JournalSourceType(StrEnum):
    MANUAL = "manual"
    OPENING_BALANCE = "opening_balance"
    BANK_IMPORT = "bank_import"
    ADJUSTMENT = "adjustment"
    DEPRECIATION = "depreciation"
    BAS_ADJUSTMENT = "bas_adjustment"
    TAX_ADJUSTMENT = "tax_adjustment"
    SYSTEM = "system"


class ApprovalActionType(StrEnum):
    PREPARED = "prepared"
    SUBMITTED_FOR_REVIEW = "submitted_for_review"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    LOCKED = "locked"
    UNLOCKED = "unlocked"


class EmploymentWorkerKind(StrEnum):
    INDIVIDUAL = "individual"
    ENTITY = "entity"


class EmploymentEngagementType(StrEnum):
    EMPLOYEE = "employee"
    DIRECTOR = "director"
    INDIVIDUAL_CONTRACTOR = "individual_contractor"
    CONTRACTOR_ENTITY = "contractor_entity"
    LABOUR_HIRE = "labour_hire"
    INTERN = "intern"


class EmploymentStatus(StrEnum):
    DRAFT = "draft"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    ACTIVE_WITH_RESTRICTIONS = "active_with_restrictions"
    ON_PAID_LEAVE = "on_paid_leave"
    ON_UNPAID_LEAVE = "on_unpaid_leave"
    SUSPENDED = "suspended"
    ON_NOTICE = "on_notice"
    ENDED = "ended"
    ARCHIVED = "archived"


class WorkRightsBasis(StrEnum):
    AUSTRALIAN_CITIZEN = "australian_citizen"
    PERMANENT_RESIDENT = "permanent_resident"
    NEW_ZEALAND_CITIZEN = "new_zealand_citizen"
    EMPLOYER_SPONSORED_TEMPORARY_VISA = "employer_sponsored_temporary_visa"
    OTHER_TEMPORARY_VISA = "other_temporary_visa"
    STUDENT_VISA = "student_visa"
    WORKING_HOLIDAY_VISA = "working_holiday_visa"
    BRIDGING_VISA = "bridging_visa"
    UNKNOWN_REVIEW_REQUIRED = "unknown_review_required"
    NO_VERIFIED_WORK_RIGHT = "no_verified_work_right"


class WorkRightsStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING_EVIDENCE = "pending_evidence"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    VERIFIED_WITH_RESTRICTIONS = "verified_with_restrictions"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    BLOCKED_PENDING_REVIEW = "blocked_pending_review"


class RemunerationBasis(StrEnum):
    SALARY = "salary"
    HOURLY = "hourly"
    DAY_RATE = "day_rate"
    COMMISSION = "commission"
    CONTRACTOR_FEE = "contractor_fee"
    DIRECTOR_FEE = "director_fee"
    UNPAID = "unpaid"


class EmploymentReimbursementStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    PAID = "paid"
    REJECTED = "rejected"


class EmploymentAssetStatus(StrEnum):
    ISSUED = "issued"
    RETURNED = "returned"
    LOST = "lost"
    DAMAGED = "damaged"


class DocumentLinkEntityType(StrEnum):
    JOURNAL_ENTRY = "journal_entry"
    JOURNAL_RECOMMENDATION_RUN = "journal_recommendation_run"
    BANK_IMPORT_SESSION = "bank_import_session"
    BANK_IMPORT_ROW = "bank_import_row"
    RECONCILIATION_ITEM = "reconciliation_item"
    ACCOUNTING_PERIOD = "accounting_period"
    EMPLOYMENT_WORKER = "employment_worker"


class JournalRecommendationStatus(StrEnum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    REVIEW_READY = "review_ready"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class JournalRecommendationProposalStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CREATED = "created"


class JournalRecommendationProposalType(StrEnum):
    ACCOUNT = "account"
    TAX_CODE = "tax_code"
    REPORTING_CATEGORY = "reporting_category"


class BankImportSessionStatus(StrEnum):
    DRAFT = "draft"
    STAGED = "staged"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class BankImportRowStatus(StrEnum):
    STAGED = "staged"
    DUPLICATE = "duplicate"
    MATCHED = "matched"
    IGNORED = "ignored"


class ReconciliationSessionStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ReconciliationItemStatus(StrEnum):
    UNMATCHED = "unmatched"
    MATCHED = "matched"
    SUGGESTED = "suggested"
    IGNORED = "ignored"


class BasPeriodStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    APPROVED = "approved"
    LOCKED = "locked"


class BasRunStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    EXPORTED = "exported"


class BasExportFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"


class FixedAssetStatus(StrEnum):
    ACTIVE = "active"
    DISPOSED = "disposed"


class DepreciationMethod(StrEnum):
    STRAIGHT_LINE = "straight_line"
    DIMINISHING_VALUE = "diminishing_value"


class DepreciationRunStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"


class TaxWorkpaperStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    EXPORTED = "exported"


class TaxWorkpaperNoteType(StrEnum):
    REVIEW = "review"
    SIGN_OFF = "sign_off"


class TaxWorkpaperExceptionStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class TaxWorkpaperExportFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"
