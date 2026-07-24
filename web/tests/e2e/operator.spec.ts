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
  status: string;
};

type TaxCodeRecord = {
  id: string;
};

type AccountRecord = {
  id: string;
  name: string;
  account_code: string;
};

type BankAccountRecord = {
  id: string;
};

type BankImportSessionRecord = {
  id: string;
};

type ReconciliationSessionRecord = {
  id: string;
  note: string | null;
  status: string;
};

type BankImportRowRecord = {
  id: string;
  status: string;
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
  options: {
    description?: string;
    reference?: string;
    amount?: string;
  } = {},
) {
  const amount = options.amount ?? "165.00";
  return apiJson<JournalRecord>(request, "POST", `/api/companies/${companyId}/journals`, token, {
    entry_date: "2026-05-12",
    accounting_period_id: periodId,
    source_type: "manual",
    description: options.description ?? "Seeded recommendation draft",
    reference: options.reference ?? "E2E-AI-ACCEPT-01",
    lines: [
      {
        account_id: debitAccountId,
        description: "Seeded debit",
        debit_amount: amount,
        credit_amount: "0.00",
        tax_code_id: null,
        reporting_category_id: null,
        source_document_reference: null,
      },
      {
        account_id: creditAccountId,
        description: "Seeded credit",
        debit_amount: "0.00",
        credit_amount: amount,
        tax_code_id: null,
        reporting_category_id: null,
        source_document_reference: null,
      },
    ],
  });
}


