import { useMemo } from "react";

import type { OperatorState } from "../operator-state";
import { formatDate } from "../operator-state";
import { EmptyState, Field, StatusPill } from "../operator-ui";


type SelectOption = {
  value: string;
  label: string;
  detail?: string;
};

type AccountTypeOption = SelectOption & {
  prefixes?: readonly string[];
  isLegacy?: boolean;
};

function buildTwoDigitPrefixes(start: number, end: number): string[] {
  return Array.from({ length: end - start + 1 }, (_, index) => String(start + index).padStart(2, "0"));
}

const reportingCategoryTypeOptions: SelectOption[] = [
  { value: "pnl", label: "Profit and Loss" },
  { value: "balance_sheet", label: "Balance Sheet" },
  { value: "gst", label: "GST" },
  { value: "bas", label: "BAS" },
  { value: "tax_support", label: "Tax Support" },
  { value: "other", label: "Other" },
];

const reportingCategoryTypeOptionMap = new Map(reportingCategoryTypeOptions.map((option) => [option.value, option]));

const taxInputOutputOptions: SelectOption[] = [
  { value: "output_taxed", label: "Output Taxed", detail: "Use for taxable sales and revenue lines." },
  { value: "input_taxed", label: "Input Taxed", detail: "Use for taxable purchases that do not create input tax credits." },
  { value: "input_tax_credit", label: "Input Tax Credit", detail: "Use for GST-creditable acquisitions and expenses." },
  { value: "gst_free", label: "GST Free", detail: "Use where GST is not charged but the transaction remains in scope." },
  { value: "none", label: "None", detail: "Use for no-GST or memo-style coding." },
];

const taxInputOutputOptionMap = new Map(taxInputOutputOptions.map((option) => [option.value, option]));

const primaryAccountTypeOptions: AccountTypeOption[] = [
  { value: "asset", label: "Assets", detail: "1000-1999", prefixes: buildTwoDigitPrefixes(10, 19) },
  { value: "liability", label: "Liabilities", detail: "2000-2999", prefixes: buildTwoDigitPrefixes(20, 29) },
  { value: "equity", label: "Equity", detail: "3000-3999", prefixes: buildTwoDigitPrefixes(30, 39) },
  { value: "revenue", label: "Revenue / Income", detail: "4000-4999", prefixes: buildTwoDigitPrefixes(40, 49) },
  { value: "cost_of_sales", label: "Cost of Sales / COGS", detail: "5000-5999", prefixes: buildTwoDigitPrefixes(50, 59) },
  { value: "expense", label: "Expenses", detail: "6000-7999", prefixes: buildTwoDigitPrefixes(60, 79) },
  { value: "other_income", label: "Other Income", detail: "8000-8999", prefixes: buildTwoDigitPrefixes(80, 89) },
  { value: "other_expense", label: "Other Expenses", detail: "9000-9499", prefixes: buildTwoDigitPrefixes(90, 94) },
  { value: "non_posting", label: "Non-posting / Memo / Statistical", detail: "9500-9999", prefixes: buildTwoDigitPrefixes(95, 99) },
];

const legacyAccountTypeOptions: AccountTypeOption[] = [
  { value: "income", label: "Legacy Income", detail: "Existing data compatibility", isLegacy: true },
  { value: "contra_asset", label: "Contra Asset", detail: "Advanced fixed asset support", isLegacy: true },
  { value: "contra_liability", label: "Contra Liability", detail: "Advanced balance sheet support", isLegacy: true },
  { value: "contra_income", label: "Contra Income", detail: "Advanced revenue support", isLegacy: true },
  { value: "contra_expense", label: "Contra Expense", detail: "Advanced expense support", isLegacy: true },
];

const accountTypeOptions: AccountTypeOption[] = [...primaryAccountTypeOptions, ...legacyAccountTypeOptions];
const accountTypeOptionMap = new Map(accountTypeOptions.map((option) => [option.value, option]));

function formatOptionLabel(optionMap: Map<string, SelectOption | AccountTypeOption>, value: string): string {
  return optionMap.get(value)?.label ?? value.replaceAll("_", " ");
}

function formatRate(rate: string): string {
  const numericRate = Number(rate);
  if (Number.isNaN(numericRate)) {
    return rate;
  }
  const percent = numericRate * 100;
  return `${percent % 1 === 0 ? percent.toFixed(0) : percent.toFixed(2)}%`;
}

