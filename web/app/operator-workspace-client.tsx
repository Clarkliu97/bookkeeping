"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { ReactNode } from "react";

import { BankingSection } from "./operator-sections/banking-section";
import { BookkeepingSection } from "./operator-sections/bookkeeping-section";
import { DashboardSection } from "./operator-sections/dashboard-section";
import { EmploymentSection } from "./operator-sections/employment-section";
import { ReportsSection } from "./operator-sections/reports-section";
import { SetupSection } from "./operator-sections/setup-section";
import { YearEndSection } from "./operator-sections/year-end-section";
import { createDefaultConfiguration, type OperatorState, useOperatorState } from "./operator-state";
import { sectionOptions, type SectionKey } from "./operator-routes";
import { EmptyState, Field, ProcessingVeil, SectionButton, StatusPill } from "./operator-ui";


export function OperatorClient({ activeSection, renderSectionContent }: { activeSection: SectionKey; renderSectionContent?: (operator: OperatorState) => ReactNode }) {
  const operator = useOperatorState();
  const [floatingMessages, setFloatingMessages] = useState(
    operator.flashMessage ? [operator.flashMessage] : [],
  );

  useEffect(() => {
    if (!operator.flashMessage) {
      return;
    }

    const message = operator.flashMessage;
    const messageId = message.id;
    setFloatingMessages((current) => [...current.filter((item) => item.id !== messageId), message].slice(-4));
    const timeoutId = window.setTimeout(() => {
      setFloatingMessages((current) => current.filter((item) => item.id !== messageId));
    }, 4200);

    return () => window.clearTimeout(timeoutId);
  }, [operator.flashMessage]);

  const dismissFloatingMessage = (messageId: number) => {
    setFloatingMessages((current) => current.filter((item) => item.id !== messageId));
  };

  const floatingNotice = floatingMessages.length ? (
    <div className="floating-flash-stack" aria-live="polite" aria-atomic="false">
      {floatingMessages.map((message) => (
        <section
          key={message.id}
          className={`floating-flash floating-flash-${message.tone}`}
          role={message.tone === "error" ? "alert" : "status"}
        >
          <div className="floating-flash-header">
            <strong>{message.tone === "success" ? "Success" : message.tone === "error" ? "Error" : "Notice"}</strong>
            <button
              className="floating-flash-dismiss"
              type="button"
              aria-label="Dismiss notification"
              onClick={() => dismissFloatingMessage(message.id)}
            >
              Dismiss
            </button>
          </div>
          <p>{message.text}</p>
        </section>
      ))}
    </div>
  ) : null;

  if (!operator.token) {
    return (
      <main className="shell shell-operator" data-testid="operator-shell-anonymous">
        {floatingNotice}
        <section className="hero hero-operator">
          <div className="hero-copy">
            <p className="eyebrow">Internal Operator Application</p>
            <h1>Run bookkeeping, review, BAS, and year-end workflows without API cards.</h1>
            <p className="lede">
              This production-facing workspace replaces the status landing page with a guided internal app.
              Sign in to reach company-aware workflow screens for setup, bookkeeping, banking, reporting, fixed assets,
              and tax workpaper support.
            </p>
          </div>
          <div className="hero-actions">
            <Link className="button-link button-link-secondary" href="/operations">
              Operations
            </Link>
            <Link className="button-link button-link-secondary" href="/workbench">
              Diagnostic workbench
            </Link>
          </div>
        </section>

        {operator.flashMessage ? <section className={`panel banner banner-${operator.flashMessage.tone}`}><p>{operator.flashMessage.text}</p></section> : null}

        <section className="grid auth-grid">
          <article className="panel auth-panel">
            <h2>Sign in</h2>
            <div className="form-grid two-up">
              <Field label="API base URL" wide>
                <input value={operator.baseUrl} onChange={(event) => operator.setBaseUrl(event.target.value)} />
              </Field>
              <Field label="Email">
                <input value={operator.loginDraft.email} onChange={(event) => operator.setLoginDraft((current) => ({ ...current, email: event.target.value }))} />
              </Field>
              <Field label="Password">
                <input type="password" value={operator.loginDraft.password} onChange={(event) => operator.setLoginDraft((current) => ({ ...current, password: event.target.value }))} />
              </Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small" type="button" data-testid="login-submit" onClick={() => operator.runAction("Logging in", async () => operator.handleLogin("login"))}>
                Log in
              </button>
            </div>
          </article>

          <article className="panel auth-panel">
            <h2>Bootstrap first admin</h2>
            <div className="form-grid two-up">
              <Field label="Email">
                <input value={operator.bootstrapDraft.email} onChange={(event) => operator.setBootstrapDraft((current) => ({ ...current, email: event.target.value }))} />
              </Field>
              <Field label="Full name">
                <input value={operator.bootstrapDraft.full_name} onChange={(event) => operator.setBootstrapDraft((current) => ({ ...current, full_name: event.target.value }))} />
              </Field>
              <Field label="Password" wide>
                <input type="password" value={operator.bootstrapDraft.password} onChange={(event) => operator.setBootstrapDraft((current) => ({ ...current, password: event.target.value }))} />
              </Field>
            </div>
            <div className="request-actions">
              <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => operator.runAction("Bootstrapping admin", async () => operator.handleLogin("bootstrap"))}>
                Bootstrap admin
              </button>
            </div>
          </article>
        </section>
      </main>
    );
  }

  let sectionContent: ReactNode = <DashboardSection operator={operator} />;
  if (activeSection === "setup") {
    sectionContent = <SetupSection operator={operator} />;
  } else if (activeSection === "bookkeeping") {
    sectionContent = <BookkeepingSection operator={operator} />;
  } else if (activeSection === "banking") {
    sectionContent = <BankingSection operator={operator} />;
  } else if (activeSection === "employment") {
    sectionContent = <EmploymentSection operator={operator} />;
  } else if (activeSection === "reports") {
    sectionContent = <ReportsSection operator={operator} />;
  } else if (activeSection === "year_end") {
    sectionContent = <YearEndSection operator={operator} />;
  }

  if (renderSectionContent) {
    sectionContent = renderSectionContent(operator);
  }

  return (
    <main className="shell shell-operator" data-testid="operator-shell-authenticated">
      {floatingNotice}
      <ProcessingVeil label={operator.busyLabel} />
      <section className="hero hero-operator hero-operator-compact">
        <div className="hero-copy">
          <p className="eyebrow">Operator Workspace</p>
          <h1>Internal bookkeeping and tax support operations.</h1>
          <p className="lede">
            Work from guided internal screens instead of raw API actions. The application stays review-oriented,
            traceable, and scoped to manual form-entry support rather than lodgment.
          </p>
        </div>
        <div className="hero-actions">
          <button className="button-link button-link-small" type="button" onClick={() => operator.runAction("Refreshing workspace", operator.refreshAll)}>
            Refresh workspace
          </button>
          <button className="button-link button-link-small button-link-secondary" type="button" onClick={operator.logout}>
            Sign out
          </button>
        </div>
      </section>

      {operator.flashMessage ? (
        <section className={`panel banner banner-${operator.flashMessage.tone}`}>
          <p>{operator.flashMessage.text}</p>
        </section>
      ) : null}

      <section className="operator-layout">
        <aside className="panel operator-sidebar">
          <div className="panel-heading">
            <h2>Session</h2>
            {operator.busyLabel ? <span className="pill">{operator.busyLabel}</span> : null}
          </div>
          <div className="session-block">
            <strong>{operator.currentUser?.full_name ?? "Authenticated user"}</strong>
            <span>{operator.currentUser?.email ?? ""}</span>
            <StatusPill value={operator.currentUser?.is_superuser ? "superuser" : "standard"} />
          </div>
          <div className="form-grid">
            <Field label="Company">
              <select value={operator.selectedCompanyId} onChange={(event) => operator.setSelectedCompanyId(event.target.value)}>
                <option value="">Select company</option>
                {operator.companyOptionList.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </Field>
          </div>
          <div className="section-nav">
            {sectionOptions.map((item) => (
              <SectionButton key={item.key} active={activeSection === item.key} sectionKey={item.key} label={item.label} detail={item.detail} href={item.href} />
            ))}
          </div>
          <div className="sidebar-links">
            <Link href="/operations">Operations</Link>
            <Link href="/workbench">Diagnostic workbench</Link>
            <a href={`${operator.baseUrl.replace(/\/$/, "")}/docs`} target="_blank" rel="noreferrer">Swagger</a>
          </div>
        </aside>

        <section className="operator-content">
          {!operator.selectedCompanyId ? (
            <article className="panel panel-wide">
              <EmptyState title="Create or select a company" detail="Start by creating the first company record or choose an existing one to load the operator workflow panels." />
              <div className="form-grid two-up">
                <Field label="Legal name"><input value={operator.newCompanyDraft.legal_name} onChange={(event) => operator.setNewCompanyDraft((current) => ({ ...current, legal_name: event.target.value }))} /></Field>
                <Field label="Trading name"><input value={operator.newCompanyDraft.trading_name} onChange={(event) => operator.setNewCompanyDraft((current) => ({ ...current, trading_name: event.target.value }))} /></Field>
                <Field label="ABN"><input value={operator.newCompanyDraft.abn} onChange={(event) => operator.setNewCompanyDraft((current) => ({ ...current, abn: event.target.value }))} /></Field>
                <Field label="ACN"><input value={operator.newCompanyDraft.acn} onChange={(event) => operator.setNewCompanyDraft((current) => ({ ...current, acn: event.target.value }))} /></Field>
                <Field label="Entity type"><input value={operator.newCompanyDraft.entity_type} onChange={(event) => operator.setNewCompanyDraft((current) => ({ ...current, entity_type: event.target.value }))} /></Field>
                <Field label="BAS frequency"><select value={operator.newCompanyDraft.initial_configuration.bas_frequency} onChange={(event) => operator.setNewCompanyDraft((current) => ({ ...current, initial_configuration: { ...current.initial_configuration, bas_frequency: event.target.value } }))}><option value="quarterly">Quarterly</option><option value="monthly">Monthly</option></select></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" data-testid="create-company" onClick={() => operator.runAction("Creating company", async () => {
                  const company = await operator.request<{ id: string; legal_name: string }>("/api/companies", "POST", {
                    ...operator.newCompanyDraft,
                    initial_configuration: operator.newCompanyDraft.initial_configuration ?? createDefaultConfiguration(),
                  });
                  operator.setSelectedCompanyId(company.id);
                  operator.showMessage("success", `Created ${company.legal_name}.`);
                  await operator.refreshAll(company.id);
                })}>Create company</button>
              </div>
            </article>
          ) : sectionContent}
        </section>
      </section>
    </main>
  );
}
