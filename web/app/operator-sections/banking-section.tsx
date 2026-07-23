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
    selectedBankAccountId,
    setSelectedBankAccountId,
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
    periodOptionList,
    reconciliationSummary,
    reconciliationItems,
    selectedReconciliationItemId,
    setSelectedReconciliationItemId,
    selectedReconciliationItem,
    reconciliationMatchJournalId,
    setReconciliationMatchJournalId,
    journals,
    journalOptionList,
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

  useEffect(() => {
    setImportNoteDraft(selectedImportSession?.note ?? "");
  }, [selectedImportSession?.id, selectedImportSession?.note]);

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

  const selectedCandidateJournal = useMemo(
    () => journals.find((item) => item.id === reconciliationMatchJournalId) ?? null,
    [journals, reconciliationMatchJournalId],
  );

  const candidateJournals = useMemo(() => {
    if (!selectedReconciliationItem?.bank_row) {
      return [];
    }
    const targetAmount = Math.abs(bankRowSignedAmount(selectedReconciliationItem.bank_row));
    const searchTokens = tokenizeMatchText(`${selectedReconciliationItem.bank_row.description} ${selectedReconciliationItem.bank_row.reference ?? ""}`);
    return journals
      .filter((journal) => journal.status === "posted")
      .map((journal) => {
        const totals = journalTotals(journal);
        const journalLabelText = `${journal.entry_number} ${journal.description} ${journal.reference ?? ""}`.toLowerCase();
        const tokenHits = searchTokens.reduce((sum, token) => sum + (journalLabelText.includes(token) ? 1 : 0), 0);
        const amountGap = Math.abs(totals.debit - targetAmount);
        const dateGap = daysBetween(journal.entry_date, selectedReconciliationItem.bank_row?.transaction_date ?? "");
        return { journal, totals, tokenHits, amountGap, dateGap };
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
  }, [journals, reconciliationMatchJournalId, selectedReconciliationItem]);

  const activeComparisonJournal = selectedCandidateJournal ?? null;
  const selectedMatchedJournalSummary = selectedReconciliationItem?.matched_journal_entry ?? null;

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
        <div className="panel-heading"><h2>Bank accounts and imports</h2><span className="pill">{bankAccounts.length} accounts</span></div>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Bank account</h3>
              <div className="compact-list">
                {bankAccounts.map((item) => <button key={item.id} className={`list-row-button${selectedBankAccountId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedBankAccountId(item.id)}>{item.name}</button>)}
              </div>
              <div className="form-grid two-up">
                <Field label="Name"><input value={bankAccountDraft.name} onChange={(event) => setBankAccountDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                <Field label="Bank name"><input value={bankAccountDraft.bank_name} onChange={(event) => setBankAccountDraft((current) => ({ ...current, bank_name: event.target.value }))} /></Field>
                <Field label="BSB"><input value={bankAccountDraft.bsb} onChange={(event) => setBankAccountDraft((current) => ({ ...current, bsb: event.target.value }))} /></Field>
                <Field label="Masked account"><input value={bankAccountDraft.account_number_masked} onChange={(event) => setBankAccountDraft((current) => ({ ...current, account_number_masked: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving bank account", async () => {
                  if (selectedBankAccountId) {
                    await request(`/api/companies/${selectedCompanyId}/bank-accounts/${selectedBankAccountId}`, "PUT", bankAccountDraft);
                  } else {
                    await request(`/api/companies/${selectedCompanyId}/bank-accounts`, "POST", bankAccountDraft);
                  }
                  showMessage("success", "Saved bank account.");
                  await refreshAll();
                })}>Save bank account</button>
              </div>
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
                            <h3>Left-to-right matching</h3>
                            <p className="summary-line">Compare one statement item against posted journals, then match or ignore it from the same window.</p>
                          </div>
                          <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => setIsReconciliationWorkspaceOpen(false)}>Close</button>
                        </div>
                  <div className="reconciliation-popup-grid">
                    <div className="mini-card reconciliation-lane-card reconciliation-statement-panel">
                      <div className="mini-card-heading">
                        <h4>Statement items</h4>
                        <span className="pill">{reconciliationSummary?.unmatched_items ?? 0} open</span>
                      </div>
                      <div className="compact-list tall-list reconciliation-item-list">
                        {orderedReconciliationItems.map((item) => (
                          <button key={item.id} className={`reconciliation-item-button${selectedReconciliationItemId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedReconciliationItemId(item.id)}>
                            <div className="reconciliation-item-button-top">
                              <strong>{item.bank_row?.description ?? `Bank row ${item.bank_import_row_id.slice(0, 8)}`}</strong>
                              <StatusPill value={item.status} />
                            </div>
                            <div className="reconciliation-item-button-meta">
                              <span>{item.bank_row?.transaction_date ?? "No date"}</span>
                              <span className="reconciliation-amount">{bankRowAmountLabel(item.bank_row)}</span>
                            </div>
                          </button>
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
                              ) : (
                                <EmptyState title="No journal selected" detail="Pick a posted journal below to compare it against the selected statement row." />
                              )}
                            </section>
                          </div>

                          <section className="reconciliation-match-panel">
                            <div className="mini-card-heading">
                              <h4>Match action</h4>
                              <span className="pill">{candidateJournals.length} shown</span>
                            </div>
                            <div className="compact-list reconciliation-candidate-list">
                              {candidateJournals.map(({ journal, totals, amountGap, tokenHits }) => (
                                <button key={journal.id} className={`reconciliation-item-button${reconciliationMatchJournalId === journal.id ? " is-active" : ""}`} type="button" onClick={() => setReconciliationMatchJournalId(journal.id)}>
                                  <div className="reconciliation-item-button-top">
                                    <strong>{journal.entry_number} · {journal.description}</strong>
                                    <span className="reconciliation-amount">{formatMoney(totals.debit)}</span>
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
                              <Field label="Posted journal"><select value={reconciliationMatchJournalId} onChange={(event) => setReconciliationMatchJournalId(event.target.value)}><option value="">Select posted journal</option>{journalOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                              <Field label="Resolution note"><input value={reconciliationItemNote} onChange={(event) => setReconciliationItemNote(event.target.value)} /></Field>
                            </div>
                            <div className="request-actions">
                              <button className="button-link button-link-small" type="button" disabled={!reconciliationMatchJournalId} onClick={() => runAction("Matching reconciliation item", matchSelectedReconciliationItem)}>Match selected journal</button>
                              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Ignoring reconciliation item", ignoreSelectedReconciliationItem)}>Ignore item</button>
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
                        {candidateJournals.length > 0 ? candidateJournals.map(({ journal, totals }) => (
                          <button key={journal.id} className={`reconciliation-item-button${reconciliationMatchJournalId === journal.id ? " is-active" : ""}`} type="button" onClick={() => setReconciliationMatchJournalId(journal.id)}>
                            <div className="reconciliation-item-button-top">
                              <strong>{journal.entry_number} - {journal.description}</strong>
                              <span className="reconciliation-amount">{formatMoney(totals.debit)}</span>
                            </div>
                            <div className="reconciliation-item-button-meta">
                              <span>{journal.entry_date}</span>
                            </div>
                          </button>
                        )) : (
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
