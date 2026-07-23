import { expect, test, type APIRequestContext, type Page } from "@playwright/test";


const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";
const operatorEmail = process.env.E2E_OPERATOR_EMAIL ?? "admin@example.com";
const operatorPassword = process.env.E2E_OPERATOR_PASSWORD ?? "StrongPass123";
const sessionStorageKey = "bookkeeping-tax-operator-session";

type AuthSession = {
  access_token: string;
  user: {
    id: string;
    email: string;
    full_name: string;
  };
};

type CompanyRecord = {
  id: string;
  legal_name: string;
};

type PeriodRecord = {
  id: string;
  name: string;
};

type JournalRecord = {
  id: string;
  entry_number: string;
};

type TaxCodeRecord = {
  id: string;
};

type AccountRecord = {
  id: string;
  name: string;
  account_code: string;
};


function uniqueSuffix(prefix: string) {
  const randomPart = Math.floor(Math.random() * 100000).toString().padStart(5, "0");
  return `${prefix}-${Date.now()}-${randomPart}`;
}


function uniqueDigits(length: number) {
  const raw = `${Date.now()}${Math.floor(Math.random() * 100000)}`;
  return raw.slice(-length).padStart(length, "0");
}


function uniqueAccountCode() {
  return `E2E-${uniqueDigits(8)}`;
}


async function parseResponse<T>(response: Awaited<ReturnType<APIRequestContext["fetch"]>>) {
  if (!response.ok()) {
    throw new Error(`Request failed with ${response.status()}: ${await response.text()}`);
  }
  return (await response.json()) as T;
}


