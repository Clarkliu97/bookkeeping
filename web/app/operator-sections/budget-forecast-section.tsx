import { Fragment, useEffect, useMemo, useState } from "react";

import { formatDate, formatDateTime, formatMoney, type OperatorState } from "../operator-state";
import { EmptyState, Field, StatusPill, WorkspaceTabs } from "../operator-ui";


type PlanningPlan = {
  id: string;
  company_id: string;
  name: string;
  plan_type: "budget" | "forecast";
  scenario_type: "baseline" | "upside" | "downside" | "custom";
  scenario_label: string;
  financial_year_start: string;
  financial_year_end: string;
  currency_code: string;
  version_number: number;
  revision: number;
  status: "draft" | "in_review" | "approved" | "locked" | "archived";
  is_primary: boolean;
  source_plan_id: string | null;
  baseline_budget_plan_id: string | null;
  actual_through_date: string | null;
  assumption_summary: string | null;
  preparer_note: string | null;
  review_note: string | null;
  created_at: string;
  updated_at: string;
};

type PlanningPeriod = {
  id: string;
  sequence_number: number;
  period_label: string;
  start_date: string;
  end_date: string;
  accounting_period_id: string | null;
};

type PlanningLine = {
  id: string;
  planning_period_id: string;
  account_id: string;
  amount: string;
  entry_method: string;
  note: string | null;
};

type PlanningBudgetItemFrequency = "one_off" | "monthly" | "quarterly" | "half_yearly" | "annually";

type PlanningBudgetItem = {
  id: string;
  account_id: string;
  name: string;
  amount: string;
  occurrence_frequency: PlanningBudgetItemFrequency;
  start_period_id: string;
  end_period_id: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
};

type PlanningBudgetItemFloor = {
  account_id: string;
  planning_period_id: string;
  amount: string;
};

type PlanningFloorAdjustment = {
  account_id: string;
  planning_period_id: string;
  requested_amount: string | null;
  applied_minimum: string;
};

type PlanningAccount = {
  id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  reporting_category_code: string | null;
  is_active: boolean;
};

type PlanningWarning = {
  code: string;
  message: string;
  account_id: string | null;
  planning_period_id: string | null;
  severity: string;
};

type PlanningPlanDetail = {
  plan: PlanningPlan;
  periods: PlanningPeriod[];
  lines: PlanningLine[];
  budget_items: PlanningBudgetItem[];
  budget_item_floors: PlanningBudgetItemFloor[];
  floor_adjustments: PlanningFloorAdjustment[];
  accounts: PlanningAccount[];
  warnings: PlanningWarning[];
  annual_budget_income: string;
  annual_budget_expenses: string;
  annual_budget_net_profit: string;
  can_edit: boolean;
};

type ForecastMonth = {
  planning_period_id: string;
  period_label: string;
  actual_amount: string;
  budget_amount: string;
  forecast_amount: string;
  projected_amount: string;
  value_source: string;
  warning_code: string | null;
};

type ForecastAccount = {
  account_id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  actual_ytd: string;
  annual_budget: string;
  forecast_remaining: string;
  projected_year_end: string;
  variance_amount: string;
  variance_percentage: string | null;
  variance_direction: string;
  months: ForecastMonth[];
};

type ForecastRun = {
  id: string | null;
  forecast_plan_id: string;
  forecast_plan_name: string;
  actual_through_date: string;
  ledger_calculated_at: string;
  warning_count: number;
  warnings: PlanningWarning[];
  actual_total_income: string;
  actual_total_expenses: string;
  actual_net_profit: string;
  forecast_total_income: string;
  forecast_total_expenses: string;
  forecast_net_profit: string;
  projected_total_income: string;
  projected_total_expenses: string;
  projected_gross_profit: string;
  projected_operating_profit: string;
  projected_net_profit: string;
  budget_total_income: string;
  budget_total_expenses: string;
  budget_gross_profit: string;
  budget_operating_profit: string;
  budget_net_profit: string;
  variance_to_budget: string;
  rows: ForecastAccount[];
};

type ForecastRunSummary = {
  id: string;
  forecast_plan_id: string;
  actual_through_date: string;
  ledger_calculated_at: string;
  warning_count: number;
  projected_net_profit: string;
  budget_net_profit: string | null;
  variance_to_budget: string | null;
};

type PlanningComparison = {
  financial_year_start: string;
  financial_year_end: string;
  items: Array<{
    plan_id: string;
    plan_name: string;
    scenario_label: string;
    actual_through_date: string;
    projected_total_income: string;
    projected_total_expenses: string;
    projected_net_profit: string;
    budget_net_profit: string;
    variance_to_budget: string;
    warning_count: number;
  }>;
};

type PlanningImportPreview = {
  valid_rows: number;
  lines: Array<{
    planning_period_id: string;
    account_id: string;
    amount: string | null;
    entry_method: string;
    note: string | null;
  }>;
  errors: Array<{ row_number: number; message: string }>;
};

type WorkspaceTab = "overview" | "builder" | "forecast" | "scenarios";


function isoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}


function defaultFinancialYear() {
  const today = new Date();
  const currentYearStart = new Date(Date.UTC(today.getUTCFullYear(), 6, 1));
  const startYear = today >= currentYearStart ? today.getUTCFullYear() : today.getUTCFullYear() - 1;
  return {
    start: `${startYear}-07-01`,
    end: `${startYear + 1}-06-30`,
  };
}


function lineKey(accountId: string, periodId: string) {
  return `${accountId}:${periodId}`;
}


function accountSection(accountType: string) {
  if (["income", "revenue", "contra_income"].includes(accountType)) {
    return "Revenue and income";
  }
  if (accountType === "cost_of_sales") {
    return "Cost of sales";
  }
  if (accountType === "other_income") {
    return "Other income";
  }
  if (accountType === "other_expense") {
    return "Other expenses";
  }
  return "Operating expenses";
}


function amountTone(value: string | number) {
  const number = Number(value);
  if (number > 0) {
    return "planning-positive";
  }
  if (number < 0) {
    return "planning-negative";
  }
  return "";
}

function emptyBudgetItemDraft(startPeriodId = "") {
  return {
    name: "",
    account_id: "",
    amount: "",
    occurrence_frequency: "monthly" as PlanningBudgetItemFrequency,
    start_period_id: startPeriodId,
    end_period_id: "",
    note: "",
  };
}


