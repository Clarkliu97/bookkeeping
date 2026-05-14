import { useMemo } from "react";

import { formatDateTime, formatMoney, type OperatorState } from "../operator-state";
import { EmptyState, Field } from "../operator-ui";


export function YearEndSection({ operator }: { operator: OperatorState }) {
  const {
    fixedAssetRegister,
    selectedFixedAssetId,
    setSelectedFixedAssetId,
    assetDraft,
    setAssetDraft,
    accounts,
    accountOptionList,
    activeAccountOptionList,
    runAction,
    request,
    selectedCompanyId,
    showMessage,
    refreshAll,
    fixedAssetDetail,
    disposeDraft,
    depreciationRuns,
    selectedDepreciationRunId,
    setSelectedDepreciationRunId,
    depreciationDraft,
    setDepreciationDraft,
    periodOptionList,
    depreciationRunDetail,
    downloadFromApi,
    taxPacks,
    selectedTaxPackId,
    setSelectedTaxPackId,
    taxPackDraft,
    setTaxPackDraft,
    taxPackDetail,
    taxAdjustmentDraft,
    setTaxAdjustmentDraft,
    taxNoteDraft,
    setTaxNoteDraft,
    taxExceptionDraft,
    setTaxExceptionDraft,
    taxActionNote,
    setTaxActionNote,
    loadTaxPack,
    taxResolveNote,
  } = operator;
  const selectedAssetAccountIds = [assetDraft.asset_account_id, assetDraft.accumulated_depreciation_account_id, assetDraft.depreciation_expense_account_id].filter(Boolean);
  const assetAccountOptionList = useMemo(() => {
    const activeOptionIds = new Set(activeAccountOptionList.map((item) => item.value));
    const selectedOptionIds = new Set(selectedAssetAccountIds);
    return accountOptionList
      .filter((item) => activeOptionIds.has(item.value) || selectedOptionIds.has(item.value))
      .map((item) => {
        if (activeOptionIds.has(item.value)) {
          return item;
        }
        const account = accounts.find((candidate) => candidate.id === item.value);
        return { ...item, label: `${item.label}${account?.is_active === false ? " (inactive)" : ""}` };
      });
  }, [accountOptionList, accounts, activeAccountOptionList, selectedAssetAccountIds]);

  return (
    <section className="sections-stack">
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Fixed assets and depreciation</h2><span className="pill">{fixedAssetRegister?.assets.length ?? 0} assets</span></div>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Asset register</h3>
              <div className="compact-list tall-list">
                {(fixedAssetRegister?.assets ?? []).map((item) => <button key={item.id} className={`list-row-button${selectedFixedAssetId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedFixedAssetId(item.id)}>{item.asset_code} · {item.name}</button>)}
              </div>
              <div className="form-grid two-up">
                <Field label="Asset code"><input value={assetDraft.asset_code} onChange={(event) => setAssetDraft((current) => ({ ...current, asset_code: event.target.value }))} /></Field>
                <Field label="Name"><input value={assetDraft.name} onChange={(event) => setAssetDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                <Field label="Acquisition date"><input type="date" value={assetDraft.acquisition_date} onChange={(event) => setAssetDraft((current) => ({ ...current, acquisition_date: event.target.value }))} /></Field>
                <Field label="In service date"><input type="date" value={assetDraft.in_service_date} onChange={(event) => setAssetDraft((current) => ({ ...current, in_service_date: event.target.value }))} /></Field>
                <Field label="Cost"><input value={assetDraft.cost_amount} onChange={(event) => setAssetDraft((current) => ({ ...current, cost_amount: event.target.value }))} /></Field>
                <Field label="Useful life months"><input type="number" value={assetDraft.useful_life_months} onChange={(event) => setAssetDraft((current) => ({ ...current, useful_life_months: Number(event.target.value) }))} /></Field>
                <Field label="Method"><select value={assetDraft.depreciation_method} onChange={(event) => setAssetDraft((current) => ({ ...current, depreciation_method: event.target.value }))}><option value="straight_line">Straight line</option><option value="diminishing_value">Diminishing value</option></select></Field>
                <Field label="Asset account"><select value={assetDraft.asset_account_id} onChange={(event) => setAssetDraft((current) => ({ ...current, asset_account_id: event.target.value }))}><option value="">Select account</option>{assetAccountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Accumulated depreciation account"><select value={assetDraft.accumulated_depreciation_account_id} onChange={(event) => setAssetDraft((current) => ({ ...current, accumulated_depreciation_account_id: event.target.value }))}><option value="">Select account</option>{assetAccountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Depreciation expense account"><select value={assetDraft.depreciation_expense_account_id} onChange={(event) => setAssetDraft((current) => ({ ...current, depreciation_expense_account_id: event.target.value }))}><option value="">Select account</option>{assetAccountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving fixed asset", async () => {
                  const payload = { ...assetDraft, description: assetDraft.description || null, diminishing_value_rate: assetDraft.diminishing_value_rate || null, acquisition_reference: assetDraft.acquisition_reference || null, note: assetDraft.note || null };
                  if (selectedFixedAssetId) {
                    await request(`/api/companies/${selectedCompanyId}/fixed-assets/${selectedFixedAssetId}`, "PUT", payload);
                  } else {
                    await request(`/api/companies/${selectedCompanyId}/fixed-assets`, "POST", payload);
                  }
                  showMessage("success", "Saved fixed asset.");
                  await refreshAll();
                })}>Save asset</button>
                {fixedAssetDetail ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Disposing asset", async () => {
                  await request(`/api/companies/${selectedCompanyId}/fixed-assets/${fixedAssetDetail.id}/dispose`, "POST", { ...disposeDraft, disposal_reference: disposeDraft.disposal_reference || null, disposal_note: disposeDraft.disposal_note || null, disposal_proceeds: disposeDraft.disposal_proceeds || null });
                  showMessage("success", "Disposed fixed asset.");
                  await refreshAll();
                })}>Dispose asset</button> : null}
              </div>
              {fixedAssetDetail ? <p className="summary-line">Carrying amount: <strong>{formatMoney(fixedAssetDetail.carrying_amount)}</strong></p> : null}
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Depreciation runs</h3>
              <div className="compact-list tall-list">
                {depreciationRuns.map((item) => <button key={item.id} className={`list-row-button${selectedDepreciationRunId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedDepreciationRunId(item.id)}>{item.start_date} to {item.end_date} · {item.status}</button>)}
              </div>
              <div className="form-grid two-up">
                <Field label="Accounting period"><select value={depreciationDraft.accounting_period_id} onChange={(event) => operator.setDepreciationDraft((current) => ({ ...current, accounting_period_id: event.target.value }))}><option value="">Select period</option>{periodOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Note"><input value={depreciationDraft.note} onChange={(event) => setDepreciationDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                <Field label="Start date"><input type="date" value={depreciationDraft.start_date} onChange={(event) => setDepreciationDraft((current) => ({ ...current, start_date: event.target.value }))} /></Field>
                <Field label="End date"><input type="date" value={depreciationDraft.end_date} onChange={(event) => setDepreciationDraft((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Saving depreciation run", async () => {
                  if (selectedDepreciationRunId) {
                    await request(`/api/companies/${selectedCompanyId}/fixed-assets/depreciation-runs/${selectedDepreciationRunId}`, "PUT", depreciationDraft);
                  } else {
                    await request(`/api/companies/${selectedCompanyId}/fixed-assets/depreciation-runs`, "POST", depreciationDraft);
                  }
                  showMessage("success", "Saved depreciation run.");
                  await refreshAll();
                })}>Save run</button>
                {selectedDepreciationRunId ? <button className="button-link button-link-small" type="button" onClick={() => runAction("Posting depreciation run", async () => {
                  await request(`/api/companies/${selectedCompanyId}/fixed-assets/depreciation-runs/${selectedDepreciationRunId}/post`, "POST");
                  showMessage("success", "Posted depreciation run.");
                  await refreshAll();
                })}>Post run</button> : null}
                {selectedDepreciationRunId ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting depreciation run", async () => {
                  await downloadFromApi(`/api/companies/${selectedCompanyId}/fixed-assets/depreciation-runs/${selectedDepreciationRunId}/export`, "depreciation-run.csv");
                })}>Export CSV</button> : null}
              </div>
              {depreciationRunDetail ? <p className="summary-line">Run amount: <strong>{formatMoney(depreciationRunDetail.total_depreciation_amount)}</strong></p> : null}
            </div>
          </div>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Tax workpapers</h2><span className="pill">{taxPacks.length} packs</span></div>
        <div className="workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Packs</h3>
              <div className="compact-list tall-list">
                {taxPacks.map((item) => <button key={item.id} className={`list-row-button${selectedTaxPackId === item.id ? " is-active" : ""}`} type="button" data-testid={`tax-pack-row-${item.id}`} onClick={() => setSelectedTaxPackId(item.id)}>{item.id.slice(0, 8)} · {item.status}</button>)}
              </div>
              <div className="form-grid two-up">
                <Field label="Year period"><select value={taxPackDraft.accounting_period_id} onChange={(event) => setTaxPackDraft((current) => ({ ...current, accounting_period_id: event.target.value }))}><option value="">Select period</option>{periodOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
                <Field label="Pack note"><input value={taxPackDraft.note} onChange={(event) => setTaxPackDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" data-testid="save-tax-pack" onClick={() => runAction("Saving tax pack", async () => {
                  if (selectedTaxPackId) {
                    await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${selectedTaxPackId}`, "PUT", { accounting_period_id: taxPackDraft.accounting_period_id, note: taxPackDraft.note || null });
                  } else {
                    await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs`, "POST", { accounting_period_id: taxPackDraft.accounting_period_id, note: taxPackDraft.note || null });
                  }
                  showMessage("success", "Saved tax workpaper pack.");
                  await refreshAll();
                })}>Save pack</button>
              </div>
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card" data-testid="selected-tax-pack-detail">
              <h3>Selected pack detail</h3>
              {taxPackDetail ? (
                <>
                  <p className="summary-line">Taxable income: <strong>{formatMoney(taxPackDetail.taxable_income)}</strong></p>
                  <div className="summary-line">Exports: <strong>{taxPackDetail.exports.length}</strong></div>
                  <div className="form-grid two-up">
                    <Field label="Adjustment label"><input value={taxAdjustmentDraft.label} onChange={(event) => setTaxAdjustmentDraft((current) => ({ ...current, label: event.target.value }))} /></Field>
                    <Field label="Adjustment amount"><input value={taxAdjustmentDraft.amount} onChange={(event) => setTaxAdjustmentDraft((current) => ({ ...current, amount: event.target.value }))} /></Field>
                    <Field label="Adjustment note" wide><input value={taxAdjustmentDraft.note} onChange={(event) => setTaxAdjustmentDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                    <Field label="Note type"><select value={taxNoteDraft.note_type} onChange={(event) => setTaxNoteDraft((current) => ({ ...current, note_type: event.target.value }))}><option value="review">Review</option><option value="sign_off">Sign off</option></select></Field>
                    <Field label="Note message" wide><input value={taxNoteDraft.message} onChange={(event) => setTaxNoteDraft((current) => ({ ...current, message: event.target.value }))} /></Field>
                    <Field label="Exception severity"><select value={taxExceptionDraft.severity} onChange={(event) => setTaxExceptionDraft((current) => ({ ...current, severity: event.target.value }))}><option value="warning">Warning</option><option value="error">Error</option></select></Field>
                    <Field label="Exception message" wide><input value={taxExceptionDraft.message} onChange={(event) => setTaxExceptionDraft((current) => ({ ...current, message: event.target.value }))} /></Field>
                  </div>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Adding tax adjustment", async () => {
                      await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${taxPackDetail.id}/adjustments`, "POST", taxAdjustmentDraft);
                      await loadTaxPack(taxPackDetail.id);
                      showMessage("success", "Added tax adjustment.");
                    })}>Add adjustment</button>
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Adding tax note", async () => {
                      await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${taxPackDetail.id}/notes`, "POST", taxNoteDraft);
                      await loadTaxPack(taxPackDetail.id);
                      showMessage("success", "Added tax note.");
                    })}>Add note</button>
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Adding tax exception", async () => {
                      await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${taxPackDetail.id}/exceptions`, "POST", taxExceptionDraft);
                      await loadTaxPack(taxPackDetail.id);
                      showMessage("success", "Added tax exception.");
                    })}>Add exception</button>
                  </div>
                  <Field label="Workflow note"><input value={taxActionNote} onChange={(event) => setTaxActionNote(event.target.value)} /></Field>
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" data-testid="submit-tax-pack" onClick={() => runAction("Submitting tax pack", async () => {
                      await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${taxPackDetail.id}/submit`, "POST", { note: taxActionNote });
                      await loadTaxPack(taxPackDetail.id);
                      showMessage("success", "Submitted tax pack.");
                    })}>Submit</button>
                    <button className="button-link button-link-small" type="button" data-testid="approve-tax-pack" onClick={() => runAction("Approving tax pack", async () => {
                      await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${taxPackDetail.id}/approve`, "POST", { note: taxActionNote });
                      await loadTaxPack(taxPackDetail.id);
                      showMessage("success", "Approved tax pack.");
                    })}>Approve</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" data-testid="create-tax-pack-pdf-export" onClick={() => runAction("Exporting tax pack", async () => {
                      await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${taxPackDetail.id}/exports/pdf`, "POST");
                      await loadTaxPack(taxPackDetail.id);
                      showMessage("success", "Created tax pack PDF export.");
                    })}>Create PDF export</button>
                  </div>
                  <div className="compact-list">
                    {taxPackDetail.exception_items.filter((item) => item.status !== "resolved").map((item) => <button key={item.id} className="list-row-button" type="button" onClick={() => runAction("Resolving tax exception", async () => {
                      await request(`/api/companies/${selectedCompanyId}/tax-workpapers/packs/${taxPackDetail.id}/exceptions/${item.id}/resolve`, "POST", { note: taxResolveNote });
                      await loadTaxPack(taxPackDetail.id);
                      showMessage("success", "Resolved tax exception.");
                    })}>{item.severity} · {item.message}</button>)}
                  </div>
                  <div className="compact-list">
                    {taxPackDetail.exports.map((item) => <button key={item.id} className="list-row-button" type="button" onClick={() => runAction("Downloading tax export", async () => {
                      await downloadFromApi(`/api/companies/${selectedCompanyId}/documents/${item.document_id}/download`, `tax-workpaper-${item.format}.pdf`);
                    })}>{item.format} export · {formatDateTime(item.created_at)}</button>)}
                  </div>
                </>
              ) : (
                <EmptyState title="No tax pack selected" detail="Create a pack from an approved year period to review taxable income support, notes, exceptions, and exports." />
              )}
            </div>
          </div>
        </div>
      </article>
    </section>
  );
}