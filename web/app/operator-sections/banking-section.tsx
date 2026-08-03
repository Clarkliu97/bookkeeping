import { useEffect, useMemo, useState } from "react";

import { formatDateTime, formatMoney, type OperatorState } from "../operator-state";
import { EmptyState, Field, StatusPill, WorkspaceTabs } from "../operator-ui";


function toDecimalNumber(value: string | number | null | undefined) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}


function bankRowSignedAmount(row: { debit_amount: string; credit_amount: string } | null | undefined) {
  if (!row) {
    return 0;
  }
  const debit = toDecimalNumber(row.debit_amount);
  const credit = toDecimalNumber(row.credit_amount);
  if (credit > 0) {
    return credit;
  }
  if (debit > 0) {
    return -debit;
  }
  return 0;
}


function bankRowAmountLabel(row: { debit_amount: string; credit_amount: string } | null | undefined) {
  if (!row) {
    return "No amount";
  }
  const credit = toDecimalNumber(row.credit_amount);
  if (credit > 0) {
    return `Credit ${formatMoney(row.credit_amount)}`;
  }
  const debit = toDecimalNumber(row.debit_amount);
  if (debit > 0) {
    return `Debit ${formatMoney(row.debit_amount)}`;
  }
  return formatMoney("0");
}


function journalTotals(journal: { lines: Array<{ debit_amount: string; credit_amount: string }> }) {
  return journal.lines.reduce(
    (totals, line) => ({
      debit: totals.debit + toDecimalNumber(line.debit_amount),
      credit: totals.credit + toDecimalNumber(line.credit_amount),
    }),
    { debit: 0, credit: 0 },
  );
}


function journalCashImpact(
  journal: { lines: Array<{ account_id: string; debit_amount: string; credit_amount: string }> },
  ledgerAccountId: string | null | undefined,
) {
  if (!ledgerAccountId) {
    return 0;
  }
  return journal.lines.reduce(
    (total, line) => line.account_id === ledgerAccountId
      ? total + toDecimalNumber(line.debit_amount) - toDecimalNumber(line.credit_amount)
      : total,
    0,
  );
}


type ReconciliationMatchGroup = {
  id: string;
  bank_total: string;
  journal_total: string;
  difference_amount: string;
  tolerance_amount: string;
  note: string | null;
  resolved_at: string;
  bank_allocations: Array<{
    id: string;
    reconciliation_item_id: string;
    source_amount: string;
    allocated_amount: string;
    bank_row: { description: string; line_number: number };
  }>;
  journal_allocations: Array<{
    id: string;
    journal_entry_id: string;
    ledger_account_id: string;
    source_amount: string;
    allocated_amount: string;
    journal_entry: { entry_number: string; description: string };
  }>;
};


type AutoReconciliationResult = {
  considered_statement_items: number;
  matched_statement_items: number;
  created_group_count: number;
  unmatched_statement_item_ids: string[];
  ambiguous_statement_item_ids: string[];
  amount_tolerance: string;
  date_window_days: number;
  max_group_size: number;
  groups: ReconciliationMatchGroup[];
};


function daysBetween(left: string, right: string) {
  const leftTime = Date.parse(left);
  const rightTime = Date.parse(right);
  if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
    return Number.MAX_SAFE_INTEGER;
  }
  return Math.abs(leftTime - rightTime);
}


function tokenizeMatchText(value: string) {
  return value
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length >= 3);
}