test.describe.serial("operator workspace journeys", () => {
  test("switches and persists the global dark theme", async ({ page }) => {
    await page.goto("/");
    const darkModeButton = page.getByRole("button", { name: "Switch to dark mode" });
    await expect(darkModeButton).toBeVisible();
    await darkModeButton.click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("button", { name: "Switch to light mode" })).toBeVisible();
  });

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

  test("keeps workspace tabs the same size within and across routes", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Tab Layout Company");
    const workspacePaths = ["/setup", "/bookkeeping", "/banking", "/employment", "/reports", "/year-end"];

    await seedSessionStorage(page, company.id);

    let desktopTabSize: { width: number; height: number } | null = null;
    let desktopTabStripSize: { width: number; height: number } | null = null;
    for (const workspacePath of workspacePaths) {
      await page.goto(workspacePath);
      await page.waitForLoadState("networkidle");
      await expect(page.locator(".processing-veil")).toBeHidden();
      const tabStripSize = await page.locator(".workspace-tabs").evaluate((tabStrip) => {
        const box = tabStrip.getBoundingClientRect();
        return { width: box.width, height: box.height, bottom: box.bottom };
      });
      const followingPanelTop = await page.locator(".sections-stack > article.panel:visible").first().evaluate((panel) => panel.getBoundingClientRect().top);
      const tabSizes = await page.locator(".workspace-tab").evaluateAll((tabs) => (
        tabs.map((tab) => {
          const box = tab.getBoundingClientRect();
          return { width: box.width, height: box.height };
        })
      ));
      expect(tabSizes.length).toBeGreaterThan(1);
      const routeTabSize = tabSizes[0];
      for (const tabSize of tabSizes) {
        expect(Math.abs(tabSize.width - routeTabSize.width)).toBeLessThanOrEqual(0.5);
        expect(Math.abs(tabSize.height - routeTabSize.height)).toBeLessThanOrEqual(0.5);
      }
      if (!desktopTabSize) {
        desktopTabSize = routeTabSize;
        desktopTabStripSize = tabStripSize;
      } else {
        expect(Math.abs(routeTabSize.width - desktopTabSize.width)).toBeLessThanOrEqual(0.5);
        expect(Math.abs(routeTabSize.height - desktopTabSize.height)).toBeLessThanOrEqual(0.5);
        expect(desktopTabStripSize).not.toBeNull();
        expect(Math.abs(tabStripSize.width - desktopTabStripSize!.width)).toBeLessThanOrEqual(0.5);
        expect(Math.abs(tabStripSize.height - desktopTabStripSize!.height)).toBeLessThanOrEqual(0.5);
      }
      expect(Math.abs(tabStripSize.height - 96)).toBeLessThanOrEqual(0.5);
      expect(Math.abs(followingPanelTop - tabStripSize.bottom - 14)).toBeLessThanOrEqual(0.5);
    }

    await page.setViewportSize({ width: 800, height: 900 });
    let responsiveTabStripWidth: number | null = null;
    for (const workspacePath of workspacePaths) {
      await page.goto(workspacePath);
      await page.waitForLoadState("networkidle");
      await expect(page.locator(".processing-veil")).toBeHidden();
      const tabStripSize = await page.locator(".workspace-tabs").evaluate((tabStrip) => {
        const box = tabStrip.getBoundingClientRect();
        return { width: box.width, height: box.height, bottom: box.bottom };
      });
      const followingPanelTop = await page.locator(".sections-stack > article.panel:visible").first().evaluate((panel) => panel.getBoundingClientRect().top);
      const tabSizes = await page.locator(".workspace-tab").evaluateAll((tabs) => (
        tabs.map((tab) => {
          const box = tab.getBoundingClientRect();
          return { width: box.width, height: box.height };
        })
      ));
      for (const tabSize of tabSizes) {
        expect(Math.abs(tabSize.width - 180)).toBeLessThanOrEqual(0.5);
        expect(Math.abs(tabSize.height - 78)).toBeLessThanOrEqual(0.5);
      }
      if (responsiveTabStripWidth === null) {
        responsiveTabStripWidth = tabStripSize.width;
      } else {
        expect(Math.abs(tabStripSize.width - responsiveTabStripWidth)).toBeLessThanOrEqual(0.5);
      }
      expect(Math.abs(tabStripSize.height - 96)).toBeLessThanOrEqual(0.5);
      expect(Math.abs(followingPanelTop - tabStripSize.bottom - 14)).toBeLessThanOrEqual(0.5);
    }
  });

  test("keeps user creation and selected-user updates as distinct setup modes", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Setup Company");

    await seedSessionStorage(page, company.id);
    await page.goto("/setup");
    await page.getByRole("button", { name: "Users & access" }).click();

    await expect(page.getByRole("heading", { name: "Create user" })).toBeVisible();
    await page.locator("tbody tr").filter({ hasText: operatorEmail }).click();
    await expect(page.getByRole("heading", { name: "Update selected user" })).toBeVisible();

    await page.getByRole("button", { name: "Switch to create user" }).click();
    await expect(page.getByRole("heading", { name: "Create user" })).toBeVisible();
  });

  test("keeps dark journal, ledger, and workbench surfaces subdued", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (error) => pageErrors.push(error));
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Dark Surface Company");
    const debitAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Dark Surface Cash",
      account_type: "asset",
    });
    const creditAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Dark Surface Revenue",
      account_type: "income",
    });
    const period = await createPeriod(page.request, auth.access_token, company.id, uniqueSuffix("E2E Dark Surface Period"));
    const journal = await createDraftJournal(
      page.request,
      auth.access_token,
      company.id,
      period.id,
      debitAccount.id,
      creditAccount.id,
    );
    await apiJson<undefined>(
      page.request,
      "POST",
      `/api/companies/${company.id}/journals/${journal.id}/post`,
      auth.access_token,
    );

    const expectSubduedBackground = async (selector: string, maximumChannel = 96) => {
      const backgroundColor = await page.locator(selector).first().evaluate((element) => getComputedStyle(element).backgroundColor);
      const channels = backgroundColor.match(/\d+(?:\.\d+)?/g)?.slice(0, 3).map(Number) ?? [];
      expect(channels, `${selector} should resolve to an RGB background`).toHaveLength(3);
      expect(Math.max(...channels), `${selector} is too bright in dark mode: ${backgroundColor}`).toBeLessThanOrEqual(maximumChannel);
    };

    await seedSessionStorage(page, company.id);
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
    await page.goto("/bookkeeping");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.getByRole("button", { name: "Journals", exact: true }).click();
    await page.getByRole("row").filter({ hasText: journal.entry_number }).click();
    await expect(page.locator(".journal-preview-row")).toBeVisible();
    await expectSubduedBackground(".journal-preview-row td", 64);
    await expectSubduedBackground(".journal-preview-lines-shell", 64);

    await page.getByRole("button", { name: "Ledger", exact: true }).click();
    await page.getByRole("button", { name: "Use all time" }).click();
    await expect(page.locator(".ledger-group-row").first()).toBeVisible();
    await expectSubduedBackground(".ledger-group-row td", 80);
    await expectSubduedBackground(".ledger-table thead th", 80);
    await page.getByRole("button", { name: "Journals", exact: true }).click();
    await page.getByRole("row").filter({ hasText: journal.entry_number }).click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Maximum update depth exceeded")).toHaveCount(0);
    expect(pageErrors).toEqual([]);

    await page.goto("/workbench");
    await expect(page.locator(".method-chip").first()).toBeVisible();
    await expectSubduedBackground(".method-chip", 90);
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
    await page.getByRole("button", { name: "Journals", exact: true }).click();
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

    await journalDialog.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("button", { name: "Periods", exact: true }).click();
    await createdPeriodRow.click();
    await expect(page.getByRole("heading", { name: "Period-end earnings rollover" })).toBeVisible();
    await expect(page.getByText(/Locking this period automatically detects or creates the Retained Earnings/)).toBeVisible();

    await page.getByRole("button", { name: "Lock", exact: true }).click();
    await expect(page.getByRole("status").getByText("Locked period and updated retained earnings.")).toBeVisible();
    await expect(page.getByText(/System journal .* transferred .*110\.00 to retained earnings/)).toBeVisible();

    await page.getByRole("button", { name: "Unlock", exact: true }).click();
    await expect(page.getByRole("status").getByText("Unlocked period and voided its previous earnings rollover.")).toBeVisible();
    await expect(page.getByText(/previous system rollover was voided with an audit event/)).toBeVisible();
  });

  test("selects and posts multiple draft journals from the Journals popup", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Bulk Journal Company");
    const period = await createPeriod(page.request, auth.access_token, company.id, uniqueSuffix("E2E Bulk Quarter"));
    const cashAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Bulk Post Cash",
      account_type: "asset",
    });
    const revenueAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Bulk Post Revenue",
      account_type: "income",
    });
    const firstDescription = uniqueSuffix("Bulk post first");
    const secondDescription = uniqueSuffix("Bulk post second");
    const firstJournal = await createDraftJournal(
      page.request,
      auth.access_token,
      company.id,
      period.id,
      cashAccount.id,
      revenueAccount.id,
      { description: firstDescription, reference: "E2E-BULK-01", amount: "125.00" },
    );
    const secondJournal = await createDraftJournal(
      page.request,
      auth.access_token,
      company.id,
      period.id,
      cashAccount.id,
      revenueAccount.id,
      { description: secondDescription, reference: "E2E-BULK-02", amount: "275.00" },
    );

    await seedSessionStorage(page, company.id);
    await page.goto("/bookkeeping");
    await page.getByRole("button", { name: "Journals", exact: true }).click();
    await page.getByRole("button", { name: "Post multiple", exact: true }).click();

    const dialog = page.getByRole("dialog", { name: "Post multiple journal entries" });
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("Accounting period").selectOption(period.id);
    await dialog.getByLabel(`Select ${firstJournal.entry_number}`).check();
    await dialog.getByLabel(`Select ${secondJournal.entry_number}`).check();
    await expect(dialog.getByText("2 selected", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Combined debit total: $400.00")).toBeVisible();
    await dialog.getByTestId("bulk-post-journals").click();

    await expect(page.getByRole("status").getByText("Posted 2 journal entries.")).toBeVisible();
    await expect(dialog).toHaveCount(0);
    const journals = await apiJson<Array<JournalRecord>>(
      page.request,
      "GET",
      `/api/companies/${company.id}/journals`,
      auth.access_token,
    );
    const journalById = new Map(journals.map((journal) => [journal.id, journal]));
    expect(journalById.get(firstJournal.id)?.status).toBe("posted");
    expect(journalById.get(secondJournal.id)?.status).toBe("posted");
  });

  test("multi-selects existing evidence, preserves source order, and accepts a selected proposal", async ({ page }) => {
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
    const existingStatementResponse = await page.request.post(
      `${apiBaseUrl}/api/companies/${company.id}/documents`,
      {
        headers: { Authorization: `Bearer ${auth.access_token}` },
        multipart: {
          file: {
            name: "existing-bank-statement.pdf",
            mimeType: "application/pdf",
            buffer: Buffer.from("%PDF-1.4 previously uploaded bank statement"),
          },
        },
      },
    );
    const existingStatement = await parseResponse<{ id: string }>(existingStatementResponse);
    const existingInvoiceResponse = await page.request.post(
      `${apiBaseUrl}/api/companies/${company.id}/documents`,
      {
        headers: { Authorization: `Bearer ${auth.access_token}` },
        multipart: {
          file: {
            name: "existing-invoice.pdf",
            mimeType: "application/pdf",
            buffer: Buffer.from("%PDF-1.4 previously uploaded invoice"),
          },
        },
      },
    );
    const existingInvoice = await parseResponse<{ id: string }>(existingInvoiceResponse);

    const createdRunId = "11111111-1111-4111-8111-111111111111";
    const analyzedRunId = "22222222-2222-4222-8222-222222222222";
    const proposalId = "33333333-3333-4333-8333-333333333333";
    let acceptRequestCount = 0;
    let createRequestBody = "";

    await page.route(/\/api\/companies\/[^/]+\/journal-recommendations(?:\/[^/]+\/(analyze|accept))?$/, async (route, request) => {
      const url = new URL(request.url());
      const pathname = url.pathname;
      if (request.method() !== "POST") {
        await route.continue();
        return;
      }
      if (/\/journal-recommendations$/.test(pathname)) {
        createRequestBody = request.postData() ?? "";
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
                original_filename: "existing-bank-statement.pdf",
                media_type: "application/pdf",
                byte_size: 2048,
                created_at: "2026-07-10T09:00:00Z",
              },
              {
                id: "66666666-6666-4666-8666-666666666666",
                document_id: "77777777-7777-4777-8777-777777777777",
                display_order: 2,
                original_filename: "existing-invoice.pdf",
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

    await page.getByRole("button", { name: "AI drafting", exact: true }).click();
    await page.getByLabel("Target accounting period").selectOption(period.id);
    await page.getByLabel("Use existing document existing-bank-statement.pdf").check();
    await page.getByLabel("Use existing document existing-invoice.pdf").check();
    await expect(page.getByLabel("Evidence mode")).toHaveValue("multiple");
    await page.locator('input[type="file"][multiple]').setInputFiles([
      { name: "title-search.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 title search") },
    ]);
    await expect(page.getByText("3 evidence documents")).toBeVisible();
    await page.getByRole("button", { name: "Analyze evidence" }).click();

    await expect(page.getByRole("status").getByText("Generated 1 review-only journal recommendation.")).toBeVisible();
    expect(createRequestBody).toContain("existing_document_ids");
    expect(createRequestBody).toContain(existingStatement.id);
    expect(createRequestBody).toContain(existingInvoice.id);
    expect(createRequestBody).toContain("title-search.pdf");
    expect(createRequestBody.indexOf(existingStatement.id)).toBeLessThan(
      createRequestBody.indexOf(existingInvoice.id),
    );
    expect(createRequestBody.indexOf(existingInvoice.id)).toBeLessThan(
      createRequestBody.indexOf("title-search.pdf"),
    );
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

  test("deletes an open reconciliation session from the banking route", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Reconciliation Delete Company");
    const bankAccount = await apiJson<BankAccountRecord>(
      page.request,
      "POST",
      `/api/companies/${company.id}/bank-accounts`,
      auth.access_token,
      {
        name: uniqueSuffix("E2E Operating Account"),
        bank_name: "Example Bank",
        bsb: "123-456",
        account_number_masked: "xxxx1234",
        is_active: true,
      },
    );
    const uploadResponse = await page.request.post(
      `${apiBaseUrl}/api/companies/${company.id}/bank-imports/upload`,
      {
        headers: { Authorization: `Bearer ${auth.access_token}` },
        multipart: {
          bank_account_id: bankAccount.id,
          date_column: "date",
          description_column: "description",
          debit_column: "debit",
          credit_column: "credit",
          reference_column: "reference",
          note: "Import for reconciliation deletion",
          file: {
            name: "reconciliation-delete.csv",
            mimeType: "text/csv",
            buffer: Buffer.from(
              "date,description,debit,credit,reference\n2026-05-12,Delete session coverage,25.00,0.00,E2E-RECON-DELETE\n",
            ),
          },
        },
      },
    );
    const bankImport = await parseResponse<BankImportSessionRecord>(uploadResponse);
    await apiJson(
      page.request,
      "POST",
      `/api/companies/${company.id}/bank-imports/${bankImport.id}/confirm`,
      auth.access_token,
      { note: "Confirmed for reconciliation deletion" },
    );
    const sessionNote = uniqueSuffix("E2E Delete Session");
    const reconciliationSession = await apiJson<ReconciliationSessionRecord>(
      page.request,
      "POST",
      `/api/companies/${company.id}/reconciliation-sessions`,
      auth.access_token,
      {
        bank_account_id: bankAccount.id,
        accounting_period_id: null,
        note: sessionNote,
      },
    );

    await seedSessionStorage(page, company.id);
    await page.goto("/banking");
    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();

    await page.getByRole("button", { name: "Reconciliation", exact: true }).click();
    const sessionButton = page.getByRole("button").filter({ hasText: sessionNote });
    await expect(sessionButton).toBeVisible();
    await sessionButton.click();
    await expect(page.getByTestId("delete-reconciliation-session")).toBeVisible();

    page.once("dialog", async (dialog) => {
      expect(dialog.type()).toBe("confirm");
      expect(dialog.message()).toContain("return to staged status");
      await dialog.accept();
    });
    await page.getByTestId("delete-reconciliation-session").click();

    await expect(page.getByRole("status").getByText(`Deleted reconciliation session "${sessionNote}".`)).toBeVisible();
    await expect(sessionButton).toHaveCount(0);
    const remainingSessions = await apiJson<ReconciliationSessionRecord[]>(
      page.request,
      "GET",
      `/api/companies/${company.id}/reconciliation-sessions`,
      auth.access_token,
    );
    expect(remainingSessions.some((item) => item.id === reconciliationSession.id)).toBe(false);
    const rows = await apiJson<BankImportRowRecord[]>(
      page.request,
      "GET",
      `/api/companies/${company.id}/bank-imports/${bankImport.id}/rows`,
      auth.access_token,
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe("staged");
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

    await page.getByRole("button", { name: "BAS support", exact: true }).click();
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

    await page.getByRole("button", { name: "Tax workpapers", exact: true }).click();
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

  test("runs cash flow and changes in equity reports and downloads an archive PDF", async ({ page }) => {
    const auth = await ensureOperatorSession(page.request);
    const company = await createCompany(page.request, auth.access_token, "E2E Financial Reports Company");
    const period = await createPeriod(page.request, auth.access_token, company.id, uniqueSuffix("E2E Reports Quarter"));
    const cashAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Cash at Bank",
      account_type: "asset",
    });
    const equityAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Owner Capital",
      account_type: "equity",
    });
    const revenueAccount = await createAccount(page.request, auth.access_token, company.id, {
      account_code: uniqueAccountCode(),
      name: "Consulting Revenue",
      account_type: "income",
    });
    const contribution = await createDraftJournal(
      page.request,
      auth.access_token,
      company.id,
      period.id,
      cashAccount.id,
      equityAccount.id,
      { description: "Owner contribution", reference: "E2E-CAPITAL-01", amount: "1000.00" },
    );
    const cashSale = await createDraftJournal(
      page.request,
      auth.access_token,
      company.id,
      period.id,
      cashAccount.id,
      revenueAccount.id,
      { description: "Cash consulting sale", reference: "E2E-SALE-01", amount: "100.00" },
    );
    await apiJson<undefined>(page.request, "POST", `/api/companies/${company.id}/journals/${contribution.id}/post`, auth.access_token);
    await apiJson<undefined>(page.request, "POST", `/api/companies/${company.id}/journals/${cashSale.id}/post`, auth.access_token);

    await seedSessionStorage(page, company.id);
    await page.goto("/reports");
    await expect(page.getByTestId("operator-shell-authenticated")).toBeVisible();
    await expect(page.getByRole("button", { name: "Cash flow", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Changes in equity", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Cash flow", exact: true }).click();
    const cashFlowPanel = page.getByRole("heading", { name: "Statement of cash flows" }).locator("..");
    await cashFlowPanel.getByLabel("Start date").fill("2026-04-01");
    await cashFlowPanel.getByLabel("End date").fill("2026-06-30");
    await cashFlowPanel.getByTestId("run-cash-flow").click();
    await expect(cashFlowPanel.getByText("Closing cash").locator("..")).toContainText("$1,100.00");
    await expect(cashFlowPanel.getByText("direct method", { exact: true })).toBeVisible();
    await expect(cashFlowPanel.getByText("Cash receipts from customers", { exact: true })).toBeVisible();
    await expect(cashFlowPanel.getByText("Proceeds from issue of share capital and owner contributions", { exact: true })).toBeVisible();
    await expect(cashFlowPanel.getByRole("heading", { name: "Operating activities", exact: true })).toBeVisible();
    await expect(cashFlowPanel.getByRole("heading", { name: "Financing activities", exact: true })).toBeVisible();
    await expect(cashFlowPanel.getByText("Ledger reconciliation difference:")).toContainText("$0.00");

    const downloadPromise = page.waitForEvent("download");
    await cashFlowPanel.getByTestId("export-cash-flow-pdf").click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("cash-flow.pdf");

    await page.getByRole("button", { name: "Changes in equity", exact: true }).click();
    const equityPanel = page.getByRole("heading", { name: "Statement of changes in equity" }).locator("..");
    await equityPanel.getByLabel("Start date").fill("2026-04-01");
    await equityPanel.getByLabel("End date").fill("2026-06-30");
    await equityPanel.getByTestId("run-changes-in-equity").click();
    await expect(equityPanel.locator(".stat-card").filter({ hasText: "Profit or loss" })).toContainText("$100.00");
    await expect(equityPanel.locator(".stat-card").filter({ hasText: "Contributions" })).toContainText("$1,000.00");
    await expect(equityPanel.locator(".stat-card").filter({ hasText: "Closing equity" })).toContainText("$1,100.00");
    await expect(equityPanel.getByText("Equity reconciliation difference:")).toContainText("$0.00");
  });
});
