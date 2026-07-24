import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { resolveClientApiBaseUrl } from "./api-base-url-client";


const SESSION_STORAGE_KEY = "bookkeeping-tax-operator-session";

type MessageTone = "success" | "error" | "info";

type FlashMessage = {
  id: number;
  tone: MessageTone;
  text: string;
};

type User = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

type AdminOverview = {
  users: number;
  companies: number;
  accounts: number;
  periods: number;
  journals: number;
};

type Company = {
  id: string;
  legal_name: string;
  trading_name: string | null;
  abn: string | null;
  acn: string | null;
  entity_type: string;
  is_active: boolean;
  base_currency: string;
  country_code: string;
};

type ConfigurationVersion = {
  id: string;
  version_number: number;
  effective_from: string;
  effective_to: string | null;
  gst_registered: boolean;
  bas_frequency: string;
  bas_reporting_basis: string;
  financial_year_start_month: number;
  financial_year_start_day: number;
  allow_self_approval: boolean;
  self_approval_mode: string;
  period_lock_policy: string;
};

type CompanyAccess = {
  user_id: string;
  company_id: string;
  can_prepare: boolean;
  can_review: boolean;
  can_approve: boolean;
  can_administer: boolean;
};

type ReportingCategory = {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  category_type: string;
};

type TaxCode = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  rate: string;
  is_gst_applicable: boolean;
  is_active: boolean;
  bas_label: string | null;
  input_output_type: string;
};

type Account = {
  id: string;
  account_code: string;
  name: string;
  account_type: string;
  reporting_category_id: string | null;
  default_tax_code_id: string | null;
  is_active: boolean;
  allow_manual_posting: boolean;
};

type AccountingPeriod = {
  id: string;
  name: string;
  period_type: string;
  start_date: string;
  end_date: string;
  status: string;
};

type JournalLine = {
  id?: string;
  line_number?: number;
  account_id: string;
  description?: string | null;
  debit_amount: string;
  credit_amount: string;
  tax_code_id?: string | null;
  reporting_category_id?: string | null;
  source_document_reference?: string | null;
};

type JournalEntry = {
  id: string;
  entry_number: string;
  entry_date: string;
  accounting_period_id: string;
  status: string;
  source_type: string;
  description: string;
  reference: string | null;
  posted_at: string | null;
  reversal_of_entry_id: string | null;
  lines: JournalLine[];
};

type DocumentRecord = {
  id: string;
  original_filename: string;
  media_type: string | null;
  byte_size: number;
  uploaded_by_user_id: string;
  created_at: string;
};

type DocumentLinkRecord = {
  id: string;
  document_id: string;
  entity_type: string;
  entity_id: string;
  note: string | null;
};

type JournalEvidenceRecord = {
  link_id: string;
  document_id: string;
  original_filename: string;
  media_type: string | null;
  byte_size: number;
  uploaded_by_user_id: string;
  document_created_at: string;
  note: string | null;
  linked_by_user_id: string;
  linked_at: string;
};

type BankAccount = {
  id: string;
  name: string;
  bank_name: string | null;
  bsb: string | null;
  account_number_masked: string | null;
  is_active: boolean;
};

type BankImportSession = {
  id: string;
  bank_account_id: string;
  uploaded_document_id: string | null;
  original_filename: string;
  status: string;
  note: string | null;
  imported_at: string;
};

type BankImportRow = {
  id: string;
  line_number: number;
  transaction_date: string;
  description: string;
  reference: string | null;
  debit_amount: string;
  credit_amount: string;
  status: string;
};

type ReconciliationSession = {
  id: string;
  bank_account_id: string;
  accounting_period_id: string | null;
  status: string;
  note: string | null;
  completed_at: string | null;
};

type ReconciliationBankRow = {
  id: string;
  line_number: number;
  transaction_date: string;
  description: string;
  reference: string | null;
  debit_amount: string;
  credit_amount: string;
  status: string;
};

type ReconciliationJournalSummary = {
  id: string;
  entry_number: string;
  entry_date: string;
  description: string;
  reference: string | null;
  status: string;
  debit_total: string;
  credit_total: string;
};

type ReconciliationItem = {
  id: string;
  bank_import_row_id: string;
  matched_journal_entry_id: string | null;
  status: string;
  note: string | null;
  bank_row: ReconciliationBankRow | null;
  matched_journal_entry: ReconciliationJournalSummary | null;
};

type ReconciliationSummary = {
  total_items: number;
  unmatched_items: number;
  matched_items: number;
  ignored_items: number;
};

type BasPeriod = {
  id: string;
  start_date: string;
  end_date: string;
  status: string;
  note: string | null;
};

type BasLineResult = {
  id: string;
  label: string;
  system_amount: string;
  adjustment_amount: string;
  final_amount: string;
  detail_count: number;
};

type BasAdjustment = {
  id: string;
  label: string;
  amount: string;
  note: string;
  created_by_user_id: string;
};

type BasReviewNote = {
  id: string;
  severity: string;
  message: string;
  related_label: string | null;
  created_by_user_id: string | null;
};

type BasExport = {
  id: string;
  format: string;
  document_id: string;
  created_at: string;
};

type BasRunDetail = {
  id: string;
  bas_period_id: string;
  status: string;
  warning_count: number;
  approved_at: string | null;
  line_results: BasLineResult[];
  adjustments: BasAdjustment[];
  review_notes: BasReviewNote[];
  exports: BasExport[];
};

type ApprovalAction = {
  id: string;
  action_type: string;
  note: string | null;
  created_at: string;
};

export type TrialBalanceReport = {
  start_date: string | null;
  end_date: string | null;
  rows: Array<{
    account_id: string;
    account_code: string;
    account_name: string;
    debit_total: string;
    credit_total: string;
    balance: string;
  }>;
};

export type ProfitAndLossReport = {
  start_date: string;
  end_date: string;
  income_lines: Array<{ account_code: string; account_name: string; amount: string }>;
  expense_lines: Array<{ account_code: string; account_name: string; amount: string }>;
  total_income: string;
  total_expenses: string;
  net_profit: string;
};

export type BalanceSheetReport = {
  as_of_date: string;
  asset_lines: Array<{ account_code: string; account_name: string; amount: string }>;
  liability_lines: Array<{ account_code: string; account_name: string; amount: string }>;
  equity_lines: Array<{ account_code: string; account_name: string; amount: string }>;
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
};

export type CashFlowReportLine = {
  line_code: string;
  label: string;
  activity_type: string;
  amount: string;
  transaction_count: number;
};

export type CashFlowReport = {
  start_date: string;
  end_date: string;
  method: string;
  classification_policy: string;
  cash_accounts: Array<{
    account_id: string;
    account_code: string;
    account_name: string;
    opening_balance: string;
    closing_balance: string;
  }>;
  operating_lines: CashFlowReportLine[];
  investing_lines: CashFlowReportLine[];
  financing_lines: CashFlowReportLine[];
  opening_cash: string;
  total_operating: string;
  total_investing: string;
  total_financing: string;
  net_cash_change: string;
  effect_of_exchange_rate_changes: string;
  calculated_closing_cash: string;
  closing_cash: string;
  reconciliation_difference: string;
};

