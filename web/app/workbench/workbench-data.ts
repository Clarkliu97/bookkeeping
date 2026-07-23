export function createDefaultWorkbenchContext() {
  return {
    baseUrl: "",
    token: "",
    reviewerToken: "",
    reviewerUserId: "",
    reviewerUserStatus: "",
    companyId: "",
    companyStatus: "",
    configurationId: "",
    salesCategoryId: "",
    saleG1TaxCodeId: "",
    gst1ATaxCodeId: "",
    cashAccountId: "",
    revenueAccountId: "",
    gstPayableAccountId: "",
    expenseAccountId: "",
    assetAccountId: "",
    accumulatedDepAccountId: "",
    depExpenseAccountId: "",
    q1PeriodId: "",
    q1PeriodStatus: "",
    yearPeriodId: "",
    yearPeriodStatus: "",
    saleJournalId: "",
    officeExpenseJournalId: "",
    officeExpenseJournalStatus: "",
    documentId: "",
    documentLinkId: "",
    exportDocumentId: "",
    bankAccountId: "",
    bankImportSessionId: "",
    bankImportSessionStatus: "",
    reconciliationSessionId: "",
    reconciliationSessionStatus: "",
    reconciliationItemId: "",
    basPeriodId: "",
    basPeriodStatus: "",
    basRunId: "",
    basRunStatus: "",
    basAdjustmentId: "",
    basReviewNoteId: "",
    fixedAssetId: "",
    fixedAssetStatus: "",
    depreciationRunId: "",
    depreciationRunStatus: "",
    taxPackId: "",
    taxPackStatus: "",
    taxAdjustmentId: "",
    taxNoteId: "",
    taxExceptionId: "",
    taxExceptionStatus: "",
  };
}


const defaultWorkbenchContextShape = createDefaultWorkbenchContext();

export type ContextKey = keyof typeof defaultWorkbenchContextShape;
export type WorkbenchContext = Record<ContextKey, string>;

export const defaultWorkbenchContext: WorkbenchContext = { ...defaultWorkbenchContextShape };

export type ContextFieldGroup = {
  title: string;
  fields: Array<{ key: ContextKey; label: string; placeholder?: string }>;
};

export type CaptureSpec = {
  target: ContextKey;
  path: string;
};

export type VisibilityRule = {
  key: ContextKey;
  present?: boolean;
  absent?: boolean;
  equals?: string;
  oneOf?: string[];
};

type BaseActionConfig = {
  title: string;
  description: string;
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  pathTemplate: string;
  auth?: "token" | "reviewerToken";
  notes?: string[];
  capture?: CaptureSpec[];
  clearOnSuccess?: ContextKey[];
  visibleWhen?: VisibilityRule[];
  responseType?: "json" | "text" | "binary";
};

export type JsonActionConfig = BaseActionConfig & {
  kind: "json";
  defaultBody?: string;
};

export type UploadActionConfig = BaseActionConfig & {
  kind: "upload";
  fields: Array<{ name: string; valueTemplate: string }>;
  accept?: string;
};

export type ActionConfig = JsonActionConfig | UploadActionConfig;

export type WorkbenchSection = {
  title: string;
  description: string;
  cards: ActionConfig[];
};

export const contextFieldGroups: ContextFieldGroup[] = [
  {
    title: "Session",
    fields: [
      { key: "baseUrl", label: "API base URL" },
      { key: "token", label: "Primary token" },
      { key: "reviewerToken", label: "Reviewer token" },
      { key: "reviewerUserId", label: "Reviewer user ID" },
      { key: "reviewerUserStatus", label: "Reviewer user status" },
    ],
  },
  {
    title: "Company and Setup",
    fields: [
      { key: "companyId", label: "Company ID" },
      { key: "companyStatus", label: "Company status" },
      { key: "configurationId", label: "Configuration ID" },
      { key: "salesCategoryId", label: "Sales category ID" },
      { key: "saleG1TaxCodeId", label: "SALE_G1 tax code ID" },
      { key: "gst1ATaxCodeId", label: "GST_1A tax code ID" },
      { key: "q1PeriodId", label: "Quarter period ID" },
      { key: "q1PeriodStatus", label: "Quarter period status" },
      { key: "yearPeriodId", label: "Year period ID" },
      { key: "yearPeriodStatus", label: "Year period status" },
    ],
  },
  {
    title: "Accounts",
    fields: [
      { key: "cashAccountId", label: "Cash account ID" },
      { key: "revenueAccountId", label: "Revenue account ID" },
      { key: "gstPayableAccountId", label: "GST payable account ID" },
      { key: "expenseAccountId", label: "Expense account ID" },
      { key: "assetAccountId", label: "Asset account ID" },
      { key: "accumulatedDepAccountId", label: "Accumulated depreciation ID" },
      { key: "depExpenseAccountId", label: "Depreciation expense ID" },
    ],
  },
  {
    title: "Workflow IDs",
    fields: [
      { key: "saleJournalId", label: "Sale journal ID" },
      { key: "officeExpenseJournalId", label: "Expense journal ID" },
      { key: "officeExpenseJournalStatus", label: "Expense journal status" },
      { key: "documentId", label: "Document ID" },
      { key: "documentLinkId", label: "Document link ID" },
      { key: "exportDocumentId", label: "Export document ID" },
      { key: "bankAccountId", label: "Bank account ID" },
      { key: "bankImportSessionId", label: "Bank import session ID" },
      { key: "bankImportSessionStatus", label: "Bank import status" },
      { key: "reconciliationSessionId", label: "Reconciliation session ID" },
      { key: "reconciliationSessionStatus", label: "Reconciliation status" },
      { key: "reconciliationItemId", label: "Reconciliation item ID" },
      { key: "basPeriodId", label: "BAS period ID" },
      { key: "basPeriodStatus", label: "BAS period status" },
      { key: "basRunId", label: "BAS run ID" },
      { key: "basRunStatus", label: "BAS run status" },
      { key: "basAdjustmentId", label: "BAS adjustment ID" },
      { key: "basReviewNoteId", label: "BAS review note ID" },
      { key: "fixedAssetId", label: "Fixed asset ID" },
      { key: "fixedAssetStatus", label: "Fixed asset status" },
      { key: "depreciationRunId", label: "Depreciation run ID" },
      { key: "depreciationRunStatus", label: "Depreciation run status" },
      { key: "taxPackId", label: "Tax pack ID" },
      { key: "taxPackStatus", label: "Tax pack status" },
      { key: "taxAdjustmentId", label: "Tax adjustment ID" },
      { key: "taxNoteId", label: "Tax note ID" },
      { key: "taxExceptionId", label: "Tax exception ID" },
      { key: "taxExceptionStatus", label: "Tax exception status" },
    ],
  },
];

const adminMutationCards: ActionConfig[] = [
  {
    kind: "json",
    title: "Update Reviewer User",
    description: "Update the seeded reviewer user account.",
    method: "PUT",
    pathTemplate: "/api/admin/users/{{reviewerUserId}}",
    auth: "token",
    defaultBody: `{
  "email": "reviewer@example.com",
  "full_name": "Reviewer User Updated",
  "password": "StrongPass123",
  "is_superuser": false,
  "is_active": true
}`,
    visibleWhen: [{ key: "reviewerUserId", present: true }],
  },
  {
    kind: "json",
    title: "Deactivate Reviewer User",
    description: "Deactivate the reviewer user through the real admin delete endpoint.",
    method: "DELETE",
    pathTemplate: "/api/admin/users/{{reviewerUserId}}",
    auth: "token",
    visibleWhen: [{ key: "reviewerUserId", present: true }],
    clearOnSuccess: ["reviewerUserStatus"],
  },
];

