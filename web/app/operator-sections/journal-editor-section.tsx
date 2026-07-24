"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { createEmptyJournalDraft, createEmptyJournalLine, formatDateTime, type OperatorState } from "../operator-state";
import { EmptyState, Field, StatusPill } from "../operator-ui";


function parseMoneyToCents(value: string): number {
  const parsed = Number(value || "0");
  if (!Number.isFinite(parsed)) {
    throw new Error("Enter valid journal line amounts before saving.");
  }
  return Math.round(parsed * 100);
}


function isJournalLineMeaningful(line: {
  account_id: string;
  tax_code_id?: string | null;
  debit_amount: string;
  credit_amount: string;
  description?: string | null;
}): boolean {
  return Boolean(
    line.account_id.trim()
    || (line.tax_code_id ?? "").trim()
    || line.debit_amount.trim()
    || line.credit_amount.trim()
    || (line.description ?? "").trim(),
  );
}


function formatFileSize(byteSize: number) {
  if (byteSize < 1024) {
    return `${byteSize} B`;
  }
  return `${Math.round(byteSize / 1024)} KB`;
}


export function JournalEditorSection({ operator, journalId, mode = "page", onClose }: { operator: OperatorState; journalId?: string; mode?: "page" | "modal"; onClose?: () => void }) {
  const router = useRouter();
  const initializedNewDraftRef = useRef(false);
  const [journalLineEditorMode, setJournalLineEditorMode] = useState<"panel" | "table">("panel");
  const {
    selectedCompanyId,
    selectedJournalId,
    setSelectedJournalId,
    selectedJournal,
    journalDraft,
    setJournalDraft,
    periodOptionList,
    selectedPeriodId,
    accounts,
    accountOptionList,
    activeAccountOptionList,
    taxCodes,
    taxCodeOptionList,
    activeTaxCodeOptionList,
    documents,
    journalEvidence,
    runAction,
    request,
    showMessage,
    refreshAll,
    loadJournalEvidence,
    confirmDanger,
    downloadFromApi,
  } = operator;

  const fallbackPeriodId = selectedPeriodId || periodOptionList[0]?.value || "";
  const effectiveJournalPeriodId = journalDraft.accounting_period_id || fallbackPeriodId;
  const [journalEvidenceDocumentId, setJournalEvidenceDocumentId] = useState("");
  const [journalEvidenceNote, setJournalEvidenceNote] = useState("Supports the selected journal");
  const [journalEvidenceFile, setJournalEvidenceFile] = useState<File | null>(null);
  const [journalEvidenceUploadKey, setJournalEvidenceUploadKey] = useState(0);

  useEffect(() => {
    if (!selectedCompanyId) {
      return;
    }

    if (journalId) {
      initializedNewDraftRef.current = false;
      if (selectedJournalId !== journalId) {
        setSelectedJournalId(journalId);
      }
      return;
    }

    if (!initializedNewDraftRef.current) {
      setSelectedJournalId("");
      setJournalDraft(createEmptyJournalDraft(fallbackPeriodId));
      initializedNewDraftRef.current = true;
    }
  }, [fallbackPeriodId, journalId, selectedCompanyId, selectedJournalId, setJournalDraft, setSelectedJournalId]);

  useEffect(() => {
    if (!selectedJournal?.id) {
      return;
    }
    void loadJournalEvidence(selectedJournal.id);
  }, [loadJournalEvidence, selectedJournal?.id]);

  const journalAccountOptionList = useMemo(() => {
    const activeOptionIds = new Set(activeAccountOptionList.map((item) => item.value));
    const selectedAccountIds = new Set(journalDraft.lines.map((line) => line.account_id).filter(Boolean));
    return accountOptionList
      .filter((item) => activeOptionIds.has(item.value) || selectedAccountIds.has(item.value))
      .map((item) => {
        if (activeOptionIds.has(item.value)) {
          return item;
        }
        const account = accounts.find((candidate) => candidate.id === item.value);
        return { ...item, label: `${item.label}${account?.is_active === false ? " (inactive)" : ""}` };
      });
  }, [accountOptionList, accounts, activeAccountOptionList, journalDraft.lines]);

  const journalTaxCodeOptionList = useMemo(() => {
    const activeOptionIds = new Set(activeTaxCodeOptionList.map((item) => item.value));
    const selectedTaxCodeIds = new Set(journalDraft.lines.map((line) => line.tax_code_id).filter(Boolean));
    return taxCodeOptionList
      .filter((item) => activeOptionIds.has(item.value) || selectedTaxCodeIds.has(item.value))
      .map((item) => {
        if (activeOptionIds.has(item.value)) {
          return item;
        }
        const taxCode = taxCodes.find((candidate) => candidate.id === item.value);
        return { ...item, label: `${item.label}${taxCode?.is_active === false ? " (inactive)" : ""}` };
      });
  }, [activeTaxCodeOptionList, journalDraft.lines, taxCodeOptionList, taxCodes]);

  const availableEvidenceDocuments = useMemo(() => {
    const linkedDocumentIds = new Set(journalEvidence.map((item) => item.document_id));
    return documents.filter((item) => !linkedDocumentIds.has(item.id));
  }, [documents, journalEvidence]);

  useEffect(() => {
    setJournalEvidenceDocumentId((current) => {
      if (availableEvidenceDocuments.some((item) => item.id === current)) {
        return current;
      }
      return availableEvidenceDocuments[0]?.id ?? "";
    });
  }, [availableEvidenceDocuments]);

  useEffect(() => {
    if (!selectedJournal) {
      setJournalEvidenceNote("Supports the selected journal");
      setJournalEvidenceFile(null);
      setJournalEvidenceUploadKey((current) => current + 1);
      return;
    }
    setJournalEvidenceNote(`Supports ${selectedJournal.entry_number}`);
    setJournalEvidenceFile(null);
    setJournalEvidenceUploadKey((current) => current + 1);
  }, [selectedJournal]);

  const isEditingMissingJournal = Boolean(journalId && selectedCompanyId && !selectedJournal);
  const canSaveDraft = !selectedJournal || selectedJournal.status === "draft";
  const isModal = mode === "modal";
  const visibleTableRowCount = Math.max(journalDraft.lines.length + 4, 10);
  const tableEditorLines = useMemo(
    () => Array.from({ length: visibleTableRowCount }, (_, index) => journalDraft.lines[index] ?? createEmptyJournalLine()),
    [journalDraft.lines, visibleTableRowCount],
  );

  function updateJournalLine(index: number, field: "account_id" | "tax_code_id" | "debit_amount" | "credit_amount" | "description", value: string) {
    setJournalDraft((current) => {
      const nextLines = [...current.lines];
      while (nextLines.length <= index) {
        nextLines.push(createEmptyJournalLine());
      }
      nextLines[index] = { ...nextLines[index], [field]: value };
      return { ...current, lines: nextLines };
    });
  }

  function addJournalLine() {
    setJournalDraft((current) => ({ ...current, lines: [...current.lines, createEmptyJournalLine()] }));
  }

  function removeJournalLine(index: number) {
    setJournalDraft((current) => ({
      ...current,
      lines: current.lines.length <= 2
        ? current.lines
        : current.lines.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  function closeEditor() {
    if (isModal) {
      onClose?.();
      return;
    }
    router.push("/bookkeeping");
  }

  function startNewJournal() {
    setSelectedJournalId("");
    setJournalDraft(createEmptyJournalDraft(fallbackPeriodId));
    if (isModal) {
      initializedNewDraftRef.current = true;
      return;
    }
    router.push("/bookkeeping/journals/new");
  }

  async function saveJournal() {
    if (!effectiveJournalPeriodId) {
      throw new Error("Create or select an accounting period before saving a journal.");
    }

    const linesToSave = journalDraft.lines
      .map((line, index) => ({ line, index }))
      .filter(({ line }) => isJournalLineMeaningful(line));

    if (linesToSave.length < 2) {
      throw new Error("Enter at least two journal lines before saving.");
    }

    let debitTotalCents = 0;
    let creditTotalCents = 0;
    linesToSave.forEach(({ line, index }) => {
      if (!line.account_id) {
        throw new Error(`Select an account for journal line ${index + 1} before saving.`);
      }
      const debitAmountCents = parseMoneyToCents(line.debit_amount);
      const creditAmountCents = parseMoneyToCents(line.credit_amount);
      const isValidSingleSidedLine = (
        (debitAmountCents > 0 && creditAmountCents === 0)
        || (creditAmountCents > 0 && debitAmountCents === 0)
      );
      if (!isValidSingleSidedLine) {
        throw new Error(`Journal line ${index + 1} must have exactly one positive amount.`);
      }
      debitTotalCents += debitAmountCents;
      creditTotalCents += creditAmountCents;
    });

    if (debitTotalCents !== creditTotalCents) {
      throw new Error("Journal is not balanced.");
    }

    const payload = {
      ...journalDraft,
      accounting_period_id: effectiveJournalPeriodId,
      lines: linesToSave.map(({ line }) => ({
        ...line,
        tax_code_id: line.tax_code_id || null,
        reporting_category_id: line.reporting_category_id || null,
        source_document_reference: line.source_document_reference || null,
      })),
    };

    if (selectedJournal && selectedJournal.status === "draft") {
      await request(`/api/companies/${selectedCompanyId}/journals/${selectedJournal.id}`, "PUT", payload);
      showMessage("success", `Saved ${selectedJournal.entry_number}.`);
      await refreshAll();
      return;
    }

    const createdJournal = await request<{ id: string; entry_number: string }>(`/api/companies/${selectedCompanyId}/journals`, "POST", payload);
    setSelectedJournalId(createdJournal.id);
    showMessage("success", `Created ${createdJournal.entry_number}.`);
    await refreshAll();
    if (!isModal) {
      router.replace(`/bookkeeping/journals/${createdJournal.id}`);
    }
  }

  return (
    <article className={`panel panel-wide journal-editor-page-panel${isModal ? " journal-editor-modal-panel" : ""}`}>
      <div className="panel-heading">
        <div>
          <h2>{selectedJournal ? `Update ${selectedJournal.entry_number}` : "Create journal"}</h2>
          <p className="summary-line">{isModal ? "Work in a focused journal popup with balanced draft lines and linked evidence before posting." : "Work in a dedicated journal page with balanced draft lines and linked evidence before posting."}</p>
        </div>
        <div className="request-actions-inline">
          <button className="button-link button-link-small button-link-secondary" type="button" onClick={closeEditor}>
            {isModal ? "Close" : "Back to journals"}
          </button>
          {selectedJournal ? (
            <button className="button-link button-link-small button-link-secondary" type="button" onClick={startNewJournal}>
              New journal
            </button>
          ) : null}
          <span className="pill">{journalDraft.lines.length} lines</span>
          {selectedJournal ? <StatusPill value={selectedJournal.status} /> : <StatusPill value="draft" />}
        </div>
      </div>

      {!selectedCompanyId ? (
        <EmptyState title="Select a company first" detail="Choose a company in the operator sidebar before creating or updating journals." />
      ) : isEditingMissingJournal ? (
        <EmptyState title="Journal not available" detail="Refresh the workspace or return to the Journals table to pick another entry." />
      ) : (
        <div className="stacked-cards journal-editor-page-stack">
          <div className="mini-card journal-editor-card">
            <div className="journal-editor-shell">
              <section className="journal-editor-panel">
                <div className="journal-editor-panel-heading">
                  <div>
                    <h4>Journal details</h4>
                    <p className="summary-line">Set the journal date, period, and source information that explains why this entry exists.</p>
                  </div>
                </div>
                <div className="form-grid two-up journal-editor-meta">
                  <Field label="Entry date"><input type="date" value={journalDraft.entry_date} onChange={(event) => setJournalDraft((current) => ({ ...current, entry_date: event.target.value }))} /></Field>
                  <Field label="Accounting period"><select value={effectiveJournalPeriodId} onChange={(event) => setJournalDraft((current) => ({ ...current, accounting_period_id: event.target.value }))}><option value="">Select period</option>{periodOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                  <Field label="Source type"><input value={journalDraft.source_type} onChange={(event) => setJournalDraft((current) => ({ ...current, source_type: event.target.value }))} /></Field>
                  <Field label="Reference"><input value={journalDraft.reference} onChange={(event) => setJournalDraft((current) => ({ ...current, reference: event.target.value }))} /></Field>
                  <Field label="Description" wide><textarea rows={3} value={journalDraft.description} onChange={(event) => setJournalDraft((current) => ({ ...current, description: event.target.value }))} /></Field>
                </div>
              </section>
              <section className="journal-editor-panel">
                <div className="journal-editor-panel-heading">
                  <div>
                    <h4>Journal lines</h4>
                    <p className="summary-line">Keep at least two lines and document the purpose of each debit and credit clearly for review. Blank spreadsheet rows stay out of validation until you fill them.</p>
                  </div>
                  <div className="journal-line-editor-toolbar">
                    <div className="journal-line-editor-switch" role="tablist" aria-label="Journal line editor mode">
                      <button className={`journal-line-editor-switch-button${journalLineEditorMode === "panel" ? " is-active" : ""}`} type="button" role="tab" aria-selected={journalLineEditorMode === "panel"} onClick={() => setJournalLineEditorMode("panel")}>Panel view</button>
                      <button className={`journal-line-editor-switch-button${journalLineEditorMode === "table" ? " is-active" : ""}`} type="button" role="tab" aria-selected={journalLineEditorMode === "table"} onClick={() => setJournalLineEditorMode("table")}>Table view</button>
                    </div>
                    {journalLineEditorMode === "panel" ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={addJournalLine}>Add line</button> : null}
                  </div>
                </div>
                {journalLineEditorMode === "panel" ? (
                  <div className="line-editor">
                    {journalDraft.lines.map((line, index) => (
                      <div className="line-editor-row" key={`${index}-${line.account_id}`}> 
                        <div className="line-editor-row-header">
                          <div className="line-editor-row-label">
                            <strong>{`Line ${index + 1}`}</strong>
                            <span>Choose the account, tax treatment, and one side of the entry amount.</span>
                          </div>
                          <button
                            className="button-link button-link-small button-link-secondary"
                            type="button"
                            aria-label={`Delete line ${index + 1}`}
                            disabled={journalDraft.lines.length <= 2}
                            onClick={() => removeJournalLine(index)}
                          >
                            Delete line
                          </button>
                        </div>
                        <div className="line-editor-row-grid">
                          <Field label="Account"><select value={line.account_id} onChange={(event) => updateJournalLine(index, "account_id", event.target.value)}><option value="">Select account</option>{journalAccountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                          <Field label="Tax code"><select value={line.tax_code_id ?? ""} onChange={(event) => updateJournalLine(index, "tax_code_id", event.target.value)}><option value="">None</option>{journalTaxCodeOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                          <Field label="Debit"><input value={line.debit_amount} onChange={(event) => updateJournalLine(index, "debit_amount", event.target.value)} /></Field>
                          <Field label="Credit"><input value={line.credit_amount} onChange={(event) => updateJournalLine(index, "credit_amount", event.target.value)} /></Field>
                          <Field label="Line note" wide><textarea rows={2} value={line.description ?? ""} onChange={(event) => updateJournalLine(index, "description", event.target.value)} /></Field>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="table-shell journal-line-table-shell">
                    <table className="data-table journal-line-table">
                      <thead>
                        <tr>
                          <th>Line</th>
                          <th>Account</th>
                          <th>Tax code</th>
                          <th className="amount-cell">Debit</th>
                          <th className="amount-cell">Credit</th>
                          <th>Line note</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tableEditorLines.map((line, index) => (
                          <tr key={`table-${index}-${line.account_id}`} className="row-static">
                            <td className="journal-line-table-index">{index + 1}</td>
                            <td>
                              <select className="journal-line-table-input" aria-label={`Line ${index + 1} account`} value={line.account_id} onChange={(event) => updateJournalLine(index, "account_id", event.target.value)}>
                                <option value="">Select account</option>
                                {journalAccountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                              </select>
                            </td>
                            <td>
                              <select className="journal-line-table-input" aria-label={`Line ${index + 1} tax code`} value={line.tax_code_id ?? ""} onChange={(event) => updateJournalLine(index, "tax_code_id", event.target.value)}>
                                <option value="">None</option>
                                {journalTaxCodeOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                              </select>
                            </td>
                            <td className="amount-cell">
                              <input className="journal-line-table-input amount-cell" aria-label={`Line ${index + 1} debit`} value={line.debit_amount} onChange={(event) => updateJournalLine(index, "debit_amount", event.target.value)} />
                            </td>
                            <td className="amount-cell">
                              <input className="journal-line-table-input amount-cell" aria-label={`Line ${index + 1} credit`} value={line.credit_amount} onChange={(event) => updateJournalLine(index, "credit_amount", event.target.value)} />
                            </td>
                            <td className="journal-line-table-note-cell">
                              <textarea className="journal-line-table-input journal-line-table-note" aria-label={`Line ${index + 1} note`} rows={2} value={line.description ?? ""} onChange={(event) => updateJournalLine(index, "description", event.target.value)} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>
            <div className="request-actions journal-editor-actions">
              {canSaveDraft ? <button className="button-link button-link-small" type="button" data-testid="save-journal" onClick={() => runAction("Saving journal", saveJournal)}>Save journal</button> : null}
              {selectedJournal && selectedJournal.status === "draft" ? <button className="button-link button-link-small button-link-danger" type="button" onClick={() => runAction("Deleting journal", async () => {
                if (!confirmDanger(`Delete draft journal ${selectedJournal.entry_number}?`)) {
                  return;
                }
                await request(`/api/companies/${selectedCompanyId}/journals/${selectedJournal.id}`, "DELETE", undefined, "void");
                setSelectedJournalId("");
                await refreshAll();
                showMessage("success", `Deleted draft journal ${selectedJournal.entry_number}.`);
                if (isModal) {
                  onClose?.();
                } else {
                  router.replace("/bookkeeping");
                }
              })}>Delete selected</button> : null}
              {selectedJournal?.status === "draft" ? <button className="button-link button-link-small" type="button" data-testid="post-journal" onClick={() => runAction("Posting journal", async () => {
                await request(`/api/companies/${selectedCompanyId}/journals/${selectedJournal.id}/post`, "POST");
                await refreshAll();
                showMessage("success", "Posted journal.");
              })}>Post selected</button> : null}
              {selectedJournal && selectedJournal.status === "posted" ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Reversing journal", async () => {
                await request(`/api/companies/${selectedCompanyId}/journals/${selectedJournal.id}/reverse`, "POST");
                await refreshAll();
                showMessage("success", "Created reversal journal.");
              })}>Reverse selected</button> : null}
            </div>
          </div>

          <div className="mini-card">
            <div className="mini-card-heading">
              <h3>Journal evidence</h3>
              <span className="pill">{selectedJournal ? `${journalEvidence.length} linked` : "Save first"}</span>
            </div>
            <p className="summary-line">Attach one or many documents to this journal, or reuse the same document across multiple journals when the evidence supports more than one entry.</p>
            <div className="form-grid two-up">
              <Field label="Existing document">
                <select value={journalEvidenceDocumentId} onChange={(event) => setJournalEvidenceDocumentId(event.target.value)} disabled={!selectedJournal}>
                  <option value="">Select uploaded document</option>
                  {availableEvidenceDocuments.map((item) => <option key={item.id} value={item.id}>{item.original_filename}</option>)}
                </select>
              </Field>
              <Field label="Evidence note">
                <input value={journalEvidenceNote} onChange={(event) => setJournalEvidenceNote(event.target.value)} disabled={!selectedJournal} />
              </Field>
              <Field label="Upload new evidence" wide>
                <input key={journalEvidenceUploadKey} type="file" onChange={(event) => setJournalEvidenceFile(event.target.files?.[0] ?? null)} disabled={!selectedJournal} />
              </Field>
            </div>
            {selectedJournal ? (
              <>
                <div className="request-actions evidence-actions">
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Linking document evidence", async () => {
                    if (!journalEvidenceDocumentId) {
                      throw new Error("Choose an existing document before attaching it to the journal.");
                    }
                    await request(`/api/companies/${selectedCompanyId}/journals/${selectedJournal.id}/documents/${journalEvidenceDocumentId}`, "POST", { note: journalEvidenceNote || null });
                    await loadJournalEvidence(selectedJournal.id);
                    showMessage("success", "Attached document evidence to the selected journal.");
                  })}>Attach selected document</button>
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Uploading journal evidence", async () => {
                    if (!journalEvidenceFile) {
                      throw new Error("Choose a file before uploading journal evidence.");
                    }
                    const formData = new FormData();
                    formData.append("file", journalEvidenceFile);
                    formData.append("note", journalEvidenceNote);
                    const uploadedDocument = await request<{ id: string; original_filename: string }>(`/api/companies/${selectedCompanyId}/documents`, "POST", formData);
                    await request(`/api/companies/${selectedCompanyId}/journals/${selectedJournal.id}/documents/${uploadedDocument.id}`, "POST", { note: journalEvidenceNote || null });
                    await refreshAll();
                    await loadJournalEvidence(selectedJournal.id);
                    setJournalEvidenceFile(null);
                    setJournalEvidenceUploadKey((current) => current + 1);
                    showMessage("success", `Uploaded and attached ${uploadedDocument.original_filename}.`);
                  })}>Upload and attach</button>
                </div>
                {journalEvidence.length > 0 ? (
                  <div className="table-shell compact-table-shell evidence-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Document</th><th>Evidence note</th><th>Attached</th><th>Actions</th></tr></thead>
                      <tbody>
                        {journalEvidence.map((item) => (
                          <tr key={item.link_id} className="row-static">
                            <td>{item.original_filename}<div className="table-meta">{item.media_type ?? "Unknown type"} · {formatFileSize(item.byte_size)}</div></td>
                            <td>{item.note || "-"}</td>
                            <td>{formatDateTime(item.linked_at)}<div className="table-meta">Uploaded {formatDateTime(item.document_created_at)}</div></td>
                            <td>
                              <div className="request-actions-inline evidence-row-actions">
                                <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Downloading evidence", async () => {
                                  await downloadFromApi(`/api/companies/${selectedCompanyId}/documents/${item.document_id}/download`, item.original_filename);
                                })}>Download</button>
                                <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Unlinking evidence", async () => {
                                  if (!confirmDanger(`Remove ${item.original_filename} from ${selectedJournal.entry_number}?`)) {
                                    return;
                                  }
                                  await request(`/api/companies/${selectedCompanyId}/journals/${selectedJournal.id}/documents/${item.document_id}/links/${item.link_id}`, "DELETE", undefined, "void");
                                  await loadJournalEvidence(selectedJournal.id);
                                  showMessage("success", "Removed evidence from the selected journal.");
                                })}>Unlink</button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state">
                    <strong>No evidence linked yet.</strong>
                    <p>Attach existing documents or upload fresh support directly against this journal so the accounting entry and its evidence stay connected.</p>
                  </div>
                )}
              </>
            ) : (
              <div className="empty-state">
                <strong>Save the journal draft to enable evidence linking.</strong>
                <p>Create the draft first, then return here to attach existing documents or upload new support directly against that saved journal.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
