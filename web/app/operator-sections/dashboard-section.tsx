import type { OperatorState } from "../operator-state";
import { StatusPill } from "../operator-ui";


export function DashboardSection({ operator }: { operator: OperatorState }) {
  const { selectedCompany, accounts, periods, journals, bankImports, basRunDetail, adminOverview, reconciliationSessions, basPeriods, fixedAssetRegister, depreciationRuns, taxPacks } = operator;

  return (
    <section className="sections-stack">
      <article className="panel panel-wide">
        <div className="panel-heading">
          <div>
            <h2>{selectedCompany?.legal_name}</h2>
            <p>Primary operator dashboard for bookkeeping, review, and support pack preparation.</p>
          </div>
          <StatusPill value={selectedCompany?.is_active ? "active" : "inactive"} />
        </div>
        <div className="stats-grid">
          <div className="stat-card"><span>Accounts</span><strong>{accounts.length}</strong></div>
          <div className="stat-card"><span>Open periods</span><strong>{periods.filter((item) => item.status !== "locked").length}</strong></div>
          <div className="stat-card"><span>Draft journals</span><strong>{journals.filter((item) => item.status === "draft").length}</strong></div>
          <div className="stat-card"><span>Staged imports</span><strong>{bankImports.filter((item) => item.status === "staged").length}</strong></div>
          <div className="stat-card"><span>Current BAS warnings</span><strong>{basRunDetail?.warning_count ?? 0}</strong></div>
          <div className="stat-card"><span>Tax packs</span><strong>{taxPacks.length}</strong></div>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading">
          <h2>Attention queue</h2>
          {adminOverview ? <span className="pill">Admin active</span> : null}
        </div>
        <div className="attention-grid">
          <div>
            <strong>Bookkeeping</strong>
            <ul>
              <li>{periods.filter((item) => item.status === "draft").length} draft periods</li>
              <li>{journals.filter((item) => item.status === "draft").length} draft journals</li>
              <li>{operator.documents.length} source documents on file</li>
            </ul>
          </div>
          <div>
            <strong>Banking and BAS</strong>
            <ul>
              <li>{bankImports.filter((item) => item.status === "staged").length} staged bank imports</li>
              <li>{reconciliationSessions.filter((item) => item.status !== "completed").length} active reconciliation sessions</li>
              <li>{basPeriods.filter((item) => item.status !== "locked").length} editable BAS periods</li>
            </ul>
          </div>
          <div>
            <strong>Year-end support</strong>
            <ul>
              <li>{(fixedAssetRegister?.assets ?? []).filter((item) => item.status === "active").length} active fixed assets</li>
              <li>{depreciationRuns.filter((item) => item.status === "draft").length} draft depreciation runs</li>
              <li>{taxPacks.filter((item) => item.status !== "approved" && item.status !== "exported").length} open tax packs</li>
            </ul>
          </div>
        </div>
      </article>
    </section>
  );
}