const companyMutationCards: ActionConfig[] = [
  {
    kind: "json",
    title: "Update Company",
    description: "Update the selected company metadata.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}",
    auth: "token",
    defaultBody: `{
  "legal_name": "Example Pty Ltd Updated",
  "trading_name": "Example Trading",
  "abn": "51824753556",
  "acn": "824753556",
  "entity_type": "company",
  "is_active": true,
  "base_currency": "AUD",
  "country_code": "AU"
}`,
    visibleWhen: [{ key: "companyId", present: true }],
  },
  {
    kind: "json",
    title: "Deactivate Company",
    description: "Soft-delete the selected company through the real company delete route.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}",
    auth: "token",
    visibleWhen: [{ key: "companyId", present: true }],
    clearOnSuccess: ["companyStatus"],
  },
  {
    kind: "json",
    title: "Update Latest Configuration",
    description: "Update the captured configuration version for the company.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/configurations/{{configurationId}}",
    auth: "token",
    defaultBody: `{
  "effective_from": "2026-10-01",
  "gst_registered": true,
  "bas_frequency": "monthly",
  "bas_reporting_basis": "accrual",
  "financial_year_start_month": 7,
  "financial_year_start_day": 1,
  "allow_self_approval": true,
  "self_approval_mode": "warn",
  "period_lock_policy": "after_export"
}`,
    visibleWhen: [
      { key: "companyId", present: true },
      { key: "configurationId", present: true },
    ],
  },
  {
    kind: "json",
    title: "Delete Latest Configuration",
    description: "Delete the captured configuration version when it is still editable.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/configurations/{{configurationId}}",
    auth: "token",
    visibleWhen: [
      { key: "companyId", present: true },
      { key: "configurationId", present: true },
    ],
    clearOnSuccess: ["configurationId"],
  },
  {
    kind: "json",
    title: "Update Reviewer Access",
    description: "Update the reviewer access row for the selected company.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/access/{{reviewerUserId}}",
    auth: "token",
    defaultBody: `{
  "can_prepare": true,
  "can_review": true,
  "can_approve": true,
  "can_administer": false
}`,
    visibleWhen: [
      { key: "companyId", present: true },
      { key: "reviewerUserId", present: true },
    ],
  },
  {
    kind: "json",
    title: "Remove Reviewer Access",
    description: "Delete the reviewer access row for the selected company.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/access/{{reviewerUserId}}",
    auth: "token",
    visibleWhen: [
      { key: "companyId", present: true },
      { key: "reviewerUserId", present: true },
    ],
  },
  {
    kind: "json",
    title: "Update Sales Category",
    description: "Update the captured reporting category.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/reporting-categories/{{salesCategoryId}}",
    auth: "token",
    defaultBody: `{
  "code": "SALES",
  "name": "Sales Updated",
  "category_type": "pnl"
}`,
    visibleWhen: [{ key: "salesCategoryId", present: true }],
  },
  {
    kind: "json",
    title: "Delete Sales Category",
    description: "Delete the captured reporting category if nothing references it yet.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/reporting-categories/{{salesCategoryId}}",
    auth: "token",
    visibleWhen: [{ key: "salesCategoryId", present: true }],
    clearOnSuccess: ["salesCategoryId"],
  },
  {
    kind: "json",
    title: "Update SALE_G1 Tax Code",
    description: "Update the main sales tax code.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/tax-codes/{{saleG1TaxCodeId}}",
    auth: "token",
    defaultBody: `{
  "code": "SALE_G1",
  "name": "Tax SALE_G1 Updated",
  "description": "Sales amount for BAS label G1",
  "rate": "0.10",
  "is_gst_applicable": true,
  "bas_label": "G1",
  "input_output_type": "output_taxed"
}`,
    visibleWhen: [{ key: "saleG1TaxCodeId", present: true }],
  },
  {
    kind: "json",
    title: "Update Cash Account",
    description: "Update the captured cash account.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/accounts/{{cashAccountId}}",
    auth: "token",
    defaultBody: `{
  "account_code": "1000",
  "name": "Cash Updated",
  "account_type": "asset",
  "is_active": true,
  "allow_manual_posting": true
}`,
    visibleWhen: [{ key: "cashAccountId", present: true }],
  },
  {
    kind: "json",
    title: "Deactivate Cash Account",
    description: "Soft-delete the captured cash account.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/accounts/{{cashAccountId}}",
    auth: "token",
    visibleWhen: [{ key: "cashAccountId", present: true }],
  },
];

const periodJournalDocumentMutationCards: ActionConfig[] = [
  {
    kind: "json",
    title: "Update Quarter Period",
    description: "Update the quarter period while it is still in draft.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/periods/{{q1PeriodId}}",
    auth: "token",
    defaultBody: `{
  "name": "FY26-Q1 Updated",
  "period_type": "quarter",
  "start_date": "2026-07-01",
  "end_date": "2026-09-30"
}`,
    notes: ["Run this before submitting or approving the period."],
    visibleWhen: [
      { key: "q1PeriodId", present: true },
      { key: "q1PeriodStatus", equals: "draft" },
    ],
  },
  {
    kind: "json",
    title: "Update Expense Journal",
    description: "Update the expense journal while it is still in draft.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/journals/{{officeExpenseJournalId}}",
    auth: "token",
    defaultBody: `{
  "entry_date": "2026-08-01",
  "accounting_period_id": "{{yearPeriodId}}",
  "source_type": "manual",
  "description": "Office supplies updated",
  "reference": "EXP-001",
  "lines": [
    {
      "account_id": "{{expenseAccountId}}",
      "debit_amount": "35.00",
      "credit_amount": "0.00"
    },
    {
      "account_id": "{{cashAccountId}}",
      "debit_amount": "0.00",
      "credit_amount": "35.00"
    }
  ]
}`,
    notes: ["Run this before posting the expense journal."],
    visibleWhen: [
      { key: "officeExpenseJournalId", present: true },
      { key: "officeExpenseJournalStatus", equals: "draft" },
    ],
  },
  {
    kind: "json",
    title: "Delete Expense Journal",
    description: "Delete the expense journal while it is still in draft.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/journals/{{officeExpenseJournalId}}",
    auth: "token",
    notes: ["Run this before posting the expense journal."],
    visibleWhen: [
      { key: "officeExpenseJournalId", present: true },
      { key: "officeExpenseJournalStatus", equals: "draft" },
    ],
    clearOnSuccess: ["officeExpenseJournalId", "officeExpenseJournalStatus"],
  },
  {
    kind: "json",
    title: "Update Document",
    description: "Rename the captured support document.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/documents/{{documentId}}",
    auth: "token",
    defaultBody: `{
  "original_filename": "invoice-updated.txt",
  "media_type": "text/plain"
}`,
    visibleWhen: [{ key: "documentId", present: true }],
  },
  {
    kind: "json",
    title: "Update Document Link",
    description: "Update the captured document link note.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/documents/{{documentId}}/links/{{documentLinkId}}",
    auth: "token",
    defaultBody: `{
  "entity_type": "journal_entry",
  "entity_id": "{{saleJournalId}}",
  "note": "Updated support link"
}`,
    visibleWhen: [
      { key: "documentId", present: true },
      { key: "documentLinkId", present: true },
    ],
  },
  {
    kind: "json",
    title: "Delete Document Link",
    description: "Delete the captured document link.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/documents/{{documentId}}/links/{{documentLinkId}}",
    auth: "token",
    visibleWhen: [
      { key: "documentId", present: true },
      { key: "documentLinkId", present: true },
    ],
    clearOnSuccess: ["documentLinkId"],
  },
  {
    kind: "json",
    title: "Delete Document",
    description: "Delete the captured support document once links are removed.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/documents/{{documentId}}",
    auth: "token",
    visibleWhen: [
      { key: "documentId", present: true },
      { key: "documentLinkId", absent: true },
    ],
    clearOnSuccess: ["documentId"],
  },
];

