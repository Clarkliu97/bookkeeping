import { useState } from "react";

import {
  formatMoney,
  type BalanceSheetReport,
  type CashFlowReport,
  type GeneralLedgerReport,
  type OperatorState,
  type ProfitAndLossReport,
  type StatementOfChangesInEquityReport,
  type TrialBalanceReport,
} from "../operator-state";
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
    cashFlowFilters,
    setCashFlowFilters,
    changesInEquityFilters,
    setChangesInEquityFilters,
    generalLedgerFilters,
    setGeneralLedgerFilters,
    accountOptionList,
  } = operator;

  const [trialBalanceVersion, setTrialBalanceVersion] = useState<ReportVersion>("final");
  const [profitAndLossVersion, setProfitAndLossVersion] = useState<ReportVersion>("final");
  const [balanceSheetVersion, setBalanceSheetVersion] = useState<ReportVersion>("final");
  const [cashFlowVersion, setCashFlowVersion] = useState<ReportVersion>("final");
  const [changesInEquityVersion, setChangesInEquityVersion] = useState<ReportVersion>("final");
  const [generalLedgerVersion, setGeneralLedgerVersion] = useState<ReportVersion>("final");
  const [activeReport, setActiveReport] = useState<"trial" | "profit_loss" | "balance_sheet" | "cash_flow" | "equity" | "ledger">("trial");

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
          { key: "cash_flow", label: "Cash flow", detail: "Operating, investing and financing" },
          { key: "equity", label: "Changes in equity", detail: "Opening balance, movements and close" },
          { key: "ledger", label: "General ledger", detail: "Transaction-level account detail" },
        ]}
      />
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Financial reports</h2><span className="pill">Archive-ready PDF &amp; CSV</span></div>
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
              <button className="button-link button-link-small button-link-secondary" type="button" data-testid="export-trial-balance-pdf" onClick={() => runAction("Exporting trial balance PDF", async () => {
                const query = new URLSearchParams();
                if (trialBalanceFilters.start_date) query.set("start_date", trialBalanceFilters.start_date);
                if (trialBalanceFilters.end_date) query.set("end_date", trialBalanceFilters.end_date);
                applyReportVersion(query, trialBalanceVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/trial-balance/export/pdf?${query.toString()}`, "trial-balance.pdf");
              })}>Export PDF</button>
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
              <button className="button-link button-link-small button-link-secondary" type="button" data-testid="export-profit-loss-pdf" onClick={() => runAction("Exporting profit and loss PDF", async () => {
                const query = new URLSearchParams({ start_date: profitAndLossFilters.start_date, end_date: profitAndLossFilters.end_date });
                applyReportVersion(query, profitAndLossVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/profit-and-loss/export/pdf?${query.toString()}`, "profit-and-loss.pdf");
              })}>Export PDF</button>
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
              <button className="button-link button-link-small button-link-secondary" type="button" data-testid="export-balance-sheet-pdf" onClick={() => runAction("Exporting balance sheet PDF", async () => {
                const query = new URLSearchParams({ as_of_date: balanceSheetFilters.as_of_date });
                applyReportVersion(query, balanceSheetVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/balance-sheet/export/pdf?${query.toString()}`, "balance-sheet.pdf");
              })}>Export PDF</button>
            </div>
            {reportState.balanceSheet ? <p className="summary-line">Assets: <strong>{formatMoney(reportState.balanceSheet.total_assets)}</strong></p> : null}
          </div>
          ) : null}

          {activeReport === "cash_flow" ? (
          <div className="mini-card">
            <h3>Statement of cash flows</h3>
            <p className="summary-line">A direct-method statement presenting major classes of gross cash receipts and payments, followed by operating, investing, and financing subtotals and a reconciliation of cash and cash equivalents.</p>
            <div className="form-grid two-up">
              <Field label="Start date"><input type="date" value={cashFlowFilters.start_date} onChange={(event) => setCashFlowFilters((current) => ({ ...current, start_date: event.target.value }))} /></Field>
              <Field label="End date"><input type="date" value={cashFlowFilters.end_date} onChange={(event) => setCashFlowFilters((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              <Field label="Version"><select value={cashFlowVersion} onChange={(event) => setCashFlowVersion(event.target.value as ReportVersion)}><option value="final">Final review (posted only)</option><option value="draft">Draft review (include draft entries)</option></select></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" data-testid="run-cash-flow" onClick={() => runAction("Running cash flow statement", async () => {
                const query = new URLSearchParams({ start_date: cashFlowFilters.start_date, end_date: cashFlowFilters.end_date });
                applyReportVersion(query, cashFlowVersion);
                const report = await request<CashFlowReport>(`/api/companies/${selectedCompanyId}/reports/cash-flow?${query.toString()}`);
                setReportState((current) => ({ ...current, cashFlow: report }));
              })}>Run</button>
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting cash flow CSV", async () => {
                const query = new URLSearchParams({ start_date: cashFlowFilters.start_date, end_date: cashFlowFilters.end_date });
                applyReportVersion(query, cashFlowVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/cash-flow/export?${query.toString()}`, "cash-flow.csv");
              })}>Export CSV</button>
              <button className="button-link button-link-small button-link-secondary" type="button" data-testid="export-cash-flow-pdf" onClick={() => runAction("Exporting cash flow PDF", async () => {
                const query = new URLSearchParams({ start_date: cashFlowFilters.start_date, end_date: cashFlowFilters.end_date });
                applyReportVersion(query, cashFlowVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/cash-flow/export/pdf?${query.toString()}`, "cash-flow.pdf");
              })}>Export PDF</button>
            </div>
            {reportState.cashFlow ? (
              <div className="stacked-cards report-result-stack">
                <div>
                  <div className="mini-card-heading"><h4>Presentation basis</h4><span className="pill">{reportState.cashFlow.method} method</span></div>
                  <p className="summary-line">{reportState.cashFlow.classification_policy}</p>
                </div>
                <div className="stats-grid report-summary-grid">
                  <div className="stat-card"><span>Opening cash</span><strong>{formatMoney(reportState.cashFlow.opening_cash)}</strong></div>
                  <div className="stat-card"><span>Operating</span><strong>{formatMoney(reportState.cashFlow.total_operating)}</strong></div>
                  <div className="stat-card"><span>Investing</span><strong>{formatMoney(reportState.cashFlow.total_investing)}</strong></div>
                  <div className="stat-card"><span>Financing</span><strong>{formatMoney(reportState.cashFlow.total_financing)}</strong></div>
                  <div className="stat-card"><span>Closing cash</span><strong>{formatMoney(reportState.cashFlow.closing_cash)}</strong></div>
                </div>
                {[
                  ["Operating activities", reportState.cashFlow.operating_lines, reportState.cashFlow.total_operating],
                  ["Investing activities", reportState.cashFlow.investing_lines, reportState.cashFlow.total_investing],
                  ["Financing activities", reportState.cashFlow.financing_lines, reportState.cashFlow.total_financing],
                ].map(([label, lines, total]) => (
                  <div key={label as string}>
                    <div className="mini-card-heading"><h4>{label as string}</h4><span className="pill">{formatMoney(total as string)}</span></div>
                    <div className="table-shell compact-table-shell">
                      <table className="data-table">
                        <thead><tr><th>Cash flow</th><th className="amount-cell">Amount</th></tr></thead>
                        <tbody>
                          {(lines as CashFlowReport["operating_lines"]).map((line) => (
                            <tr key={line.line_code}>
                              <td>{line.label}</td>
                              <td className="amount-cell">{formatMoney(line.amount)}</td>
                            </tr>
                          ))}
                          {(lines as CashFlowReport["operating_lines"]).length === 0 ? <tr className="row-static"><td colSpan={2}>No cash flows in this activity group.</td></tr> : null}
                          <tr className="row-static"><td><strong>Net cash from {String(label).toLowerCase()}</strong></td><td className="amount-cell"><strong>{formatMoney(total as string)}</strong></td></tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
                <div>
                  <h4>Reconciliation of cash and cash equivalents</h4>
                  <div className="table-shell compact-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Measure</th><th className="amount-cell">Amount</th></tr></thead>
                      <tbody>
                        <tr><td>Net increase/(decrease) in cash and cash equivalents</td><td className="amount-cell">{formatMoney(reportState.cashFlow.net_cash_change)}</td></tr>
                        <tr><td>Effect of exchange rate changes</td><td className="amount-cell">{formatMoney(reportState.cashFlow.effect_of_exchange_rate_changes)}</td></tr>
                        <tr><td>Cash and cash equivalents at beginning of period</td><td className="amount-cell">{formatMoney(reportState.cashFlow.opening_cash)}</td></tr>
                        <tr className="row-static"><td><strong>Cash and cash equivalents at end of period</strong></td><td className="amount-cell"><strong>{formatMoney(reportState.cashFlow.closing_cash)}</strong></td></tr>
                      </tbody>
                    </table>
                  </div>
                  <p className={Number(reportState.cashFlow.reconciliation_difference) === 0 ? "summary-line" : "field-error"}>
                    Ledger reconciliation difference: <strong>{formatMoney(reportState.cashFlow.reconciliation_difference)}</strong>
                  </p>
                </div>
                <div>
                  <h4>Cash and cash equivalents</h4>
                  <div className="table-shell compact-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Account</th><th className="amount-cell">Opening balance</th><th className="amount-cell">Closing balance</th></tr></thead>
                      <tbody>
                        {reportState.cashFlow.cash_accounts.map((account) => (
                          <tr key={account.account_id}>
                            <td>{account.account_code} · {account.account_name}</td>
                            <td className="amount-cell">{formatMoney(account.opening_balance)}</td>
                            <td className="amount-cell">{formatMoney(account.closing_balance)}</td>
                          </tr>
                        ))}
                        {reportState.cashFlow.cash_accounts.length === 0 ? <tr className="row-static"><td colSpan={3}>No cash accounts were identified.</td></tr> : null}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
          ) : null}

          {activeReport === "equity" ? (
          <div className="mini-card">
            <h3>Statement of changes in equity</h3>
            <p className="summary-line">Reconciles opening equity to closing equity through profit or loss, capital contributions, distributions, and other equity movements. Period rollover journals are excluded as internal reclassifications.</p>
            <div className="form-grid two-up">
              <Field label="Start date"><input type="date" value={changesInEquityFilters.start_date} onChange={(event) => setChangesInEquityFilters((current) => ({ ...current, start_date: event.target.value }))} /></Field>
              <Field label="End date"><input type="date" value={changesInEquityFilters.end_date} onChange={(event) => setChangesInEquityFilters((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              <Field label="Version"><select value={changesInEquityVersion} onChange={(event) => setChangesInEquityVersion(event.target.value as ReportVersion)}><option value="final">Final review (posted only)</option><option value="draft">Draft review (include draft entries)</option></select></Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" data-testid="run-changes-in-equity" onClick={() => runAction("Running changes in equity statement", async () => {
                const query = new URLSearchParams({ start_date: changesInEquityFilters.start_date, end_date: changesInEquityFilters.end_date });
                applyReportVersion(query, changesInEquityVersion);
                const report = await request<StatementOfChangesInEquityReport>(`/api/companies/${selectedCompanyId}/reports/statement-of-changes-in-equity?${query.toString()}`);
                setReportState((current) => ({ ...current, changesInEquity: report }));
              })}>Run</button>
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting changes in equity CSV", async () => {
                const query = new URLSearchParams({ start_date: changesInEquityFilters.start_date, end_date: changesInEquityFilters.end_date });
                applyReportVersion(query, changesInEquityVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/statement-of-changes-in-equity/export?${query.toString()}`, "statement-of-changes-in-equity.csv");
              })}>Export CSV</button>
              <button className="button-link button-link-small button-link-secondary" type="button" data-testid="export-changes-in-equity-pdf" onClick={() => runAction("Exporting changes in equity PDF", async () => {
                const query = new URLSearchParams({ start_date: changesInEquityFilters.start_date, end_date: changesInEquityFilters.end_date });
                applyReportVersion(query, changesInEquityVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/statement-of-changes-in-equity/export/pdf?${query.toString()}`, "statement-of-changes-in-equity.pdf");
              })}>Export PDF</button>
            </div>
            {reportState.changesInEquity ? (
              <div className="stacked-cards report-result-stack">
                <div className="stats-grid report-summary-grid">
                  <div className="stat-card"><span>Opening equity</span><strong>{formatMoney(reportState.changesInEquity.opening_equity)}</strong></div>
                  <div className="stat-card"><span>Profit or loss</span><strong>{formatMoney(reportState.changesInEquity.profit_or_loss)}</strong></div>
                  <div className="stat-card"><span>Contributions</span><strong>{formatMoney(reportState.changesInEquity.total_contributions)}</strong></div>
                  <div className="stat-card"><span>Distributions</span><strong>{formatMoney(reportState.changesInEquity.total_distributions)}</strong></div>
                  <div className="stat-card"><span>Closing equity</span><strong>{formatMoney(reportState.changesInEquity.closing_equity)}</strong></div>
                </div>
                <div className="table-shell compact-table-shell">
                  <table className="data-table">
                    <thead><tr><th>Movement</th><th>Account</th><th className="amount-cell">Amount</th></tr></thead>
                    <tbody>
                      <tr className="row-static"><td>Opening equity</td><td>Opening balance</td><td className="amount-cell">{formatMoney(reportState.changesInEquity.opening_equity)}</td></tr>
                      <tr className="row-static"><td>Profit or loss</td><td>Current reporting period</td><td className="amount-cell">{formatMoney(reportState.changesInEquity.profit_or_loss)}</td></tr>
                      {reportState.changesInEquity.movement_lines.map((line) => (
                        <tr key={line.account_id}>
                          <td>{line.movement_type.replaceAll("_", " ")}</td>
                          <td>{line.account_code} · {line.account_name}</td>
                          <td className="amount-cell">{formatMoney(line.amount)}</td>
                        </tr>
                      ))}
                      <tr className="row-static"><td><strong>Closing equity</strong></td><td>Ledger closing balance</td><td className="amount-cell"><strong>{formatMoney(reportState.changesInEquity.closing_equity)}</strong></td></tr>
                    </tbody>
                  </table>
                </div>
                <p className={Number(reportState.changesInEquity.reconciliation_difference) === 0 ? "summary-line" : "field-error"}>
                  Equity reconciliation difference: <strong>{formatMoney(reportState.changesInEquity.reconciliation_difference)}</strong>
                </p>
              </div>
            ) : null}
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
              <button className="button-link button-link-small button-link-secondary" type="button" data-testid="export-general-ledger-pdf" onClick={() => runAction("Exporting general ledger PDF", async () => {
                const query = new URLSearchParams({ start_date: generalLedgerFilters.start_date, end_date: generalLedgerFilters.end_date });
                if (generalLedgerFilters.account_id) query.set("account_id", generalLedgerFilters.account_id);
                applyReportVersion(query, generalLedgerVersion);
                await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/general-ledger/export/pdf?${query.toString()}`, "general-ledger.pdf");
              })}>Export PDF</button>
            </div>
            {reportState.generalLedger ? <p className="summary-line">Accounts returned: <strong>{reportState.generalLedger.accounts.length}</strong></p> : null}
          </div>
          ) : null}
        </div>
      </article>
    </section>
  );
}
