import { useEffect, useState } from "react";

import { formatDateTime, formatMoney, type OperatorState } from "../operator-state";
import { EmptyState, Field, StatusPill } from "../operator-ui";


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
  } = operator;
  const [importNoteDraft, setImportNoteDraft] = useState("");

  useEffect(() => {
    setImportNoteDraft(selectedImportSession?.note ?? "");
  }, [selectedImportSession?.id, selectedImportSession?.note]);

  return (
    <section className="sections-stack">
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
                  <div className="form-grid">
                    <Field label="Update note"><input value={reconciliationUpdateDraft.note} onChange={(event) => setReconciliationUpdateDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  </div>
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
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Items and summary</h3>
              {reconciliationSummary ? (
                <div className="stats-grid mini-stats-grid">
                  <div className="stat-card"><span>Total</span><strong>{reconciliationSummary.total_items}</strong></div>
                  <div className="stat-card"><span>Matched</span><strong>{reconciliationSummary.matched_items}</strong></div>
                  <div className="stat-card"><span>Ignored</span><strong>{reconciliationSummary.ignored_items}</strong></div>
                  <div className="stat-card"><span>Unmatched</span><strong>{reconciliationSummary.unmatched_items}</strong></div>
                </div>
              ) : null}
              <div className="table-shell compact-table-shell">
                <table className="data-table">
                  <thead><tr><th>Status</th><th>Item</th><th>Journal</th></tr></thead>
                  <tbody>
                    {reconciliationItems.map((item) => (
                      <tr key={item.id} className={selectedReconciliationItemId === item.id ? "is-selected" : ""} onClick={() => setSelectedReconciliationItemId(item.id)}>
                        <td><StatusPill value={item.status} /></td>
                        <td>{item.bank_import_row_id.slice(0, 8)}</td>
                        <td>{item.matched_journal_entry_id?.slice(0, 8) ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selectedReconciliationItem ? (
                <div className="form-grid two-up">
                  <Field label="Posted journal"><select value={reconciliationMatchJournalId} onChange={(event) => setReconciliationMatchJournalId(event.target.value)}><option value="">Select posted journal</option>{journalOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                  <Field label="Item action note"><input value={reconciliationUpdateDraft.note} onChange={(event) => setReconciliationUpdateDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                  <div className="request-actions inline-span">
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Matching reconciliation item", async () => {
                      await request(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/items/${selectedReconciliationItem.id}/match`, "POST", { matched_journal_entry_id: reconciliationMatchJournalId, note: reconciliationUpdateDraft.note || null });
                      showMessage("success", "Matched reconciliation item.");
                      await refreshAll();
                    })}>Match</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Ignoring reconciliation item", async () => {
                      await request(`/api/companies/${selectedCompanyId}/reconciliation-sessions/${selectedReconciliationSessionId}/items/${selectedReconciliationItem.id}/ignore`, "POST", { note: reconciliationUpdateDraft.note || null });
                      showMessage("success", "Ignored reconciliation item.");
                      await refreshAll();
                    })}>Ignore</button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </article>

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
    </section>
  );
}