const bankingBasMutationCards: ActionConfig[] = [
  {
    kind: "json",
    title: "Update Bank Account",
    description: "Update the captured bank account metadata.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/bank-accounts/{{bankAccountId}}",
    auth: "token",
    defaultBody: `{
  "name": "Main Operating Updated",
  "bank_name": "Example Bank",
  "bsb": "123-456",
  "account_number_masked": "xxxx5678",
  "is_active": true
}`,
    visibleWhen: [{ key: "bankAccountId", present: true }],
  },
  {
    kind: "json",
    title: "Deactivate Bank Account",
    description: "Soft-delete the captured bank account.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/bank-accounts/{{bankAccountId}}",
    auth: "token",
    visibleWhen: [{ key: "bankAccountId", present: true }],
  },
  {
    kind: "json",
    title: "Update Bank Import Session",
    description: "Update the note on a staged bank import session.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/bank-imports/{{bankImportSessionId}}",
    auth: "token",
    defaultBody: `{
  "note": "Updated staged import note"
}`,
    visibleWhen: [
      { key: "bankImportSessionId", present: true },
      { key: "bankImportSessionStatus", equals: "staged" },
    ],
  },
  {
    kind: "json",
    title: "Delete Bank Import Session",
    description: "Delete a staged bank import session.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/bank-imports/{{bankImportSessionId}}",
    auth: "token",
    visibleWhen: [
      { key: "bankImportSessionId", present: true },
      { key: "bankImportSessionStatus", equals: "staged" },
    ],
    clearOnSuccess: ["bankImportSessionId", "bankImportSessionStatus", "reconciliationItemId"],
  },
  {
    kind: "json",
    title: "Update Reconciliation Session",
    description: "Update the note on the active reconciliation session.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions/{{reconciliationSessionId}}",
    auth: "token",
    defaultBody: `{
  "accounting_period_id": "{{q1PeriodId}}",
  "note": "Updated reconciliation note"
}`,
    visibleWhen: [
      { key: "reconciliationSessionId", present: true },
      { key: "reconciliationSessionStatus", oneOf: ["draft", "in_progress"] },
    ],
  },
  {
    kind: "json",
    title: "Delete Reconciliation Session",
    description: "Delete the active reconciliation session and reset all of its bank rows to staged.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions/{{reconciliationSessionId}}",
    auth: "token",
    visibleWhen: [
      { key: "reconciliationSessionId", present: true },
      { key: "reconciliationSessionStatus", oneOf: ["draft", "in_progress"] },
    ],
    clearOnSuccess: ["reconciliationSessionId", "reconciliationSessionStatus", "reconciliationItemId"],
  },
  {
    kind: "json",
    title: "Update BAS Period",
    description: "Update the note on the selected BAS period.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/bas/periods/{{basPeriodId}}",
    auth: "token",
    defaultBody: `{
  "note": "Updated BAS period note"
}`,
    visibleWhen: [
      { key: "basPeriodId", present: true },
      { key: "basPeriodStatus", oneOf: ["draft", "generated", "approved"] },
      { key: "basRunId", absent: true },
    ],
  },
  {
    kind: "json",
    title: "Delete BAS Period",
    description: "Delete the selected BAS period when no run exists.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/bas/periods/{{basPeriodId}}",
    auth: "token",
    visibleWhen: [
      { key: "basPeriodId", present: true },
      { key: "basPeriodStatus", oneOf: ["draft", "generated", "approved"] },
      { key: "basRunId", absent: true },
    ],
    clearOnSuccess: ["basPeriodId", "basPeriodStatus"],
  },
  {
    kind: "json",
    title: "Update BAS Run",
    description: "Rebuild the selected BAS run against the selected BAS period.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}",
    auth: "token",
    defaultBody: `{
  "bas_period_id": "{{basPeriodId}}"
}`,
    visibleWhen: [
      { key: "basRunId", present: true },
      { key: "basRunStatus", equals: "draft" },
    ],
  },
  {
    kind: "json",
    title: "Delete BAS Run",
    description: "Delete the selected draft BAS run.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}",
    auth: "token",
    visibleWhen: [
      { key: "basRunId", present: true },
      { key: "basRunStatus", equals: "draft" },
    ],
    clearOnSuccess: ["basRunId", "basRunStatus", "basAdjustmentId", "basReviewNoteId", "exportDocumentId"],
  },
  {
    kind: "json",
    title: "Update BAS Adjustment",
    description: "Update the captured BAS adjustment.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/adjustments/{{basAdjustmentId}}",
    auth: "token",
    defaultBody: `{
  "label": "G1",
  "amount": "7.50",
  "note": "Updated BAS adjustment"
}`,
    visibleWhen: [
      { key: "basAdjustmentId", present: true },
      { key: "basRunStatus", oneOf: ["draft", "review"] },
    ],
  },
  {
    kind: "json",
    title: "Delete BAS Adjustment",
    description: "Delete the captured BAS adjustment.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/adjustments/{{basAdjustmentId}}",
    auth: "token",
    visibleWhen: [
      { key: "basAdjustmentId", present: true },
      { key: "basRunStatus", oneOf: ["draft", "review"] },
    ],
    clearOnSuccess: ["basAdjustmentId"],
  },
  {
    kind: "json",
    title: "Update BAS Review Note",
    description: "Update the captured manual BAS review note.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/review-notes/{{basReviewNoteId}}",
    auth: "token",
    defaultBody: `{
  "severity": "warning",
  "message": "Updated BAS review note",
  "related_label": "G1"
}`,
    visibleWhen: [
      { key: "basReviewNoteId", present: true },
      { key: "basRunStatus", oneOf: ["draft", "review"] },
    ],
  },
  {
    kind: "json",
    title: "Delete BAS Review Note",
    description: "Delete the captured manual BAS review note.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/review-notes/{{basReviewNoteId}}",
    auth: "token",
    visibleWhen: [
      { key: "basReviewNoteId", present: true },
      { key: "basRunStatus", oneOf: ["draft", "review"] },
    ],
    clearOnSuccess: ["basReviewNoteId"],
  },
];

