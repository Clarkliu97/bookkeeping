import Link from "next/link";

import { getServerApiBaseUrl } from "../api-base-url-server";


type HealthPayload = {
  status: string;
  environment?: string;
  checks?: Record<string, string>;
};

type RecentAlertsPayload = {
  count: number;
  items: Array<{
    code: string;
    severity: string;
    message: string;
    created_at: string;
    details?: Record<string, unknown>;
  }>;
};

type OperationsData = {
  baseUrl: string;
  health: HealthPayload | null;
  metrics: Record<string, string>;
  alerts: RecentAlertsPayload | null;
  errors: string[];
};


export const dynamic = "force-dynamic";


async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return (await response.json()) as T;
}


async function fetchText(url: string): Promise<string> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.text();
}


function parseMetrics(metricsText: string): Record<string, string> {
  const metrics: Record<string, string> = {};
  for (const line of metricsText.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const [key, value] = trimmed.split(/\s+/, 2);
    if (!key || !value || key.includes("{")) {
      continue;
    }
    metrics[key] = value;
  }
  return metrics;
}


async function getOperationsData(): Promise<OperationsData> {
  const baseUrl = await getServerApiBaseUrl();
  const errors: string[] = [];

  const [healthResult, metricsResult, alertsResult] = await Promise.allSettled([
    fetchJson<HealthPayload>(`${baseUrl}/health/ready`),
    fetchText(`${baseUrl}/metrics`),
    fetchJson<RecentAlertsPayload>(`${baseUrl}/alerts/recent`),
  ]);

  const health = healthResult.status === "fulfilled" ? healthResult.value : null;
  if (healthResult.status === "rejected") {
    errors.push("Readiness data is currently unavailable.");
  }

  const metrics = metricsResult.status === "fulfilled" ? parseMetrics(metricsResult.value) : {};
  if (metricsResult.status === "rejected") {
    errors.push("Metrics data is currently unavailable.");
  }

  const alerts = alertsResult.status === "fulfilled" ? alertsResult.value : null;
  if (alertsResult.status === "rejected") {
    errors.push("Recent alert data is currently unavailable.");
  }

  return {
    baseUrl,
    health,
    metrics,
    alerts,
    errors,
  };
}


function statusTone(status: string | undefined) {
  if (status === "ok") {
    return "pill pill-ok";
  }
  if (status === "degraded") {
    return "pill pill-warn";
  }
  return "pill";
}


export default async function OperationsPage() {
  const data = await getOperationsData();
  const requestTotal = data.metrics["bookkeeping_http_requests_total"] ?? "n/a";
  const readinessChecks = data.metrics["bookkeeping_readiness_checks_total"] ?? "n/a";
  const alertTotal = data.metrics["bookkeeping_alerts_total"] ?? "n/a";

  return (
    <main className="shell shell-operations">
      <section className="hero hero-operations">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Runtime health, alert state, and recovery procedures in one place.</h1>
          <p className="lede">
            This workflow page replaces the static status-only landing view with live operational
            signals from the API plus restore-drill guidance for routine recovery checks.
          </p>
        </div>
        <div className="hero-actions">
          <a className="button-link" href={`${data.baseUrl}/health/ready`} target="_blank" rel="noreferrer">
            Open readiness JSON
          </a>
          <a className="button-link button-link-secondary" href={`${data.baseUrl}/metrics`} target="_blank" rel="noreferrer">
            Open metrics feed
          </a>
        </div>
      </section>

      {data.errors.length > 0 ? (
        <section className="panel panel-wide banner banner-warn">
          <h2>Connection warnings</h2>
          <ul>
            {data.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="grid operations-grid">
        <article className="panel">
          <div className="panel-heading">
            <h2>Readiness</h2>
            <span className={statusTone(data.health?.status)}>{data.health?.status ?? "unknown"}</span>
          </div>
          <p>
            Environment: <strong>{data.health?.environment ?? "unavailable"}</strong>
          </p>
          <dl className="stat-list">
            <div>
              <dt>Database</dt>
              <dd>{data.health?.checks?.database ?? "unknown"}</dd>
            </div>
            <div>
              <dt>Documents</dt>
              <dd>{data.health?.checks?.documents ?? "unknown"}</dd>
            </div>
          </dl>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Metrics Snapshot</h2>
            <span className="pill">live</span>
          </div>
          <dl className="stat-list stat-list-compact">
            <div>
              <dt>Total requests</dt>
              <dd>{requestTotal}</dd>
            </div>
            <div>
              <dt>Readiness checks</dt>
              <dd>{readinessChecks}</dd>
            </div>
            <div>
              <dt>Alerts emitted</dt>
              <dd>{alertTotal}</dd>
            </div>
          </dl>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Recent Alerts</h2>
            <span className="pill">{data.alerts?.count ?? 0}</span>
          </div>
          {data.alerts && data.alerts.count > 0 ? (
            <ul className="alert-list">
              {data.alerts.items.map((item) => (
                <li key={`${item.code}-${item.created_at}`}>
                  <strong>{item.code}</strong>
                  <span>{item.severity}</span>
                  <p>{item.message}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p>No alert events have been emitted in the current process lifetime.</p>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Restore Drill</h2>
            <span className="pill">monthly</span>
          </div>
          <p>
            Use the latest backup set, run the restore workflow in maintenance mode, confirm
            readiness, then verify one document-backed record and one report path.
          </p>
          <ol className="workflow-list">
            <li>Confirm the backup set includes `database.sql`, `metadata.json`, and `documents.zip` where applicable.</li>
            <li>Run the restore script against the chosen backup directory.</li>
            <li>Check readiness, metrics, and this dashboard before reopening the system.</li>
          </ol>
        </article>
      </section>

      <section className="panel panel-wide workflow-panel">
        <div className="panel-heading">
          <h2>Workflow Entry Points</h2>
          <span className="pill">phase 12</span>
        </div>
        <div className="workflow-links">
          <Link className="action-card" href="/">
            <strong>Back to overview</strong>
            <span>Keep the broader product status visible while operational workflows expand.</span>
          </Link>
          <a className="action-card" href={`${data.baseUrl}/alerts/recent`} target="_blank" rel="noreferrer">
            <strong>Inspect alert feed</strong>
            <span>Review recent in-process alert events exposed by the API.</span>
          </a>
          <a className="action-card" href={`${data.baseUrl}/metrics`} target="_blank" rel="noreferrer">
            <strong>Review metrics output</strong>
            <span>Use the Prometheus-style endpoint for scraping or manual diagnostics.</span>
          </a>
        </div>
      </section>
    </main>
  );
}