function getManagedAccountCodeState(accountType: string, accountCode: string) {
  const option = accountTypeOptionMap.get(accountType);
  if (!option?.prefixes) {
    return null;
  }
  const digitsOnly = accountCode.replace(/\D/g, "").slice(0, 4);
  const prefixFromCode = digitsOnly.slice(0, 2);
  const prefix = option.prefixes.includes(prefixFromCode) ? prefixFromCode : option.prefixes[0];
  const suffix = digitsOnly.startsWith(prefix) ? digitsOnly.slice(2, 4) : digitsOnly.slice(2, 4);
  return {
    prefixOptions: option.prefixes,
    prefix,
    suffix,
    isRangeMatch: digitsOnly.length === 4 && option.prefixes.includes(prefixFromCode),
  };
}

function RowActionsMenu({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <details className="row-actions-menu" onClick={(event) => event.stopPropagation()}>
      <summary className="row-actions-trigger" aria-label="Row actions">...</summary>
      <div className="row-actions-popover">
        <button type="button" onClick={onEdit}>Edit</button>
        <button type="button" onClick={onDelete}>Delete</button>
      </div>
    </details>
  );
}


function buildSelectableOptions(options: SelectOption[], allOptions: SelectOption[], selectedValue: string) {
  if (!selectedValue || options.some((item) => item.value === selectedValue)) {
    return options;
  }
  const fallback = allOptions.find((item) => item.value === selectedValue);
  if (!fallback) {
    return options;
  }
  return [...options, { ...fallback, label: `${fallback.label} (inactive)` }];
}