export function BudgetForecastSection({ operator }: { operator: OperatorState }) {
  const {
    selectedCompanyId,
    request,
    runAction,
    showMessage,
    downloadFromApi,
    confirmDanger,
  } = operator;
  const financialYear = useMemo(() => defaultFinancialYear(), []);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [plans, setPlans] = useState<PlanningPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [detail, setDetail] = useState<PlanningPlanDetail | null>(null);
  const [runs, setRuns] = useState<ForecastRunSummary[]>([]);
  const [forecast, setForecast] = useState<ForecastRun | null>(null);
  const [comparison, setComparison] = useState<PlanningComparison | null>(null);
  const [comparisonPlanIds, setComparisonPlanIds] = useState<string[]>([]);
  const [lineDrafts, setLineDrafts] = useState<Record<string, string>>({});
  const [actionNote, setActionNote] = useState("Ready for planning review");
  const [forecastCutoff, setForecastCutoff] = useState("");
  const [createDraft, setCreateDraft] = useState({
    name: `FY${Number(financialYear.end.slice(0, 4))} Baseline Budget`,
    plan_type: "budget" as "budget" | "forecast",
    scenario_type: "baseline",
    scenario_label: "Baseline",
    financial_year_start: financialYear.start,
    financial_year_end: financialYear.end,
    baseline_budget_plan_id: "",
    actual_through_date: "",
    assumption_summary: "",
    preparer_note: "",
  });
  const [manageDraft, setManageDraft] = useState({
    name: "",
    scenario_type: "baseline",
    scenario_label: "",
    baseline_budget_plan_id: "",
    actual_through_date: "",
    assumption_summary: "",
    preparer_note: "",
  });
  const [spreadDraft, setSpreadDraft] = useState({
    account_id: "",
    annual_amount: "",
    note: "",
  });
  const [priorActualGrowth, setPriorActualGrowth] = useState("0.00");
  const [planGrowth, setPlanGrowth] = useState("0.00");
  const [planningImportFile, setPlanningImportFile] = useState<File | null>(null);
  const [planningImportPreview, setPlanningImportPreview] = useState<PlanningImportPreview | null>(null);
  const [selectedBudgetItemId, setSelectedBudgetItemId] = useState("");
  const [budgetItemDraft, setBudgetItemDraft] = useState(emptyBudgetItemDraft());
  const [cloneDraft, setCloneDraft] = useState({
    name: "",
    plan_type: "forecast" as "budget" | "forecast",
    scenario_type: "baseline",
    scenario_label: "Reforecast",
    actual_through_date: "",
  });

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan.id === selectedPlanId) ?? null,
    [plans, selectedPlanId],
  );
  const baselineBudgets = useMemo(
    () => plans.filter((plan) => plan.plan_type === "budget" && plan.status !== "archived"),
    [plans],
  );
  const groupedAccounts = useMemo(() => {
    const groups = new Map<string, PlanningAccount[]>();
    for (const account of detail?.accounts ?? []) {
      const section = accountSection(account.account_type);
      groups.set(section, [...(groups.get(section) ?? []), account]);
    }
    return [...groups.entries()];
  }, [detail?.accounts]);
  const budgetItemFloorByLine = useMemo(() => {
    const floors = new Map<string, PlanningBudgetItemFloor>();
    for (const floor of detail?.budget_item_floors ?? []) {
      floors.set(lineKey(floor.account_id, floor.planning_period_id), floor);
    }
    return floors;
  }, [detail?.budget_item_floors]);
  const latestRun = forecast ?? null;

  async function loadPlans(preferredPlanId?: string) {
    if (!selectedCompanyId) {
      setPlans([]);
      setSelectedPlanId("");
      setDetail(null);
      return;
    }
    const loaded = await request<PlanningPlan[]>(
      `/api/companies/${selectedCompanyId}/planning/plans`,
    );
    setPlans(loaded);
    const nextId = preferredPlanId
      ?? (loaded.some((plan) => plan.id === selectedPlanId) ? selectedPlanId : loaded[0]?.id ?? "");
    setSelectedPlanId(nextId);
  }

  async function loadPlanDetail(planId: string) {
    if (!selectedCompanyId || !planId) {
      setDetail(null);
      setRuns([]);
      return;
    }
    const [loadedDetail, loadedRuns] = await Promise.all([
      request<PlanningPlanDetail>(
        `/api/companies/${selectedCompanyId}/planning/plans/${planId}`,
      ),
      request<ForecastRunSummary[]>(
        `/api/companies/${selectedCompanyId}/planning/forecast-runs?plan_id=${planId}`,
      ),
    ]);
    setDetail(loadedDetail);
    setRuns(loadedRuns);
    setSelectedBudgetItemId("");
    setBudgetItemDraft(emptyBudgetItemDraft(loadedDetail.periods[0]?.id ?? ""));
    setForecastCutoff(
      loadedDetail.plan.actual_through_date
      ?? new Date(`${loadedDetail.plan.financial_year_start}T00:00:00Z`).toISOString().slice(0, 10),
    );
    setManageDraft({
      name: loadedDetail.plan.name,
      scenario_type: loadedDetail.plan.scenario_type,
      scenario_label: loadedDetail.plan.scenario_label,
      baseline_budget_plan_id: loadedDetail.plan.baseline_budget_plan_id ?? "",
      actual_through_date: loadedDetail.plan.actual_through_date ?? "",
      assumption_summary: loadedDetail.plan.assumption_summary ?? "",
      preparer_note: loadedDetail.plan.preparer_note ?? "",
    });
    const values: Record<string, string> = {};
    for (const line of loadedDetail.lines) {
      values[lineKey(line.account_id, line.planning_period_id)] = line.amount;
    }
    setLineDrafts(values);
  }

  useEffect(() => {
    void loadPlans().catch((error) => {
      showMessage("error", error instanceof Error ? error.message : "Unable to load planning plans.");
    });
    // request and message helpers are intentionally omitted because the operator hook recreates them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCompanyId]);

  useEffect(() => {
    setForecast(null);
    setComparison(null);
    if (!selectedPlanId) {
      setDetail(null);
      return;
    }
    void loadPlanDetail(selectedPlanId).catch((error) => {
      showMessage("error", error instanceof Error ? error.message : "Unable to load planning detail.");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPlanId]);

  async function createPlan() {
    if (!createDraft.name.trim()) {
      throw new Error("Enter a plan name.");
    }
    const created = await request<PlanningPlan>(
      `/api/companies/${selectedCompanyId}/planning/plans`,
      "POST",
      {
        ...createDraft,
        name: createDraft.name.trim(),
        baseline_budget_plan_id: createDraft.baseline_budget_plan_id || null,
        actual_through_date: createDraft.plan_type === "forecast"
          ? createDraft.actual_through_date || null
          : null,
        assumption_summary: createDraft.assumption_summary || null,
        preparer_note: createDraft.preparer_note || null,
      },
    );
    await loadPlans(created.id);
    setActiveTab("builder");
    showMessage("success", `Created ${created.plan_type} "${created.name}".`);
  }

  async function savePlanningValues() {
    if (!detail) {
      throw new Error("Select a planning plan.");
    }
    const lines = Object.entries(lineDrafts).map(([key, value]) => {
      const [accountId, periodId] = key.split(":");
      return {
        account_id: accountId,
        planning_period_id: periodId,
        amount: value.trim() === "" ? null : value,
        entry_method: detail.plan.plan_type === "forecast" ? "forecast_override" : "manual",
      };
    });
    if (!lines.length) {
      throw new Error("Enter at least one monthly planning value.");
    }
    const updated = await request<PlanningPlanDetail>(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/lines/bulk`,
      "PUT",
      { revision: detail.plan.revision, lines },
    );
    applyUpdatedDetail(updated);
    showPlanningMutationResult(updated, `Saved ${lines.length} planning values.`);
  }

  async function savePlanDetails() {
    if (!detail || !manageDraft.name.trim() || !manageDraft.scenario_label.trim()) {
      throw new Error("Select a draft plan and enter its name and scenario label.");
    }
    const updated = await request<PlanningPlan>(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}`,
      "PUT",
      {
        revision: detail.plan.revision,
        name: manageDraft.name.trim(),
        scenario_type: manageDraft.scenario_type,
        scenario_label: manageDraft.scenario_label.trim(),
        baseline_budget_plan_id: detail.plan.plan_type === "forecast"
          ? manageDraft.baseline_budget_plan_id || null
          : null,
        actual_through_date: detail.plan.plan_type === "forecast"
          ? manageDraft.actual_through_date || null
          : null,
        assumption_summary: manageDraft.assumption_summary || null,
        preparer_note: manageDraft.preparer_note || null,
      },
    );
    await loadPlans(updated.id);
    await loadPlanDetail(updated.id);
    showMessage("success", `Updated planning plan "${updated.name}".`);
  }

  async function spreadAnnualAmount() {
    if (!detail || !spreadDraft.account_id || !spreadDraft.annual_amount) {
      throw new Error("Choose an account and enter an annual amount.");
    }
    const updated = await request<PlanningPlanDetail>(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/spread`,
      "POST",
      {
        revision: detail.plan.revision,
        account_id: spreadDraft.account_id,
        annual_amount: spreadDraft.annual_amount,
        note: spreadDraft.note || null,
      },
    );
    applyUpdatedDetail(updated);
    showPlanningMutationResult(updated, "Spread the annual amount across all fiscal months.");
  }

  function applyUpdatedDetail(updated: PlanningPlanDetail) {
    setDetail(updated);
    setPlans((current) => current.map((plan) => plan.id === updated.plan.id ? updated.plan : plan));
    setManageDraft({
      name: updated.plan.name,
      scenario_type: updated.plan.scenario_type,
      scenario_label: updated.plan.scenario_label,
      baseline_budget_plan_id: updated.plan.baseline_budget_plan_id ?? "",
      actual_through_date: updated.plan.actual_through_date ?? "",
      assumption_summary: updated.plan.assumption_summary ?? "",
      preparer_note: updated.plan.preparer_note ?? "",
    });
    const values: Record<string, string> = {};
    for (const line of updated.lines) {
      values[lineKey(line.account_id, line.planning_period_id)] = line.amount;
    }
    setLineDrafts(values);
  }

  function showPlanningMutationResult(updated: PlanningPlanDetail, successMessage: string) {
    if (!updated.floor_adjustments.length) {
      showMessage("success", successMessage);
      return;
    }
    const first = updated.floor_adjustments[0];
    const account = updated.accounts.find((candidate) => candidate.id === first.account_id);
    const period = updated.periods.find((candidate) => candidate.id === first.planning_period_id);
    const example = account && period
      ? ` ${account.account_name} ${period.period_label} was set to ${formatMoney(first.applied_minimum)}.`
      : "";
    showMessage(
      "info",
      `${successMessage} ${updated.floor_adjustments.length} value${updated.floor_adjustments.length === 1 ? "" : "s"} could not be lower than the budget-item total and were changed to the minimum.${example}`,
    );
  }

  function resetBudgetItemEditor() {
    setSelectedBudgetItemId("");
    setBudgetItemDraft(emptyBudgetItemDraft(detail?.periods[0]?.id ?? ""));
  }

  function editBudgetItem(item: PlanningBudgetItem) {
    setSelectedBudgetItemId(item.id);
    setBudgetItemDraft({
      name: item.name,
      account_id: item.account_id,
      amount: item.amount,
      occurrence_frequency: item.occurrence_frequency,
      start_period_id: item.start_period_id,
      end_period_id: item.end_period_id ?? "",
      note: item.note ?? "",
    });
  }

  async function saveBudgetItem() {
    if (
      !detail
      || detail.plan.plan_type !== "budget"
      || !budgetItemDraft.name.trim()
      || !budgetItemDraft.account_id
      || !budgetItemDraft.amount.trim()
      || !budgetItemDraft.start_period_id
    ) {
      throw new Error("Enter an item name, account, amount, frequency, and starting month.");
    }
    const updated = await request<PlanningPlanDetail>(
      selectedBudgetItemId
        ? `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/budget-items/${selectedBudgetItemId}`
        : `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/budget-items`,
      selectedBudgetItemId ? "PUT" : "POST",
      {
        revision: detail.plan.revision,
        name: budgetItemDraft.name.trim(),
        account_id: budgetItemDraft.account_id,
        amount: budgetItemDraft.amount,
        occurrence_frequency: budgetItemDraft.occurrence_frequency,
        start_period_id: budgetItemDraft.start_period_id,
        end_period_id: budgetItemDraft.occurrence_frequency === "one_off"
          ? null
          : budgetItemDraft.end_period_id || null,
        note: budgetItemDraft.note || null,
      },
    );
    const action = selectedBudgetItemId ? "Updated" : "Created";
    applyUpdatedDetail(updated);
    resetBudgetItemEditor();
    showPlanningMutationResult(updated, `${action} budget item "${budgetItemDraft.name.trim()}".`);
  }

  async function deleteSelectedBudgetItem() {
    if (!detail || !selectedBudgetItemId) {
      throw new Error("Select a budget item to delete.");
    }
    const item = detail.budget_items.find((candidate) => candidate.id === selectedBudgetItemId);
    if (!item || !confirmDanger(`Delete budget item "${item.name}"? Existing monthly budget values will be retained.`)) {
      return;
    }
    await request(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/budget-items/${item.id}?revision=${detail.plan.revision}`,
      "DELETE",
      undefined,
      "void",
    );
    await loadPlanDetail(detail.plan.id);
    showMessage(
      "success",
      `Deleted budget item "${item.name}". Existing monthly values were retained and can now be reduced manually.`,
    );
  }

  function enforceDraftFloor(account: PlanningAccount, period: PlanningPeriod) {
    const key = lineKey(account.id, period.id);
    const floor = budgetItemFloorByLine.get(key);
    if (!floor) {
      return;
    }
    const draft = lineDrafts[key]?.trim() ?? "";
    const requested = draft === "" ? null : Number(draft);
    if (requested !== null && (!Number.isFinite(requested) || requested >= Number(floor.amount))) {
      return;
    }
    setLineDrafts((current) => ({ ...current, [key]: floor.amount }));
    showMessage(
      "info",
      `${account.account_name} ${period.period_label} cannot be lower than the ${formatMoney(floor.amount)} budget-item total. The value was changed to that minimum.`,
    );
  }

  function clearAccountLine(account: PlanningAccount) {
    if (!detail || !detail.can_edit || !account.is_active) {
      return;
    }
    const protectedMonthCount = detail.periods.filter((period) => (
      budgetItemFloorByLine.has(lineKey(account.id, period.id))
    )).length;
    setLineDrafts((current) => {
      const next = { ...current };
      for (const period of detail.periods) {
        const key = lineKey(account.id, period.id);
        const floor = budgetItemFloorByLine.get(key);
        next[key] = floor?.amount ?? "";
      }
      return next;
    });
    showMessage(
      "info",
      protectedMonthCount
        ? `Cleared the ${account.account_name} line. ${protectedMonthCount} protected month${protectedMonthCount === 1 ? " remains" : "s remain"} at the budget-item minimum. Save planning values to persist the change.`
        : `Cleared the ${account.account_name} line. Save planning values to persist the change.`,
    );
  }

  async function copyPriorActuals() {
    if (!detail) {
      throw new Error("Select a draft planning plan.");
    }
    const updated = await request<PlanningPlanDetail>(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/copy-prior-actuals`,
      "POST",
      {
        revision: detail.plan.revision,
        growth_percentage: priorActualGrowth || "0.00",
        note: "Copied from prior-year posted actuals",
      },
    );
    applyUpdatedDetail(updated);
    showPlanningMutationResult(updated, "Copied prior-year posted actuals into the monthly plan.");
  }

  async function applyGrowthToPlan() {
    if (!detail) {
      throw new Error("Select a draft planning plan.");
    }
    const updated = await request<PlanningPlanDetail>(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/apply-growth`,
      "POST",
      {
        revision: detail.plan.revision,
        growth_percentage: planGrowth,
        note: `Applied ${planGrowth}% planning adjustment`,
      },
    );
    applyUpdatedDetail(updated);
    showPlanningMutationResult(updated, `Applied ${planGrowth}% to the existing planning values.`);
  }

  async function previewPlanningImport() {
    if (!detail || !planningImportFile) {
      throw new Error("Choose a planning CSV file.");
    }
    const formData = new FormData();
    formData.append("file", planningImportFile);
    const preview = await request<PlanningImportPreview>(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/imports/preview`,
      "POST",
      formData,
    );
    setPlanningImportPreview(preview);
    showMessage(
      preview.errors.length ? "info" : "success",
      `Planning CSV preview found ${preview.valid_rows} valid rows and ${preview.errors.length} errors.`,
    );
  }

  async function commitPlanningImport() {
    if (!detail || !planningImportFile || !planningImportPreview) {
      throw new Error("Preview a planning CSV before importing it.");
    }
    if (planningImportPreview.errors.length) {
      throw new Error("Resolve every CSV preview error before importing.");
    }
    const formData = new FormData();
    formData.append("revision", String(detail.plan.revision));
    formData.append("file", planningImportFile);
    const updated = await request<PlanningPlanDetail>(
      `/api/companies/${selectedCompanyId}/planning/plans/${detail.plan.id}/imports/commit`,
      "POST",
      formData,
    );
    applyUpdatedDetail(updated);
    setPlanningImportPreview(null);
    setPlanningImportFile(null);
    showPlanningMutationResult(updated, `Imported ${planningImportPreview.valid_rows} planning values.`);
  }

  async function lifecycleAction(action: "submit" | "review" | "approve" | "reject" | "lock" | "archive") {
    if (!selectedPlan) {
      throw new Error("Select a planning plan.");
    }
    const updated = await request<PlanningPlan>(
      `/api/companies/${selectedCompanyId}/planning/plans/${selectedPlan.id}/${action}`,
      "POST",
      { note: actionNote || null },
    );
    await loadPlans(updated.id);
    await loadPlanDetail(updated.id);
    showMessage("success", `${action[0].toUpperCase()}${action.slice(1)} completed for "${updated.name}".`);
  }

  async function deletePlan() {
    if (!selectedPlan) {
      throw new Error("Select a planning plan.");
    }
    if (!confirmDanger(`Delete draft planning plan "${selectedPlan.name}"? This cannot be undone.`)) {
      return;
    }
    await request(
      `/api/companies/${selectedCompanyId}/planning/plans/${selectedPlan.id}`,
      "DELETE",
      undefined,
      "void",
    );
    setSelectedPlanId("");
    await loadPlans();
    showMessage("success", `Deleted draft planning plan "${selectedPlan.name}".`);
  }

  async function cloneSelectedPlan() {
    if (!selectedPlan || !cloneDraft.name.trim()) {
      throw new Error("Select a source plan and enter a name for the new version.");
    }
    const clone = await request<PlanningPlan>(
      `/api/companies/${selectedCompanyId}/planning/plans/${selectedPlan.id}/clone`,
      "POST",
      {
        ...cloneDraft,
        name: cloneDraft.name.trim(),
        baseline_budget_plan_id: cloneDraft.plan_type === "forecast"
          ? selectedPlan.plan_type === "budget"
            ? selectedPlan.id
            : selectedPlan.baseline_budget_plan_id
          : null,
        actual_through_date: cloneDraft.plan_type === "forecast"
          ? cloneDraft.actual_through_date || null
          : null,
      },
    );
    await loadPlans(clone.id);
    setActiveTab(clone.plan_type === "forecast" ? "forecast" : "builder");
    showMessage("success", `Cloned "${selectedPlan.name}" into "${clone.name}".`);
  }

  async function calculateProjection() {
    if (!selectedPlan) {
      throw new Error("Select a plan to calculate.");
    }
    const result = await request<ForecastRun>(
      `/api/companies/${selectedCompanyId}/planning/plans/${selectedPlan.id}/calculate`,
      "POST",
      {
        actual_through_date: selectedPlan.plan_type === "forecast"
          ? forecastCutoff || selectedPlan.actual_through_date
          : null,
        persist: true,
      },
    );
    setForecast(result);
    await loadPlanDetail(selectedPlan.id);
    showMessage("success", `Calculated projected year-end profit for "${selectedPlan.name}".`);
  }

  async function loadRun(runId: string) {
    const result = await request<ForecastRun>(
      `/api/companies/${selectedCompanyId}/planning/forecast-runs/${runId}`,
    );
    setForecast(result);
    setActiveTab("forecast");
  }

  async function compareSelectedPlans() {
    if (comparisonPlanIds.length < 2) {
      throw new Error("Select at least two plans to compare.");
    }
    const result = await request<PlanningComparison>(
      `/api/companies/${selectedCompanyId}/planning/comparisons`,
      "POST",
      {
        plan_ids: comparisonPlanIds,
        actual_through_date: forecastCutoff || null,
      },
    );
    setComparison(result);
    showMessage("success", `Compared ${result.items.length} planning scenarios.`);
  }

  function annualDraftTotal(accountId: string) {
    return (detail?.periods ?? []).reduce(
      (total, period) => total + Number(lineDrafts[lineKey(accountId, period.id)] || 0),
      0,
    );
  }

  return (
    <section className="sections-stack">
      <WorkspaceTabs
        label="Budget and forecast workspaces"
        activeTab={activeTab}
        onChange={setActiveTab}
        options={[
          { key: "overview", label: "Overview", detail: "Plans, versions and projected result", count: plans.length },
          { key: "builder", label: "Budget builder", detail: "Monthly account-level income and expenses" },
          { key: "forecast", label: "Forecast", detail: "Actuals plus future months", count: runs.length },
          { key: "scenarios", label: "Scenarios", detail: "Compare versions and assumptions" },
        ]}
      />

      <article className="panel panel-wide">
        <div className="panel-heading">
          <div>
            <h2>Planning context</h2>
            <p>Planning estimates remain separate from journals and do not change ledger, BAS, tax, or reconciliation results.</p>
          </div>
          <span className="pill">{plans.length} active plans</span>
        </div>
        <div className="planning-context-grid">
          <Field label="Selected plan">
            <select value={selectedPlanId} onChange={(event) => setSelectedPlanId(event.target.value)}>
              <option value="">Select planning plan</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name} v{plan.version_number} · {plan.scenario_label} · {plan.status.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </Field>
          {selectedPlan ? (
            <div className="planning-selected-meta">
              <StatusPill value={selectedPlan.status} />
              <span>{selectedPlan.plan_type}</span>
              <span>{formatDate(selectedPlan.financial_year_start)} – {formatDate(selectedPlan.financial_year_end)}</span>
              <span>Revision {selectedPlan.revision}</span>
            </div>
          ) : null}
        </div>
      </article>

      {activeTab === "overview" ? (
        <>
          <article className="panel panel-wide">
            <div className="panel-heading"><h2>Create planning plan</h2><span className="pill">New version</span></div>
            <div className="form-grid three-up" data-testid="create-planning-plan-form">
              <Field label="Plan name"><input value={createDraft.name} onChange={(event) => setCreateDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
              <Field label="Plan type"><select value={createDraft.plan_type} onChange={(event) => setCreateDraft((current) => ({ ...current, plan_type: event.target.value as "budget" | "forecast" }))}><option value="budget">Budget</option><option value="forecast">Forecast</option></select></Field>
              <Field label="Scenario"><select value={createDraft.scenario_type} onChange={(event) => setCreateDraft((current) => ({ ...current, scenario_type: event.target.value }))}><option value="baseline">Baseline</option><option value="upside">Upside</option><option value="downside">Downside</option><option value="custom">Custom</option></select></Field>
              <Field label="Scenario label"><input value={createDraft.scenario_label} onChange={(event) => setCreateDraft((current) => ({ ...current, scenario_label: event.target.value }))} /></Field>
              <Field label="Financial-year start"><input type="date" value={createDraft.financial_year_start} onChange={(event) => setCreateDraft((current) => ({ ...current, financial_year_start: event.target.value }))} /></Field>
              <Field label="Financial-year end"><input type="date" value={createDraft.financial_year_end} onChange={(event) => setCreateDraft((current) => ({ ...current, financial_year_end: event.target.value }))} /></Field>
              {createDraft.plan_type === "forecast" ? (
                <>
                  <Field label="Baseline budget"><select value={createDraft.baseline_budget_plan_id} onChange={(event) => setCreateDraft((current) => ({ ...current, baseline_budget_plan_id: event.target.value }))}><option value="">No baseline</option>{baselineBudgets.map((plan) => <option key={plan.id} value={plan.id}>{plan.name} v{plan.version_number}</option>)}</select></Field>
                  <Field label="Actual through"><input type="date" value={createDraft.actual_through_date} onChange={(event) => setCreateDraft((current) => ({ ...current, actual_through_date: event.target.value }))} /></Field>
                </>
              ) : null}
              <Field label="Assumption summary" wide><textarea rows={2} value={createDraft.assumption_summary} onChange={(event) => setCreateDraft((current) => ({ ...current, assumption_summary: event.target.value }))} /></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" data-testid="create-planning-plan" type="button" onClick={() => runAction("Creating planning plan", createPlan)}>Create plan</button>
            </div>
          </article>

          <article className="panel panel-wide">
            <div className="panel-heading">
              <div>
                <h2>Manage selected plan</h2>
                <p>Update the current draft separately from creating a new version. Approved and locked versions remain immutable.</p>
              </div>
              {detail ? <StatusPill value={detail.plan.status} /> : null}
            </div>
            {detail ? (
              <>
                <div className="form-grid three-up">
                  <Field label="Plan name"><input disabled={!detail.can_edit} value={manageDraft.name} onChange={(event) => setManageDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                  <Field label="Scenario"><select disabled={!detail.can_edit} value={manageDraft.scenario_type} onChange={(event) => setManageDraft((current) => ({ ...current, scenario_type: event.target.value }))}><option value="baseline">Baseline</option><option value="upside">Upside</option><option value="downside">Downside</option><option value="custom">Custom</option></select></Field>
                  <Field label="Scenario label"><input disabled={!detail.can_edit} value={manageDraft.scenario_label} onChange={(event) => setManageDraft((current) => ({ ...current, scenario_label: event.target.value }))} /></Field>
                  {detail.plan.plan_type === "forecast" ? (
                    <>
                      <Field label="Baseline budget"><select disabled={!detail.can_edit} value={manageDraft.baseline_budget_plan_id} onChange={(event) => setManageDraft((current) => ({ ...current, baseline_budget_plan_id: event.target.value }))}><option value="">No baseline</option>{baselineBudgets.map((plan) => <option key={plan.id} value={plan.id}>{plan.name} v{plan.version_number}</option>)}</select></Field>
                      <Field label="Actual through"><input disabled={!detail.can_edit} type="date" value={manageDraft.actual_through_date} onChange={(event) => setManageDraft((current) => ({ ...current, actual_through_date: event.target.value }))} /></Field>
                    </>
                  ) : null}
                  <Field label="Assumption summary" wide><textarea disabled={!detail.can_edit} rows={2} value={manageDraft.assumption_summary} onChange={(event) => setManageDraft((current) => ({ ...current, assumption_summary: event.target.value }))} /></Field>
                  <Field label="Preparer note" wide><textarea disabled={!detail.can_edit} rows={2} value={manageDraft.preparer_note} onChange={(event) => setManageDraft((current) => ({ ...current, preparer_note: event.target.value }))} /></Field>
                </div>
                <div className="request-actions">
                  <button className="button-link button-link-small" disabled={!detail.can_edit} type="button" onClick={() => runAction("Updating planning plan", savePlanDetails)}>Save selected plan</button>
                </div>
              </>
            ) : <EmptyState title="No planning plan selected" detail="Select a plan to manage its scenario, assumptions, and forecast cutoff." />}
          </article>

          <article className="panel panel-wide">
            <div className="panel-heading"><h2>Year-end outlook</h2>{selectedPlan ? <StatusPill value={selectedPlan.status} /> : null}</div>
            {detail ? (
              <>
                <div className="stats-grid">
                  <div className="stat-card"><span>Annual planned income</span><strong>{formatMoney(detail.annual_budget_income)}</strong></div>
                  <div className="stat-card"><span>Annual planned expenses</span><strong>{formatMoney(detail.annual_budget_expenses)}</strong></div>
                  <div className="stat-card"><span>Planned net profit</span><strong>{formatMoney(detail.annual_budget_net_profit)}</strong></div>
                  <div className="stat-card"><span>Projected net profit</span><strong>{latestRun ? formatMoney(latestRun.projected_net_profit) : "Calculate forecast"}</strong></div>
                  <div className="stat-card"><span>Variance to budget</span><strong>{latestRun ? formatMoney(latestRun.variance_to_budget) : "-"}</strong></div>
                  <div className="stat-card"><span>Review warnings</span><strong>{latestRun?.warning_count ?? detail.warnings.length}</strong></div>
                </div>
                <div className="form-grid two-up planning-lifecycle-form">
                  <Field label="Workflow note" wide><input value={actionNote} onChange={(event) => setActionNote(event.target.value)} /></Field>
                </div>
                <div className="request-actions">
                  {selectedPlan?.status === "draft" ? <button className="button-link button-link-small" type="button" onClick={() => runAction("Submitting planning plan", async () => lifecycleAction("submit"))}>Submit for review</button> : null}
                  {selectedPlan?.status === "in_review" ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Reviewing planning plan", async () => lifecycleAction("review"))}>Record review</button> : null}
                  {selectedPlan?.status === "in_review" ? <button className="button-link button-link-small" type="button" onClick={() => runAction("Approving planning plan", async () => lifecycleAction("approve"))}>Approve</button> : null}
                  {selectedPlan?.status === "in_review" ? <button className="button-link button-link-small button-link-danger" type="button" onClick={() => runAction("Rejecting planning plan", async () => lifecycleAction("reject"))}>Return to draft</button> : null}
                  {selectedPlan?.status === "approved" ? <button className="button-link button-link-small" type="button" onClick={() => runAction("Locking planning plan", async () => lifecycleAction("lock"))}>Lock version</button> : null}
                  {selectedPlan?.status === "draft" ? <button className="button-link button-link-small button-link-danger" data-testid="delete-planning-plan" type="button" onClick={() => runAction("Deleting planning plan", deletePlan)}>Delete draft</button> : null}
                  {selectedPlan ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => downloadFromApi(`/api/companies/${selectedCompanyId}/planning/plans/${selectedPlan.id}/export/csv`, "budget-plan.csv")}>Export CSV</button> : null}
                  {selectedPlan ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => downloadFromApi(`/api/companies/${selectedCompanyId}/planning/plans/${selectedPlan.id}/export/pdf`, "budget-plan.pdf")}>Export PDF</button> : null}
                </div>
              </>
            ) : <EmptyState title="No planning plan selected" detail="Create or select a budget or forecast to see its year-end outlook." />}
          </article>
        </>
      ) : null}

      {activeTab === "builder" ? (
        <>
          <article className="panel panel-wide">
            <div className="panel-heading">
              <div><h2>Monthly P&amp;L planning grid</h2><p>Enter net-of-GST income and expenses as positive amounts; use negative amounts for contra accounts or reductions. Blank is unplanned; zero is an explicit expectation.</p></div>
              {detail ? <StatusPill value={detail.plan.status} /> : null}
            </div>
            {detail ? (
              <>
                {detail.plan.plan_type === "budget" ? (
                  <div className="mini-card planning-budget-items-card" data-testid="budget-items-card">
                    <div className="mini-card-heading">
                      <div>
                        <h3>Budget items</h3>
                        <p className="reference-management-copy">Describe recurring or one-off income and expenses. Their monthly totals become protected minimums in the grid below.</p>
                      </div>
                      <span className="pill">{detail.budget_items.length} items</span>
                    </div>
                    <div className="planning-budget-item-layout">
                      <div>
                        <div className="form-grid three-up">
                          <Field label="Item name"><input disabled={!detail.can_edit} value={budgetItemDraft.name} onChange={(event) => setBudgetItemDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                          <Field label="Item account"><select disabled={!detail.can_edit} value={budgetItemDraft.account_id} onChange={(event) => setBudgetItemDraft((current) => ({ ...current, account_id: event.target.value }))}><option value="">Select account</option>{detail.accounts.filter((account) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.account_code} · {account.account_name}</option>)}</select></Field>
                          <Field label="Amount per occurrence"><input disabled={!detail.can_edit} inputMode="decimal" value={budgetItemDraft.amount} onChange={(event) => setBudgetItemDraft((current) => ({ ...current, amount: event.target.value }))} /></Field>
                          <Field label="Occurrence frequency"><select disabled={!detail.can_edit} value={budgetItemDraft.occurrence_frequency} onChange={(event) => setBudgetItemDraft((current) => ({ ...current, occurrence_frequency: event.target.value as PlanningBudgetItemFrequency }))}><option value="one_off">One off</option><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="half_yearly">Half-yearly</option><option value="annually">Annually</option></select></Field>
                          <Field label="Starting month"><select disabled={!detail.can_edit} value={budgetItemDraft.start_period_id} onChange={(event) => setBudgetItemDraft((current) => ({ ...current, start_period_id: event.target.value }))}>{detail.periods.map((period) => <option key={period.id} value={period.id}>{period.period_label}</option>)}</select></Field>
                          <Field label="Ending month"><select disabled={!detail.can_edit || budgetItemDraft.occurrence_frequency === "one_off"} value={budgetItemDraft.end_period_id} onChange={(event) => setBudgetItemDraft((current) => ({ ...current, end_period_id: event.target.value }))}><option value="">Through year end</option>{detail.periods.filter((period) => period.sequence_number >= (detail.periods.find((candidate) => candidate.id === budgetItemDraft.start_period_id)?.sequence_number ?? 1)).map((period) => <option key={period.id} value={period.id}>{period.period_label}</option>)}</select></Field>
                          <Field label="Item note" wide><textarea disabled={!detail.can_edit} rows={2} value={budgetItemDraft.note} onChange={(event) => setBudgetItemDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                        </div>
                        <div className="request-actions">
                          <button className="button-link button-link-small" data-testid="save-budget-item" disabled={!detail.can_edit} type="button" onClick={() => runAction(selectedBudgetItemId ? "Updating budget item" : "Creating budget item", saveBudgetItem)}>{selectedBudgetItemId ? "Update budget item" : "Add budget item"}</button>
                          {selectedBudgetItemId ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={resetBudgetItemEditor}>Cancel editing</button> : null}
                          {selectedBudgetItemId ? <button className="button-link button-link-small button-link-danger" data-testid="delete-budget-item" disabled={!detail.can_edit} type="button" onClick={() => runAction("Deleting budget item", deleteSelectedBudgetItem)}>Delete budget item</button> : null}
                        </div>
                      </div>
                      <div className="planning-budget-item-list">
                        {detail.budget_items.length ? detail.budget_items.map((item) => {
                          const account = detail.accounts.find((candidate) => candidate.id === item.account_id);
                          const start = detail.periods.find((period) => period.id === item.start_period_id);
                          const end = item.end_period_id ? detail.periods.find((period) => period.id === item.end_period_id) : detail.periods.at(-1);
                          return (
                            <button aria-label={`Manage budget item ${item.name}`} className={`planning-budget-item-row${selectedBudgetItemId === item.id ? " is-selected" : ""}`} key={item.id} type="button" onClick={() => editBudgetItem(item)}>
                              <span><strong>{item.name}</strong><small>{account?.account_code} · {account?.account_name}</small></span>
                              <span><strong>{formatMoney(item.amount)}</strong><small>{item.occurrence_frequency.replaceAll("_", " ")} · {start?.period_label}{item.occurrence_frequency !== "one_off" ? ` to ${end?.period_label}` : ""}</small></span>
                            </button>
                          );
                        }) : <p className="reference-management-copy">No item schedules yet. Add one to build protected monthly values automatically.</p>}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mini-card planning-budget-items-card">
                    <div className="mini-card-heading"><h3>Budget items</h3><span className="pill">Budget plans only</span></div>
                    <p className="reference-management-copy">Forecasts keep their monthly values and baseline link. Create or manage recurring items on the source budget.</p>
                  </div>
                )}
                <div className="mini-card planning-spread-card">
                  <div className="mini-card-heading"><h3>Spread annual amount</h3><span className="pill">Deterministic cents</span></div>
                  <div className="form-grid three-up">
                    <Field label="P&L account"><select value={spreadDraft.account_id} onChange={(event) => setSpreadDraft((current) => ({ ...current, account_id: event.target.value }))}><option value="">Select account</option>{detail.accounts.filter((account) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.account_code} · {account.account_name}</option>)}</select></Field>
                    <Field label="Annual amount"><input inputMode="decimal" value={spreadDraft.annual_amount} onChange={(event) => setSpreadDraft((current) => ({ ...current, annual_amount: event.target.value }))} /></Field>
                    <Field label="Assumption note"><input value={spreadDraft.note} onChange={(event) => setSpreadDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions"><button className="button-link button-link-small button-link-secondary" disabled={!detail.can_edit} type="button" onClick={() => runAction("Spreading annual budget", spreadAnnualAmount)}>Spread over 12 months</button></div>
                </div>
                <div className="mini-card planning-spread-card">
                  <div className="mini-card-heading"><div><h3>Seed and adjust plan</h3><p className="reference-management-copy">Use posted prior-year actuals, apply a controlled percentage change, or import account-month values.</p></div><span className="pill">Draft only</span></div>
                  <div className="form-grid three-up">
                    <Field label="Prior-actual growth %"><input inputMode="decimal" value={priorActualGrowth} onChange={(event) => setPriorActualGrowth(event.target.value)} /></Field>
                    <div className="request-actions planning-calculate-action"><button className="button-link button-link-small button-link-secondary" disabled={!detail.can_edit} type="button" onClick={() => runAction("Copying prior-year actuals", copyPriorActuals)}>Copy prior-year actuals</button></div>
                    <Field label="Adjust current plan %"><input inputMode="decimal" value={planGrowth} onChange={(event) => setPlanGrowth(event.target.value)} /></Field>
                    <div className="request-actions planning-calculate-action"><button className="button-link button-link-small button-link-secondary" disabled={!detail.can_edit} type="button" onClick={() => runAction("Applying planning growth", applyGrowthToPlan)}>Apply to current values</button></div>
                    <Field label="Planning CSV"><input type="file" accept=".csv,text/csv" onChange={(event) => { setPlanningImportFile(event.target.files?.[0] ?? null); setPlanningImportPreview(null); }} /></Field>
                    <div className="request-actions planning-calculate-action"><button className="button-link button-link-small button-link-secondary" disabled={!detail.can_edit || !planningImportFile} type="button" onClick={() => runAction("Previewing planning CSV", previewPlanningImport)}>Preview CSV</button>{planningImportPreview && !planningImportPreview.errors.length ? <button className="button-link button-link-small" type="button" onClick={() => runAction("Importing planning CSV", commitPlanningImport)}>Import {planningImportPreview.valid_rows} rows</button> : null}</div>
                  </div>
                  <p className="reference-management-copy">CSV columns: <code>account_code,period_start,amount,note</code>. The period start must match one of this plan&apos;s fiscal months.</p>
                  {planningImportPreview ? <div className={`planning-import-summary${planningImportPreview.errors.length ? " has-errors" : ""}`}><strong>{planningImportPreview.valid_rows} valid rows</strong><span>{planningImportPreview.errors.length} errors</span>{planningImportPreview.errors.slice(0, 8).map((error) => <small key={`${error.row_number}-${error.message}`}>Row {error.row_number}: {error.message}</small>)}</div> : null}
                </div>
                <div className="planning-grid-shell">
                  <table className="planning-grid" data-testid="planning-grid">
                    <thead>
                      <tr><th>Account</th>{detail.periods.map((period) => <th key={period.id}>{period.period_label}</th>)}<th>Annual total</th></tr>
                    </thead>
                    <tbody>
                      {groupedAccounts.map(([section, accounts]) => (
                        <Fragment key={section}>
                          <tr className="planning-section-row"><th colSpan={14}>{section}</th></tr>
                          {accounts.map((account) => (
                            <tr key={account.id}>
                              <th>
                                <div className="planning-account-cell">
                                  <div className="planning-account-identity"><strong>{account.account_code}</strong><span>{account.account_name}</span></div>
                                  <button
                                    aria-label={`Clear ${account.account_name} line`}
                                    className="planning-clear-line-button"
                                    data-testid={`clear-planning-line-${account.id}`}
                                    disabled={!detail.can_edit || !account.is_active}
                                    title={`Clear all monthly values for ${account.account_name}`}
                                    type="button"
                                    onClick={() => clearAccountLine(account)}
                                  >
                                    Clear
                                  </button>
                                </div>
                              </th>
                              {detail.periods.map((period) => {
                                const key = lineKey(account.id, period.id);
                                const floor = budgetItemFloorByLine.get(key);
                                return <td className={floor ? "planning-floor-cell" : undefined} key={period.id}><input aria-label={`${account.account_name} ${period.period_label}`} className="planning-grid-input" inputMode="decimal" min={floor?.amount} disabled={!detail.can_edit || !account.is_active} value={lineDrafts[key] ?? ""} onChange={(event) => setLineDrafts((current) => ({ ...current, [key]: event.target.value }))} onBlur={() => enforceDraftFloor(account, period)} />{floor ? <small className="planning-floor-hint">Min {formatMoney(floor.amount)}</small> : null}</td>;
                              })}
                              <td className="planning-total-cell">{formatMoney(annualDraftTotal(account.id))}</td>
                            </tr>
                          ))}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="request-actions planning-grid-actions">
                  <button className="button-link button-link-small" data-testid="save-planning-values" disabled={!detail.can_edit} type="button" onClick={() => runAction("Saving planning values", savePlanningValues)}>Save planning values</button>
                  <span className="reference-management-copy">{detail.lines.length} persisted account-month values · revision {detail.plan.revision}</span>
                </div>
              </>
            ) : <EmptyState title="Select a plan" detail="Choose a draft budget or forecast before editing monthly values." />}
          </article>
        </>
      ) : null}

      {activeTab === "forecast" ? (
        <article className="panel panel-wide">
          <div className="panel-heading"><div><h2>Projected year-end profit and loss</h2><p>Completed months use posted ledger actuals; future months use forecast overrides and then budget fallback.</p></div>{forecast ? <span className="pill">{forecast.warning_count} warnings</span> : null}</div>
          {detail ? (
            <>
              <div className="form-grid three-up">
                <Field label="Actual through">
                  <select value={forecastCutoff} onChange={(event) => setForecastCutoff(event.target.value)} disabled={detail.plan.plan_type === "budget"}>
                    <option value={isoDate(new Date(new Date(`${detail.plan.financial_year_start}T00:00:00Z`).getTime() - 86400000))}>No actual months</option>
                    {detail.periods.map((period) => <option key={period.id} value={period.end_date}>{period.period_label} month-end</option>)}
                  </select>
                </Field>
                <div className="request-actions planning-calculate-action"><button className="button-link button-link-small" data-testid="calculate-forecast" type="button" onClick={() => runAction("Calculating year-end forecast", calculateProjection)}>Calculate and save run</button></div>
              </div>
              {forecast ? (
                <>
                  <div className="stats-grid planning-forecast-stats">
                    <div className="stat-card"><span>Actual YTD profit</span><strong>{formatMoney(forecast.actual_net_profit)}</strong></div>
                    <div className="stat-card"><span>Forecast remaining profit</span><strong>{formatMoney(forecast.forecast_net_profit)}</strong></div>
                    <div className="stat-card"><span>Budget net profit</span><strong>{formatMoney(forecast.budget_net_profit)}</strong></div>
                    <div className="stat-card"><span>Projected gross profit</span><strong>{formatMoney(forecast.projected_gross_profit)}</strong></div>
                    <div className="stat-card"><span>Projected operating profit</span><strong>{formatMoney(forecast.projected_operating_profit)}</strong></div>
                    <div className="stat-card"><span>Projected net profit</span><strong data-testid="projected-net-profit">{formatMoney(forecast.projected_net_profit)}</strong></div>
                    <div className="stat-card"><span>Variance to budget</span><strong className={amountTone(forecast.variance_to_budget)}>{formatMoney(forecast.variance_to_budget)}</strong></div>
                  </div>
                  <div className="table-shell">
                    <table className="data-table">
                      <thead><tr><th>Account</th><th>Budget</th><th>Actual YTD</th><th>Forecast remaining</th><th>Projected</th><th>Variance</th><th>Direction</th></tr></thead>
                      <tbody>{forecast.rows.filter((row) => Number(row.annual_budget) || Number(row.actual_ytd) || Number(row.forecast_remaining)).map((row) => <tr key={row.account_id}><td><strong>{row.account_code}</strong><br />{row.account_name}</td><td>{formatMoney(row.annual_budget)}</td><td>{formatMoney(row.actual_ytd)}</td><td>{formatMoney(row.forecast_remaining)}</td><td>{formatMoney(row.projected_year_end)}</td><td>{formatMoney(row.variance_amount)}</td><td><StatusPill value={row.variance_direction} /></td></tr>)}</tbody>
                    </table>
                  </div>
                  <div className="request-actions">
                    {forecast.id ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => downloadFromApi(`/api/companies/${selectedCompanyId}/planning/forecast-runs/${forecast.id}/export/csv`, "forecast-run.csv")}>Download CSV</button> : null}
                    {forecast.id ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => downloadFromApi(`/api/companies/${selectedCompanyId}/planning/forecast-runs/${forecast.id}/export/pdf`, "forecast-run.pdf")}>Download PDF</button> : null}
                  </div>
                </>
              ) : <EmptyState title="No forecast run loaded" detail="Choose an actual-through month and calculate the projected year-end result." />}
              {runs.length ? <div className="mini-card"><h3>Saved calculation runs</h3><div className="compact-list">{runs.map((run) => <button key={run.id} className="list-row-button" type="button" onClick={() => runAction("Loading forecast run", async () => loadRun(run.id))}><span><strong>{formatDateTime(run.ledger_calculated_at)}</strong><small>Actual through {formatDate(run.actual_through_date)}</small></span><span>{formatMoney(run.projected_net_profit)}</span></button>)}</div></div> : null}
            </>
          ) : <EmptyState title="Select a plan" detail="Select a budget or forecast before calculating year-end profit." />}
        </article>
      ) : null}

      {activeTab === "scenarios" ? (
        <>
          <article className="panel panel-wide">
            <div className="panel-heading"><h2>Scenario comparison</h2><span className="pill">Up to 4 plans</span></div>
            <div className="planning-scenario-picker">
              {plans.map((plan) => <label key={plan.id} className="planning-scenario-option"><input type="checkbox" checked={comparisonPlanIds.includes(plan.id)} disabled={!comparisonPlanIds.includes(plan.id) && comparisonPlanIds.length >= 4} onChange={(event) => setComparisonPlanIds((current) => event.target.checked ? [...current, plan.id] : current.filter((id) => id !== plan.id))} /><span><strong>{plan.name}</strong><small>{plan.scenario_label} · {plan.plan_type} · {plan.status.replaceAll("_", " ")}</small></span></label>)}
            </div>
            <div className="request-actions"><button className="button-link button-link-small" type="button" onClick={() => runAction("Comparing planning scenarios", compareSelectedPlans)}>Compare selected plans</button></div>
            {comparison ? <div className="table-shell"><table className="data-table"><thead><tr><th>Plan</th><th>Scenario</th><th>Projected income</th><th>Projected expenses</th><th>Projected net profit</th><th>Variance</th><th>Warnings</th></tr></thead><tbody>{comparison.items.map((item) => <tr key={item.plan_id}><td>{item.plan_name}</td><td>{item.scenario_label}</td><td>{formatMoney(item.projected_total_income)}</td><td>{formatMoney(item.projected_total_expenses)}</td><td>{formatMoney(item.projected_net_profit)}</td><td>{formatMoney(item.variance_to_budget)}</td><td>{item.warning_count}</td></tr>)}</tbody></table></div> : null}
          </article>

          <article className="panel panel-wide">
            <div className="panel-heading"><h2>Clone or reforecast selected plan</h2><span className="pill">Version history</span></div>
            {selectedPlan ? <>
              <div className="form-grid three-up">
                <Field label="New plan name"><input value={cloneDraft.name} onChange={(event) => setCloneDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                <Field label="New plan type"><select value={cloneDraft.plan_type} onChange={(event) => setCloneDraft((current) => ({ ...current, plan_type: event.target.value as "budget" | "forecast" }))}><option value="forecast">Forecast / reforecast</option><option value="budget">Budget version</option></select></Field>
                <Field label="Scenario"><select value={cloneDraft.scenario_type} onChange={(event) => setCloneDraft((current) => ({ ...current, scenario_type: event.target.value }))}><option value="baseline">Baseline</option><option value="upside">Upside</option><option value="downside">Downside</option><option value="custom">Custom</option></select></Field>
                <Field label="Scenario label"><input value={cloneDraft.scenario_label} onChange={(event) => setCloneDraft((current) => ({ ...current, scenario_label: event.target.value }))} /></Field>
                {cloneDraft.plan_type === "forecast" ? <Field label="Actual through"><select value={cloneDraft.actual_through_date} onChange={(event) => setCloneDraft((current) => ({ ...current, actual_through_date: event.target.value }))}><option value="">No actual months</option>{detail?.periods.map((period) => <option key={period.id} value={period.end_date}>{period.period_label} month-end</option>)}</select></Field> : null}
              </div>
              <div className="request-actions"><button className="button-link button-link-small" type="button" onClick={() => runAction("Cloning planning plan", cloneSelectedPlan)}>Clone selected plan</button>{selectedPlan.status !== "archived" ? <button className="button-link button-link-small button-link-danger" type="button" onClick={() => runAction("Archiving planning plan", async () => lifecycleAction("archive"))}>Archive selected plan</button> : null}</div>
            </> : <EmptyState title="Select a source plan" detail="Choose a budget or forecast to create a controlled new version." />}
          </article>
        </>
      ) : null}

      <article className="panel panel-wide planning-disclaimer">
        <strong>Internal planning support only.</strong>
        <p>Budget and forecast values are estimates, do not modify the accounting ledger, and should be reviewed before operational or financial decisions are made.</p>
      </article>
    </section>
  );
}
