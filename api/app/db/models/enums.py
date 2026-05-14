from enum import StrEnum


class EntityType(StrEnum):
    COMPANY = "company"
    COMPANY_CONFIGURATION = "company_configuration"
    ACCOUNT = "account"
    ACCOUNTING_PERIOD = "accounting_period"
    JOURNAL_ENTRY = "journal_entry"
    JOURNAL_RECOMMENDATION_RUN = "journal_recommendation_run"
    BAS_RUN = "bas_run"
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


class DocumentLinkEntityType(StrEnum):
    JOURNAL_ENTRY = "journal_entry"
    JOURNAL_RECOMMENDATION_RUN = "journal_recommendation_run"
    BANK_IMPORT_SESSION = "bank_import_session"
    BANK_IMPORT_ROW = "bank_import_row"
    RECONCILIATION_ITEM = "reconciliation_item"
    ACCOUNTING_PERIOD = "accounting_period"


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