async function apiJson<T>(
  request: APIRequestContext,
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  token?: string,
  data?: unknown,
) {
  const response = await request.fetch(`${apiBaseUrl}${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(data !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    data,
  });
  if (response.status() === 204) {
    return undefined as T;
  }
  return parseResponse<T>(response);
}


async function ensureOperatorSession(request: APIRequestContext) {
  const loginResponse = await request.post(`${apiBaseUrl}/api/auth/login`, {
    data: {
      email: operatorEmail,
      password: operatorPassword,
    },
  });
  if (loginResponse.ok()) {
    return (await loginResponse.json()) as AuthSession;
  }

  const bootstrapResponse = await request.post(`${apiBaseUrl}/api/auth/bootstrap`, {
    data: {
      email: operatorEmail,
      full_name: "E2E Operator",
      password: operatorPassword,
    },
  });
  if (bootstrapResponse.ok()) {
    return (await bootstrapResponse.json()) as AuthSession;
  }

  throw new Error(
    `Unable to authenticate E2E operator. Login status ${loginResponse.status()}, bootstrap status ${bootstrapResponse.status()}. ` +
      "Set E2E_OPERATOR_EMAIL and E2E_OPERATOR_PASSWORD to a valid user if bootstrap is no longer available.",
  );
}


async function seedSessionStorage(page: Page, companyId = "") {
  await ensureOperatorSession(page.request);
  await page.goto("/");
  await page.getByLabel("API base URL").fill(apiBaseUrl);
  await page.getByLabel("Email").first().fill(operatorEmail);
  await page.getByLabel("Password").first().fill(operatorPassword);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();
  if (companyId) {
    await page.evaluate(
      ({ storageKey, selectedCompanyId }) => {
        const current = JSON.parse(window.localStorage.getItem(storageKey) ?? "{}");
        window.localStorage.setItem(storageKey, JSON.stringify({ ...current, selectedCompanyId }));
      },
      { storageKey: sessionStorageKey, selectedCompanyId: companyId },
    );
  }
}


async function createCompany(request: APIRequestContext, token: string, prefix: string) {
  const abn = `51${uniqueDigits(9)}`;
  const acn = uniqueDigits(9);
  return apiJson<CompanyRecord>(request, "POST", "/api/companies", token, {
    legal_name: uniqueSuffix(prefix),
    trading_name: uniqueSuffix(`${prefix}-trading`),
    abn,
    acn,
    entity_type: "company",
    initial_configuration: {
      effective_from: "2026-01-01",
      gst_registered: true,
      bas_frequency: "quarterly",
      bas_reporting_basis: "accrual",
      financial_year_start_month: 7,
      financial_year_start_day: 1,
      allow_self_approval: true,
      self_approval_mode: "warn",
      period_lock_policy: "after_approval",
    },
  });
}


async function createAccount(request: APIRequestContext, token: string, companyId: string, payload: Record<string, unknown>) {
  return apiJson<AccountRecord>(request, "POST", `/api/companies/${companyId}/accounts`, token, {
    reporting_category_id: null,
    default_tax_code_id: null,
    is_active: true,
    allow_manual_posting: true,
    ...payload,
  });
}


async function createPeriod(request: APIRequestContext, token: string, companyId: string, name: string) {
  return apiJson<PeriodRecord>(request, "POST", `/api/companies/${companyId}/periods`, token, {
    name,
    period_type: "quarter",
    start_date: "2026-04-01",
    end_date: "2026-06-30",
  });
}


async function createYearPeriod(request: APIRequestContext, token: string, companyId: string, name: string) {
  return apiJson<PeriodRecord>(request, "POST", `/api/companies/${companyId}/periods`, token, {
    name,
    period_type: "year",
    start_date: "2025-07-01",
    end_date: "2026-06-30",
  });
}


async function createTaxCode(request: APIRequestContext, token: string, companyId: string) {
  return apiJson<TaxCodeRecord>(request, "POST", `/api/companies/${companyId}/tax-codes`, token, {
    code: uniqueSuffix("GST10").slice(-20),
    name: "GST Sales 10%",
    description: "E2E BAS sales tax code",
    rate: "0.10",
    is_gst_applicable: true,
    bas_label: "G1",
    input_output_type: "output_taxed",
  });
}


async function createPostedJournal(
  request: APIRequestContext,
  token: string,
  companyId: string,
  periodId: string,
  debitAccountId: string,
  creditAccountId: string,
  taxCodeId: string,
) {
  const journal = await apiJson<JournalRecord>(request, "POST", `/api/companies/${companyId}/journals`, token, {
    entry_date: "2026-05-12",
    accounting_period_id: periodId,
    source_type: "manual",
    description: "E2E BAS Revenue Journal",
    reference: "E2E-BAS-01",
    lines: [
      {
        account_id: debitAccountId,
        description: "Cash receipt",
        debit_amount: "110.00",
        credit_amount: "0.00",
        tax_code_id: null,
        reporting_category_id: null,
        source_document_reference: null,
      },
      {
        account_id: creditAccountId,
        description: "Sales",
        debit_amount: "0.00",
        credit_amount: "110.00",
        tax_code_id: taxCodeId,
        reporting_category_id: null,
        source_document_reference: null,
      },
    ],
  });
  await apiJson<undefined>(request, "POST", `/api/companies/${companyId}/journals/${journal.id}/post`, token);
  return journal;
}


async function createDraftJournal(
  request: APIRequestContext,
  token: string,
  companyId: string,
  periodId: string,
  debitAccountId: string,
  creditAccountId: string,
) {
  return apiJson<JournalRecord>(request, "POST", `/api/companies/${companyId}/journals`, token, {
    entry_date: "2026-05-12",
    accounting_period_id: periodId,
    source_type: "manual",
    description: "Seeded recommendation draft",
    reference: "E2E-AI-ACCEPT-01",
    lines: [
      {
        account_id: debitAccountId,
        description: "Seeded debit",
        debit_amount: "165.00",
        credit_amount: "0.00",
        tax_code_id: null,
        reporting_category_id: null,
        source_document_reference: null,
      },
      {
        account_id: creditAccountId,
        description: "Seeded credit",
        debit_amount: "0.00",
        credit_amount: "165.00",
        tax_code_id: null,
        reporting_category_id: null,
        source_document_reference: null,
      },
    ],
  });
}


test.describe.serial("operator workspace journeys", () => {
  test("signs in from the UI and navigates the route-specific operator pages", async ({ page }) => {
    await ensureOperatorSession(page.request);

    await page.goto("/");
    await page.getByLabel("API base URL").fill(apiBaseUrl);
    await page.getByLabel("Email").first().fill(operatorEmail);
    await page.getByLabel("Password").first().fill(operatorPassword);
    await page.getByTestId("login-submit").click();

    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();

    await page.getByTestId("section-link-setup").click();
    await expect(page).toHaveURL(/\/setup$/);
    await expect(page.getByTestId("section-link-setup")).toHaveClass(/is-active/);

    await page.getByTestId("section-link-bookkeeping").click();
    await expect(page).toHaveURL(/\/bookkeeping$/);
    await expect(page.getByTestId("section-link-bookkeeping")).toHaveClass(/is-active/);

    await page.getByTestId("section-link-banking").click();
    await expect(page).toHaveURL(/\/banking$/);
    await expect(page.getByTestId("section-link-banking")).toHaveClass(/is-active/);

    await page.getByTestId("section-link-employment").click();
    await expect(page).toHaveURL(/\/employment$/);
    await expect(page.getByTestId("section-link-employment")).toHaveClass(/is-active/);

    await page.getByTestId("section-link-reports").click();
    await expect(page).toHaveURL(/\/reports$/);
    await expect(page.getByTestId("section-link-reports")).toHaveClass(/is-active/);

    await page.getByTestId("section-link-year_end").click();
    await expect(page).toHaveURL(/\/year-end$/);
    await expect(page.getByTestId("section-link-year_end")).toHaveClass(/is-active/);
  });

  test("creates a period, drafts a journal, and posts it on the bookkeeping route", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Bookkeeping Company");
    const cashAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Cash at Bank",
      account_type: "asset",
    });
    const revenueAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Service Revenue",
      account_type: "income",
    });

    await seedSessionStorage(page, company.id);
    await page.goto("/bookkeeping");
    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();

    const periodName = uniqueSuffix("E2E Quarter");
    await expect(page.getByTestId("save-period")).toBeVisible();
    await page.getByLabel("Name").first().fill(periodName);
    await page.getByTestId("save-period").click();
    const createdPeriodRow = page.getByRole("row", { name: new RegExp(periodName) });
    await expect(createdPeriodRow).toBeVisible();
    await createdPeriodRow.click();

    const journalDescription = uniqueSuffix("E2E Posted Journal");
    await page.getByRole("button", { name: "Create journal", exact: true }).click();
    const journalDialog = page.getByRole("dialog", { name: "Create journal" });
    await expect(journalDialog).toBeVisible();
    await journalDialog.getByLabel("Accounting period").selectOption({ index: 1 });
    await journalDialog.getByLabel("Description").fill(journalDescription);

    const lineRows = journalDialog.locator(".line-editor-row");
    await lineRows.nth(0).locator("select").first().selectOption(cashAccount.id);
    await lineRows.nth(0).locator("input").nth(0).fill("110.00");
    await lineRows.nth(0).locator("input").nth(1).fill("0.00");

    await lineRows.nth(1).locator("select").first().selectOption(revenueAccount.id);
    await lineRows.nth(1).locator("input").nth(0).fill("0.00");
    await lineRows.nth(1).locator("input").nth(1).fill("110.00");

    await journalDialog.getByTestId("save-journal").click();
    await expect(journalDialog.getByRole("heading", { name: /^Update / })).toBeVisible();
    await journalDialog.getByTestId("post-journal").click();

    await expect(page.getByRole("row", { name: new RegExp(`${journalDescription}.*posted`) })).toBeVisible();
    await expect(journalDialog.getByRole("button", { name: "Reverse selected" })).toBeVisible();
  });

  test("analyzes a multi-document bundle, shows search verification sources, and accepts a selected proposal", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E AI Recommendation Company");
    const period = await createPeriod(page.request, auth.access_token, company.id, uniqueSuffix("E2E AI Quarter"));
    const expenseAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Settlement Fees",
      account_type: "expense",
    });
    const bankAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Operating Bank",
      account_type: "asset",
    });
    const seededJournal = await createDraftJournal(
      page.request,
      auth.access_token,
      company.id,
      period.id,
      expenseAccount.id,
      bankAccount.id,
    );

    const createdRunId = "11111111-1111-4111-8111-111111111111";
    const analyzedRunId = "22222222-2222-4222-8222-222222222222";
    const proposalId = "33333333-3333-4333-8333-333333333333";
    let acceptRequestCount = 0;

    await page.route(/\/api\/companies\/[^/]+\/journal-recommendations(?:\/[^/]+\/(analyze|accept))?$/, async (route, request) => {
      const url = new URL(request.url());
      const pathname = url.pathname;
      if (request.method() !== "POST") {
        await route.continue();
        return;
      }
      if (/\/journal-recommendations$/.test(pathname)) {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: createdRunId,
            status: "draft",
            provider_name: "openai",
            provider_model: "gpt-5.4",
            analysis_mode: "multiple",
            user_context_note: "Three-file bundle for settlement adjustments.",
            extracted_entry_date: null,
            target_accounting_period_id: period.id,
            accepted_journal_entry_id: null,
            analysis_summary: null,
            confidence_summary: null,
            warning_text: null,
            failure_reason: null,
            documents: [],
            lines: [],
            proposals: [],
            search_sources: [],
          }),
        });
        return;
      }
      if (pathname.endsWith(`/journal-recommendations/${createdRunId}/analyze`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: analyzedRunId,
            status: "review_ready",
            provider_name: "openai",
            provider_model: "gpt-5.4",
            analysis_mode: "multiple",
            user_context_note: "Three-file bundle for settlement adjustments.",
            extracted_entry_date: "2026-07-09",
            target_accounting_period_id: period.id,
            accepted_journal_entry_id: null,
            analysis_summary: "Settlement bundle separated into legal fee, GST, and GST-free title search components.",
            confidence_summary: "High confidence after document review and web verification.",
            warning_text: "Review the GST-free title search item before posting.",
            failure_reason: null,
            documents: [
              {
                id: "44444444-4444-4444-8444-444444444444",
                document_id: "55555555-5555-4555-8555-555555555555",
                display_order: 1,
                original_filename: "settlement-letter.pdf",
                media_type: "application/pdf",
                byte_size: 2048,
                created_at: "2026-07-10T09:00:00Z",
              },
              {
                id: "66666666-6666-4666-8666-666666666666",
                document_id: "77777777-7777-4777-8777-777777777777",
                display_order: 2,
                original_filename: "adjustment-sheet.pdf",
                media_type: "application/pdf",
                byte_size: 1980,
                created_at: "2026-07-10T09:00:05Z",
              },
              {
                id: "88888888-8888-4888-8888-888888888888",
                document_id: "99999999-9999-4999-8999-999999999999",
                display_order: 3,
                original_filename: "title-search.pdf",
                media_type: "application/pdf",
                byte_size: 1024,
                created_at: "2026-07-10T09:00:10Z",
              },
            ],
            lines: [
              {
                id: "aaaaaaa1-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
                line_number: 1,
                description: "Legal fee adjustment",
                explanation: "Taxable legal fee component.",
                suggested_account_id: expenseAccount.id,
                suggested_account_code: null,
                suggested_tax_code_id: null,
                suggested_tax_code_code: "GST_PURCHASE_10",
                suggested_reporting_category_id: null,
                suggested_reporting_category_code: null,
                debit_amount: "100.00",
                credit_amount: "0.00",
              },
              {
                id: "aaaaaaa2-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
                line_number: 2,
                description: "GST on legal fee",
                explanation: "GST component separated for review.",
                suggested_account_id: null,
                suggested_account_code: "2200",
                suggested_tax_code_id: null,
                suggested_tax_code_code: "GST_CONTROL",
                suggested_reporting_category_id: null,
                suggested_reporting_category_code: null,
                debit_amount: "10.00",
                credit_amount: "0.00",
              },
              {
                id: "aaaaaaa3-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
                line_number: 3,
                description: "Title search adjustment",
                explanation: "GST-free title search component.",
                suggested_account_id: null,
                suggested_account_code: "7310",
                suggested_tax_code_id: null,
                suggested_tax_code_code: "GST_FREE_PURCHASE",
                suggested_reporting_category_id: null,
                suggested_reporting_category_code: null,
                debit_amount: "55.00",
                credit_amount: "0.00",
              },
              {
                id: "aaaaaaa4-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
                line_number: 4,
                description: "Settlement cleared through operating bank",
                explanation: "Balancing payment line.",
                suggested_account_id: bankAccount.id,
                suggested_account_code: null,
                suggested_tax_code_id: null,
                suggested_tax_code_code: "NO_TAX",
                suggested_reporting_category_id: null,
                suggested_reporting_category_code: null,
                debit_amount: "0.00",
                credit_amount: "165.00",
              },
            ],
            proposals: [
              {
                id: proposalId,
                recommendation_run_id: analyzedRunId,
                proposal_type: "account",
                status: "proposed",
                suggested_code: "7310",
                suggested_name: "Title Search Fees",
                suggested_attributes_json: { account_type: "expense", allow_manual_posting: true },
                rationale: "The chart does not contain a separate title search expense account.",
                created_entity_id: null,
                created_at: "2026-07-10T09:00:20Z",
                updated_at: "2026-07-10T09:00:20Z",
              },
            ],
            search_sources: [
              {
                title: "ATO GST overview",
                url: "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst",
                domain: "www.ato.gov.au",
              },
              {
                title: "NSW Land Registry title search fees",
                url: "https://www.nswlrs.com.au/title-search",
                domain: "www.nswlrs.com.au",
              },
            ],
          }),
        });
        return;
      }
      if (pathname.endsWith(`/journal-recommendations/${analyzedRunId}/accept`)) {
        acceptRequestCount += 1;
        expect(request.postDataJSON()).toEqual({ accepted_proposal_ids: [proposalId] });
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ journals: [{ id: seededJournal.id, entry_number: seededJournal.entry_number }] }),
        });
        return;
      }
      await route.continue();
    });

    await seedSessionStorage(page, company.id);
    await page.goto("/bookkeeping");
    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();

    await page.getByLabel("Target accounting period").selectOption(period.id);
    await page.getByLabel("Upload mode").selectOption("multiple");
    await page.locator('input[type="file"][multiple]').setInputFiles([
      { name: "settlement-letter.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 settlement letter") },
      { name: "adjustment-sheet.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 adjustment sheet") },
      { name: "title-search.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 title search") },
    ]);
    await page.getByRole("button", { name: "Analyze files" }).click();

    await expect(page.getByRole("status").getByText("Generated 1 review-only journal recommendation.")).toBeVisible();
    await expect(page.getByTestId("recommendation-search-sources")).toContainText("www.ato.gov.au");
    await expect(page.getByTestId("recommendation-search-sources")).toContainText("www.nswlrs.com.au");
    await expect(page.locator("table").filter({ hasText: "Evidence" }).getByText("title-search.pdf")).toBeVisible();

    const proposalRow = page.getByRole("row", { name: /Title Search Fees/ });
    await proposalRow.locator('input[type="checkbox"]').check();
    await page.getByRole("button", { name: "Create 1 draft journal" }).click();

    await expect(page.getByRole("status").getByText(`Created 1 draft journal: ${seededJournal.entry_number}.`)).toBeVisible();
    expect(acceptRequestCount).toBe(1);
  });

  test("shows the processing veil and blocks duplicate operator actions", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Processing Company");
    let periodPostCount = 0;
    let releasePeriodPost: () => void = () => {};
    let resolveFirstPeriodPost: () => void = () => {};
    const firstPeriodPost = new Promise<void>((resolve) => {
      resolveFirstPeriodPost = resolve;
    });
    await page.route("**/api/companies/*/periods", async (route, request) => {
      if (request.method() === "POST") {
        periodPostCount += 1;
        if (periodPostCount === 1) {
          resolveFirstPeriodPost();
          await new Promise<void>((release) => {
            releasePeriodPost = release;
          });
        }
      }
      await route.continue();
    });

    await seedSessionStorage(page, company.id);
    await page.goto("/bookkeeping");
    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();

    const periodName = uniqueSuffix("E2E Processing Quarter");
    await page.getByLabel("Name").first().fill(periodName);
    await page.getByTestId("save-period").click();
    await firstPeriodPost;
    await expect(page.getByRole("status", { name: "Saving period" })).toBeVisible();

    await page.getByTestId("save-period").click({ force: true });
    await page.waitForTimeout(150);
    expect(periodPostCount).toBe(1);

    releasePeriodPost();
    await expect(page.getByRole("status", { name: "Saving period" })).toBeHidden();
    await expect(page.getByRole("row", { name: new RegExp(periodName) })).toBeVisible();
  });

  test("generates and exports a BAS run from the banking route", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E BAS Company");
    const taxCode = await createTaxCode(page.request, auth.access_token, company.id);
    const cashAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Cash at Bank",
      account_type: "asset",
    });
    const salesAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Taxable Sales",
      account_type: "income",
      default_tax_code_id: taxCode.id,
    });
    const period = await createPeriod(page.request, auth.access_token, company.id, uniqueSuffix("E2E BAS Quarter"));
    await createPostedJournal(page.request, auth.access_token, company.id, period.id, cashAccount.id, salesAccount.id, taxCode.id);

    await seedSessionStorage(page, company.id);
    await page.goto("/banking");
    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();

    await page.getByLabel("Generate from").fill("2026-04-01");
    await page.getByLabel("Generate to").fill("2026-06-30");
    await page.getByTestId("generate-bas-periods").click();
    await expect(page.getByRole("status").getByText("Generated BAS periods.")).toBeVisible();

    await page.getByRole("button", { name: /2026-04-01 to 2026-06-30/i }).click();
    await page.getByTestId("generate-bas-run").click();
    await expect(page.getByRole("status").getByText("Generated BAS run.")).toBeVisible();
    await expect(page.getByText("G1")).toBeVisible();

    await page.getByRole("button", { name: "Submit" }).click();
    await expect(page.getByRole("status").getByText("Submitted BAS run.")).toBeVisible();

    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByRole("status").getByText("Approved BAS run.")).toBeVisible();

    await page.getByTestId("create-bas-csv-export").click();
    await expect(page.getByRole("button", { name: /csv export/i })).toBeVisible();
  });

  test("creates, approves, and exports a year-end tax workpaper pack", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Year End Company");
    const taxCode = await createTaxCode(page.request, auth.access_token, company.id);
    const cashAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Year End Cash",
      account_type: "asset",
    });
    const revenueAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Year End Revenue",
      account_type: "income",
      default_tax_code_id: taxCode.id,
    });
    const yearPeriod = await createYearPeriod(page.request, auth.access_token, company.id, uniqueSuffix("E2E Financial Year"));
    await createPostedJournal(page.request, auth.access_token, company.id, yearPeriod.id, cashAccount.id, revenueAccount.id, taxCode.id);

    await seedSessionStorage(page, company.id);
    await page.goto("/year-end");
    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();

    await page.getByLabel("Year period").selectOption(yearPeriod.id);
    await page.getByLabel("Pack note").fill("Year-end workpapers for operator e2e");
    await page.getByTestId("save-tax-pack").click();
    await expect(page.getByRole("status").getByText("Saved tax workpaper pack.")).toBeVisible();

    await expect(page.locator('[data-testid^="tax-pack-row-"]')).toHaveCount(1);
    await page.locator('[data-testid^="tax-pack-row-"]').first().click();
    await expect(page.getByTestId("selected-tax-pack-detail")).toContainText("Taxable income");

    await page.getByTestId("submit-tax-pack").click();
    await expect(page.getByRole("status").getByText("Submitted tax pack.")).toBeVisible();

    await page.getByTestId("approve-tax-pack").click();
    await expect(page.getByRole("status").getByText("Approved tax pack.")).toBeVisible();

    await page.getByTestId("create-tax-pack-pdf-export").click();
    await expect(page.getByRole("status").getByText("Created tax pack PDF export.")).toBeVisible();
    await expect(page.getByTestId("selected-tax-pack-detail")).toContainText("Exports: 1");
  });
});