export type StatementOfChangesInEquityReport = {
  start_date: string;
  end_date: string;
  opening_equity_lines: Array<{
    account_code: string;
    account_name: string;
    amount: string;
  }>;
  movement_lines: Array<{
    account_id: string;
    account_code: string;
    account_name: string;
    movement_type: string;
    amount: string;
  }>;
  opening_equity: string;
  profit_or_loss: string;
  total_contributions: string;
  total_distributions: string;
  total_other_movements: string;
  total_changes: string;
  calculated_closing_equity: string;
  closing_equity: string;
  reconciliation_difference: string;
};

export type GeneralLedgerReport = {
  start_date: string;
  end_date: string;
  accounts: Array<{
    account_id: string;
    account_code: string;
    account_name: string;
    account_type: string;
    opening_balance: string;
    closing_balance: string;
    entries: Array<{
      journal_entry_id: string;
      entry_number: string;
      journal_status: string;
      entry_date: string;
      line_number: number;
      journal_description: string;
      line_description: string | null;
      reference: string | null;
      debit_amount: string;
      credit_amount: string;
      running_balance: string;
    }>;
  }>;
};

type FixedAsset = {
  id: string;
  asset_code: string;
  name: string;
  description: string | null;
  acquisition_date: string;
  in_service_date: string;
  cost_amount: string;
  salvage_value: string;
  useful_life_months: number;
  depreciation_method: string;
  diminishing_value_rate: string | null;
  asset_account_id: string;
  accumulated_depreciation_account_id: string;
  depreciation_expense_account_id: string;
  status: string;
  disposal_date: string | null;
  disposal_reference: string | null;
  disposal_note: string | null;
  disposal_proceeds: string | null;
  acquisition_reference: string | null;
  note: string | null;
  accumulated_depreciation?: string;
  carrying_amount?: string;
  history?: Array<{ id: string; to_status: string; effective_date: string; note: string | null }>;
};

type FixedAssetRegister = {
  as_of_date: string;
  assets: FixedAsset[];
};

type DepreciationRun = {
  id: string;
  accounting_period_id: string;
  start_date: string;
  end_date: string;
  status: string;
  journal_entry_id: string | null;
  note: string | null;
};

type DepreciationRunDetail = DepreciationRun & {
  total_depreciation_amount: string;
  lines: Array<{
    id: string;
    fixed_asset_id: string;
    depreciation_amount: string;
    carrying_amount_closing: string;
  }>;
};

type TaxAdjustment = {
  id: string;
  label: string;
  amount: string;
  note: string;
};

type TaxNote = {
  id: string;
  note_type: string;
  message: string;
};

type TaxException = {
  id: string;
  severity: string;
  message: string;
  status: string;
  resolution_note: string | null;
};

type TaxPack = {
  id: string;
  accounting_period_id: string;
  status: string;
  note: string | null;
  taxable_income?: string;
};

type TaxPackDetail = TaxPack & {
  accounting_profit_schedule: {
    net_profit: string;
  };
  gst_reconciliation_lines: Array<{ label: string; final_amount: string; run_count: number }>;
  fixed_asset_lines: Array<{ asset_code: string; asset_name: string; carrying_amount: string }>;
  total_adjustments: string;
  taxable_income: string;
  tax_adjustments: TaxAdjustment[];
  review_notes: TaxNote[];
  sign_off_notes: TaxNote[];
  exception_items: TaxException[];
  exports: Array<{ id: string; format: string; document_id: string; created_at: string }>;
};

type StoredSession = {
  baseUrl: string;
  token: string;
  selectedCompanyId: string;
  selectedBasRunId: string;
};

type RequestMethod = "GET" | "POST" | "PUT" | "DELETE";

type ReportState = {
  trialBalance: TrialBalanceReport | null;
  profitAndLoss: ProfitAndLossReport | null;
  balanceSheet: BalanceSheetReport | null;
  cashFlow: CashFlowReport | null;
  changesInEquity: StatementOfChangesInEquityReport | null;
  generalLedger: GeneralLedgerReport | null;
};


function resolveBaseUrl(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}


function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function createEmptyJournalDraft(accountingPeriodId = "") {
  return {
    entry_date: todayIso(),
    accounting_period_id: accountingPeriodId,
    source_type: "manual",
    description: "",
    reference: "",
    lines: [createEmptyJournalLine(), createEmptyJournalLine()],
  };
}


export function createDefaultConfiguration() {
  return {
    effective_from: todayIso(),
    gst_registered: true,
    bas_frequency: "quarterly",
    bas_reporting_basis: "accrual",
    financial_year_start_month: 7,
    financial_year_start_day: 1,
    allow_self_approval: true,
    self_approval_mode: "warn",
    period_lock_policy: "after_approval",
  };
}


export function createEmptyJournalLine(): JournalLine {
  return {
    account_id: "",
    description: "",
    debit_amount: "0.00",
    credit_amount: "0.00",
    tax_code_id: "",
    reporting_category_id: "",
    source_document_reference: "",
  };
}


export function formatMoney(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const amount = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(amount)) {
    return String(value);
  }
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    minimumFractionDigits: 2,
  }).format(amount);
}


export function formatDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleDateString();
}


export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}


function safeJsonParse<T>(value: string | null): T | null {
  if (!value) {
    return null;
  }
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}


function formatApiErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }
  if (!Array.isArray(detail)) {
    return null;
  }

  const messages = detail
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const candidate = item as { loc?: unknown; msg?: unknown };
      const location = Array.isArray(candidate.loc)
        ? candidate.loc
            .filter((part): part is string | number => typeof part === "string" || typeof part === "number")
            .slice(1)
            .join(".")
        : "";
      const message = typeof candidate.msg === "string" ? candidate.msg : "Validation error";
      return location ? `${location}: ${message}` : message;
    })
    .filter((value): value is string => Boolean(value));

  return messages.length > 0 ? messages.join(" | ") : null;
}


function inferFileName(headers: Headers, fallback: string) {
  const header = headers.get("content-disposition");
  if (!header) {
    return fallback;
  }
  const match = header.match(/filename="([^"]+)"/i);
  return match?.[1] ?? fallback;
}


function triggerDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
}