export function BankingSection({ operator }: { operator: OperatorState }) {
  const {
    bankAccounts,
    accounts,
    selectedBankAccountId,
    setSelectedBankAccountId,
    selectedBankAccount,
    bankAccountDraft,
    setBankAccountDraft,
    selectedCompanyId,
    request,
    runAction,
    showMessage,
    refreshAll,
    bankAccountOptionList,
    setReconciliationDraft,
    bankImportFile,
    setBankImportFile,
    bankImportDraft,
    setBankImportDraft,
    bankImports,
    selectedImportSessionId,
    setSelectedImportSessionId,
    selectedImportSession,
    importRows,
    reconciliationDraft,
    reconciliationSessions,
    selectedReconciliationSessionId,
    setSelectedReconciliationSessionId,
    selectedReconciliationSession,
    reconciliationUpdateDraft,
    setReconciliationUpdateDraft,
    periods,
    periodOptionList,
    reconciliationSummary,
    reconciliationItems,
    selectedReconciliationItemId,
    setSelectedReconciliationItemId,
    selectedReconciliationItem,
    reconciliationMatchJournalId,
    setReconciliationMatchJournalId,
    journals,
    basRunDetail,
    basGenerationDraft,
    setBasGenerationDraft,
    basPeriods,
    selectedBasPeriodId,
    setSelectedBasPeriodId,
    selectedBasPeriod,
    basPeriodNote,
    setBasPeriodNote,
    setSelectedBasRunId,
    basAdjustmentDraft,
    setBasAdjustmentDraft,
    basReviewNoteDraft,
    setBasReviewNoteDraft,
    basActionNote,
    setBasActionNote,
    loadBasRun,
    downloadFromApi,
    confirmDanger,
  } = operator;
  const [importNoteDraft, setImportNoteDraft] = useState("");
  const [reconciliationItemNote, setReconciliationItemNote] = useState("");
  const [isReconciliationWorkspaceOpen, setIsReconciliationWorkspaceOpen] = useState(false);
  const [activeWorkspace, setActiveWorkspace] = useState<"accounts" | "reconciliation" | "bas">("accounts");
  const [newBankAccountDraft, setNewBankAccountDraft] = useState({
    name: "",
    bank_name: "",
    bsb: "",
    account_number_masked: "",
    ledger_account_id: "",
    is_active: true,
  });
  const [reconciliationMatchGroups, setReconciliationMatchGroups] = useState<ReconciliationMatchGroup[]>([]);
  const [selectedGroupBankItemIds, setSelectedGroupBankItemIds] = useState<string[]>([]);
  const [selectedGroupJournalIds, setSelectedGroupJournalIds] = useState<string[]>([]);
  const [bankAllocationDrafts, setBankAllocationDrafts] = useState<Record<string, string>>({});
  const [journalAllocationDrafts, setJournalAllocationDrafts] = useState<Record<string, string>>({});
  const [groupTolerance, setGroupTolerance] = useState("0.00");
  const [groupNote, setGroupNote] = useState("");
  const [autoReconciliationDraft, setAutoReconciliationDraft] = useState({
    amount_tolerance: "0.01",
    date_window_days: "3",
    max_group_size: "3",
  });
  const [autoReconciliationResult, setAutoReconciliationResult] = useState<AutoReconciliationResult | null>(null);

  const activeBankAccounts = useMemo(
    () => bankAccounts.filter((item) => item.is_active),
    [bankAccounts],
  );

  const ledgerAccountOptions = useMemo(
    () => accounts
      .filter((account) => account.is_active && ["asset", "liability"].includes(account.account_type))
      .sort((left, right) => left.account_code.localeCompare(right.account_code)),
    [accounts],
  );

  useEffect(() => {
    setImportNoteDraft(selectedImportSession?.note ?? "");
  }, [selectedImportSession?.id, selectedImportSession?.note]);

  useEffect(() => {
    setNewBankAccountDraft({
      name: "",
      bank_name: "",
      bsb: "",
      account_number_masked: "",
      ledger_account_id: "",
      is_active: true,
    });
  }, [selectedCompanyId]);

  useEffect(() => {
    setSelectedGroupBankItemIds([]);
    setSelectedGroupJournalIds([]);
    setBankAllocationDrafts({});
    setJournalAllocationDrafts({});
    setGroupTolerance("0.00");
    setGroupNote("");
    setAutoReconciliationResult(null);
    if (!selectedCompanyId || !selectedReconciliationSessionId) {
      setReconciliationMatchGroups([]);
      return;
    }
    void request<ReconciliationMatchGroup[]>(
      `/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/match-groups`,
    ).then(setReconciliationMatchGroups).catch(() => {
      setReconciliationMatchGroups([]);
      showMessage("error", "Could not load grouped reconciliation history.");
    });
    // The request helper is intentionally excluded: session identity is the reload boundary.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCompanyId, selectedReconciliationSessionId]);

  useEffect(() => {
    setReconciliationItemNote(selectedReconciliationItem?.note ?? "");
    setReconciliationMatchJournalId(selectedReconciliationItem?.matched_journal_entry_id ?? "");
  }, [selectedReconciliationItem?.id, selectedReconciliationItem?.matched_journal_entry_id, selectedReconciliationItem?.note, setReconciliationMatchJournalId]);

  useEffect(() => {
    if (!isReconciliationWorkspaceOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsReconciliationWorkspaceOpen(false);
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isReconciliationWorkspaceOpen]);

  const reconciliationSessionBankName = useMemo(
    () => bankAccounts.find((item) => item.id === selectedReconciliationSession?.bank_account_id)?.name ?? "No bank account",
    [bankAccounts, selectedReconciliationSession?.bank_account_id],
  );

  const reconciliationSessionPeriodLabel = useMemo(
    () => periodOptionList.find((item) => item.value === selectedReconciliationSession?.accounting_period_id)?.label ?? "No period linked",
    [periodOptionList, selectedReconciliationSession?.accounting_period_id],
  );

  const reconciliationSessionBankAccount = useMemo(
    () => bankAccounts.find((item) => item.id === selectedReconciliationSession?.bank_account_id) ?? null,
    [bankAccounts, selectedReconciliationSession?.bank_account_id],
  );

  const reconciliationLedgerAccount = useMemo(
    () => accounts.find((item) => item.id === reconciliationSessionBankAccount?.ledger_account_id) ?? null,
    [accounts, reconciliationSessionBankAccount?.ledger_account_id],
  );

  const selectedReconciliationPeriod = useMemo(
    () => periods.find((period) => period.id === selectedReconciliationSession?.accounting_period_id) ?? null,
    [periods, selectedReconciliationSession?.accounting_period_id],
  );

  const eligibleReconciliationJournals = useMemo(
    () => journals.filter((journal) => (
      journal.status === "posted"
      && (
        !selectedReconciliationPeriod
        || (
          journal.accounting_period_id === selectedReconciliationPeriod.id
          && journal.entry_date >= selectedReconciliationPeriod.start_date
          && journal.entry_date <= selectedReconciliationPeriod.end_date
        )
      )
    )),
    [journals, selectedReconciliationPeriod],
  );

  const orderedReconciliationItems = useMemo(() => {
    const statusWeight: Record<string, number> = { matched: 0, unmatched: 1, ignored: 2 };
    return [...reconciliationItems].sort((left, right) => {
      const weightDelta = (statusWeight[left.status] ?? 99) - (statusWeight[right.status] ?? 99);
      if (weightDelta !== 0) {
        return weightDelta;
      }
      return daysBetween(left.bank_row?.transaction_date ?? "", right.bank_row?.transaction_date ?? "");
    });
  }, [reconciliationItems]);

  const allocatedBankAmounts = useMemo(() => {
    const totals: Record<string, number> = {};
    reconciliationMatchGroups.forEach((group) => group.bank_allocations.forEach((allocation) => {
      totals[allocation.reconciliation_item_id] = (totals[allocation.reconciliation_item_id] ?? 0)
        + toDecimalNumber(allocation.allocated_amount);
    }));
    return totals;
  }, [reconciliationMatchGroups]);

  const allocatedJournalAmounts = useMemo(() => {
    const totals: Record<string, number> = {};
    reconciliationMatchGroups.forEach((group) => group.journal_allocations.forEach((allocation) => {
      if (allocation.ledger_account_id === reconciliationSessionBankAccount?.ledger_account_id) {
        totals[allocation.journal_entry_id] = (totals[allocation.journal_entry_id] ?? 0)
          + toDecimalNumber(allocation.allocated_amount);
      }
    }));
    return totals;
  }, [reconciliationMatchGroups, reconciliationSessionBankAccount?.ledger_account_id]);

  const selectedItemMatchGroups = useMemo(
    () => selectedReconciliationItem
      ? reconciliationMatchGroups.filter((group) => group.bank_allocations.some(
        (allocation) => allocation.reconciliation_item_id === selectedReconciliationItem.id,
      ))
      : [],
    [reconciliationMatchGroups, selectedReconciliationItem],
  );

  const selectedItemAllocatedAmount = selectedReconciliationItem
    ? (allocatedBankAmounts[selectedReconciliationItem.id] ?? 0)
    : 0;
  const selectedItemSourceAmount = selectedReconciliationItem?.bank_row
    ? bankRowSignedAmount(selectedReconciliationItem.bank_row)
    : 0;
  const selectedItemRemainingAmount = selectedItemSourceAmount - selectedItemAllocatedAmount;

  const selectedCandidateJournal = useMemo(
    () => eligibleReconciliationJournals.find((item) => item.id === reconciliationMatchJournalId) ?? null,
    [eligibleReconciliationJournals, reconciliationMatchJournalId],
  );

  const candidateJournals = useMemo(() => {
    if (!selectedReconciliationItem?.bank_row) {
      return [];
    }
    const targetAmount = Math.abs(bankRowSignedAmount(selectedReconciliationItem.bank_row));
    const searchTokens = tokenizeMatchText(`${selectedReconciliationItem.bank_row.description} ${selectedReconciliationItem.bank_row.reference ?? ""}`);
    return eligibleReconciliationJournals
      .map((journal) => {
        const totals = journalTotals(journal);
        const cashImpact = journalCashImpact(journal, reconciliationSessionBankAccount?.ledger_account_id);
        const journalLabelText = `${journal.entry_number} ${journal.description} ${journal.reference ?? ""}`.toLowerCase();
        const tokenHits = searchTokens.reduce((sum, token) => sum + (journalLabelText.includes(token) ? 1 : 0), 0);
        const amountGap = Math.abs(Math.abs(cashImpact) - targetAmount);
        const dateGap = daysBetween(journal.entry_date, selectedReconciliationItem.bank_row?.transaction_date ?? "");
        return { journal, totals, cashImpact, tokenHits, amountGap, dateGap };
      })
      .sort((left, right) => {
        const leftIsActive = left.journal.id === reconciliationMatchJournalId || left.journal.id === selectedReconciliationItem.matched_journal_entry_id;
        const rightIsActive = right.journal.id === reconciliationMatchJournalId || right.journal.id === selectedReconciliationItem.matched_journal_entry_id;
        if (leftIsActive !== rightIsActive) {
          return leftIsActive ? -1 : 1;
        }
        return left.amountGap - right.amountGap || right.tokenHits - left.tokenHits || left.dateGap - right.dateGap;
      })
      .slice(0, 24);
  }, [eligibleReconciliationJournals, reconciliationMatchJournalId, reconciliationSessionBankAccount?.ledger_account_id, selectedReconciliationItem]);

  const selectedGroupBankTotal = selectedGroupBankItemIds.reduce(
    (total, itemId) => total + toDecimalNumber(bankAllocationDrafts[itemId]),
    0,
  );
  const selectedGroupJournalTotal = selectedGroupJournalIds.reduce(
    (total, journalId) => total + toDecimalNumber(journalAllocationDrafts[journalId]),
    0,
  );
  const selectedGroupDifference = selectedGroupBankTotal - selectedGroupJournalTotal;

  const activeComparisonJournal = selectedCandidateJournal ?? null;
  const selectedMatchedJournalSummary = selectedReconciliationItem?.matched_journal_entry ?? null;

  async function loadReconciliationMatchGroups() {
    if (!selectedCompanyId || !selectedReconciliationSessionId) {
      setReconciliationMatchGroups([]);
      return;
    }
    setReconciliationMatchGroups(await request<ReconciliationMatchGroup[]>(
      `/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/match-groups`,
    ));
  }

  function toggleGroupBankItem(itemId: string) {
    const item = reconciliationItems.find((candidate) => candidate.id === itemId);
    if (!item?.bank_row) {
      return;
    }
    const isSelected = selectedGroupBankItemIds.includes(itemId);
    setSelectedGroupBankItemIds((current) => isSelected
      ? current.filter((id) => id !== itemId)
      : [...current, itemId]);
    setBankAllocationDrafts((current) => {
      if (isSelected) {
        const next = { ...current };
        delete next[itemId];
        return next;
      }
      const remaining = bankRowSignedAmount(item.bank_row) - (allocatedBankAmounts[itemId] ?? 0);
      return { ...current, [itemId]: remaining.toFixed(2) };
    });
  }

  function toggleGroupJournal(journalId: string) {
    const journal = eligibleReconciliationJournals.find((candidate) => candidate.id === journalId);
    if (!journal) {
      return;
    }
    const isSelected = selectedGroupJournalIds.includes(journalId);
    setSelectedGroupJournalIds((current) => isSelected
      ? current.filter((id) => id !== journalId)
      : [...current, journalId]);
    setJournalAllocationDrafts((current) => {
      if (isSelected) {
        const next = { ...current };
        delete next[journalId];
        return next;
      }
      const remaining = journalCashImpact(
        journal,
        reconciliationSessionBankAccount?.ledger_account_id,
      ) - (allocatedJournalAmounts[journalId] ?? 0);
      return { ...current, [journalId]: remaining.toFixed(2) };
    });
  }

  function clearGroupDraft() {
    setSelectedGroupBankItemIds([]);
    setSelectedGroupJournalIds([]);
    setBankAllocationDrafts({});
    setJournalAllocationDrafts({});
    setGroupTolerance("0.00");
    setGroupNote("");
  }

  async function createGroupedMatch() {
    if (!reconciliationSessionBankAccount?.ledger_account_id) {
      throw new Error("Link this bank account to its ledger cash account before grouping matches.");
    }
    if (selectedGroupBankItemIds.length === 0 || selectedGroupJournalIds.length === 0) {
      throw new Error("Select at least one statement item and one journal.");
    }
    await request(
      `/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/match-groups`,
      "POST",
      {
        bank_allocations: selectedGroupBankItemIds.map((itemId) => ({
          reconciliation_item_id: itemId,
          allocated_amount: bankAllocationDrafts[itemId],
        })),
        journal_allocations: selectedGroupJournalIds.map((journalId) => ({
          journal_entry_id: journalId,
          allocated_amount: journalAllocationDrafts[journalId],
        })),
        tolerance_amount: groupTolerance || "0.00",
        note: groupNote.trim() || null,
      },
    );
    clearGroupDraft();
    await refreshAll();
    await loadReconciliationMatchGroups();
    showMessage("success", "Created grouped reconciliation match.");
  }

  async function autoReconcile() {
    if (!reconciliationSessionBankAccount?.ledger_account_id) {
      throw new Error("Link this bank account to its ledger cash account before auto-reconciling.");
    }
    const dateWindowDays = Number(autoReconciliationDraft.date_window_days);
    const maxGroupSize = Number(autoReconciliationDraft.max_group_size);
    const amountTolerance = Number(autoReconciliationDraft.amount_tolerance);
    if (!Number.isFinite(amountTolerance) || amountTolerance < 0 || amountTolerance > 10) {
      throw new Error("Amount tolerance must be between 0.00 and 10.00.");
    }
    if (!Number.isInteger(dateWindowDays) || dateWindowDays < 0 || dateWindowDays > 31) {
      throw new Error("Date window must be between 0 and 31 days.");
    }
    if (!Number.isInteger(maxGroupSize) || maxGroupSize < 1 || maxGroupSize > 4) {
      throw new Error("Maximum sources per side must be between 1 and 4.");
    }
    const result = await request<AutoReconciliationResult>(
      `/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/auto-reconcile`,
      "POST",
      {
        amount_tolerance: autoReconciliationDraft.amount_tolerance,
        date_window_days: dateWindowDays,
        max_group_size: maxGroupSize,
      },
    );
    setAutoReconciliationResult(result);
    clearGroupDraft();
    await refreshAll();
    await loadReconciliationMatchGroups();
    showMessage(
      "success",
      `Auto-reconciled ${result.matched_statement_items} of ${result.considered_statement_items} open statement items; ${result.unmatched_statement_item_ids.length} remain unmatched.`,
    );
  }

  async function deleteGroupedMatch(group: ReconciliationMatchGroup) {
    if (!confirmDanger(
      `Unmatch this group of ${group.bank_allocations.length} statement item(s) and ${group.journal_allocations.length} journal(s)?`,
    )) {
      return;
    }
    await request(
      `/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/match-groups/${group.id}`,
      "DELETE",
      undefined,
      "void",
    );
    await refreshAll();
    await loadReconciliationMatchGroups();
    showMessage("success", "Removed grouped reconciliation match.");
  }

  function openReconciliationWorkspace() {
    if (!selectedReconciliationItemId && orderedReconciliationItems[0]) {
      setSelectedReconciliationItemId(orderedReconciliationItems[0].id);
    }
    setIsReconciliationWorkspaceOpen(true);
  }

  async function matchSelectedReconciliationItem() {
    if (!selectedReconciliationItem) {
      throw new Error("Select a reconciliation item before matching.");
    }
    await request(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/items/${selectedReconciliationItem.id}/match`, "POST", { matched_journal_entry_id: reconciliationMatchJournalId, note: reconciliationItemNote || null });
    showMessage("success", "Matched reconciliation item.");
    await refreshAll();
    await loadReconciliationMatchGroups();
  }

  async function ignoreSelectedReconciliationItem() {
    if (!selectedReconciliationItem) {
      throw new Error("Select a reconciliation item before ignoring.");
    }
    await request(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/items/${selectedReconciliationItem.id}/ignore`, "POST", { note: reconciliationItemNote || null });
    showMessage("success", "Ignored reconciliation item.");
    await refreshAll();
  }

  async function deleteSelectedReconciliationSession() {
    if (!selectedReconciliationSession) {
      throw new Error("Select a reconciliation session before deleting.");
    }
    const sessionLabel = selectedReconciliationSession.note?.trim() || selectedReconciliationSession.id.slice(0, 8);
    if (!confirmDanger(
      `Delete reconciliation session "${sessionLabel}"? All bank rows included in this session will return to staged status. This cannot be undone.`,
    )) {
      return;
    }

    await request(
      `/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSession.id}`,
      "DELETE",
      undefined,
      "void",
    );
    setIsReconciliationWorkspaceOpen(false);
    setSelectedReconciliationSessionId("");
    setSelectedReconciliationItemId("");
    setReconciliationMatchJournalId("");
    await refreshAll();
    showMessage("success", `Deleted reconciliation session "${sessionLabel}".`);
  }

  async function createBankAccount() {
    const name = newBankAccountDraft.name.trim();
    if (!name) {
      throw new Error("Enter an account name before creating the bank account.");
    }
    const created = await request<{ id: string }>(
      `/api/companies/${selectedCompanyId}/bank-accounts`,
      "POST",
      { ...newBankAccountDraft, name, ledger_account_id: newBankAccountDraft.ledger_account_id || null },
    );
    setNewBankAccountDraft({
      name: "",
      bank_name: "",
      bsb: "",
      account_number_masked: "",
      ledger_account_id: "",
      is_active: true,
    });
    await refreshAll();
    setSelectedBankAccountId(created.id);
    setReconciliationDraft((current) => ({ ...current, bank_account_id: created.id }));
    showMessage("success", `Created bank account "${name}".`);
  }

  async function updateSelectedBankAccount() {
    if (!selectedBankAccount) {
      throw new Error("Select a bank account before updating it.");
    }
    const name = bankAccountDraft.name.trim();
    if (!name) {
      throw new Error("Enter an account name before updating the bank account.");
    }
    await request(
      `/api/companies/${selectedCompanyId}/bank-accounts/${selectedBankAccount.id}`,
      "PUT",
      { ...bankAccountDraft, name, ledger_account_id: bankAccountDraft.ledger_account_id || null },
    );
    await refreshAll();
    showMessage("success", `Updated bank account "${name}".`);
  }

  async function deleteSelectedBankAccount() {
    if (!selectedBankAccount) {
      throw new Error("Select a bank account before deleting it.");
    }
    const accountName = selectedBankAccount.name;
    if (!confirmDanger(
      `Delete bank account "${accountName}"? It will no longer be available for new imports or reconciliations. Historical banking records will be retained.`,
    )) {
      return;
    }
    await request(
      `/api/companies/${selectedCompanyId}/bank-accounts/${selectedBankAccount.id}`,
      "DELETE",
      undefined,
      "void",
    );
    setSelectedBankAccountId("");
    setBankAccountDraft({
      name: "",
      bank_name: "",
      bsb: "",
      account_number_masked: "",
      ledger_account_id: "",
      is_active: true,
    });
    setReconciliationDraft((current) => (
      current.bank_account_id === selectedBankAccount.id
        ? { ...current, bank_account_id: "" }
        : current
    ));
    await refreshAll();
    showMessage("success", `Deleted bank account "${accountName}". Historical banking records were retained.`);
  }

  return (
    <section className="sections-stack">
      <WorkspaceTabs
        label="Banking and BAS workspaces"
        activeTab={activeWorkspace}
        onChange={setActiveWorkspace}
        options={[
          { key: "accounts", label: "Accounts & imports", detail: "Bank accounts and CSV intake", count: bankImports.length },
          { key: "reconciliation", label: "Reconciliation", detail: "Match confirmed statement rows", count: reconciliationSessions.length },
          { key: "bas", label: "BAS support", detail: "Periods, review and exports", count: basPeriods.length },
        ]}
      />
      {activeWorkspace === "accounts" ? (
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Bank accounts and imports</h2><span className="pill">{activeBankAccounts.length} active accounts</span></div>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card" data-testid="create-bank-account-card">
              <div className="mini-card-heading">
                <div>
                  <h3>Create bank account</h3>
                  <p className="reference-management-copy">Add an account before importing its bank transactions.</p>
                </div>
              </div>
              <div className="form-grid two-up">
                <Field label="Name"><input value={newBankAccountDraft.name} onChange={(event) => setNewBankAccountDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                <Field label="Bank name"><input value={newBankAccountDraft.bank_name} onChange={(event) => setNewBankAccountDraft((current) => ({ ...current, bank_name: event.target.value }))} /></Field>
                <Field label="BSB"><input value={newBankAccountDraft.bsb} onChange={(event) => setNewBankAccountDraft((current) => ({ ...current, bsb: event.target.value }))} /></Field>
                <Field label="Masked account"><input value={newBankAccountDraft.account_number_masked} onChange={(event) => setNewBankAccountDraft((current) => ({ ...current, account_number_masked: event.target.value }))} /></Field>
                <Field label="Ledger cash account" wide><select data-testid="new-bank-ledger-account" value={newBankAccountDraft.ledger_account_id} onChange={(event) => setNewBankAccountDraft((current) => ({ ...current, ledger_account_id: event.target.value }))}><option value="">Not linked yet</option>{ledgerAccountOptions.map((account) => <option key={account.id} value={account.id}>{account.account_code} - {account.name}</option>)}</select></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" data-testid="create-bank-account" type="button" onClick={() => runAction("Creating bank account", createBankAccount)}>Create bank account</button>
              </div>
            </div>

            <div className="mini-card" data-testid="manage-bank-accounts-card">
              <div className="mini-card-heading">
                <div>
                  <h3>Manage bank accounts</h3>
                  <p className="reference-management-copy">Select an active account to update or delete it.</p>
                </div>
              </div>
              <div className="compact-list">
                {activeBankAccounts.map((item) => <button key={item.id} className={`list-row-button${selectedBankAccountId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedBankAccountId(item.id)}>{item.name}</button>)}
              </div>
              {selectedBankAccount ? (
                <>
                  <div className="form-grid two-up">
                    <Field label="Name"><input value={bankAccountDraft.name} onChange={(event) => setBankAccountDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                    <Field label="Bank name"><input value={bankAccountDraft.bank_name} onChange={(event) => setBankAccountDraft((current) => ({ ...current, bank_name: event.target.value }))} /></Field>
                    <Field label="BSB"><input value={bankAccountDraft.bsb} onChange={(event) => setBankAccountDraft((current) => ({ ...current, bsb: event.target.value }))} /></Field>
                    <Field label="Masked account"><input value={bankAccountDraft.account_number_masked} onChange={(event) => setBankAccountDraft((current) => ({ ...current, account_number_masked: event.target.value }))} /></Field>
                    <Field label="Ledger cash account" wide><select data-testid="bank-ledger-account" value={bankAccountDraft.ledger_account_id} onChange={(event) => setBankAccountDraft((current) => ({ ...current, ledger_account_id: event.target.value }))}><option value="">Not linked yet</option>{ledgerAccountOptions.map((account) => <option key={account.id} value={account.id}>{account.account_code} - {account.name}</option>)}</select></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" data-testid="update-bank-account" type="button" onClick={() => runAction("Updating bank account", updateSelectedBankAccount)}>Update bank account</button>
                    <button className="button-link button-link-small button-link-danger" data-testid="delete-bank-account" type="button" onClick={() => runAction("Deleting bank account", deleteSelectedBankAccount)}>Delete bank account</button>
                  </div>
                </>
              ) : (
                <EmptyState title="No bank account selected" detail={activeBankAccounts.length > 0 ? "Select an account above to manage it." : "Create the first bank account above."} />
              )}
            </div>

            <div className="mini-card">
              <h3>Upload bank CSV</h3>
              <div className="form-grid">
                <Field label="Bank account"><select value={selectedBankAccountId} onChange={(event) => { setSelectedBankAccountId(event.target.value); setReconciliationDraft((current) => ({ ...current, bank_account_id: event.target.value })); }}><option value="">Select bank account</option>{bankAccountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="CSV file"><input type="file" accept=".csv,text/csv" onChange={(event) => setBankImportFile(event.target.files?.[0] ?? null)} /></Field>
                <Field label="Import note"><input value={bankImportDraft.note} onChange={(event) => setBankImportDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Uploading bank import", async () => {
                  if (!selectedBankAccountId) {
                    throw new Error("Select a bank account before uploading.");
                  }
                  if (!bankImportFile) {
                    throw new Error("Choose a CSV file before uploading.");
                  }
                  const formData = new FormData();
                  formData.append("bank_account_id", selectedBankAccountId);
                  formData.append("file", bankImportFile);
                  formData.append("note", bankImportDraft.note);
                  formData.append("date_column", bankImportDraft.date_column);
                  formData.append("description_column", bankImportDraft.description_column);
                  formData.append("debit_column", bankImportDraft.debit_column);
                  formData.append("credit_column", bankImportDraft.credit_column);
                  formData.append("reference_column", bankImportDraft.reference_column);
                  await request(`/api/companies/${selectedCompanyId}/bank-imports/upload`, "POST", formData);
                  showMessage("success", "Uploaded bank import session.");
                  await refreshAll();
                })}>Upload CSV</button>
              </div>
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Import sessions</h3>
              <div className="compact-list tall-list">
                {bankImports.map((item) => <button key={item.id} className={`list-row-button${selectedImportSessionId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedImportSessionId(item.id)}>{item.original_filename} · {item.status}</button>)}
              </div>
              {selectedImportSession ? (
                <div>
                  <div className="form-grid two-up">
                    <Field label="Imported"><input value={formatDateTime(selectedImportSession.imported_at)} readOnly /></Field>
                    <Field label="Status"><input value={selectedImportSession.status} readOnly /></Field>
                    <Field label="Session note" wide><input value={importNoteDraft} onChange={(event) => setImportNoteDraft(event.target.value)} /></Field>
                  </div>
                  <div className="request-actions">
                    {selectedImportSession.status === "staged" ? (
                      <button className="button-link button-link-small" type="button" onClick={() => runAction("Updating import note", async () => {
                        await request(`/api/companies/${selectedCompanyId}/bank-imports/${selectedImportSession.id}`, "PUT", { note: importNoteDraft || null });
                        showMessage("success", "Updated import note.");
                        await refreshAll();
                      })}>Save note</button>
                    ) : null}
                    {selectedImportSession.status === "staged" ? (
                      <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Deleting import session", async () => {
                        await request(`/api/companies/${selectedCompanyId}/bank-imports/${selectedImportSession.id}`, "DELETE");
                        setSelectedImportSessionId("");
                        showMessage("success", "Deleted bank import session.");
                        await refreshAll();
                      })}>Delete</button>
                    ) : null}
                    {selectedImportSession.status === "staged" ? (
                      <button className="button-link button-link-small" type="button" onClick={() => runAction("Confirming import", async () => {
                        await request(`/api/companies/${selectedCompanyId}/bank-imports/${selectedImportSession.id}/confirm`, "POST", { note: "Confirmed for reconciliation" });
                        showMessage("success", "Confirmed bank import.");
                        await refreshAll();
                      })}>Confirm</button>
                    ) : null}
                  </div>
                </div>
              ) : null}
              <div className="table-shell compact-table-shell">
                <table className="data-table">
                  <thead><tr><th>Line</th><th>Description</th><th>Status</th></tr></thead>
                  <tbody>
                    {importRows.map((item) => <tr key={item.id}><td>{item.line_number}</td><td>{item.description}</td><td><StatusPill value={item.status} /></td></tr>)}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </article>
      ) : null}

      {activeWorkspace === "reconciliation" ? (
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Reconciliation</h2><span className="pill">{reconciliationSessions.length} sessions</span></div>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Create session</h3>
              <div className="form-grid two-up">
                <Field label="Bank account"><select value={reconciliationDraft.bank_account_id} onChange={(event) => setReconciliationDraft((current) => ({ ...current, bank_account_id: event.target.value }))}><option value="">Select bank account</option>{bankAccountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Accounting period"><select value={reconciliationDraft.accounting_period_id} onChange={(event) => setReconciliationDraft((current) => ({ ...current, accounting_period_id: event.target.value }))}><option value="">Optional</option>{periodOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Note" wide><input value={reconciliationDraft.note} onChange={(event) => setReconciliationDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Creating reconciliation", async () => {
                  await request(`/api/companies/${selectedCompanyId}/reconciliation-sessions`, "POST", { ...reconciliationDraft, accounting_period_id: reconciliationDraft.accounting_period_id || null, note: reconciliationDraft.note || null });
                  showMessage("success", "Created reconciliation session.");
                  await refreshAll();
                })}>Create session</button>
              </div>
            </div>

            <div className="mini-card">
              <h3>Sessions</h3>
              <div className="compact-list tall-list">
                {reconciliationSessions.map((item) => <button key={item.id} className={`list-row-button${selectedReconciliationSessionId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedReconciliationSessionId(item.id)}>{item.note || item.id} · {item.status}</button>)}
              </div>
              {selectedReconciliationSession ? (
                <div>
                  <div className="stats-grid mini-stats-grid">
                    <div className="stat-card"><span>Bank account</span><strong>{reconciliationSessionBankName}</strong></div>
                    <div className="stat-card"><span>Period</span><strong>{reconciliationSessionPeriodLabel}</strong></div>
                    <div className="stat-card"><span>Status</span><strong>{selectedReconciliationSession.status}</strong></div>
                    <div className="stat-card"><span>Completed</span><strong>{selectedReconciliationSession.completed_at ? formatDateTime(selectedReconciliationSession.completed_at) : "Open"}</strong></div>
                  </div>
                  {reconciliationSummary ? (
                    <div className="stats-grid mini-stats-grid">
                      <div className="stat-card"><span>Total items</span><strong>{reconciliationSummary.total_items}</strong></div>
                      <div className="stat-card"><span>Ready to action</span><strong>{reconciliationSummary.unmatched_items}</strong></div>
                      <div className="stat-card"><span>Matched</span><strong>{reconciliationSummary.matched_items}</strong></div>
                      <div className="stat-card"><span>Ignored</span><strong>{reconciliationSummary.ignored_items}</strong></div>
                    </div>
                  ) : null}
                  <div className="form-grid">
                    <Field label="Session note"><input value={reconciliationUpdateDraft.note} readOnly={selectedReconciliationSession.status === "completed"} onChange={(event) => setReconciliationUpdateDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
                  {selectedReconciliationSession.status !== "completed" ? (
                    <div className="request-actions">
                      <button className="button-link button-link-small" type="button" onClick={() => runAction("Updating reconciliation", async () => {
                        await request(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSession.id}`, "PUT", { accounting_period_id: reconciliationUpdateDraft.accounting_period_id || null, note: reconciliationUpdateDraft.note || null });
                        showMessage("success", "Updated reconciliation session.");
                        await refreshAll();
                      })}>Save session</button>
                      <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Completing reconciliation", async () => {
                        await request(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSession.id}/complete`, "POST", { note: reconciliationUpdateDraft.note || null });
                        showMessage("success", "Completed reconciliation session.");
                        await refreshAll();
                      })}>Complete</button>
                      <button className="button-link button-link-small button-link-danger" data-testid="delete-reconciliation-session" type="button" onClick={() => runAction("Deleting reconciliation session", deleteSelectedReconciliationSession)}>Delete session</button>
                    </div>
                  ) : (
                    <p className="summary-line">Completed reconciliation sessions are retained for audit history and cannot be changed or deleted.</p>
                  )}
                </div>
              ) : null}
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card">
              <div className="mini-card-heading">
                <h3>Left-to-right matching</h3>
                <span className="pill">{orderedReconciliationItems.length} items</span>
              </div>
              {selectedReconciliationSession ? (
                <>
                  <p className="summary-line reconciliation-guidance">Open the matching window to compare statement rows beside posted journals with enough room for review notes and resolution actions.</p>
                  <div className="reconciliation-launch-panel">
                    <div className="stats-grid mini-stats-grid">
                      <div className="stat-card"><span>Open</span><strong>{reconciliationSummary?.unmatched_items ?? 0}</strong></div>
                      <div className="stat-card"><span>Matched</span><strong>{reconciliationSummary?.matched_items ?? 0}</strong></div>
                    </div>
                    <div className="request-actions">
                      <button className="button-link button-link-small" type="button" onClick={openReconciliationWorkspace}>Open matching window</button>
                    </div>
                    {selectedReconciliationItem ? (
                      <div className="reconciliation-selected-summary">
                        <span>Selected item</span>
                        <strong>{selectedReconciliationItem.bank_row?.description ?? `Bank row ${selectedReconciliationItem.bank_import_row_id.slice(0, 8)}`}</strong>
                        <p>{selectedReconciliationItem.bank_row?.transaction_date ?? "No date"} - {bankRowAmountLabel(selectedReconciliationItem.bank_row)}</p>
                      </div>
                    ) : null}
                  </div>
                  {isReconciliationWorkspaceOpen ? (
                    <div className="journal-popup-backdrop" role="presentation" onClick={() => setIsReconciliationWorkspaceOpen(false)}>
                      <div className="journal-popup-card reconciliation-popup-card" role="dialog" aria-modal="true" aria-label="Left-to-right reconciliation matching" onClick={(event) => event.stopPropagation()}>
                        <div className="journal-popup-header">
                          <div>
                            <h3>Reconciliation matching</h3>
                            <p className="summary-line">Match one or many statement items to one or many posted journals{selectedReconciliationPeriod ? ` within ${reconciliationSessionPeriodLabel}` : ""}. Allocations may be partial and remain open until the full statement amount is allocated.</p>
                          </div>
                          <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => setIsReconciliationWorkspaceOpen(false)}>Close</button>
                        </div>
                        <details className="reconciliation-group-composer" open>
                          <summary>
                            <strong>Grouped match</strong>
                            <span>{selectedGroupBankItemIds.length} statement / {selectedGroupJournalIds.length} journal selected</span>
                          </summary>
                          <div className="reconciliation-group-composer-body">
                            <div className="reconciliation-group-summary">
                              <span>Ledger link <strong>{reconciliationLedgerAccount ? `${reconciliationLedgerAccount.account_code} - ${reconciliationLedgerAccount.name}` : "Required"}</strong></span>
                              <span>Statement <strong>{formatMoney(selectedGroupBankTotal)}</strong></span>
                              <span>Ledger movement <strong>{formatMoney(selectedGroupJournalTotal)}</strong></span>
                              <span>Difference <strong>{formatMoney(selectedGroupDifference)}</strong></span>
                            </div>
                            {!reconciliationLedgerAccount ? <p className="validation-hint">Link the selected bank account to its asset or liability ledger account in Accounts &amp; imports before creating grouped matches.</p> : null}
                            <section className="reconciliation-auto-panel">
                              <div className="mini-card-heading">
                                <div>
                                  <h4>Auto reconcile open items</h4>
                                  <p className="summary-line">Searches signed statement amounts against posted movement on the linked ledger account. It tries 1-to-1 and grouped combinations, uses journal line amounts as a tie-breaker, and leaves missing or equally ranked matches open.</p>
                                </div>
                                <span className="pill">Conservative</span>
                              </div>
                              <div className="reconciliation-auto-controls">
                                <Field label="Amount tolerance"><input type="number" min="0" max="10" step="0.01" value={autoReconciliationDraft.amount_tolerance} onChange={(event) => setAutoReconciliationDraft((current) => ({ ...current, amount_tolerance: event.target.value }))} /></Field>
                                <Field label="Date window (days)"><input type="number" min="0" max="31" step="1" value={autoReconciliationDraft.date_window_days} onChange={(event) => setAutoReconciliationDraft((current) => ({ ...current, date_window_days: event.target.value }))} /></Field>
                                <Field label="Maximum sources per side"><select value={autoReconciliationDraft.max_group_size} onChange={(event) => setAutoReconciliationDraft((current) => ({ ...current, max_group_size: event.target.value }))}><option value="1">1 (one-to-one only)</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select></Field>
                                <button className="button-link button-link-small" data-testid="auto-reconcile" type="button" disabled={!reconciliationLedgerAccount || selectedReconciliationSession?.status === "completed" || (reconciliationSummary?.unmatched_items ?? 0) === 0} onClick={() => runAction("Auto-reconciling statement items", autoReconcile)}>Run auto reconcile</button>
                              </div>
                              {autoReconciliationResult ? (
                                <div className="reconciliation-auto-result" data-testid="auto-reconcile-result">
                                  <span>Considered <strong>{autoReconciliationResult.considered_statement_items}</strong></span>
                                  <span>Matched <strong>{autoReconciliationResult.matched_statement_items}</strong></span>
                                  <span>Groups <strong>{autoReconciliationResult.created_group_count}</strong></span>
                                  <span>Left open <strong>{autoReconciliationResult.unmatched_statement_item_ids.length}</strong></span>
                                  {autoReconciliationResult.ambiguous_statement_item_ids.length > 0 ? <p>{autoReconciliationResult.ambiguous_statement_item_ids.length} item(s) had equally ranked candidates and were deliberately left unmatched.</p> : null}
                                </div>
                              ) : null}
                            </section>
                            {(selectedGroupBankItemIds.length > 0 || selectedGroupJournalIds.length > 0) ? (
                              <div className="reconciliation-allocation-editor">
                                <div>
                                  <h4>Statement allocations</h4>
                                  {selectedGroupBankItemIds.map((itemId) => {
                                    const item = reconciliationItems.find((candidate) => candidate.id === itemId);
                                    return <Field key={itemId} label={item?.bank_row?.description ?? itemId}><input aria-label={`Statement allocation ${item?.bank_row?.description ?? itemId}`} type="number" step="0.01" value={bankAllocationDrafts[itemId] ?? ""} onChange={(event) => setBankAllocationDrafts((current) => ({ ...current, [itemId]: event.target.value }))} /></Field>;
                                  })}
                                </div>
                                <div>
                                  <h4>Journal allocations</h4>
                                  {selectedGroupJournalIds.map((journalId) => {
                                    const journal = eligibleReconciliationJournals.find((candidate) => candidate.id === journalId);
                                    return <Field key={journalId} label={journal ? `${journal.entry_number} - ${journal.description}` : journalId}><input aria-label={`Journal allocation ${journal?.entry_number ?? journalId}`} type="number" step="0.01" value={journalAllocationDrafts[journalId] ?? ""} onChange={(event) => setJournalAllocationDrafts((current) => ({ ...current, [journalId]: event.target.value }))} /></Field>;
                                  })}
                                </div>
                              </div>
                            ) : <p className="summary-line">Use the checkboxes in the left and right lanes to build an n-to-1, 1-to-n, or n-to-n match.</p>}
                            <div className="reconciliation-group-actions">
                              <Field label="Tolerance"><input type="number" min="0" step="0.01" value={groupTolerance} onChange={(event) => setGroupTolerance(event.target.value)} /></Field>
                              <Field label="Note"><input value={groupNote} placeholder="Required for a non-zero difference" onChange={(event) => setGroupNote(event.target.value)} /></Field>
                              <button className="button-link button-link-small" data-testid="create-grouped-match" type="button" disabled={!reconciliationLedgerAccount || selectedGroupBankItemIds.length === 0 || selectedGroupJournalIds.length === 0 || selectedReconciliationSession?.status === "completed"} onClick={() => runAction("Creating grouped reconciliation", createGroupedMatch)}>Create grouped match</button>
                              <button className="button-link button-link-small button-link-secondary" type="button" disabled={selectedGroupBankItemIds.length === 0 && selectedGroupJournalIds.length === 0} onClick={clearGroupDraft}>Clear selection</button>
                            </div>
                            {reconciliationMatchGroups.length > 0 ? (
                              <details className="reconciliation-group-history" open>
                                <summary>{reconciliationMatchGroups.length} saved match group(s)</summary>
                                <div className="compact-list">
                                  {reconciliationMatchGroups.map((group) => (
                                    <div className="reconciliation-group-record" key={group.id}>
                                      <div><strong>{group.bank_allocations.length} statement ↔ {group.journal_allocations.length} journal</strong><span>{formatMoney(group.bank_total)} / {formatMoney(group.journal_total)} · difference {formatMoney(group.difference_amount)}</span><span>{group.note || "No note"} · {formatDateTime(group.resolved_at)}</span></div>
                                      {selectedReconciliationSession?.status !== "completed" ? <button className="button-link button-link-small button-link-danger" type="button" onClick={() => runAction("Removing grouped reconciliation", async () => deleteGroupedMatch(group))}>Unmatch</button> : null}
                                    </div>
                                  ))}
                                </div>
                              </details>
                            ) : null}
                          </div>
                        </details>
                  <div className="reconciliation-popup-grid">
                    <div className="mini-card reconciliation-lane-card reconciliation-statement-panel">
                      <div className="mini-card-heading">
                        <h4>Statement items</h4>
                        <span className="pill">{reconciliationSummary?.unmatched_items ?? 0} open</span>
                      </div>
                      <div className="compact-list tall-list reconciliation-item-list">
                        {orderedReconciliationItems.map((item) => (
                          <div className="reconciliation-selectable-row" key={item.id}>
                            <label className="reconciliation-group-checkbox" title="Include this statement item in the grouped match">
                              <input type="checkbox" aria-label={`Group statement item ${item.bank_row?.description ?? item.id}`} checked={selectedGroupBankItemIds.includes(item.id)} disabled={item.status !== "unmatched" || Math.abs(bankRowSignedAmount(item.bank_row) - (allocatedBankAmounts[item.id] ?? 0)) < 0.005} onChange={() => toggleGroupBankItem(item.id)} />
                            </label>
                            <button className={`reconciliation-item-button${selectedReconciliationItemId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedReconciliationItemId(item.id)}>
                              <div className="reconciliation-item-button-top">
                                <strong>{item.bank_row?.description ?? `Bank row ${item.bank_import_row_id.slice(0, 8)}`}</strong>
                                <StatusPill value={item.status} />
                              </div>
                              <div className="reconciliation-item-button-meta">
                                <span>{item.bank_row?.transaction_date ?? "No date"}</span>
                                <span className="reconciliation-amount">{bankRowAmountLabel(item.bank_row)}</span>
                              </div>
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="mini-card reconciliation-lane-card reconciliation-comparison-panel">
                      <div className="mini-card-heading">
                        <h4>Comparison and resolution</h4>
                        {selectedReconciliationItem ? <StatusPill value={selectedReconciliationItem.status} /> : null}
                      </div>
                      {selectedReconciliationItem ? (
                        <div className="reconciliation-comparison-scroll">
                          <div className="reconciliation-detail-grid">
                            <section className="reconciliation-detail-card">
                              <h4>Statement side</h4>
                              <div className="reconciliation-detail-list">
                                <div><span>Date</span><strong>{selectedReconciliationItem.bank_row?.transaction_date ?? "-"}</strong></div>
                                <div><span>Description</span><strong>{selectedReconciliationItem.bank_row?.description ?? "-"}</strong></div>
                                <div><span>Reference</span><strong>{selectedReconciliationItem.bank_row?.reference || "-"}</strong></div>
                                <div><span>Line</span><strong>{selectedReconciliationItem.bank_row?.line_number ?? "-"}</strong></div>
                                <div><span>Amount</span><strong>{bankRowAmountLabel(selectedReconciliationItem.bank_row)}</strong></div>
                                <div><span>Allocated in groups</span><strong>{formatMoney(selectedItemAllocatedAmount)}</strong></div>
                                <div><span>Remaining</span><strong>{formatMoney(selectedItemRemainingAmount)}</strong></div>
                                <div><span>Match groups</span><strong>{selectedItemMatchGroups.length}</strong></div>
                                <div><span>Bank row status</span><strong>{selectedReconciliationItem.bank_row?.status ?? "-"}</strong></div>
                              </div>
                            </section>

                            <section className="reconciliation-detail-card">
                              <h4>Journal side</h4>
                              {activeComparisonJournal ? (
                                <div className="reconciliation-detail-list">
                                  <div><span>Entry</span><strong>{activeComparisonJournal.entry_number}</strong></div>
                                  <div><span>Entry date</span><strong>{activeComparisonJournal.entry_date}</strong></div>
                                  <div><span>Description</span><strong>{activeComparisonJournal.description}</strong></div>
                                  <div><span>Reference</span><strong>{activeComparisonJournal.reference || "-"}</strong></div>
                                  <div><span>Debit total</span><strong>{formatMoney(journalTotals(activeComparisonJournal).debit)}</strong></div>
                                  <div><span>Credit total</span><strong>{formatMoney(journalTotals(activeComparisonJournal).credit)}</strong></div>
                                </div>
                              ) : selectedMatchedJournalSummary ? (
                                <div className="reconciliation-detail-list">
                                  <div><span>Current match</span><strong>{selectedMatchedJournalSummary.entry_number}</strong></div>
                                  <div><span>Entry date</span><strong>{selectedMatchedJournalSummary.entry_date}</strong></div>
                                  <div><span>Description</span><strong>{selectedMatchedJournalSummary.description}</strong></div>
                                  <div><span>Reference</span><strong>{selectedMatchedJournalSummary.reference || "-"}</strong></div>
                                  <div><span>Debit total</span><strong>{formatMoney(selectedMatchedJournalSummary.debit_total)}</strong></div>
                                  <div><span>Credit total</span><strong>{formatMoney(selectedMatchedJournalSummary.credit_total)}</strong></div>
                                </div>
                              ) : selectedItemMatchGroups.length > 0 ? (
                                <div className="reconciliation-detail-list">
                                  <div><span>Current resolution</span><strong>Grouped allocation</strong></div>
                                  <div><span>Groups</span><strong>{selectedItemMatchGroups.length}</strong></div>
                                  <div><span>Related journals</span><strong>{new Set(selectedItemMatchGroups.flatMap((group) => group.journal_allocations.map((allocation) => allocation.journal_entry_id))).size}</strong></div>
                                  <div><span>Allocated</span><strong>{formatMoney(selectedItemAllocatedAmount)}</strong></div>
                                  <div><span>Remaining</span><strong>{formatMoney(selectedItemRemainingAmount)}</strong></div>
                                </div>
                              ) : (
                                <EmptyState title="No journal selected" detail="Pick a posted journal below to compare it against the selected statement row." />
                              )}
                            </section>
                          </div>

                          {selectedItemMatchGroups.length > 0 ? (
                            <section className="reconciliation-selected-groups" data-testid="selected-item-grouped-allocations">
                              <div className="mini-card-heading">
                                <div>
                                  <h4>Grouped allocations</h4>
                                  <p>Saved matches involving this statement row, including partial and many-sided allocations.</p>
                                </div>
                                <span className="pill">{selectedItemMatchGroups.length} {selectedItemMatchGroups.length === 1 ? "group" : "groups"}</span>
                              </div>
                              <div className="reconciliation-selected-group-list">
                                {selectedItemMatchGroups.map((group) => {
                                  const selectedAllocation = group.bank_allocations.find(
                                    (allocation) => allocation.reconciliation_item_id === selectedReconciliationItem.id,
                                  );
                                  return (
                                    <article className="reconciliation-selected-group-card" key={group.id}>
                                      <div className="reconciliation-selected-group-header">
                                        <div>
                                          <strong>{group.bank_allocations.length} statement {group.bank_allocations.length === 1 ? "item" : "items"} ↔ {group.journal_allocations.length} {group.journal_allocations.length === 1 ? "journal" : "journals"}</strong>
                                          <span>Group {group.id.slice(0, 8)} · saved {formatDateTime(group.resolved_at)}</span>
                                        </div>
                                        {selectedReconciliationSession?.status !== "completed" ? (
                                          <button className="button-link button-link-small button-link-danger" type="button" onClick={() => runAction("Removing grouped reconciliation match", () => deleteGroupedMatch(group))}>Unmatch group</button>
                                        ) : null}
                                      </div>
                                      <div className="reconciliation-selected-group-metrics">
                                        <span>This statement<strong>{formatMoney(selectedAllocation?.allocated_amount ?? "0")}</strong></span>
                                        <span>Statement total<strong>{formatMoney(group.bank_total)}</strong></span>
                                        <span>Ledger total<strong>{formatMoney(group.journal_total)}</strong></span>
                                        <span>Difference<strong>{formatMoney(group.difference_amount)}</strong></span>
                                      </div>
                                      <div className="reconciliation-selected-group-sources">
                                        <div className="reconciliation-selected-group-source">
                                          <h5>Statement allocations</h5>
                                          {group.bank_allocations.map((allocation) => (
                                            <div className="reconciliation-selected-group-row" key={allocation.id}>
                                              <span>{allocation.bank_row.description}<small>Line {allocation.bank_row.line_number}</small></span>
                                              <strong>{formatMoney(allocation.allocated_amount)}</strong>
                                            </div>
                                          ))}
                                        </div>
                                        <div className="reconciliation-selected-group-source">
                                          <h5>Journal allocations</h5>
                                          {group.journal_allocations.map((allocation) => (
                                            <div className="reconciliation-selected-group-row" key={allocation.id}>
                                              <span>{allocation.journal_entry.entry_number} · {allocation.journal_entry.description}</span>
                                              <strong>{formatMoney(allocation.allocated_amount)}</strong>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                      {group.note ? <p className="reconciliation-selected-group-note">Note: {group.note}</p> : null}
                                    </article>
                                  );
                                })}
                              </div>
                            </section>
                          ) : null}

                          <section className="reconciliation-match-panel">
                            <div className="mini-card-heading">
                              <h4>Match action</h4>
                              <span className="pill">{candidateJournals.length} shown</span>
                            </div>
                            <div className="compact-list reconciliation-candidate-list">
                              {candidateJournals.map(({ journal, cashImpact, amountGap, tokenHits }) => (
                                <button key={journal.id} className={`reconciliation-item-button${reconciliationMatchJournalId === journal.id ? " is-active" : ""}`} type="button" onClick={() => setReconciliationMatchJournalId(journal.id)}>
                                  <div className="reconciliation-item-button-top">
                                    <strong>{journal.entry_number} · {journal.description}</strong>
                                    <span className="reconciliation-amount">{reconciliationLedgerAccount ? formatMoney(cashImpact) : "Link account"}</span>
                                  </div>
                                  <div className="reconciliation-item-button-meta">
                                    <span>{journal.entry_date}</span>
                                    <span>{journal.reference || "No reference"}</span>
                                  </div>
                                  <div className="reconciliation-item-button-meta">
                                    <span>{tokenHits > 0 ? `${tokenHits} text matches` : "No text overlap"}</span>
                                    <span>{amountGap === 0 ? "Amount aligned" : `${formatMoney(amountGap)} difference`}</span>
                                  </div>
                                </button>
                              ))}
                            </div>
                            <div className="form-grid two-up">
                              <Field label="Posted journal"><select value={reconciliationMatchJournalId} onChange={(event) => setReconciliationMatchJournalId(event.target.value)}><option value="">Select posted journal</option>{eligibleReconciliationJournals.map((journal) => <option key={journal.id} value={journal.id}>{journal.entry_number} · {journal.description}</option>)}</select></Field>
                              <Field label="Resolution note"><input value={reconciliationItemNote} onChange={(event) => setReconciliationItemNote(event.target.value)} /></Field>
                            </div>
                            <div className="request-actions">
                              <button className="button-link button-link-small" type="button" disabled={!reconciliationMatchJournalId} onClick={() => runAction("Matching reconciliation item", matchSelectedReconciliationItem)}>Match selected journal</button>
                              <button className="button-link button-link-small button-link-secondary" type="button" disabled={(allocatedBankAmounts[selectedReconciliationItem.id] ?? 0) !== 0} title={(allocatedBankAmounts[selectedReconciliationItem.id] ?? 0) !== 0 ? "Unmatch the item's saved groups before ignoring it" : undefined} onClick={() => runAction("Ignoring reconciliation item", ignoreSelectedReconciliationItem)}>Ignore item</button>
                            </div>
                          </section>
                        </div>
                      ) : (
                        <EmptyState title="Select an item to compare" detail="The matching lane will show the statement row on the left and the chosen journal on the right." />
                      )}
                    </div>

                    <div className="mini-card reconciliation-lane-card reconciliation-journal-panel">
                      <div className="mini-card-heading">
                        <h4>Posted journals</h4>
                        <span className="pill">{candidateJournals.length} shown</span>
                      </div>
                      <div className="compact-list reconciliation-candidate-list">
                        {eligibleReconciliationJournals.length > 0 ? eligibleReconciliationJournals.map((journal) => {
                          const cashImpact = journalCashImpact(journal, reconciliationSessionBankAccount?.ledger_account_id);
                          const remaining = cashImpact - (allocatedJournalAmounts[journal.id] ?? 0);
                          return (
                            <div className="reconciliation-selectable-row" key={journal.id}>
                              <label className="reconciliation-group-checkbox" title="Include this journal in the grouped match">
                                <input type="checkbox" aria-label={`Group journal ${journal.entry_number}`} checked={selectedGroupJournalIds.includes(journal.id)} disabled={!reconciliationLedgerAccount || Math.abs(remaining) < 0.005 || cashImpact === 0} onChange={() => toggleGroupJournal(journal.id)} />
                              </label>
                              <button className={`reconciliation-item-button${reconciliationMatchJournalId === journal.id ? " is-active" : ""}`} type="button" onClick={() => setReconciliationMatchJournalId(journal.id)}>
                                <div className="reconciliation-item-button-top">
                                  <strong>{journal.entry_number} - {journal.description}</strong>
                                  <span className="reconciliation-amount">{reconciliationLedgerAccount ? formatMoney(cashImpact) : "Link account"}</span>
                                </div>
                                <div className="reconciliation-item-button-meta">
                                  <span>{journal.entry_date}</span>
                                  <span>{Math.abs(remaining) < Math.abs(cashImpact) ? `${formatMoney(remaining)} remaining` : "Available"}</span>
                                </div>
                              </button>
                            </div>
                          );
                        }) : (
                          <EmptyState title="No posted journals found" detail="No posted journal candidates are available for this statement item." />
                        )}
                      </div>
                    </div>
                  </div>
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                <EmptyState title="No reconciliation session selected" detail="Create or select a reconciliation session to start the left-to-right matching workflow." />
              )}
            </div>
          </div>
        </div>
      </article>
      ) : null}

      {activeWorkspace === "bas" ? (
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>BAS support</h2><StatusPill value={basRunDetail?.status ?? "no run"} /></div>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>BAS periods</h3>
              <div className="form-grid two-up">
                <Field label="Generate from"><input type="date" value={basGenerationDraft.start_date} onChange={(event) => setBasGenerationDraft((current) => ({ ...current, start_date: event.target.value }))} /></Field>
                <Field label="Generate to"><input type="date" value={basGenerationDraft.end_date} onChange={(event) => setBasGenerationDraft((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" data-testid="generate-bas-periods" onClick={() => runAction("Generating BAS periods", async () => {
                  await request(`/api/companies/${selectedCompanyId}/bas/periods/generate`, "POST", basGenerationDraft);
                  showMessage("success", "Generated BAS periods.");
                  await refreshAll();
                })}>Generate periods</button>
              </div>
              <div className="compact-list tall-list">
                {basPeriods.map((item) => <button key={item.id} className={`list-row-button${selectedBasPeriodId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedBasPeriodId(item.id)}>{item.start_date} to {item.end_date} · {item.status}</button>)}
              </div>
              {selectedBasPeriod ? (
                <div>
                  <Field label="Period note"><input value={basPeriodNote} onChange={(event) => setBasPeriodNote(event.target.value)} /></Field>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving BAS period", async () => {
                      await request(`/api/companies/${selectedCompanyId}/bas/periods/${selectedBasPeriod.id}`, "PUT", { note: basPeriodNote || null });
                      showMessage("success", "Updated BAS period note.");
                      await refreshAll();
                    })}>Save note</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" data-testid="generate-bas-run" onClick={() => runAction("Creating BAS run", async () => {
                      const created = await request<{ id: string }>(`/api/companies/${selectedCompanyId}/bas/runs`, "POST", { bas_period_id: selectedBasPeriod.id });
                      setSelectedBasRunId(created.id);
                      await loadBasRun(created.id);
                      await refreshAll();
                      showMessage("success", "Generated BAS run.");
                    })}>Generate run</button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Current BAS run</h3>
              {basRunDetail ? (
                <>
                  <div className="stats-grid mini-stats-grid">
                    <div className="stat-card"><span>Status</span><strong>{basRunDetail.status}</strong></div>
                    <div className="stat-card"><span>Warnings</span><strong>{basRunDetail.warning_count}</strong></div>
                    <div className="stat-card"><span>Lines</span><strong>{basRunDetail.line_results.length}</strong></div>
                  </div>
                  <div className="table-shell compact-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Label</th><th>Final amount</th><th>Count</th></tr></thead>
                      <tbody>
                        {basRunDetail.line_results.map((item) => <tr key={item.id}><td>{item.label}</td><td>{formatMoney(item.final_amount)}</td><td>{item.detail_count}</td></tr>)}
                      </tbody>
                    </table>
                  </div>
                  <div className="form-grid two-up">
                    <Field label="Adjustment label"><input value={basAdjustmentDraft.label} onChange={(event) => setBasAdjustmentDraft((current) => ({ ...current, label: event.target.value }))} /></Field>
                    <Field label="Adjustment amount"><input value={basAdjustmentDraft.amount} onChange={(event) => setBasAdjustmentDraft((current) => ({ ...current, amount: event.target.value }))} /></Field>
                    <Field label="Adjustment note" wide><input value={basAdjustmentDraft.note} onChange={(event) => setBasAdjustmentDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                    <Field label="Review note severity"><select value={basReviewNoteDraft.severity} onChange={(event) => setBasReviewNoteDraft((current) => ({ ...current, severity: event.target.value }))}><option value="warning">Warning</option><option value="info">Info</option></select></Field>
                    <Field label="Related label"><input value={basReviewNoteDraft.related_label} onChange={(event) => setBasReviewNoteDraft((current) => ({ ...current, related_label: event.target.value }))} /></Field>
                    <Field label="Review note" wide><input value={basReviewNoteDraft.message} onChange={(event) => setBasReviewNoteDraft((current) => ({ ...current, message: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Adding BAS adjustment", async () => {
                      await request(`/api/companies/${selectedCompanyId}/bas/runs/${basRunDetail.id}/adjustments`, "POST", basAdjustmentDraft);
                      await loadBasRun(basRunDetail.id);
                      showMessage("success", "Added BAS adjustment.");
                    })}>Add adjustment</button>
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Adding BAS review note", async () => {
                      await request(`/api/companies/${selectedCompanyId}/bas/runs/${basRunDetail.id}/review-notes`, "POST", { ...basReviewNoteDraft, related_label: basReviewNoteDraft.related_label || null });
                      await loadBasRun(basRunDetail.id);
                      showMessage("success", "Added BAS review note.");
                    })}>Add review note</button>
                  </div>
                  <Field label="Workflow note"><input value={basActionNote} onChange={(event) => setBasActionNote(event.target.value)} /></Field>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Submitting BAS run", async () => {
                      await request(`/api/companies/${selectedCompanyId}/bas/runs/${basRunDetail.id}/submit`, "POST", { note: basActionNote });
                      await loadBasRun(basRunDetail.id);
                      showMessage("success", "Submitted BAS run.");
                    })}>Submit</button>
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Approving BAS run", async () => {
                      await request(`/api/companies/${selectedCompanyId}/bas/runs/${basRunDetail.id}/approve`, "POST", { note: basActionNote });
                      await loadBasRun(basRunDetail.id);
                      showMessage("success", "Approved BAS run.");
                    })}>Approve</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" data-testid="create-bas-csv-export" onClick={() => runAction("Exporting BAS CSV", async () => {
                      await request(`/api/companies/${selectedCompanyId}/bas/runs/${basRunDetail.id}/exports/csv`, "POST");
                      await loadBasRun(basRunDetail.id);
                      showMessage("success", "Created BAS CSV export.");
                    })}>Create CSV export</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting BAS PDF", async () => {
                      await request(`/api/companies/${selectedCompanyId}/bas/runs/${basRunDetail.id}/exports/pdf`, "POST");
                      await loadBasRun(basRunDetail.id);
                      showMessage("success", "Created BAS PDF export.");
                    })}>Create PDF export</button>
                  </div>
                  <div className="compact-list">
                    {basRunDetail.exports.map((item) => <button key={item.id} className="list-row-button" type="button" onClick={() => runAction("Downloading BAS export", async () => {
                      await downloadFromApi(`/api/companies/${selectedCompanyId}/documents/${item.document_id}/download`, `bas-export-${item.format}.bin`);
                    })}>{item.format} export · {formatDateTime(item.created_at)}</button>)}
                  </div>
                </>
              ) : (
                <EmptyState title="No BAS run selected" detail="Generate a BAS period and create a run to review totals, notes, and export packs here." />
              )}
            </div>
          </div>
        </div>
      </article>
      ) : null}
    </section>
  );
}
