import { useState } from "react";

import { formatMoney, type BalanceSheetReport, type GeneralLedgerReport, type OperatorState, type ProfitAndLossReport, type TrialBalanceReport } from "../operator-state";
import { Field, WorkspaceTabs } from "../operator-ui";


type ReportVersion = "final" | "draft";


function applyReportVersion(query: URLSearchParams, version: ReportVersion) {
  if (version === "draft") {
    query.set("include_draft", "true");
  }
}


export function ReportsSection({ operator }: { operator: OperatorState }) {
  const {
    trialBalanceFilters,
    setTrialBalanceFilters,
    runAction,
    selectedCompanyId,
    request,
    setReportState,
    downloadFromApi,
    reportState,
    profitAndLossFilters,
    setProfitAndLossFilters,
    balanceSheetFilters,
    setBalanceSheetFilters,
    generalLedgerFilters,
    setGeneralLedgerFilters,
    accountOptionList,
  } = operator;

  const [trialBalanceVersion, setTrialBalanceVersion] = useState<ReportVersion>("final");
  const [profitAndLossVersion, setProfitAndLossVersion] = useState<ReportVersion>("final");
  const [balanceSheetVersion, setBalanceSheetVersion] = useState<ReportVersion>("final");
  const [generalLedgerVersion, setGeneralLedgerVersion] = useState<ReportVersion>("final");
  const [activeReport, setActiveReport] = useState<"trial" | "profit_loss" | "balance_sheet" | "ledger">("trial");

  return (
    <section className="sections-stack">
      <WorkspaceTabs
        label="Financial reports"
        activeTab={activeReport}
        onChange={setActiveReport}
        options={[
          { key: "trial", label: "Trial balance", detail: "Account balances by date range" },
          { key: "profit_loss", label: "Profit & loss", detail: "Income, expenses and result" },
          { key: "balance_sheet", label: "Balance sheet", detail: "Financial position at a date" },
          { key: "ledger", label: "General ledger", detail: "Transaction-level account detail" },
        ]}
      />
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Financial reports</h2><span className="pill">Browser-ready reporting</span></div>
        <div className="report-focus">
          {activeReport === "trial" ? (
          <div className="mini-card">
            <h3>Trial balance</h3>
            <div className="form-grid two-up">
              <Field label="Start date"><input type="date" value={trialBalanceFilters.start_date} onChange={(event) => setTrialBalanceFilters((current) => ({ ...current, start_date: event.target.value }))} /></Field>
              <Field label="End date"><input type="date" value={trialBalanceFilters.end_date} onChange={(event) => setTrialBalanceFilters((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              <Field label="Version"><select value={trialBalanceVersion} onChange={(event) => setTrialBalanceVersion(event.target.value as ReportVersion)}><option value="final">Final review (posted only)</option><option value="draft">Draft review (include draft entries)</option></select></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" onClick={() => runAction("Running trial balance", async () => {
                const query = new URLSearchParams();
                if (trialBalanceFilters.start_date) query.set("start_date", trialBalanceFilters.start_date);
                if (trialBalanceFilters.end_date) query.set("end_date", trialBalanceFilters.end_date);
                applyReportVersion(query, trialBalanceVersion);
                const report = await request<TrialBalanceReport>(`/api/companies/${selectedCompanyId}/reports/trial-balance?${query.toString()}`);
                setReportState((current) => ({ ...current, trialBalance: report }));
              })}>Run</button>
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting trial balance", async () => {
                const query = new URLSearchParams();
                if (trialBalanceFilters.start_date) query.set("start_date", trialBalanceFilters.start_date);
                if (trialBalanceFilters.end_date) query.set("end_date", trialBalanceFilters.end_date);
                applyReportVersion(query, trialBalanceVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/trial-balance/export?${query.toString()}`, "trial-balance.csv");
              })}>Export CSV</button>
            </div>
            <div className="table-shell compact-table-shell">
              <table className="data-table">
                <thead><tr><th>Account</th><th>Balance</th></tr></thead>
                <tbody>
                  {(reportState.trialBalance?.rows ?? []).map((item) => <tr key={item.account_id}><td>{item.account_code} · {item.account_name}</td><td>{formatMoney(item.balance)}</td></tr>)}
                </tbody>
              </table>
            </div>
          </div>
          ) : null}

          {activeReport === "profit_loss" ? (
          <div className="mini-card">
            <h3>Profit and loss</h3>
            <div className="form-grid two-up">
              <Field label="Start date"><input type="date" value={profitAndLossFilters.start_date} onChange={(event) => setProfitAndLossFilters((current) => ({ ...current, start_date: event.target.value }))} /></Field>
              <Field label="End date"><input type="date" value={profitAndLossFilters.end_date} onChange={(event) => setProfitAndLossFilters((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              <Field label="Version"><select value={profitAndLossVersion} onChange={(event) => setProfitAndLossVersion(event.target.value as ReportVersion)}><option value="final">Final review (posted only)</option><option value="draft">Draft review (include draft entries)</option></select></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" onClick={() => runAction("Running profit and loss", async () => {
                const query = new URLSearchParams({ start_date: profitAndLossFilters.start_date, end_date: profitAndLossFilters.end_date });
                applyReportVersion(query, profitAndLossVersion);
                const report = await request<ProfitAndLossReport>(`/api/companies/${selectedCompanyId}/reports/profit-and-loss?${query.toString()}`);
                setReportState((current) => ({ ...current, profitAndLoss: report }));
              })}>Run</button>
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting profit and loss", async () => {
                const query = new URLSearchParams({ start_date: profitAndLossFilters.start_date, end_date: profitAndLossFilters.end_date });
                applyReportVersion(query, profitAndLossVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/profit-and-loss/export?${query.toString()}`, "profit-and-loss.csv");
              })}>Export CSV</button>
            </div>
            {reportState.profitAndLoss ? <p className="summary-line">Net profit: <strong>{formatMoney(reportState.profitAndLoss.net_profit)}</strong></p> : null}
          </div>
          ) : null}

          {activeReport === "balance_sheet" ? (
          <div className="mini-card">
            <h3>Balance sheet</h3>
            <div className="form-grid two-up">
              <Field label="As of date"><input type="date" value={balanceSheetFilters.as_of_date} onChange={(event) => setBalanceSheetFilters({ as_of_date: event.target.value })} /></Field>
              <Field label="Version"><select value={balanceSheetVersion} onChange={(event) => setBalanceSheetVersion(event.target.value as ReportVersion)}><option value="final">Final review (posted only)</option><option value="draft">Draft review (include draft entries)</option></select></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" onClick={() => runAction("Running balance sheet", async () => {
                const query = new URLSearchParams({ as_of_date: balanceSheetFilters.as_of_date });
                applyReportVersion(query, balanceSheetVersion);
                const report = await request<BalanceSheetReport>(`/api/companies/${selectedCompanyId}/reports/balance-sheet?${query.toString()}`);
                setReportState((current) => ({ ...current, balanceSheet: report }));
              })}>Run</button>
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting balance sheet", async () => {
                const query = new URLSearchParams({ as_of_date: balanceSheetFilters.as_of_date });
                applyReportVersion(query, balanceSheetVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/balance-sheet/export?${query.toString()}`, "balance-sheet.csv");
              })}>Export CSV</button>
            </div>
            {reportState.balanceSheet ? <p className="summary-line">Assets: <strong>{formatMoney(reportState.balanceSheet.total_assets)}</strong></p> : null}
          </div>
          ) : null}

          {activeReport === "ledger" ? (
          <div className="mini-card">
            <h3>General ledger</h3>
            <div className="form-grid two-up">
              <Field label="Start date"><input type="date" value={generalLedgerFilters.start_date} onChange={(event) => setGeneralLedgerFilters((current) => ({ ...current, start_date: event.target.value }))} /></Field>
              <Field label="End date"><input type="date" value={generalLedgerFilters.end_date} onChange={(event) => setGeneralLedgerFilters((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              <Field label="Account"><select value={generalLedgerFilters.account_id} onChange={(event) => setGeneralLedgerFilters((current) => ({ ...current, account_id: event.target.value }))}><option value="">All accounts</option>{accountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
              <Field label="Version"><select value={generalLedgerVersion} onChange={(event) => setGeneralLedgerVersion(event.target.value as ReportVersion)}><option value="final">Final review (posted only)</option><option value="draft">Draft review (include draft entries)</option></select></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" onClick={() => runAction("Running general ledger", async () => {
                const query = new URLSearchParams({ start_date: generalLedgerFilters.start_date, end_date: generalLedgerFilters.end_date });
                if (generalLedgerFilters.account_id) query.set("account_id", generalLedgerFilters.account_id);
                applyReportVersion(query, generalLedgerVersion);
                const report = await request<GeneralLedgerReport>(`/api/companies/${selectedCompanyId}/reports/general-ledger?${query.toString()}`);
                setReportState((current) => ({ ...current, generalLedger: report }));
              })}>Run</button>
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting general ledger", async () => {
                const query = new URLSearchParams({ start_date: generalLedgerFilters.start_date, end_date: generalLedgerFilters.end_date });
                if (generalLedgerFilters.account_id) query.set("account_id", generalLedgerFilters.account_id);
                applyReportVersion(query, generalLedgerVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/general-ledger/export?${query.toString()}`, "general-ledger.csv");
              })}>Export CSV</button>
            </div>
            {reportState.generalLedger ? <p className="summary-line">Accounts returned: <strong>{reportState.generalLedger.accounts.length}</strong></p> : null}
          </div>
          ) : null}
        </div>
      </article>
    </section>
  );
}