const fixedAssetTaxMutationCards: ActionConfig[] = [
  {
    kind: "json",
    title: "Update Fixed Asset",
    description: "Update the selected fixed asset before depreciation history exists.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/fixed-assets/{{fixedAssetId}}",
    auth: "token",
    defaultBody: `{
  "asset_code": "FA-100",
  "name": "Laptop Updated",
  "acquisition_date": "2026-07-01",
  "in_service_date": "2026-07-01",
  "cost_amount": "1200.00",
  "salvage_value": "0.00",
  "useful_life_months": 12,
  "depreciation_method": "straight_line",
  "asset_account_id": "{{assetAccountId}}",
  "accumulated_depreciation_account_id": "{{accumulatedDepAccountId}}",
  "depreciation_expense_account_id": "{{depExpenseAccountId}}",
  "acquisition_reference": "INV-001",
  "note": "Updated fixed asset"
}`,
    visibleWhen: [
      { key: "fixedAssetId", present: true },
      { key: "fixedAssetStatus", equals: "active" },
      { key: "depreciationRunId", absent: true },
    ],
  },
  {
    kind: "json",
    title: "Delete Fixed Asset",
    description: "Delete the selected fixed asset before depreciation history exists.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/fixed-assets/{{fixedAssetId}}",
    auth: "token",
    visibleWhen: [
      { key: "fixedAssetId", present: true },
      { key: "fixedAssetStatus", equals: "active" },
      { key: "depreciationRunId", absent: true },
    ],
    clearOnSuccess: ["fixedAssetId", "fixedAssetStatus"],
  },
  {
    kind: "json",
    title: "Update Depreciation Run",
    description: "Rebuild the selected draft depreciation run.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/fixed-assets/depreciation-runs/{{depreciationRunId}}",
    auth: "token",
    defaultBody: `{
  "accounting_period_id": "{{q1PeriodId}}",
  "start_date": "2026-07-01",
  "end_date": "2026-08-31",
  "note": "Updated depreciation run"
}`,
    visibleWhen: [
      { key: "depreciationRunId", present: true },
      { key: "depreciationRunStatus", equals: "draft" },
    ],
  },
  {
    kind: "json",
    title: "Delete Depreciation Run",
    description: "Delete the selected draft depreciation run.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/fixed-assets/depreciation-runs/{{depreciationRunId}}",
    auth: "token",
    visibleWhen: [
      { key: "depreciationRunId", present: true },
      { key: "depreciationRunStatus", equals: "draft" },
    ],
    clearOnSuccess: ["depreciationRunId", "depreciationRunStatus"],
  },
  {
    kind: "json",
    title: "Update Tax Pack",
    description: "Rebuild the selected draft tax workpaper pack.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}",
    auth: "token",
    defaultBody: `{
  "accounting_period_id": "{{yearPeriodId}}",
  "note": "Updated tax pack"
}`,
    visibleWhen: [
      { key: "taxPackId", present: true },
      { key: "taxPackStatus", equals: "draft" },
      { key: "taxAdjustmentId", absent: true },
      { key: "taxNoteId", absent: true },
      { key: "taxExceptionId", absent: true },
    ],
  },
  {
    kind: "json",
    title: "Delete Tax Pack",
    description: "Delete the selected draft tax workpaper pack.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}",
    auth: "token",
    visibleWhen: [
      { key: "taxPackId", present: true },
      { key: "taxPackStatus", equals: "draft" },
      { key: "taxAdjustmentId", absent: true },
      { key: "taxNoteId", absent: true },
      { key: "taxExceptionId", absent: true },
    ],
    clearOnSuccess: ["taxPackId", "taxPackStatus", "taxAdjustmentId", "taxNoteId", "taxExceptionId"],
  },
  {
    kind: "json",
    title: "Update Tax Adjustment",
    description: "Update the captured tax adjustment.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/adjustments/{{taxAdjustmentId}}",
    auth: "token",
    defaultBody: `{
  "label": "NON_DEDUCTIBLE",
  "amount": "25.00",
  "note": "Updated tax adjustment"
}`,
    visibleWhen: [
      { key: "taxAdjustmentId", present: true },
      { key: "taxPackStatus", oneOf: ["draft", "review"] },
    ],
  },
  {
    kind: "json",
    title: "Delete Tax Adjustment",
    description: "Delete the captured tax adjustment.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/adjustments/{{taxAdjustmentId}}",
    auth: "token",
    visibleWhen: [
      { key: "taxAdjustmentId", present: true },
      { key: "taxPackStatus", oneOf: ["draft", "review"] },
    ],
    clearOnSuccess: ["taxAdjustmentId"],
  },
  {
    kind: "json",
    title: "Update Tax Note",
    description: "Update the captured tax review or sign-off note.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/notes/{{taxNoteId}}",
    auth: "token",
    defaultBody: `{
  "note_type": "review",
  "message": "Updated tax review note"
}`,
    visibleWhen: [
      { key: "taxNoteId", present: true },
      { key: "taxPackStatus", oneOf: ["draft", "review"] },
    ],
  },
  {
    kind: "json",
    title: "Delete Tax Note",
    description: "Delete the captured tax note.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/notes/{{taxNoteId}}",
    auth: "token",
    visibleWhen: [
      { key: "taxNoteId", present: true },
      { key: "taxPackStatus", oneOf: ["draft", "review"] },
    ],
    clearOnSuccess: ["taxNoteId"],
  },
  {
    kind: "json",
    title: "Update Tax Exception",
    description: "Update the captured open tax exception.",
    method: "PUT",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/exceptions/{{taxExceptionId}}",
    auth: "token",
    defaultBody: `{
  "severity": "warning",
  "message": "Updated tax exception"
}`,
    visibleWhen: [
      { key: "taxExceptionId", present: true },
      { key: "taxExceptionStatus", equals: "open" },
      { key: "taxPackStatus", oneOf: ["draft", "review"] },
    ],
  },
  {
    kind: "json",
    title: "Delete Tax Exception",
    description: "Delete the captured tax exception.",
    method: "DELETE",
    pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/exceptions/{{taxExceptionId}}",
    auth: "token",
    visibleWhen: [
      { key: "taxExceptionId", present: true },
      { key: "taxExceptionStatus", equals: "open" },
      { key: "taxPackStatus", oneOf: ["draft", "review"] },
    ],
    clearOnSuccess: ["taxExceptionId", "taxExceptionStatus"],
  },
];