export function SetupSection({ operator }: { operator: OperatorState }) {
  const {
    adminOverview,
    selectedCompany,
    selectedCompanyId,
    companyDraft,
    setCompanyDraft,
    runAction,
    request,
    showMessage,
    refreshAll,
    users,
    selectedUserId,
    setSelectedUserId,
    userDraft,
    setUserDraft,
    selectedUser,
    accessDraft,
    setAccessDraft,
    accessRows,
    userOptionList,
    configurations,
    selectedConfigurationId,
    setSelectedConfigurationId,
    configurationDraft,
    setConfigurationDraft,
    selectedConfiguration,
    categories,
    selectedCategoryId,
    setSelectedCategoryId,
    categoryDraft,
    setCategoryDraft,
    taxCodes,
    selectedTaxCodeId,
    setSelectedTaxCodeId,
    taxCodeDraft,
    setTaxCodeDraft,
    accounts,
    selectedAccountId,
    setSelectedAccountId,
    accountDraft,
    setAccountDraft,
    categoryOptionList,
    taxCodeOptionList,
    activeCategoryOptionList,
    activeTaxCodeOptionList,
  } = operator;

  const categoryLabelById = new Map(categories.map((item) => [item.id, `${item.code} · ${item.name}`]));
  const taxCodeLabelById = new Map(taxCodes.map((item) => [item.id, `${item.code} · ${item.name}`]));
  const managedAccountCode = getManagedAccountCodeState(accountDraft.account_type, accountDraft.account_code);
  const selectedAccountTypeOption = accountTypeOptionMap.get(accountDraft.account_type);
  const selectedTaxInputOutputOption = taxInputOutputOptionMap.get(taxCodeDraft.input_output_type);
  const accountCategoryOptions = useMemo(
    () => buildSelectableOptions(activeCategoryOptionList, categoryOptionList, accountDraft.reporting_category_id),
    [activeCategoryOptionList, categoryOptionList, accountDraft.reporting_category_id],
  );
  const accountTaxCodeOptions = useMemo(
    () => buildSelectableOptions(activeTaxCodeOptionList, taxCodeOptionList, accountDraft.default_tax_code_id),
    [activeTaxCodeOptionList, taxCodeOptionList, accountDraft.default_tax_code_id],
  );

  function resetCategoryForm() {
    setSelectedCategoryId("");
    setCategoryDraft({ code: "", name: "", is_active: true, category_type: "pnl" });
  }

  function resetTaxCodeForm() {
    setSelectedTaxCodeId("");
    setTaxCodeDraft({
      code: "",
      name: "",
      description: "",
      rate: "0.10",
      is_gst_applicable: true,
      is_active: true,
      bas_label: "",
      input_output_type: "output_taxed",
    });
  }

  function resetConfigurationForm() {
    setSelectedConfigurationId("");
    setConfigurationDraft({
      effective_from: new Date().toISOString().slice(0, 10),
      gst_registered: true,
      bas_frequency: "quarterly",
      bas_reporting_basis: "accrual",
      financial_year_start_month: 7,
      financial_year_start_day: 1,
      allow_self_approval: true,
      self_approval_mode: "warn",
      period_lock_policy: "after_approval",
    });
  }

  function resetAccountForm() {
    setSelectedAccountId("");
    setAccountDraft({
      account_code: "",
      name: "",
      account_type: "asset",
      reporting_category_id: "",
      default_tax_code_id: "",
      is_active: true,
      allow_manual_posting: true,
    });
  }

  function handleAccountTypeChange(nextType: string) {
    setAccountDraft((current) => {
      const nextOption = accountTypeOptionMap.get(nextType);
      const digitsOnly = current.account_code.replace(/\D/g, "").slice(0, 4);
      return {
        ...current,
        account_type: nextType,
        account_code: nextOption?.prefixes
          ? `${nextOption.prefixes.includes(digitsOnly.slice(0, 2)) ? digitsOnly.slice(0, 2) : nextOption.prefixes[0]}${digitsOnly.slice(2, 4)}`
          : current.account_code,
        allow_manual_posting: nextType === "non_posting" ? false : current.allow_manual_posting,
      };
    });
  }

  async function saveCategory() {
    const categoryCode = categoryDraft.code.trim();
    const categoryName = categoryDraft.name.trim();
    if (!categoryCode) {
      throw new Error("Enter a reporting category code before saving.");
    }
    if (!categoryName) {
      throw new Error("Enter a reporting category name before saving.");
    }
    if (!reportingCategoryTypeOptionMap.has(categoryDraft.category_type)) {
      throw new Error("Choose a valid reporting category type before saving.");
    }
    const payload = {
      ...categoryDraft,
      code: categoryCode,
      name: categoryName,
    };
    if (selectedCategoryId) {
      await request(`/api/companies/${selectedCompanyId}/reporting-categories/${selectedCategoryId}`, "PUT", payload);
    } else {
      await request(`/api/companies/${selectedCompanyId}/reporting-categories`, "POST", payload);
    }
    showMessage("success", "Saved reporting category.");
    await refreshAll();
  }

  async function deleteCategory(categoryId: string, categoryName: string) {
    if (!operator.confirmDanger(`Delete reporting category ${categoryName}?`)) {
      return;
    }
    await request(`/api/companies/${selectedCompanyId}/reporting-categories/${categoryId}`, "DELETE", undefined, "void");
    if (selectedCategoryId === categoryId) {
      resetCategoryForm();
    }
    showMessage("success", "Deleted reporting category.");
    await refreshAll();
  }

  async function saveTaxCode() {
    const code = taxCodeDraft.code.trim();
    const name = taxCodeDraft.name.trim();
    if (!code) {
      throw new Error("Enter a tax code before saving.");
    }
    if (!name) {
      throw new Error("Enter a tax code name before saving.");
    }
    if (!taxInputOutputOptionMap.has(taxCodeDraft.input_output_type)) {
      throw new Error("Choose a valid GST input/output type before saving.");
    }
    if (Number.isNaN(Number(taxCodeDraft.rate))) {
      throw new Error("Enter a valid GST rate before saving.");
    }
    const payload = {
      ...taxCodeDraft,
      code,
      name,
      description: taxCodeDraft.description.trim() || null,
      bas_label: taxCodeDraft.bas_label.trim() || null,
    };
    if (selectedTaxCodeId) {
      await request(`/api/companies/${selectedCompanyId}/tax-codes/${selectedTaxCodeId}`, "PUT", payload);
    } else {
      await request(`/api/companies/${selectedCompanyId}/tax-codes`, "POST", payload);
    }
    showMessage("success", "Saved tax code.");
    await refreshAll();
  }

  async function deleteTaxCode(taxCodeId: string, taxCodeName: string) {
    if (!operator.confirmDanger(`Delete tax code ${taxCodeName}?`)) {
      return;
    }
    await request(`/api/companies/${selectedCompanyId}/tax-codes/${taxCodeId}`, "DELETE", undefined, "void");
    if (selectedTaxCodeId === taxCodeId) {
      resetTaxCodeForm();
    }
    showMessage("success", "Deleted tax code.");
    await refreshAll();
  }

  async function saveAccount() {
    const accountName = accountDraft.name.trim();
    if (!accountName) {
      throw new Error("Enter an account name before saving.");
    }
    if (!accountTypeOptionMap.has(accountDraft.account_type)) {
      throw new Error("Select a valid account type before saving.");
    }

    let accountCode = accountDraft.account_code.trim();
    if (managedAccountCode) {
      const cleanSuffix = managedAccountCode.suffix.replace(/\D/g, "");
      if (cleanSuffix.length !== 2) {
        throw new Error("Enter the last two digits of the account code before saving.");
      }
      accountCode = `${managedAccountCode.prefix}${cleanSuffix}`;
    }
    if (!accountCode) {
      throw new Error("Enter an account code before saving.");
    }

    const payload = {
      ...accountDraft,
      account_code: accountCode,
      name: accountName,
      reporting_category_id: accountDraft.reporting_category_id || null,
      default_tax_code_id: accountDraft.default_tax_code_id || null,
      allow_manual_posting: accountDraft.account_type === "non_posting" ? false : accountDraft.allow_manual_posting,
    };
    if (selectedAccountId) {
      await request(`/api/companies/${selectedCompanyId}/accounts/${selectedAccountId}`, "PUT", payload);
    } else {
      await request(`/api/companies/${selectedCompanyId}/accounts`, "POST", payload);
    }
    showMessage("success", "Saved account.");
    await refreshAll();
  }

  async function deleteAccount(accountId: string, accountName: string) {
    if (!operator.confirmDanger(`Deactivate account ${accountName}?`)) {
      return;
    }
    await request(`/api/companies/${selectedCompanyId}/accounts/${accountId}`, "DELETE", undefined, "void");
    if (selectedAccountId === accountId) {
      resetAccountForm();
    }
    showMessage("success", "Deactivated account.");
    await refreshAll();
  }

  async function deleteConfiguration(configurationId: string, versionNumber: number) {
    if (!operator.confirmDanger(`Delete configuration version ${versionNumber}?`)) {
      return;
    }
    await request(`/api/companies/${selectedCompanyId}/configurations/${configurationId}`, "DELETE", undefined, "void");
    if (selectedConfigurationId === configurationId) {
      resetConfigurationForm();
    }
    showMessage("success", `Deleted configuration version ${versionNumber}.`);
    await refreshAll();
  }

  return (
    <section className="sections-stack">
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Company profile</h2><StatusPill value={selectedCompany?.is_active ? "active" : "inactive"} /></div>
        <div className="form-grid two-up">
          <Field label="Legal name"><input value={companyDraft.legal_name} onChange={(event) => setCompanyDraft((current) => ({ ...current, legal_name: event.target.value }))} /></Field>
          <Field label="Trading name"><input value={companyDraft.trading_name} onChange={(event) => setCompanyDraft((current) => ({ ...current, trading_name: event.target.value }))} /></Field>
          <Field label="ABN"><input value={companyDraft.abn} onChange={(event) => setCompanyDraft((current) => ({ ...current, abn: event.target.value }))} /></Field>
          <Field label="ACN"><input value={companyDraft.acn} onChange={(event) => setCompanyDraft((current) => ({ ...current, acn: event.target.value }))} /></Field>
          <Field label="Entity type"><input value={companyDraft.entity_type} onChange={(event) => setCompanyDraft((current) => ({ ...current, entity_type: event.target.value }))} /></Field>
          <Field label="Active"><input type="checkbox" checked={companyDraft.is_active} onChange={(event) => setCompanyDraft((current) => ({ ...current, is_active: event.target.checked }))} /></Field>
        </div>
        <div className="request-actions">
          <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving company", async () => {
            await request(`/api/companies/${selectedCompanyId}`, "PUT", companyDraft);
            showMessage("success", "Updated company profile.");
            await refreshAll();
          })}>Save company</button>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Users and access</h2>{adminOverview ? <span className="pill">{adminOverview.users} users</span> : null}</div>
        <div className="workspace-split">
          <div>
            <div className="table-shell">
              <table className="data-table">
                <thead><tr><th>User</th><th>Role</th><th>Status</th></tr></thead>
                <tbody>
                  {users.map((item) => (
                    <tr key={item.id} className={selectedUserId === item.id ? "is-selected" : ""} onClick={() => setSelectedUserId(item.id)}>
                      <td>{item.full_name}<div className="table-meta">{item.email}</div></td>
                      <td>{item.is_superuser ? "Superuser" : "Standard"}</td>
                      <td><StatusPill value={item.is_active ? "active" : "inactive"} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Create or update user</h3>
              <div className="form-grid">
                <Field label="Email"><input value={userDraft.email} onChange={(event) => setUserDraft((current) => ({ ...current, email: event.target.value }))} /></Field>
                <Field label="Full name"><input value={userDraft.full_name} onChange={(event) => setUserDraft((current) => ({ ...current, full_name: event.target.value }))} /></Field>
                <Field label="Password"><input type="password" value={userDraft.password} onChange={(event) => setUserDraft((current) => ({ ...current, password: event.target.value }))} /></Field>
                <Field label="Superuser"><input type="checkbox" checked={userDraft.is_superuser} onChange={(event) => setUserDraft((current) => ({ ...current, is_superuser: event.target.checked }))} /></Field>
                <Field label="Active"><input type="checkbox" checked={userDraft.is_active} onChange={(event) => setUserDraft((current) => ({ ...current, is_active: event.target.checked }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction(selectedUser ? "Updating user" : "Creating user", async () => {
                  if (selectedUser) {
                    await request(`/api/admin/users/${selectedUser.id}`, "PUT", userDraft);
                  } else {
                    await request("/api/admin/users", "POST", { ...userDraft, password: userDraft.password || "StrongPass123" });
                  }
                  showMessage("success", selectedUser ? "Updated user." : "Created user.");
                  await refreshAll();
                })}>{selectedUser ? "Save selected user" : "Create user"}</button>
                {selectedUser ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => { setSelectedUserId(""); setUserDraft({ email: "reviewer@example.com", full_name: "Reviewer User", password: "StrongPass123", is_superuser: false, is_active: true }); }}>New user</button> : null}
              </div>
            </div>

            <div className="mini-card">
              <h3>Company access</h3>
              <div className="form-grid two-up">
                <Field label="User"><select value={accessDraft.user_id} onChange={(event) => setAccessDraft((current) => ({ ...current, user_id: event.target.value }))}><option value="">Select user</option>{userOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Can prepare"><input type="checkbox" checked={accessDraft.can_prepare} onChange={(event) => setAccessDraft((current) => ({ ...current, can_prepare: event.target.checked }))} /></Field>
                <Field label="Can review"><input type="checkbox" checked={accessDraft.can_review} onChange={(event) => setAccessDraft((current) => ({ ...current, can_review: event.target.checked }))} /></Field>
                <Field label="Can approve"><input type="checkbox" checked={accessDraft.can_approve} onChange={(event) => setAccessDraft((current) => ({ ...current, can_approve: event.target.checked }))} /></Field>
                <Field label="Can administer"><input type="checkbox" checked={accessDraft.can_administer} onChange={(event) => setAccessDraft((current) => ({ ...current, can_administer: event.target.checked }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving access", async () => {
                  const existing = accessRows.find((item) => item.user_id === accessDraft.user_id);
                  if (existing) {
                    await request(`/api/companies/${selectedCompanyId}/access/${accessDraft.user_id}`, "PUT", accessDraft);
                  } else {
                    await request(`/api/companies/${selectedCompanyId}/access`, "POST", accessDraft);
                  }
                  showMessage("success", "Saved company access.");
                  await refreshAll();
                })}>Save access</button>
                {accessDraft.user_id ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Removing access", async () => {
                  if (!operator.confirmDanger("Remove the selected access row?")) {
                    return;
                  }
                  await request(`/api/companies/${selectedCompanyId}/access/${accessDraft.user_id}`, "DELETE", undefined, "void");
                  showMessage("success", "Removed company access.");
                  await refreshAll();
                })}>Remove access</button> : null}
              </div>
            </div>
          </div>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Configuration versions</h2><span className="pill">{configurations.length} versions</span></div>
        <div className="workspace-split">
          <div className="table-shell">
            <table className="data-table">
              <thead><tr><th>Version</th><th>Effective from</th><th>BAS frequency</th><th>Actions</th></tr></thead>
              <tbody>
                {configurations.map((item) => (
                  <tr key={item.id} className={selectedConfigurationId === item.id ? "is-selected" : ""} onClick={() => setSelectedConfigurationId(item.id)}>
                    <td>v{item.version_number}</td>
                    <td>{formatDate(item.effective_from)}</td>
                    <td>{item.bas_frequency}</td>
                    <td className="row-actions-cell">
                      <RowActionsMenu
                        onEdit={() => setSelectedConfigurationId(item.id)}
                        onDelete={() => runAction("Deleting configuration", async () => deleteConfiguration(item.id, item.version_number))}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mini-card">
            <h3>{selectedConfiguration ? "Update selected configuration" : "Add configuration version"}</h3>
            <p className="reference-form-meta">Select a configuration version to edit it, or create a fresh version for changed BAS and approval settings.</p>
            <div className="form-grid two-up">
              <Field label="Effective from"><input type="date" value={configurationDraft.effective_from} onChange={(event) => setConfigurationDraft((current) => ({ ...current, effective_from: event.target.value }))} /></Field>
              <Field label="GST registered"><input type="checkbox" checked={configurationDraft.gst_registered} onChange={(event) => setConfigurationDraft((current) => ({ ...current, gst_registered: event.target.checked }))} /></Field>
              <Field label="BAS frequency"><select value={configurationDraft.bas_frequency} onChange={(event) => setConfigurationDraft((current) => ({ ...current, bas_frequency: event.target.value }))}><option value="quarterly">Quarterly</option><option value="monthly">Monthly</option></select></Field>
              <Field label="Reporting basis"><select value={configurationDraft.bas_reporting_basis} onChange={(event) => setConfigurationDraft((current) => ({ ...current, bas_reporting_basis: event.target.value }))}><option value="accrual">Accrual</option><option value="cash">Cash</option></select></Field>
              <Field label="Self approval"><input type="checkbox" checked={configurationDraft.allow_self_approval} onChange={(event) => setConfigurationDraft((current) => ({ ...current, allow_self_approval: event.target.checked }))} /></Field>
              <Field label="Self approval mode"><select value={configurationDraft.self_approval_mode} onChange={(event) => setConfigurationDraft((current) => ({ ...current, self_approval_mode: event.target.value }))}><option value="warn">Warn</option><option value="block">Block</option><option value="allow">Allow</option></select></Field>
              <Field label="Lock policy"><select value={configurationDraft.period_lock_policy} onChange={(event) => setConfigurationDraft((current) => ({ ...current, period_lock_policy: event.target.value }))}><option value="after_approval">After approval</option><option value="after_export">After export</option></select></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving configuration", async () => {
                if (selectedConfigurationId) {
                  await request(`/api/companies/${selectedCompanyId}/configurations/${selectedConfigurationId}`, "PUT", configurationDraft);
                } else {
                  await request(`/api/companies/${selectedCompanyId}/configurations`, "POST", configurationDraft);
                }
                showMessage("success", "Saved configuration version.");
                await refreshAll();
              })}>Save configuration</button>
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={resetConfigurationForm}>New configuration</button>
              {selectedConfigurationId ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Deleting configuration", async () => deleteConfiguration(selectedConfigurationId, selectedConfiguration?.version_number ?? 0))}>Delete selected</button> : null}
            </div>
          </div>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Reference data</h2><span className="pill">Chart and GST mapping</span></div>
        <div className="stacked-cards">
          <div className="mini-card reference-management-block">
            <div className="reference-management-header">
              <div>
                <h3>Reporting categories</h3>
                <p className="reference-management-copy">Formal categories for financial statements, BAS support, GST support, and tax-support mapping.</p>
              </div>
              <span className="pill">{categories.length} categories</span>
            </div>
            <div className="stats-grid mini-stats-grid">
              <div className="stat-card"><span>Profit and Loss</span><strong>{categories.filter((item) => item.category_type === "pnl").length}</strong></div>
              <div className="stat-card"><span>Balance Sheet</span><strong>{categories.filter((item) => item.category_type === "balance_sheet").length}</strong></div>
            </div>
            <div className="workspace-split">
              <div>
                {categories.length ? (
                  <div className="table-shell compact-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Code</th><th>Name</th><th>Category type</th><th>Status</th><th>Actions</th></tr></thead>
                      <tbody>
                        {categories.map((item) => (
                          <tr key={item.id} className={selectedCategoryId === item.id ? "is-selected" : ""} onClick={() => setSelectedCategoryId(item.id)}>
                            <td><strong>{item.code}</strong></td>
                            <td>{item.name}</td>
                            <td>{formatOptionLabel(reportingCategoryTypeOptionMap, item.category_type)}</td>
                            <td><StatusPill value={item.is_active ? "active" : "inactive"} /></td>
                            <td className="row-actions-cell">
                              <RowActionsMenu
                                onEdit={() => setSelectedCategoryId(item.id)}
                                onDelete={() => runAction("Deleting reporting category", async () => deleteCategory(item.id, item.name))}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState title="No reporting categories yet" detail="Create formal reporting categories before assigning accounts to statements, GST support, or BAS support buckets." />
                )}
              </div>
              <div className="mini-card reference-form-card">
                <h3>{selectedCategoryId ? "Update selected reporting category" : "Add reporting category"}</h3>
                <p className="reference-form-meta">Read from the list, adjust the formal label, then save or delete from the row actions menu.</p>
                <div className="form-grid">
                  <Field label="Code"><input value={categoryDraft.code} onChange={(event) => setCategoryDraft((current) => ({ ...current, code: event.target.value }))} /></Field>
                  <Field label="Name"><input value={categoryDraft.name} onChange={(event) => setCategoryDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                  <Field label="Active"><input type="checkbox" checked={categoryDraft.is_active} onChange={(event) => setCategoryDraft((current) => ({ ...current, is_active: event.target.checked }))} /></Field>
                  <Field label="Category type">
                    <select value={categoryDraft.category_type} onChange={(event) => setCategoryDraft((current) => ({ ...current, category_type: event.target.value }))}>
                      {reportingCategoryTypeOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="request-actions">
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving category", saveCategory)}>Save category</button>
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={resetCategoryForm}>New category</button>
                </div>
              </div>
            </div>
          </div>

          <div className="mini-card reference-management-block">
            <div className="reference-management-header">
              <div>
                <h3>Tax codes</h3>
                <p className="reference-management-copy">Manage GST treatments, BAS labels, rates, and descriptions from a single block instead of raw free-text inputs.</p>
              </div>
              <span className="pill">{taxCodes.length} tax codes</span>
            </div>
            <div className="stats-grid mini-stats-grid">
              <div className="stat-card"><span>GST applicable</span><strong>{taxCodes.filter((item) => item.is_gst_applicable).length}</strong></div>
              <div className="stat-card"><span>BAS mapped</span><strong>{taxCodes.filter((item) => item.bas_label).length}</strong></div>
            </div>
            <div className="workspace-split">
              <div>
                {taxCodes.length ? (
                  <div className="table-shell compact-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Code</th><th>Name</th><th>Rate</th><th>GST treatment</th><th>BAS label</th><th>Status</th><th>Actions</th></tr></thead>
                      <tbody>
                        {taxCodes.map((item) => (
                          <tr key={item.id} className={selectedTaxCodeId === item.id ? "is-selected" : ""} onClick={() => setSelectedTaxCodeId(item.id)}>
                            <td><strong>{item.code}</strong></td>
                            <td>{item.name}<div className="table-meta">{item.description || "No description"}</div></td>
                            <td>{formatRate(String(item.rate))}</td>
                            <td>{formatOptionLabel(taxInputOutputOptionMap, item.input_output_type)}</td>
                            <td>{item.bas_label || "-"}</td>
                            <td><StatusPill value={item.is_active ? "active" : "inactive"} /></td>
                            <td className="row-actions-cell">
                              <RowActionsMenu
                                onEdit={() => setSelectedTaxCodeId(item.id)}
                                onDelete={() => runAction("Deleting tax code", async () => deleteTaxCode(item.id, item.code))}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState title="No tax codes yet" detail="Create GST codes with clear BAS labels and input/output treatment before using them on accounts or journal lines." />
                )}
              </div>
              <div className="mini-card reference-form-card">
                <h3>{selectedTaxCodeId ? "Update selected tax code" : "Add tax code"}</h3>
                <p className="reference-form-meta">Use formal GST treatment labels so operators do not have to remember raw enum names.</p>
                <div className="form-grid two-up">
                  <Field label="Code"><input value={taxCodeDraft.code} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, code: event.target.value }))} /></Field>
                  <Field label="Name"><input value={taxCodeDraft.name} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                  <Field label="Rate"><input value={taxCodeDraft.rate} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, rate: event.target.value }))} /></Field>
                  <Field label="BAS label"><input value={taxCodeDraft.bas_label} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, bas_label: event.target.value }))} /></Field>
                  <Field label="Input / output type">
                    <select value={taxCodeDraft.input_output_type} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, input_output_type: event.target.value }))}>
                      {taxInputOutputOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </Field>
                  <Field label="GST applicable"><input type="checkbox" checked={taxCodeDraft.is_gst_applicable} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, is_gst_applicable: event.target.checked }))} /></Field>
                  <Field label="Active"><input type="checkbox" checked={taxCodeDraft.is_active} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, is_active: event.target.checked }))} /></Field>
                  <Field label="Description" wide><textarea rows={4} value={taxCodeDraft.description} onChange={(event) => setTaxCodeDraft((current) => ({ ...current, description: event.target.value }))} /></Field>
                </div>
                <p className="reference-form-meta">Selected treatment: {selectedTaxInputOutputOption?.detail ?? "Choose a GST treatment."}</p>
                <div className="request-actions">
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving tax code", saveTaxCode)}>Save tax code</button>
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={resetTaxCodeForm}>New tax code</button>
                </div>
              </div>
            </div>
          </div>

          <div className="mini-card reference-management-block">
            <div className="reference-management-header">
              <div>
                <h3>Accounts</h3>
                <p className="reference-management-copy">Use the formal account type map, lock the first two digits from the selected range, and manage chart metadata from the list view.</p>
              </div>
              <span className="pill">{accounts.length} accounts</span>
            </div>
            <div className="stats-grid mini-stats-grid">
              <div className="stat-card"><span>Active</span><strong>{accounts.filter((item) => item.is_active).length}</strong></div>
              <div className="stat-card"><span>Manual posting</span><strong>{accounts.filter((item) => item.allow_manual_posting).length}</strong></div>
            </div>
            <div className="workspace-split">
              <div>
                {accounts.length ? (
                  <div className="table-shell compact-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Account</th><th>Type</th><th>Reporting</th><th>Tax code</th><th>Status</th><th>Actions</th></tr></thead>
                      <tbody>
                        {accounts.map((item) => (
                          <tr key={item.id} className={selectedAccountId === item.id ? "is-selected" : ""} onClick={() => setSelectedAccountId(item.id)}>
                            <td><strong>{item.account_code}</strong><div className="table-meta">{item.name}</div></td>
                            <td>{formatOptionLabel(accountTypeOptionMap, item.account_type)}</td>
                            <td>{item.reporting_category_id ? categoryLabelById.get(item.reporting_category_id) : "None"}</td>
                            <td>{item.default_tax_code_id ? taxCodeLabelById.get(item.default_tax_code_id) : "None"}</td>
                            <td>
                              <div className="reference-status-stack">
                                <StatusPill value={item.is_active ? "active" : "inactive"} />
                                <StatusPill value={item.allow_manual_posting ? "manual_allowed" : "manual_blocked"} />
                              </div>
                            </td>
                            <td className="row-actions-cell">
                              <RowActionsMenu
                                onEdit={() => setSelectedAccountId(item.id)}
                                onDelete={() => runAction("Deactivating account", async () => deleteAccount(item.id, item.name))}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState title="No accounts yet" detail="Create accounts from the formal type ranges first so journals, reports, and GST defaults stay consistent." />
                )}
              </div>
              <div className="mini-card reference-form-card">
                <h3>{selectedAccountId ? "Update selected account" : "Add account"}</h3>
                <p className="reference-form-meta">Standard account types lock the first two digits of the code range. Legacy advanced types keep manual code entry for compatibility.</p>
                <div className="form-grid two-up">
                  <Field label="Account type" wide>
                    <select value={accountDraft.account_type} onChange={(event) => handleAccountTypeChange(event.target.value)}>
                      <optgroup label="Standard account types">
                        {primaryAccountTypeOptions.map((item) => <option key={item.value} value={item.value}>{item.label} ({item.detail})</option>)}
                      </optgroup>
                      <optgroup label="Advanced / legacy account types">
                        {legacyAccountTypeOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                      </optgroup>
                    </select>
                  </Field>
                  {managedAccountCode ? (
                    <>
                      <Field label="Account prefix">
                        <select value={managedAccountCode.prefix} onChange={(event) => setAccountDraft((current) => ({ ...current, account_code: `${event.target.value}${managedAccountCode.suffix.replace(/\D/g, "").slice(0, 2)}` }))}>
                          {managedAccountCode.prefixOptions.map((prefix) => <option key={prefix} value={prefix}>{prefix}xx</option>)}
                        </select>
                      </Field>
                      <Field label="Last two digits">
                        <input inputMode="numeric" maxLength={2} placeholder="00" value={managedAccountCode.suffix} onChange={(event) => setAccountDraft((current) => ({ ...current, account_code: `${managedAccountCode.prefix}${event.target.value.replace(/\D/g, "").slice(0, 2)}` }))} />
                      </Field>
                      <Field label="Account code preview" wide><input value={`${managedAccountCode.prefix}${managedAccountCode.suffix.replace(/\D/g, "").slice(0, 2)}`} readOnly /></Field>
                    </>
                  ) : (
                    <Field label="Account code" wide><input value={accountDraft.account_code} onChange={(event) => setAccountDraft((current) => ({ ...current, account_code: event.target.value }))} /></Field>
                  )}
                  <Field label="Name" wide><input value={accountDraft.name} onChange={(event) => setAccountDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                  <Field label="Reporting category"><select value={accountDraft.reporting_category_id} onChange={(event) => setAccountDraft((current) => ({ ...current, reporting_category_id: event.target.value }))}><option value="">None</option>{accountCategoryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                  <Field label="Default tax code"><select value={accountDraft.default_tax_code_id} onChange={(event) => setAccountDraft((current) => ({ ...current, default_tax_code_id: event.target.value }))}><option value="">None</option>{accountTaxCodeOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                  <Field label="Active"><input type="checkbox" checked={accountDraft.is_active} onChange={(event) => setAccountDraft((current) => ({ ...current, is_active: event.target.checked }))} /></Field>
                  <Field label="Allow manual posting"><input type="checkbox" checked={accountDraft.account_type === "non_posting" ? false : accountDraft.allow_manual_posting} disabled={accountDraft.account_type === "non_posting"} onChange={(event) => setAccountDraft((current) => ({ ...current, allow_manual_posting: event.target.checked }))} /></Field>
                </div>
                <p className="reference-form-meta">Selected type: {selectedAccountTypeOption?.label ?? "Unknown"}{selectedAccountTypeOption?.detail ? ` · ${selectedAccountTypeOption.detail}` : ""}</p>
                {managedAccountCode && accountDraft.account_code && !managedAccountCode.isRangeMatch ? <p className="workbench-warning">The current account code does not yet sit inside the selected range. Save after entering a valid two-digit suffix.</p> : null}
                <div className="request-actions">
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving account", saveAccount)}>Save account</button>
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={resetAccountForm}>New account</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>
    </section>
  );
}