export function useOperatorState() {
  const [baseUrl, setBaseUrl] = useState("");
  const [token, setToken] = useState("");
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [selectedBasRunId, setSelectedBasRunId] = useState("");
  const [flashMessage, setFlashMessage] = useState<FlashMessage | null>(null);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const flashMessageIdRef = useRef(0);
  const activeActionLabelsRef = useRef<string[]>([]);
  const [sessionReady, setSessionReady] = useState(false);

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [configurations, setConfigurations] = useState<ConfigurationVersion[]>([]);
  const [accessRows, setAccessRows] = useState<CompanyAccess[]>([]);
  const [categories, setCategories] = useState<ReportingCategory[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentLinks, setDocumentLinks] = useState<DocumentLinkRecord[]>([]);
  const [journalEvidence, setJournalEvidence] = useState<JournalEvidenceRecord[]>([]);
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [bankImports, setBankImports] = useState<BankImportSession[]>([]);
  const [importRows, setImportRows] = useState<BankImportRow[]>([]);
  const [reconciliationSessions, setReconciliationSessions] = useState<ReconciliationSession[]>([]);
  const [reconciliationItems, setReconciliationItems] = useState<ReconciliationItem[]>([]);
  const [reconciliationSummary, setReconciliationSummary] = useState<ReconciliationSummary | null>(null);
  const [basPeriods, setBasPeriods] = useState<BasPeriod[]>([]);
  const [basRunDetail, setBasRunDetail] = useState<BasRunDetail | null>(null);
  const [basApprovalActions, setBasApprovalActions] = useState<ApprovalAction[]>([]);
  const [fixedAssetRegister, setFixedAssetRegister] = useState<FixedAssetRegister | null>(null);
  const [fixedAssetDetail, setFixedAssetDetail] = useState<FixedAsset | null>(null);
  const [depreciationRuns, setDepreciationRuns] = useState<DepreciationRun[]>([]);
  const [depreciationRunDetail, setDepreciationRunDetail] = useState<DepreciationRunDetail | null>(null);
  const [taxPacks, setTaxPacks] = useState<TaxPack[]>([]);
  const [taxPackDetail, setTaxPackDetail] = useState<TaxPackDetail | null>(null);
  const [taxApprovalActions, setTaxApprovalActions] = useState<ApprovalAction[]>([]);

  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedConfigurationId, setSelectedConfigurationId] = useState("");
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedTaxCodeId, setSelectedTaxCodeId] = useState("");
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [selectedPeriodId, setSelectedPeriodId] = useState("");
  const [selectedJournalId, setSelectedJournalId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedDocumentLinkId, setSelectedDocumentLinkId] = useState("");
  const [selectedBankAccountId, setSelectedBankAccountId] = useState("");
  const [selectedImportSessionId, setSelectedImportSessionId] = useState("");
  const [selectedReconciliationSessionId, setSelectedReconciliationSessionId] = useState("");
  const [selectedReconciliationItemId, setSelectedReconciliationItemId] = useState("");
  const [selectedBasPeriodId, setSelectedBasPeriodId] = useState("");
  const [selectedFixedAssetId, setSelectedFixedAssetId] = useState("");
  const [selectedDepreciationRunId, setSelectedDepreciationRunId] = useState("");
  const [selectedTaxPackId, setSelectedTaxPackId] = useState("");

  const [bootstrapDraft, setBootstrapDraft] = useState({ email: "admin@example.com", full_name: "Initial Admin", password: "StrongPass123" });
  const [loginDraft, setLoginDraft] = useState({ email: "admin@example.com", password: "StrongPass123" });
  const [newCompanyDraft, setNewCompanyDraft] = useState({
    legal_name: "Example Pty Ltd",
    trading_name: "Example Trading",
    abn: "51824753556",
    acn: "824753556",
    entity_type: "company",
    initial_configuration: createDefaultConfiguration(),
  });
  const [companyDraft, setCompanyDraft] = useState({
    legal_name: "",
    trading_name: "",
    abn: "",
    acn: "",
    entity_type: "company",
    is_active: true,
    base_currency: "AUD",
    country_code: "AU",
  });
  const [configurationDraft, setConfigurationDraft] = useState(createDefaultConfiguration());
  const [userDraft, setUserDraft] = useState({ email: "reviewer@example.com", full_name: "Reviewer User", password: "StrongPass123", is_superuser: false, is_active: true });
  const [accessDraft, setAccessDraft] = useState({ user_id: "", can_prepare: true, can_review: true, can_approve: true, can_administer: false });
  const [categoryDraft, setCategoryDraft] = useState({ code: "", name: "", is_active: true, category_type: "pnl" });
  const [taxCodeDraft, setTaxCodeDraft] = useState({ code: "", name: "", description: "", rate: "0.10", is_gst_applicable: true, is_active: true, bas_label: "", input_output_type: "output_taxed" });
  const [accountDraft, setAccountDraft] = useState({ account_code: "", name: "", account_type: "asset", reporting_category_id: "", default_tax_code_id: "", is_active: true, allow_manual_posting: true });
  const [periodDraft, setPeriodDraft] = useState({ name: "", period_type: "quarter", start_date: todayIso(), end_date: todayIso() });
  const [periodActionNote, setPeriodActionNote] = useState("Ready for review");
  const [journalDraft, setJournalDraft] = useState(createEmptyJournalDraft());
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [documentNote, setDocumentNote] = useState("Supporting evidence");
  const [documentDraft, setDocumentDraft] = useState({ original_filename: "", media_type: "" });
  const [documentLinkDraft, setDocumentLinkDraft] = useState({ entity_type: "journal_entry", entity_id: "", note: "Supports the selected journal" });
  const [bankAccountDraft, setBankAccountDraft] = useState({ name: "", bank_name: "", bsb: "", account_number_masked: "", is_active: true });
  const [bankImportDraft, setBankImportDraft] = useState({ note: "Uploaded from operator app", date_column: "date", description_column: "description", debit_column: "debit", credit_column: "credit", reference_column: "reference" });
  const [bankImportFile, setBankImportFile] = useState<File | null>(null);
  const [reconciliationDraft, setReconciliationDraft] = useState({ bank_account_id: "", accounting_period_id: "", note: "Monthly reconciliation" });
  const [reconciliationUpdateDraft, setReconciliationUpdateDraft] = useState({ accounting_period_id: "", note: "" });
  const [reconciliationMatchJournalId, setReconciliationMatchJournalId] = useState("");
  const [basGenerationDraft, setBasGenerationDraft] = useState({ start_date: todayIso(), end_date: todayIso() });
  const [basPeriodNote, setBasPeriodNote] = useState("Review support period");
  const [basAdjustmentDraft, setBasAdjustmentDraft] = useState({ label: "G1", amount: "0.00", note: "Manual adjustment" });
  const [basReviewNoteDraft, setBasReviewNoteDraft] = useState({ severity: "warning", message: "Check coding before export", related_label: "G1" });
  const [basActionNote, setBasActionNote] = useState("Prepared for review");
  const [trialBalanceFilters, setTrialBalanceFilters] = useState({ start_date: "", end_date: "" });
  const [profitAndLossFilters, setProfitAndLossFilters] = useState({ start_date: todayIso(), end_date: todayIso() });
  const [balanceSheetFilters, setBalanceSheetFilters] = useState({ as_of_date: todayIso() });
  const [cashFlowFilters, setCashFlowFilters] = useState({ start_date: todayIso(), end_date: todayIso() });
  const [changesInEquityFilters, setChangesInEquityFilters] = useState({ start_date: todayIso(), end_date: todayIso() });
  const [generalLedgerFilters, setGeneralLedgerFilters] = useState({ start_date: todayIso(), end_date: todayIso(), account_id: "" });
  const [reportState, setReportState] = useState<ReportState>({
    trialBalance: null,
    profitAndLoss: null,
    balanceSheet: null,
    cashFlow: null,
    changesInEquity: null,
    generalLedger: null,
  });
  const [assetDraft, setAssetDraft] = useState({ asset_code: "", name: "", description: "", acquisition_date: todayIso(), in_service_date: todayIso(), cost_amount: "0.00", salvage_value: "0.00", useful_life_months: 12, depreciation_method: "straight_line", diminishing_value_rate: "", asset_account_id: "", accumulated_depreciation_account_id: "", depreciation_expense_account_id: "", acquisition_reference: "", note: "" });
  const [disposeDraft, setDisposeDraft] = useState({ disposal_date: todayIso(), disposal_reference: "", disposal_note: "", disposal_proceeds: "0.00" });
  const [depreciationDraft, setDepreciationDraft] = useState({ accounting_period_id: "", start_date: todayIso(), end_date: todayIso(), note: "Monthly depreciation" });
  const [taxPackDraft, setTaxPackDraft] = useState({ accounting_period_id: "", note: "Annual workpaper pack" });
  const [taxAdjustmentDraft, setTaxAdjustmentDraft] = useState({ label: "NON_DEDUCTIBLE", amount: "0.00", note: "Review adjustment" });
  const [taxNoteDraft, setTaxNoteDraft] = useState({ note_type: "review", message: "Reviewed and ready" });
  const [taxExceptionDraft, setTaxExceptionDraft] = useState({ severity: "warning", message: "Review required" });
  const [taxResolveNote, setTaxResolveNote] = useState("Resolved by reviewer");
  const [taxActionNote, setTaxActionNote] = useState("Ready for review");

  const selectedCompany = useMemo(() => companies.find((item) => item.id === selectedCompanyId) ?? null, [companies, selectedCompanyId]);
  const selectedUser = useMemo(() => users.find((item) => item.id === selectedUserId) ?? null, [users, selectedUserId]);
  const selectedConfiguration = useMemo(() => configurations.find((item) => item.id === selectedConfigurationId) ?? null, [configurations, selectedConfigurationId]);
  const selectedCategory = useMemo(() => categories.find((item) => item.id === selectedCategoryId) ?? null, [categories, selectedCategoryId]);
  const selectedTaxCode = useMemo(() => taxCodes.find((item) => item.id === selectedTaxCodeId) ?? null, [taxCodes, selectedTaxCodeId]);
  const selectedAccount = useMemo(() => accounts.find((item) => item.id === selectedAccountId) ?? null, [accounts, selectedAccountId]);
  const selectedPeriod = useMemo(() => periods.find((item) => item.id === selectedPeriodId) ?? null, [periods, selectedPeriodId]);
  const selectedJournal = useMemo(() => journals.find((item) => item.id === selectedJournalId) ?? null, [journals, selectedJournalId]);
  const selectedDocument = useMemo(() => documents.find((item) => item.id === selectedDocumentId) ?? null, [documents, selectedDocumentId]);
  const selectedDocumentLink = useMemo(() => documentLinks.find((item) => item.id === selectedDocumentLinkId) ?? null, [documentLinks, selectedDocumentLinkId]);
  const selectedBankAccount = useMemo(() => bankAccounts.find((item) => item.id === selectedBankAccountId) ?? null, [bankAccounts, selectedBankAccountId]);
  const selectedImportSession = useMemo(() => bankImports.find((item) => item.id === selectedImportSessionId) ?? null, [bankImports, selectedImportSessionId]);
  const selectedReconciliationSession = useMemo(() => reconciliationSessions.find((item) => item.id === selectedReconciliationSessionId) ?? null, [reconciliationSessions, selectedReconciliationSessionId]);
  const selectedReconciliationItem = useMemo(() => reconciliationItems.find((item) => item.id === selectedReconciliationItemId) ?? null, [reconciliationItems, selectedReconciliationItemId]);
  const selectedBasPeriod = useMemo(() => basPeriods.find((item) => item.id === selectedBasPeriodId) ?? null, [basPeriods, selectedBasPeriodId]);
  const selectedFixedAsset = useMemo(() => (fixedAssetRegister?.assets ?? []).find((item) => item.id === selectedFixedAssetId) ?? null, [fixedAssetRegister, selectedFixedAssetId]);
  const selectedDepreciationRun = useMemo(() => depreciationRuns.find((item) => item.id === selectedDepreciationRunId) ?? null, [depreciationRuns, selectedDepreciationRunId]);
  const selectedTaxPack = useMemo(() => taxPacks.find((item) => item.id === selectedTaxPackId) ?? null, [taxPacks, selectedTaxPackId]);

  function clearCompanyWorkspaceState() {
    setConfigurations([]);
    setAccessRows([]);
    setCategories([]);
    setTaxCodes([]);
    setAccounts([]);
    setPeriods([]);
    setJournals([]);
    setDocuments([]);
    setDocumentLinks([]);
    setJournalEvidence([]);
    setBankAccounts([]);
    setBankImports([]);
    setImportRows([]);
    setReconciliationSessions([]);
    setReconciliationItems([]);
    setReconciliationSummary(null);
    setBasPeriods([]);
    setBasRunDetail(null);
    setBasApprovalActions([]);
    setFixedAssetRegister(null);
    setFixedAssetDetail(null);
    setDepreciationRuns([]);
    setDepreciationRunDetail(null);
    setTaxPacks([]);
    setTaxPackDetail(null);
    setTaxApprovalActions([]);
    setReportState({
      trialBalance: null,
      profitAndLoss: null,
      balanceSheet: null,
      cashFlow: null,
      changesInEquity: null,
      generalLedger: null,
    });
    setSelectedConfigurationId("");
    setSelectedCategoryId("");
    setSelectedTaxCodeId("");
    setSelectedAccountId("");
    setSelectedPeriodId("");
    setSelectedJournalId("");
    setSelectedDocumentId("");
    setSelectedDocumentLinkId("");
    setSelectedBankAccountId("");
    setSelectedImportSessionId("");
    setSelectedReconciliationSessionId("");
    setSelectedReconciliationItemId("");
    setSelectedBasPeriodId("");
    setSelectedFixedAssetId("");
    setSelectedDepreciationRunId("");
    setSelectedTaxPackId("");
    setConfigurationDraft(createDefaultConfiguration());
  }

  useEffect(() => {
    const persistedSession = safeJsonParse<StoredSession>(window.localStorage.getItem(SESSION_STORAGE_KEY));
    setBaseUrl(resolveClientApiBaseUrl(persistedSession?.baseUrl));
    if (persistedSession) {
      setToken(persistedSession.token || "");
      setSelectedCompanyId(persistedSession.selectedCompanyId || "");
      setSelectedBasRunId(persistedSession.selectedBasRunId || "");
    }
    setSessionReady(true);
  }, []);

  useEffect(() => {
    if (!sessionReady) {
      return;
    }
    window.localStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ baseUrl, token, selectedCompanyId, selectedBasRunId } satisfies StoredSession),
    );
  }, [baseUrl, token, selectedCompanyId, selectedBasRunId, sessionReady]);

  function clearPersistedSession(message: string) {
    setToken("");
    setSelectedCompanyId("");
    setSelectedBasRunId("");
    setCurrentUser(null);
    setCompanies([]);
    setAdminOverview(null);
    setUsers([]);
    clearCompanyWorkspaceState();
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
    }
    showMessage("info", message);
  }

  async function request<T>(path: string, method: RequestMethod = "GET", body?: unknown, responseType: "json" | "blob" | "void" = "json") {
    const headers = new Headers();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const isFormData = body instanceof FormData;
    if (body !== undefined && !isFormData) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${resolveBaseUrl(baseUrl)}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
      cache: "no-store",
    });

    if (response.status === 401) {
      clearPersistedSession("The saved session is no longer valid. Sign in again or bootstrap a new admin after a database reset.");
    }

    if (!response.ok) {
      const text = await response.text();
      let message = text || `${method} ${path} failed with ${response.status}`;
      try {
        const parsed = JSON.parse(text) as { detail?: unknown };
        message = formatApiErrorDetail(parsed.detail) ?? message;
      } catch {
        message = text || `${method} ${path} failed with ${response.status}`;
      }
      throw new Error(message);
    }

    if (responseType === "void" || response.status === 204) {
      return undefined as T;
    }
    if (responseType === "blob") {
      return { blob: await response.blob(), headers: response.headers } as T;
    }
    const text = await response.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }

  function showMessage(tone: MessageTone, text: string) {
    startTransition(() => {
      flashMessageIdRef.current += 1;
      setFlashMessage({ id: flashMessageIdRef.current, tone, text });
    });
  }

  async function runAction(label: string, action: () => Promise<void>) {
    if (activeActionLabelsRef.current.includes(label)) {
      return;
    }
    activeActionLabelsRef.current = [...activeActionLabelsRef.current, label];
    setBusyLabel(label);
    try {
      await action();
    } catch (error) {
      showMessage("error", error instanceof Error ? error.message : `${label} failed`);
    } finally {
      activeActionLabelsRef.current = activeActionLabelsRef.current.filter((item) => item !== label);
      setBusyLabel(activeActionLabelsRef.current.at(-1) ?? null);
    }
  }

  async function loadSessionData() {
    const me = await request<LoginResponse>("/api/auth/me");
    setCurrentUser(me.user);
    const companyList = await request<Company[]>("/api/companies");
    setCompanies(companyList);
    const hasSelectedCompany = companyList.some((item) => item.id === selectedCompanyId);
    if (!hasSelectedCompany) {
      const nextCompanyId = companyList[0]?.id ?? "";
      setSelectedCompanyId(nextCompanyId);
      if (!nextCompanyId) {
        clearCompanyWorkspaceState();
      }
    }

    if (me.user.is_superuser) {
      try {
        const [overview, adminUsers] = await Promise.all([
          request<AdminOverview>("/api/admin/overview"),
          request<User[]>("/api/admin/users"),
        ]);
        setAdminOverview(overview);
        setUsers(adminUsers);
      } catch {
        setAdminOverview(null);
        setUsers([]);
      }
    } else {
      setAdminOverview(null);
      setUsers([]);
    }
  }

  async function loadCompanyWorkspace(companyId: string) {
    const currentDate = todayIso();
    const [
      configurationResult,
      accessResult,
      categoryResult,
      taxCodeResult,
      accountResult,
      periodResult,
      journalResult,
      documentResult,
      bankAccountResult,
      bankImportResult,
      reconciliationResult,
      basPeriodResult,
      fixedAssetResult,
      depreciationResult,
      taxPackResult,
    ] = await Promise.all([
      request<ConfigurationVersion[]>(`/api/companies/${companyId}/configurations`),
      request<CompanyAccess[]>(`/api/companies/${companyId}/access`),
      request<ReportingCategory[]>(`/api/companies/${companyId}/reporting-categories`),
      request<TaxCode[]>(`/api/companies/${companyId}/tax-codes`),
      request<Account[]>(`/api/companies/${companyId}/accounts`),
      request<AccountingPeriod[]>(`/api/companies/${companyId}/periods`),
      request<JournalEntry[]>(`/api/companies/${companyId}/journals`),
      request<DocumentRecord[]>(`/api/companies/${companyId}/documents`),
      request<BankAccount[]>(`/api/companies/${companyId}/bank-accounts`),
      request<BankImportSession[]>(`/api/companies/${companyId}/bank-imports`),
      request<ReconciliationSession[]>(`/api/companies/${companyId}/reconciliation-sessions`),
      request<BasPeriod[]>(`/api/companies/${companyId}/bas/periods`),
      request<FixedAssetRegister>(`/api/companies/${companyId}/fixed-assets?as_of_date=${currentDate}`),
      request<DepreciationRun[]>(`/api/companies/${companyId}/fixed-assets/depreciation-runs`),
      request<TaxPack[]>(`/api/companies/${companyId}/tax-workpapers/packs`),
    ]);

    setConfigurations(configurationResult);
    setAccessRows(accessResult);
    setCategories(categoryResult);
    setTaxCodes(taxCodeResult);
    setAccounts(accountResult);
    setPeriods(periodResult);
    setJournals(journalResult);
    setDocuments(documentResult);
    setBankAccounts(bankAccountResult);
    setBankImports(bankImportResult);
    setReconciliationSessions(reconciliationResult);
    setBasPeriods(basPeriodResult);
    setFixedAssetRegister(fixedAssetResult);
    setDepreciationRuns(depreciationResult);
    setTaxPacks(taxPackResult);
  }

  async function refreshAll(companyIdOverride?: string) {
    await loadSessionData();
    const companyId = companyIdOverride ?? selectedCompanyId;
    if (companyId) {
      await loadCompanyWorkspace(companyId);
    }
  }

  async function loadDocumentLinks(documentId: string) {
    if (!selectedCompanyId || !documentId) {
      setDocumentLinks([]);
      return;
    }
    const links = await request<DocumentLinkRecord[]>(`/api/companies/${selectedCompanyId}/documents/${documentId}/links`);
    setDocumentLinks(links);
    if (links.length > 0 && !selectedDocumentLinkId) {
      setSelectedDocumentLinkId(links[0].id);
    }
  }

  async function loadJournalEvidence(journalId: string) {
    if (!selectedCompanyId || !journalId) {
      setJournalEvidence([]);
      return;
    }
    const evidence = await request<JournalEvidenceRecord[]>(`/api/companies/${selectedCompanyId}/journals/${journalId}/documents`);
    setJournalEvidence(evidence);
  }

  async function loadImportDetail(sessionId: string) {
    if (!selectedCompanyId || !sessionId) {
      setImportRows([]);
      return;
    }
    const rows = await request<BankImportRow[]>(`/api/companies/${selectedCompanyId}/bank-imports/${sessionId}/rows`);
    setImportRows(rows);
  }

  async function loadReconciliationDetail(sessionId: string) {
    if (!selectedCompanyId || !sessionId) {
      setReconciliationItems([]);
      setReconciliationSummary(null);
      return;
    }
    const [items, summary] = await Promise.all([
      request<ReconciliationItem[]>(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${sessionId}/items`),
      request<ReconciliationSummary>(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${sessionId}/summary`),
    ]);
    setReconciliationItems(items);
    setReconciliationSummary(summary);
    if (items.length > 0 && !selectedReconciliationItemId) {
      setSelectedReconciliationItemId(items[0].id);
    }
  }

  async function loadBasRun(runId: string) {
    if (!selectedCompanyId || !runId) {
      setBasRunDetail(null);
      setBasApprovalActions([]);
      return;
    }
    const [detail, actions] = await Promise.all([
      request<BasRunDetail>(`/api/companies/${selectedCompanyId}/bas/runs/${runId}`),
      request<ApprovalAction[]>(`/api/companies/${selectedCompanyId}/bas/runs/${runId}/approval-actions`),
    ]);
    setBasRunDetail(detail);
    setBasApprovalActions(actions);
  }

  async function loadFixedAsset(assetId: string) {
    if (!selectedCompanyId || !assetId) {
      setFixedAssetDetail(null);
      return;
    }
    const detail = await request<FixedAsset>(`/api/companies/${selectedCompanyId}/fixed-assets/${assetId}?as_of_date=${todayIso()}`);
    setFixedAssetDetail(detail);
  }

  async function loadDepreciationRun(runId: string) {
    if (!selectedCompanyId || !runId) {
      setDepreciationRunDetail(null);
      return;
    }
    const detail = await request<DepreciationRunDetail>(`/api/companies/${selectedCompanyId}/fixed-assets/depreciation-runs/${runId}`);
    setDepreciationRunDetail(detail);
  }

  async function loadTaxPack(packId: string) {
    if (!selectedCompanyId || !packId) {
      setTaxPackDetail(null);
      setTaxApprovalActions([]);
      return;
    }
    const [detail, actions] = await Promise.all([
      request<TaxPackDetail>(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${packId}`),
      request<ApprovalAction[]>(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${packId}/approval-actions`),
    ]);
    setTaxPackDetail(detail);
    setTaxApprovalActions(actions);
  }

  useEffect(() => {
    if (!token) {
      setCurrentUser(null);
      setCompanies([]);
      setAdminOverview(null);
      setUsers([]);
      clearCompanyWorkspaceState();
      return;
    }
    runAction("Loading session", async () => {
      await loadSessionData();
    });
  }, [token, baseUrl]);

  useEffect(() => {
    if (!token || !selectedCompanyId) {
      return;
    }
    runAction("Loading company workspace", async () => {
      await loadCompanyWorkspace(selectedCompanyId);
    });
  }, [token, selectedCompanyId, baseUrl]);

  useEffect(() => {
    if (selectedDocumentId) {
      runAction("Loading document links", async () => {
        await loadDocumentLinks(selectedDocumentId);
      });
    } else {
      setDocumentLinks([]);
    }
  }, [selectedDocumentId]);

  useEffect(() => {
    if (selectedJournalId) {
      runAction("Loading journal evidence", async () => {
        await loadJournalEvidence(selectedJournalId);
      });
    } else {
      setJournalEvidence([]);
    }
  }, [selectedJournalId]);

  useEffect(() => {
    if (selectedImportSessionId) {
      runAction("Loading import rows", async () => {
        await loadImportDetail(selectedImportSessionId);
      });
    } else {
      setImportRows([]);
    }
  }, [selectedImportSessionId]);

  useEffect(() => {
    if (selectedReconciliationSessionId) {
      runAction("Loading reconciliation detail", async () => {
        await loadReconciliationDetail(selectedReconciliationSessionId);
      });
    } else {
      setReconciliationItems([]);
      setReconciliationSummary(null);
    }
  }, [selectedReconciliationSessionId]);

  useEffect(() => {
    if (selectedBasRunId) {
      runAction("Loading BAS run", async () => {
        await loadBasRun(selectedBasRunId);
      });
    } else {
      setBasRunDetail(null);
      setBasApprovalActions([]);
    }
  }, [selectedBasRunId]);

  useEffect(() => {
    if (selectedFixedAssetId) {
      runAction("Loading fixed asset", async () => {
        await loadFixedAsset(selectedFixedAssetId);
      });
    } else {
      setFixedAssetDetail(null);
    }
  }, [selectedFixedAssetId]);

  useEffect(() => {
    if (selectedDepreciationRunId) {
      runAction("Loading depreciation run", async () => {
        await loadDepreciationRun(selectedDepreciationRunId);
      });
    } else {
      setDepreciationRunDetail(null);
    }
  }, [selectedDepreciationRunId]);

  useEffect(() => {
    if (selectedTaxPackId) {
      runAction("Loading tax pack", async () => {
        await loadTaxPack(selectedTaxPackId);
      });
    } else {
      setTaxPackDetail(null);
      setTaxApprovalActions([]);
    }
  }, [selectedTaxPackId]);

  useEffect(() => {
    if (selectedCompany) {
      setCompanyDraft({
        legal_name: selectedCompany.legal_name,
        trading_name: selectedCompany.trading_name ?? "",
        abn: selectedCompany.abn ?? "",
        acn: selectedCompany.acn ?? "",
        entity_type: selectedCompany.entity_type,
        is_active: selectedCompany.is_active,
        base_currency: selectedCompany.base_currency,
        country_code: selectedCompany.country_code,
      });
    }
  }, [selectedCompany]);

  useEffect(() => {
    if (selectedConfiguration) {
      setConfigurationDraft({
        effective_from: selectedConfiguration.effective_from,
        gst_registered: selectedConfiguration.gst_registered,
        bas_frequency: selectedConfiguration.bas_frequency,
        bas_reporting_basis: selectedConfiguration.bas_reporting_basis,
        financial_year_start_month: selectedConfiguration.financial_year_start_month,
        financial_year_start_day: selectedConfiguration.financial_year_start_day,
        allow_self_approval: selectedConfiguration.allow_self_approval,
        self_approval_mode: selectedConfiguration.self_approval_mode,
        period_lock_policy: selectedConfiguration.period_lock_policy,
      });
    }
  }, [selectedConfiguration]);

  useEffect(() => {
    if (selectedUser) {
      setUserDraft({
        email: selectedUser.email,
        full_name: selectedUser.full_name,
        password: "",
        is_superuser: selectedUser.is_superuser,
        is_active: selectedUser.is_active,
      });
      const matchingAccess = accessRows.find((item) => item.user_id === selectedUser.id);
      if (matchingAccess) {
        setAccessDraft({ ...matchingAccess });
      } else {
        setAccessDraft({ user_id: selectedUser.id, can_prepare: true, can_review: true, can_approve: false, can_administer: false });
      }
    }
  }, [selectedUser, accessRows]);

  useEffect(() => {
    if (selectedCategory) {
      setCategoryDraft({ code: selectedCategory.code, name: selectedCategory.name, is_active: selectedCategory.is_active, category_type: selectedCategory.category_type });
    }
  }, [selectedCategory]);

  useEffect(() => {
    if (selectedTaxCode) {
      setTaxCodeDraft({
        code: selectedTaxCode.code,
        name: selectedTaxCode.name,
        description: selectedTaxCode.description ?? "",
        rate: selectedTaxCode.rate,
        is_gst_applicable: selectedTaxCode.is_gst_applicable,
        is_active: selectedTaxCode.is_active,
        bas_label: selectedTaxCode.bas_label ?? "",
        input_output_type: selectedTaxCode.input_output_type,
      });
    }
  }, [selectedTaxCode]);

  useEffect(() => {
    if (selectedAccount) {
      setAccountDraft({
        account_code: selectedAccount.account_code,
        name: selectedAccount.name,
        account_type: selectedAccount.account_type,
        reporting_category_id: selectedAccount.reporting_category_id ?? "",
        default_tax_code_id: selectedAccount.default_tax_code_id ?? "",
        is_active: selectedAccount.is_active,
        allow_manual_posting: selectedAccount.allow_manual_posting,
      });
    }
  }, [selectedAccount]);

  useEffect(() => {
    if (selectedPeriod) {
      setPeriodDraft({
        name: selectedPeriod.name,
        period_type: selectedPeriod.period_type,
        start_date: selectedPeriod.start_date,
        end_date: selectedPeriod.end_date,
      });
    }
  }, [selectedPeriod]);

  useEffect(() => {
    if (selectedJournal) {
      setJournalDraft({
        entry_date: selectedJournal.entry_date,
        accounting_period_id: selectedJournal.accounting_period_id,
        source_type: selectedJournal.source_type,
        description: selectedJournal.description,
        reference: selectedJournal.reference ?? "",
        lines: selectedJournal.lines.map((line) => ({
          account_id: line.account_id,
          description: line.description ?? "",
          debit_amount: line.debit_amount,
          credit_amount: line.credit_amount,
          tax_code_id: line.tax_code_id ?? "",
          reporting_category_id: line.reporting_category_id ?? "",
          source_document_reference: line.source_document_reference ?? "",
        })),
      });
    }
  }, [selectedJournal]);

  useEffect(() => {
    if (selectedDocument) {
      setDocumentDraft({ original_filename: selectedDocument.original_filename, media_type: selectedDocument.media_type ?? "" });
    }
  }, [selectedDocument]);

  useEffect(() => {
    if (selectedDocumentLink) {
      setDocumentLinkDraft({ entity_type: selectedDocumentLink.entity_type, entity_id: selectedDocumentLink.entity_id, note: selectedDocumentLink.note ?? "" });
    }
  }, [selectedDocumentLink]);

  useEffect(() => {
    if (selectedBankAccount) {
      setBankAccountDraft({
        name: selectedBankAccount.name,
        bank_name: selectedBankAccount.bank_name ?? "",
        bsb: selectedBankAccount.bsb ?? "",
        account_number_masked: selectedBankAccount.account_number_masked ?? "",
        is_active: selectedBankAccount.is_active,
      });
    }
  }, [selectedBankAccount]);

  useEffect(() => {
    if (selectedReconciliationSession) {
      setReconciliationUpdateDraft({
        accounting_period_id: selectedReconciliationSession.accounting_period_id ?? "",
        note: selectedReconciliationSession.note ?? "",
      });
    }
  }, [selectedReconciliationSession]);

  useEffect(() => {
    if (selectedFixedAsset ?? fixedAssetDetail) {
      const asset = fixedAssetDetail ?? selectedFixedAsset;
      if (!asset) {
        return;
      }
      setAssetDraft({
        asset_code: asset.asset_code,
        name: asset.name,
        description: asset.description ?? "",
        acquisition_date: asset.acquisition_date,
        in_service_date: asset.in_service_date,
        cost_amount: asset.cost_amount,
        salvage_value: asset.salvage_value,
        useful_life_months: asset.useful_life_months,
        depreciation_method: asset.depreciation_method,
        diminishing_value_rate: asset.diminishing_value_rate ?? "",
        asset_account_id: asset.asset_account_id,
        accumulated_depreciation_account_id: asset.accumulated_depreciation_account_id,
        depreciation_expense_account_id: asset.depreciation_expense_account_id,
        acquisition_reference: asset.acquisition_reference ?? "",
        note: asset.note ?? "",
      });
    }
  }, [selectedFixedAsset, fixedAssetDetail]);

  useEffect(() => {
    if (selectedDepreciationRun) {
      setDepreciationDraft({
        accounting_period_id: selectedDepreciationRun.accounting_period_id,
        start_date: selectedDepreciationRun.start_date,
        end_date: selectedDepreciationRun.end_date,
        note: selectedDepreciationRun.note ?? "",
      });
    }
  }, [selectedDepreciationRun]);

  useEffect(() => {
    if (selectedTaxPack) {
      setTaxPackDraft({ accounting_period_id: selectedTaxPack.accounting_period_id, note: selectedTaxPack.note ?? "" });
    }
  }, [selectedTaxPack]);

  function logout() {
    setToken("");
    setSelectedCompanyId("");
    setSelectedBasRunId("");
    setCurrentUser(null);
    showMessage("info", "Signed out of the operator workspace.");
  }

  const companyOptionList = companies.map((item) => ({ value: item.id, label: item.legal_name }));
  const userOptionList = users.map((item) => ({ value: item.id, label: `${item.full_name} (${item.email})` }));
  const categoryOptionList = categories.map((item) => ({ value: item.id, label: `${item.code} · ${item.name}` }));
  const taxCodeOptionList = taxCodes.map((item) => ({ value: item.id, label: `${item.code} · ${item.name}` }));
  const accountOptionList = accounts.map((item) => ({ value: item.id, label: `${item.account_code} · ${item.name}` }));
  const activeCategoryOptionList = categories.filter((item) => item.is_active).map((item) => ({ value: item.id, label: `${item.code} · ${item.name}` }));
  const activeTaxCodeOptionList = taxCodes.filter((item) => item.is_active).map((item) => ({ value: item.id, label: `${item.code} · ${item.name}` }));
  const activeAccountOptionList = accounts.filter((item) => item.is_active).map((item) => ({ value: item.id, label: `${item.account_code} · ${item.name}` }));
  const periodOptionList = periods.map((item) => ({ value: item.id, label: `${item.name} · ${item.status}` }));
  const journalOptionList = journals.map((item) => ({ value: item.id, label: `${item.entry_number} · ${item.description}` }));
  const bankAccountOptionList = bankAccounts.map((item) => ({ value: item.id, label: item.name }));
  const basPeriodOptionList = basPeriods.map((item) => ({ value: item.id, label: `${item.start_date} to ${item.end_date}` }));

  async function handleLogin(mode: "login" | "bootstrap") {
    const payload = mode === "login" ? loginDraft : bootstrapDraft;
    const response = await request<LoginResponse>(`/api/auth/${mode}`, "POST", payload);
    setToken(response.access_token);
    setCurrentUser(response.user);
    showMessage("success", `${mode === "login" ? "Logged in" : "Bootstrapped admin"} as ${response.user.full_name}.`);
  }

  function confirmDanger(message: string) {
    return typeof window !== "undefined" ? window.confirm(message) : false;
  }

  async function downloadFromApi(path: string, fallback: string) {
    const response = await request<{ blob: Blob; headers: Headers }>(path, "GET", undefined, "blob");
    const filename = inferFileName(response.headers, fallback);
    triggerDownload(response.blob, filename);
    showMessage("success", `Downloaded ${filename}.`);
  }

  return {
    baseUrl,
    setBaseUrl,
    token,
    setToken,
    selectedCompanyId,
    setSelectedCompanyId,
    selectedBasRunId,
    setSelectedBasRunId,
    flashMessage,
    busyLabel,
    currentUser,
    adminOverview,
    users,
    companies,
    configurations,
    accessRows,
    categories,
    taxCodes,
    accounts,
    periods,
    journals,
    documents,
    documentLinks,
    journalEvidence,
    bankAccounts,
    bankImports,
    importRows,
    reconciliationSessions,
    reconciliationItems,
    reconciliationSummary,
    basPeriods,
    basRunDetail,
    basApprovalActions,
    fixedAssetRegister,
    fixedAssetDetail,
    depreciationRuns,
    depreciationRunDetail,
    taxPacks,
    taxPackDetail,
    taxApprovalActions,
    selectedUserId,
    setSelectedUserId,
    selectedConfigurationId,
    setSelectedConfigurationId,
    selectedCategoryId,
    setSelectedCategoryId,
    selectedTaxCodeId,
    setSelectedTaxCodeId,
    selectedAccountId,
    setSelectedAccountId,
    selectedPeriodId,
    setSelectedPeriodId,
    selectedJournalId,
    setSelectedJournalId,
    selectedDocumentId,
    setSelectedDocumentId,
    selectedDocumentLinkId,
    setSelectedDocumentLinkId,
    selectedBankAccountId,
    setSelectedBankAccountId,
    selectedImportSessionId,
    setSelectedImportSessionId,
    selectedReconciliationSessionId,
    setSelectedReconciliationSessionId,
    selectedReconciliationItemId,
    setSelectedReconciliationItemId,
    selectedBasPeriodId,
    setSelectedBasPeriodId,
    selectedFixedAssetId,
    setSelectedFixedAssetId,
    selectedDepreciationRunId,
    setSelectedDepreciationRunId,
    selectedTaxPackId,
    setSelectedTaxPackId,
    bootstrapDraft,
    setBootstrapDraft,
    loginDraft,
    setLoginDraft,
    newCompanyDraft,
    setNewCompanyDraft,
    companyDraft,
    setCompanyDraft,
    configurationDraft,
    setConfigurationDraft,
    userDraft,
    setUserDraft,
    accessDraft,
    setAccessDraft,
    categoryDraft,
    setCategoryDraft,
    taxCodeDraft,
    setTaxCodeDraft,
    accountDraft,
    setAccountDraft,
    periodDraft,
    setPeriodDraft,
    periodActionNote,
    setPeriodActionNote,
    journalDraft,
    setJournalDraft,
    documentFile,
    setDocumentFile,
    documentNote,
    setDocumentNote,
    documentDraft,
    setDocumentDraft,
    documentLinkDraft,
    setDocumentLinkDraft,
    bankAccountDraft,
    setBankAccountDraft,
    bankImportDraft,
    setBankImportDraft,
    bankImportFile,
    setBankImportFile,
    reconciliationDraft,
    setReconciliationDraft,
    reconciliationUpdateDraft,
    setReconciliationUpdateDraft,
    reconciliationMatchJournalId,
    setReconciliationMatchJournalId,
    basGenerationDraft,
    setBasGenerationDraft,
    basPeriodNote,
    setBasPeriodNote,
    basAdjustmentDraft,
    setBasAdjustmentDraft,
    basReviewNoteDraft,
    setBasReviewNoteDraft,
    basActionNote,
    setBasActionNote,
    trialBalanceFilters,
    setTrialBalanceFilters,
    profitAndLossFilters,
    setProfitAndLossFilters,
    balanceSheetFilters,
    setBalanceSheetFilters,
    cashFlowFilters,
    setCashFlowFilters,
    changesInEquityFilters,
    setChangesInEquityFilters,
    generalLedgerFilters,
    setGeneralLedgerFilters,
    reportState,
    setReportState,
    assetDraft,
    setAssetDraft,
    disposeDraft,
    setDisposeDraft,
    depreciationDraft,
    setDepreciationDraft,
    taxPackDraft,
    setTaxPackDraft,
    taxAdjustmentDraft,
    setTaxAdjustmentDraft,
    taxNoteDraft,
    setTaxNoteDraft,
    taxExceptionDraft,
    setTaxExceptionDraft,
    taxResolveNote,
    setTaxResolveNote,
    taxActionNote,
    setTaxActionNote,
    selectedCompany,
    selectedUser,
    selectedConfiguration,
    selectedCategory,
    selectedTaxCode,
    selectedAccount,
    selectedPeriod,
    selectedJournal,
    selectedDocument,
    selectedDocumentLink,
    selectedBankAccount,
    selectedImportSession,
    selectedReconciliationSession,
    selectedReconciliationItem,
    selectedBasPeriod,
    selectedFixedAsset,
    selectedDepreciationRun,
    selectedTaxPack,
    companyOptionList,
    userOptionList,
    categoryOptionList,
    taxCodeOptionList,
    accountOptionList,
    activeCategoryOptionList,
    activeTaxCodeOptionList,
    activeAccountOptionList,
    periodOptionList,
    journalOptionList,
    bankAccountOptionList,
    basPeriodOptionList,
    handleLogin,
    logout,
    runAction,
    showMessage,
    refreshAll,
    request,
    loadJournalEvidence,
    loadBasRun,
    loadTaxPack,
    downloadFromApi,
    confirmDanger,
  };
}


export type OperatorState = ReturnType<typeof useOperatorState>;