export const workbenchSections: WorkbenchSection[] = [
  {
    title: "Authentication and Admin",
    description: "Bootstrap users, log in, inspect session identity, and manage admin-level data.",
    cards: [
      {
        kind: "json",
        title: "Bootstrap Admin",
        description: "Create the initial admin user and capture the returned token.",
        method: "POST",
        pathTemplate: "/api/auth/bootstrap",
        defaultBody: `{
  "email": "admin@example.com",
  "full_name": "Initial Admin",
  "password": "StrongPass123"
}`,
        capture: [{ target: "token", path: "access_token" }],
      },
      {
        kind: "json",
        title: "Login As Admin",
        description: "Request a bearer token for the primary operator.",
        method: "POST",
        pathTemplate: "/api/auth/login",
        defaultBody: `{
  "email": "admin@example.com",
  "password": "StrongPass123"
}`,
        capture: [{ target: "token", path: "access_token" }],
      },
      {
        kind: "json",
        title: "Login As Reviewer",
        description: "Request a second token for maker-checker validation flows.",
        method: "POST",
        pathTemplate: "/api/auth/login",
        defaultBody: `{
  "email": "reviewer@example.com",
  "password": "StrongPass123"
}`,
        capture: [{ target: "reviewerToken", path: "access_token" }],
      },
      {
        kind: "json",
        title: "Current Session",
        description: "Verify the current authorized user identity.",
        method: "GET",
        pathTemplate: "/api/auth/me",
        auth: "token",
      },
      {
        kind: "json",
        title: "Admin Overview",
        description: "Inspect top-level system counts.",
        method: "GET",
        pathTemplate: "/api/admin/overview",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create Reviewer User",
        description: "Create a non-superuser reviewer account and capture its ID.",
        method: "POST",
        pathTemplate: "/api/admin/users",
        auth: "token",
        defaultBody: `{
  "email": "reviewer@example.com",
  "full_name": "Reviewer User",
  "password": "StrongPass123",
  "is_superuser": false
}`,
        capture: [
          { target: "reviewerUserId", path: "id" },
          { target: "reviewerUserStatus", path: "is_active" },
        ],
      },
      {
        kind: "json",
        title: "List Users",
        description: "Show all users available to the admin.",
        method: "GET",
        pathTemplate: "/api/admin/users",
        auth: "token",
      },
      ...adminMutationCards,
    ],
  },
  {
    title: "Company and Reference Data",
    description: "Create the company, grant access, and seed chart, tax, and account reference data.",
    cards: [
      {
        kind: "json",
        title: "Create Company",
        description: "Create the primary company and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies",
        auth: "token",
        defaultBody: `{
  "legal_name": "Example Pty Ltd",
  "trading_name": "Example Trading",
  "abn": "51824753556",
  "acn": "824753556",
  "entity_type": "company",
  "initial_configuration": {
    "effective_from": "2026-07-01",
    "gst_registered": true,
    "bas_frequency": "quarterly",
    "bas_reporting_basis": "accrual",
    "financial_year_start_month": 7,
    "financial_year_start_day": 1,
    "allow_self_approval": true,
    "self_approval_mode": "warn",
    "period_lock_policy": "after_approval"
  }
}`,
        capture: [
          { target: "companyId", path: "id" },
          { target: "companyStatus", path: "is_active" },
        ],
      },
      {
        kind: "json",
        title: "List Companies",
        description: "List all accessible companies.",
        method: "GET",
        pathTemplate: "/api/companies",
        auth: "token",
      },
      {
        kind: "json",
        title: "Get Company",
        description: "Inspect the currently selected company.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}",
        auth: "token",
      },
      {
        kind: "json",
        title: "Add Company Configuration",
        description: "Create a second configuration version to test history and effectivity.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/configurations",
        auth: "token",
        defaultBody: `{
  "effective_from": "2026-10-01",
  "gst_registered": true,
  "bas_frequency": "monthly",
  "bas_reporting_basis": "accrual",
  "financial_year_start_month": 7,
  "financial_year_start_day": 1,
  "allow_self_approval": true,
  "self_approval_mode": "warn",
  "period_lock_policy": "after_export"
}`,
        capture: [{ target: "configurationId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Configurations",
        description: "Show the configuration history for the selected company.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/configurations",
        auth: "token",
        capture: [{ target: "configurationId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Grant Reviewer Access",
        description: "Grant the reviewer user company-scoped permissions.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/access",
        auth: "token",
        defaultBody: `{
  "user_id": "{{reviewerUserId}}",
  "can_prepare": true,
  "can_review": true,
  "can_approve": true,
  "can_administer": false
}`,
      },
      {
        kind: "json",
        title: "List Company Access",
        description: "Inspect all access rows for the selected company.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/access",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create Reporting Category",
        description: "Create the sales reporting category used by revenue accounts.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/reporting-categories",
        auth: "token",
        defaultBody: `{
  "code": "SALES",
  "name": "Sales",
  "category_type": "pnl"
}`,
        capture: [{ target: "salesCategoryId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Reporting Categories",
        description: "Show company and shared reporting categories.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reporting-categories",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create SALE_G1 Tax Code",
        description: "Create the BAS G1 sales tax code.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-codes",
        auth: "token",
        defaultBody: `{
  "code": "SALE_G1",
  "name": "Tax SALE_G1",
  "description": "Sales amount for BAS label G1",
  "rate": "0.10",
  "is_gst_applicable": true,
  "bas_label": "G1",
  "input_output_type": "output_taxed"
}`,
        capture: [{ target: "saleG1TaxCodeId", path: "id" }],
      },
      {
        kind: "json",
        title: "Create GST_1A Tax Code",
        description: "Create the GST payable tax code for BAS label 1A.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-codes",
        auth: "token",
        defaultBody: `{
  "code": "GST_1A",
  "name": "Tax GST_1A",
  "description": "GST payable for BAS label 1A",
  "rate": "0.10",
  "is_gst_applicable": true,
  "bas_label": "1A",
  "input_output_type": "output_taxed"
}`,
        capture: [{ target: "gst1ATaxCodeId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Tax Codes",
        description: "Show company and shared tax codes.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-codes",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create Cash Account",
        description: "Create the operating cash account.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
        defaultBody: `{
  "account_code": "1000",
  "name": "Cash",
  "account_type": "asset"
}`,
        capture: [{ target: "cashAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "Create Revenue Account",
        description: "Create the sales revenue account linked to the reporting category and default tax code.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
        defaultBody: `{
  "account_code": "4000",
  "name": "Revenue",
  "account_type": "income",
  "reporting_category_id": "{{salesCategoryId}}",
  "default_tax_code_id": "{{saleG1TaxCodeId}}"
}`,
        capture: [{ target: "revenueAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "Create GST Payable Account",
        description: "Create the GST payable liability account.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
        defaultBody: `{
  "account_code": "2200",
  "name": "GST Payable",
  "account_type": "liability",
  "default_tax_code_id": "{{gst1ATaxCodeId}}"
}`,
        capture: [{ target: "gstPayableAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "Create Expense Account",
        description: "Create the office expense account.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
        defaultBody: `{
  "account_code": "5000",
  "name": "Office Expense",
  "account_type": "expense"
}`,
        capture: [{ target: "expenseAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "Create Asset Account",
        description: "Create the plant equipment account for fixed assets.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
        defaultBody: `{
  "account_code": "1500",
  "name": "Plant Equipment",
  "account_type": "asset"
}`,
        capture: [{ target: "assetAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "Create Accumulated Depreciation Account",
        description: "Create the contra asset account for accumulated depreciation.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
        defaultBody: `{
  "account_code": "1590",
  "name": "Accumulated Depreciation",
  "account_type": "contra_asset"
}`,
        capture: [{ target: "accumulatedDepAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "Create Depreciation Expense Account",
        description: "Create the expense account used by depreciation postings.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
        defaultBody: `{
  "account_code": "6100",
  "name": "Depreciation Expense",
  "account_type": "expense"
}`,
        capture: [{ target: "depExpenseAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Accounts",
        description: "Show all company chart of accounts rows.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/accounts",
        auth: "token",
      },
      ...companyMutationCards,
    ],
  },
  {
    title: "Periods, Journals, and Documents",
    description: "Run the core accounting lifecycle with period controls, journals, and supporting documents.",
    cards: [
      {
        kind: "json",
        title: "Create Quarter Period",
        description: "Create the working quarter for day-to-day transactions.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods",
        auth: "token",
        defaultBody: `{
  "name": "FY26-Q1",
  "period_type": "quarter",
  "start_date": "2026-07-01",
  "end_date": "2026-09-30"
}`,
        capture: [
          { target: "q1PeriodId", path: "id" },
          { target: "q1PeriodStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "Create Year Period",
        description: "Create the financial year period for tax workpapers.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods",
        auth: "token",
        defaultBody: `{
  "name": "FY27",
  "period_type": "year",
  "start_date": "2026-07-01",
  "end_date": "2027-06-30"
}`,
        capture: [
          { target: "yearPeriodId", path: "id" },
          { target: "yearPeriodStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "List Periods",
        description: "Inspect all accounting periods for the company.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/periods",
        auth: "token",
      },
      {
        kind: "json",
        title: "Submit Quarter Period",
        description: "Move the quarter period into review.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods/{{q1PeriodId}}/submit",
        auth: "token",
        defaultBody: `{
  "note": "Quarter period ready"
}`,
          capture: [{ target: "q1PeriodStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Approve Quarter Period",
        description: "Approve the quarter period for posting and BAS testing.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods/{{q1PeriodId}}/approve",
        auth: "token",
        defaultBody: `{
  "note": "Quarter period approved"
}`,
          capture: [{ target: "q1PeriodStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Submit Year Period",
        description: "Move the year period into review.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods/{{yearPeriodId}}/submit",
        auth: "token",
        defaultBody: `{
  "note": "Year period ready"
}`,
          capture: [{ target: "yearPeriodStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Approve Year Period",
        description: "Approve the year period for tax workpaper generation.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods/{{yearPeriodId}}/approve",
        auth: "token",
        defaultBody: `{
  "note": "Year period approved"
}`,
          capture: [{ target: "yearPeriodStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Lock Quarter Period",
        description: "Manually lock the quarter period if you want to test lock enforcement.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods/{{q1PeriodId}}/lock",
        auth: "token",
        defaultBody: `{
  "reason": "Manual lock from frontend workbench"
}`,
          capture: [{ target: "q1PeriodStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Unlock Quarter Period",
        description: "Undo a manual lock for continued testing.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/periods/{{q1PeriodId}}/unlock",
        auth: "token",
        defaultBody: `{
  "reason": "Reopened for testing"
}`,
          capture: [{ target: "q1PeriodStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Create Sale Journal",
        description: "Create the GST sale journal and capture the journal ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/journals",
        auth: "token",
        defaultBody: `{
  "entry_date": "2026-07-15",
  "accounting_period_id": "{{q1PeriodId}}",
  "source_type": "manual",
  "description": "Sale with GST",
  "reference": "INV-001",
  "lines": [
    {
      "account_id": "{{cashAccountId}}",
      "debit_amount": "110.00",
      "credit_amount": "0.00"
    },
    {
      "account_id": "{{revenueAccountId}}",
      "debit_amount": "0.00",
      "credit_amount": "100.00",
      "tax_code_id": "{{saleG1TaxCodeId}}"
    },
    {
      "account_id": "{{gstPayableAccountId}}",
      "debit_amount": "0.00",
      "credit_amount": "10.00",
      "tax_code_id": "{{gst1ATaxCodeId}}"
    }
  ]
}`,
        capture: [{ target: "saleJournalId", path: "id" }],
      },
      {
        kind: "json",
        title: "Post Sale Journal",
        description: "Post the sale journal into the ledger.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/journals/{{saleJournalId}}/post",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create Expense Journal",
        description: "Create an office expense journal for year-end reporting and tax support.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/journals",
        auth: "token",
        defaultBody: `{
  "entry_date": "2026-08-01",
  "accounting_period_id": "{{yearPeriodId}}",
  "source_type": "manual",
  "description": "Office supplies",
  "reference": "EXP-001",
  "lines": [
    {
      "account_id": "{{expenseAccountId}}",
      "debit_amount": "30.00",
      "credit_amount": "0.00"
    },
    {
      "account_id": "{{cashAccountId}}",
      "debit_amount": "0.00",
      "credit_amount": "30.00"
    }
  ]
}`,
        capture: [
          { target: "officeExpenseJournalId", path: "id" },
          { target: "officeExpenseJournalStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "Post Expense Journal",
        description: "Post the office expense journal into the ledger.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/journals/{{officeExpenseJournalId}}/post",
        auth: "token",
        capture: [{ target: "officeExpenseJournalStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Reverse Expense Journal",
        description: "Optional reversal test for posted journals.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/journals/{{officeExpenseJournalId}}/reverse",
        auth: "token",
      },
      {
        kind: "json",
        title: "List Journals",
        description: "Show all journal entries and line details.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/journals",
        auth: "token",
      },
      {
        kind: "json",
        title: "Trial Balance",
        description: "Show trial balance rows from the ledger endpoint.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/journals/trial-balance",
        auth: "token",
      },
      {
        kind: "upload",
        title: "Upload Support Document",
        description: "Upload a document directly from the browser and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/documents",
        auth: "token",
        fields: [{ name: "note", valueTemplate: "Invoice attachment" }],
        accept: ".txt,.pdf,.csv,.jpg,.jpeg,.png",
        capture: [{ target: "documentId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Documents",
        description: "Inspect all uploaded company documents.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/documents",
        auth: "token",
      },
      {
        kind: "json",
        title: "Link Document to Sale Journal",
        description: "Attach the uploaded document to the sale journal entry.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/documents/{{documentId}}/links",
        auth: "token",
        defaultBody: `{
  "entity_type": "journal_entry",
  "entity_id": "{{saleJournalId}}",
  "note": "Supports the posted journal"
}`,
        capture: [{ target: "documentLinkId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Document Links",
        description: "Show all links for the currently selected document.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/documents/{{documentId}}/links",
        auth: "token",
        capture: [{ target: "documentLinkId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Download Document",
        description: "Download the selected document through the frontend.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/documents/{{documentId}}/download",
        auth: "token",
        responseType: "binary",
      },
      ...periodJournalDocumentMutationCards,
    ],
  },
  {
    title: "Banking, Reconciliation, and BAS",
    description: "Load imported bank data, reconcile it, and drive the BAS workflow from the same browser workspace.",
    cards: [
      {
        kind: "json",
        title: "Create Bank Account",
        description: "Create the operating bank account and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bank-accounts",
        auth: "token",
        defaultBody: `{
  "name": "Main Operating",
  "bank_name": "Example Bank",
  "bsb": "123-456",
  "account_number_masked": "xxxx1234",
  "is_active": true
}`,
  capture: [{ target: "bankAccountId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Bank Accounts",
        description: "Inspect all bank accounts for the selected company.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bank-accounts",
        auth: "token",
      },
      {
        kind: "upload",
        title: "Upload Bank CSV",
        description: "Upload a bank CSV using the selected bank account ID and capture the import session.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bank-imports/upload",
        auth: "token",
        fields: [
          { name: "bank_account_id", valueTemplate: "{{bankAccountId}}" },
          { name: "note", valueTemplate: "Uploaded from frontend workbench" },
        ],
        accept: ".csv,text/csv",
        capture: [
          { target: "bankImportSessionId", path: "id" },
          { target: "bankImportSessionStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "List Bank Import Sessions",
        description: "Inspect staged and confirmed bank import sessions.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bank-imports",
        auth: "token",
      },
      {
        kind: "json",
        title: "List Import Rows",
        description: "Inspect imported rows for the captured bank import session.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bank-imports/{{bankImportSessionId}}/rows",
        auth: "token",
      },
      {
        kind: "json",
        title: "Confirm Import Session",
        description: "Promote the staged bank import into a confirmed import session.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bank-imports/{{bankImportSessionId}}/confirm",
        auth: "token",
        defaultBody: `{
  "note": "Ready to reconcile"
}`,
          capture: [{ target: "bankImportSessionStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Create Reconciliation Session",
        description: "Create a reconciliation session and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions",
        auth: "token",
        defaultBody: `{
  "bank_account_id": "{{bankAccountId}}",
  "accounting_period_id": "{{q1PeriodId}}",
  "note": "July reconciliation"
}`,
        capture: [
          { target: "reconciliationSessionId", path: "id" },
          { target: "reconciliationSessionStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "List Reconciliation Sessions",
        description: "Inspect all reconciliation sessions for the company.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions",
        auth: "token",
      },
      {
        kind: "json",
        title: "List Reconciliation Items",
        description: "Inspect the items for the selected reconciliation session and capture the first item ID.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions/{{reconciliationSessionId}}/items",
        auth: "token",
        capture: [{ target: "reconciliationItemId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Match Reconciliation Item",
        description: "Match the first reconciliation item against the posted sale journal.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions/{{reconciliationSessionId}}/items/{{reconciliationItemId}}/match",
        auth: "token",
        defaultBody: `{
  "matched_journal_entry_id": "{{saleJournalId}}",
  "note": "Matched to posted sale"
}`,
      },
      {
        kind: "json",
        title: "Ignore Reconciliation Item",
        description: "Optional ignore action for unresolved items.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions/{{reconciliationSessionId}}/items/{{reconciliationItemId}}/ignore",
        auth: "token",
        defaultBody: `{
  "note": "Ignored from the frontend workbench"
}`,
      },
      {
        kind: "json",
        title: "Reconciliation Summary",
        description: "Inspect matched and unmatched totals for the selected session.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions/{{reconciliationSessionId}}/summary",
        auth: "token",
      },
      {
        kind: "json",
        title: "Complete Reconciliation Session",
        description: "Complete the selected reconciliation session.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/reconciliation-sessions/{{reconciliationSessionId}}/complete",
        auth: "token",
        defaultBody: `{
  "note": "Completed cleanly"
}`,
          capture: [{ target: "reconciliationSessionStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Generate BAS Periods",
        description: "Generate BAS periods and capture the first BAS period ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/periods/generate",
        auth: "token",
        defaultBody: `{
  "start_date": "2026-07-01",
  "end_date": "2026-09-30"
}`,
        capture: [
          { target: "basPeriodId", path: "0.id" },
          { target: "basPeriodStatus", path: "0.status" },
        ],
      },
      {
        kind: "json",
        title: "List BAS Periods",
        description: "Inspect generated BAS periods.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bas/periods",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create BAS Run",
        description: "Create a BAS run and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs",
        auth: "token",
        defaultBody: `{
  "bas_period_id": "{{basPeriodId}}"
}`,
        capture: [
          { target: "basRunId", path: "id" },
          { target: "basRunStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "Get BAS Run Detail",
        description: "Inspect BAS line totals, adjustments, and warnings.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}",
        auth: "token",
      },
      {
        kind: "json",
        title: "Add BAS Adjustment",
        description: "Add a BAS adjustment to the selected run.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/adjustments",
        auth: "token",
        defaultBody: `{
  "label": "G1",
  "amount": "5.00",
  "note": "Fuel rounding adjustment"
}`,
      },
      {
        kind: "json",
        title: "List BAS Adjustments",
        description: "Inspect all adjustments attached to the selected BAS run.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/adjustments",
        auth: "token",
        capture: [{ target: "basAdjustmentId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Add BAS Review Note",
        description: "Create a BAS review note for the selected label.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/review-notes",
        auth: "token",
        defaultBody: `{
  "severity": "warning",
  "message": "Check GST coding before final export",
  "related_label": "G1"
}`,
        capture: [{ target: "basReviewNoteId", path: "id" }],
      },
      {
        kind: "json",
        title: "List BAS Review Notes",
        description: "Inspect all review notes attached to the BAS run.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/review-notes",
        auth: "token",
        capture: [{ target: "basReviewNoteId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Submit BAS Run",
        description: "Move the BAS run into review.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/submit",
        auth: "token",
        defaultBody: `{
  "note": "Ready for BAS review"
}`,
          capture: [{ target: "basRunStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Approve BAS Run",
        description: "Approve the BAS run for manual form entry.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/approve",
        auth: "token",
        defaultBody: `{
  "note": "Approved for manual BAS entry"
}`,
          capture: [{ target: "basRunStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "List BAS Approval Actions",
        description: "Inspect BAS workflow history.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/approval-actions",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create BAS CSV Export",
        description: "Generate a CSV export record for the BAS run.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/exports/csv",
        auth: "token",
        capture: [{ target: "exportDocumentId", path: "document_id" }],
      },
      {
        kind: "json",
        title: "Create BAS PDF Export",
        description: "Generate a PDF export record for the BAS run.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/exports/pdf",
        auth: "token",
        capture: [{ target: "exportDocumentId", path: "document_id" }],
      },
      {
        kind: "json",
        title: "List BAS Exports",
        description: "Inspect export records created for the BAS run.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/bas/runs/{{basRunId}}/exports",
        auth: "token",
      },
      ...bankingBasMutationCards,
    ],
  },
  {
    title: "Reports, Fixed Assets, Tax Workpapers, and Operations",
    description: "Finish the finance support cycle with reports, assets, annual workpapers, and runtime observability.",
    cards: [
      {
        kind: "json",
        title: "Report Trial Balance",
        description: "Run the reporting service trial balance with a date range.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/trial-balance?start_date=2026-07-01&end_date=2026-09-30",
        auth: "token",
      },
      {
        kind: "json",
        title: "Export Trial Balance CSV",
        description: "Download the trial balance CSV directly from the frontend.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/trial-balance/export?start_date=2026-07-01&end_date=2026-09-30",
        auth: "token",
        responseType: "binary",
      },
      {
        kind: "json",
        title: "Report Profit and Loss",
        description: "Run the profit and loss report.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/profit-and-loss?start_date=2026-07-01&end_date=2027-06-30",
        auth: "token",
      },
      {
        kind: "json",
        title: "Export Profit and Loss CSV",
        description: "Download the profit and loss CSV directly from the frontend.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/profit-and-loss/export?start_date=2026-07-01&end_date=2027-06-30",
        auth: "token",
        responseType: "binary",
      },
      {
        kind: "json",
        title: "Report Balance Sheet",
        description: "Run the balance sheet report.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/balance-sheet?as_of_date=2027-06-30",
        auth: "token",
      },
      {
        kind: "json",
        title: "Export Balance Sheet CSV",
        description: "Download the balance sheet CSV directly from the frontend.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/balance-sheet/export?as_of_date=2027-06-30",
        auth: "token",
        responseType: "binary",
      },
      {
        kind: "json",
        title: "Report General Ledger",
        description: "Run the general ledger report.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/general-ledger?start_date=2026-07-01&end_date=2027-06-30",
        auth: "token",
      },
      {
        kind: "json",
        title: "Export General Ledger CSV",
        description: "Download the general ledger CSV directly from the frontend.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/reports/general-ledger/export?start_date=2026-07-01&end_date=2027-06-30",
        auth: "token",
        responseType: "binary",
      },
      {
        kind: "json",
        title: "Create Fixed Asset",
        description: "Create the primary fixed asset and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets",
        auth: "token",
        defaultBody: `{
  "asset_code": "FA-100",
  "name": "Laptop Fleet",
  "description": "Staff laptops",
  "acquisition_date": "2026-07-01",
  "in_service_date": "2026-07-01",
  "cost_amount": "1200.00",
  "salvage_value": "0.00",
  "useful_life_months": 12,
  "depreciation_method": "straight_line",
  "asset_account_id": "{{assetAccountId}}",
  "accumulated_depreciation_account_id": "{{accumulatedDepAccountId}}",
  "depreciation_expense_account_id": "{{depExpenseAccountId}}",
  "acquisition_reference": "INV-001",
  "note": "Primary asset for QA"
}`,
        capture: [
          { target: "fixedAssetId", path: "id" },
          { target: "fixedAssetStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "List Fixed Assets",
        description: "Inspect the asset register at month end.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets?as_of_date=2026-07-31",
        auth: "token",
      },
      {
        kind: "json",
        title: "Get Fixed Asset Detail",
        description: "Inspect a single asset detail view with depreciation state.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets/{{fixedAssetId}}?as_of_date=2026-07-31",
        auth: "token",
      },
      {
        kind: "json",
        title: "Dispose Fixed Asset",
        description: "Optional disposal test for the selected asset.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets/{{fixedAssetId}}/dispose",
        auth: "token",
        defaultBody: `{
  "disposal_date": "2026-10-15",
  "disposal_reference": "SALE-100",
  "disposal_note": "Disposed after hardware refresh",
  "disposal_proceeds": "150.00"
}`,
          capture: [{ target: "fixedAssetStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Create Depreciation Run",
        description: "Generate a depreciation run and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets/depreciation-runs",
        auth: "token",
        defaultBody: `{
  "accounting_period_id": "{{q1PeriodId}}",
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "note": "July depreciation"
}`,
        capture: [
          { target: "depreciationRunId", path: "id" },
          { target: "depreciationRunStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "List Depreciation Runs",
        description: "Inspect all depreciation runs.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets/depreciation-runs",
        auth: "token",
      },
      {
        kind: "json",
        title: "Get Depreciation Run Detail",
        description: "Inspect the generated depreciation run detail.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets/depreciation-runs/{{depreciationRunId}}",
        auth: "token",
      },
      {
        kind: "json",
        title: "Post Depreciation Run",
        description: "Post the depreciation run into the ledger.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets/depreciation-runs/{{depreciationRunId}}/post",
        auth: "token",
        capture: [{ target: "depreciationRunStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Export Depreciation Run CSV",
        description: "Download the depreciation run export directly from the frontend.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/fixed-assets/depreciation-runs/{{depreciationRunId}}/export",
        auth: "token",
        responseType: "binary",
      },
      {
        kind: "json",
        title: "Create Tax Workpaper Pack",
        description: "Generate the annual tax workpaper pack and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs",
        auth: "token",
        defaultBody: `{
  "accounting_period_id": "{{yearPeriodId}}",
  "note": "FY27 workpaper pack"
}`,
        capture: [
          { target: "taxPackId", path: "id" },
          { target: "taxPackStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "List Tax Workpaper Packs",
        description: "Inspect all annual workpaper packs.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs",
        auth: "token",
      },
      {
        kind: "json",
        title: "Get Tax Pack Detail",
        description: "Inspect the selected workpaper pack detail.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}",
        auth: "token",
      },
      {
        kind: "json",
        title: "Add Tax Adjustment",
        description: "Add an annual tax adjustment to the selected pack.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/adjustments",
        auth: "token",
        defaultBody: `{
  "label": "NON_DEDUCTIBLE",
  "amount": "15.00",
  "note": "Entertainment adjustment"
}`,
  capture: [{ target: "taxAdjustmentId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "List Tax Adjustments",
        description: "Inspect tax adjustments attached to the selected pack.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/adjustments",
        auth: "token",
        capture: [{ target: "taxAdjustmentId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Add Review Note",
        description: "Create a review note on the selected tax pack.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/notes",
        auth: "token",
        defaultBody: `{
  "note_type": "review",
  "message": "Reviewed profit support schedule"
}`,
        capture: [{ target: "taxNoteId", path: "id" }],
      },
      {
        kind: "json",
        title: "Add Sign-off Note",
        description: "Create a sign-off note on the selected tax pack.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/notes",
        auth: "token",
        defaultBody: `{
  "note_type": "sign_off",
  "message": "Ready for accountant review"
}`,
        capture: [{ target: "taxNoteId", path: "id" }],
      },
      {
        kind: "json",
        title: "List Tax Notes",
        description: "Inspect notes attached to the selected pack.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/notes",
        auth: "token",
        capture: [{ target: "taxNoteId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Create Tax Exception",
        description: "Create an exception item and capture its ID.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/exceptions",
        auth: "token",
        defaultBody: `{
  "severity": "warning",
  "message": "Check private-use apportionment"
}`,
        capture: [
          { target: "taxExceptionId", path: "id" },
          { target: "taxExceptionStatus", path: "status" },
        ],
      },
      {
        kind: "json",
        title: "List Tax Exceptions",
        description: "Inspect exceptions on the selected workpaper pack.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/exceptions",
        auth: "token",
        capture: [{ target: "taxExceptionId", path: "0.id" }],
      },
      {
        kind: "json",
        title: "Resolve Tax Exception",
        description: "Resolve the selected tax exception.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/exceptions/{{taxExceptionId}}/resolve",
        auth: "token",
        defaultBody: `{
  "note": "Confirmed no private use"
}`,
          capture: [{ target: "taxExceptionStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Submit Tax Pack",
        description: "Move the selected tax workpaper pack into review.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/submit",
        auth: "token",
        defaultBody: `{
  "note": "Annual pack ready for review"
}`,
          capture: [{ target: "taxPackStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "Approve Tax Pack",
        description: "Approve the selected tax pack for accountant review.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/approve",
        auth: "token",
        defaultBody: `{
  "note": "Approved for accountant review"
}`,
          capture: [{ target: "taxPackStatus", path: "status" }],
      },
      {
        kind: "json",
        title: "List Tax Approval Actions",
        description: "Inspect the workflow history for the selected pack.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/approval-actions",
        auth: "token",
      },
      {
        kind: "json",
        title: "Create Tax Pack PDF Export",
        description: "Generate the PDF export record for the selected pack.",
        method: "POST",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/exports/pdf",
        auth: "token",
        capture: [{ target: "exportDocumentId", path: "document_id" }],
      },
      {
        kind: "json",
        title: "List Tax Exports",
        description: "Inspect export records for the selected pack.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/tax-workpapers/packs/{{taxPackId}}/exports",
        auth: "token",
      },
      {
        kind: "json",
        title: "Download Export Document",
        description: "Download the last captured export document directly from the frontend.",
        method: "GET",
        pathTemplate: "/api/companies/{{companyId}}/documents/{{exportDocumentId}}/download",
        auth: "token",
        responseType: "binary",
      },
      {
        kind: "json",
        title: "Health Live",
        description: "Fetch the liveness probe directly from the browser.",
        method: "GET",
        pathTemplate: "/health/live",
      },
      {
        kind: "json",
        title: "Health Ready",
        description: "Fetch the readiness probe directly from the browser.",
        method: "GET",
        pathTemplate: "/health/ready",
      },
      {
        kind: "json",
        title: "Aggregate Health",
        description: "Fetch the aggregate health endpoint.",
        method: "GET",
        pathTemplate: "/health",
      },
      {
        kind: "json",
        title: "Metrics Feed",
        description: "Inspect Prometheus-style runtime metrics.",
        method: "GET",
        pathTemplate: "/metrics",
        responseType: "text",
      },
      {
        kind: "json",
        title: "Recent Alerts",
        description: "Inspect recent in-process alert events.",
        method: "GET",
        pathTemplate: "/alerts/recent",
      },
      ...fixedAssetTaxMutationCards,
    ],
  },
];
