"use client";

import Link from "next/link";
import { startTransition, useEffect, useState } from "react";

import { resolveClientApiBaseUrl } from "../api-base-url-client";

import {
  createDefaultWorkbenchContext,
  contextFieldGroups,
  defaultWorkbenchContext,
  type ActionConfig,
  type ContextKey,
  type WorkbenchContext,
  workbenchSections,
} from "./workbench-data";


type ExecutionResult = {
  statusLabel: string;
  responseKind: "json" | "text" | "binary" | "error";
  body: string;
  contextUpdates: string[];
};

type RequestCardProps = {
  action: ActionConfig;
  context: WorkbenchContext;
  onContextUpdate: (updates: Array<{ target: ContextKey; value: string }>) => void;
};


const STORAGE_KEY = "bookkeeping-tax-workbench-state";


function resolveTemplate(input: string, context: WorkbenchContext) {
  return input.replace(/\{\{(.*?)\}\}/g, (_, rawKey: string) => {
    const key = rawKey.trim() as ContextKey;
    return context[key] ?? "";
  });
}


function findMissingPlaceholders(input: string, context: WorkbenchContext) {
  const matches = Array.from(input.matchAll(/\{\{(.*?)\}\}/g));
  const missing = new Set<string>();
  for (const match of matches) {
    const key = match[1].trim() as ContextKey;
    if (!context[key]) {
      missing.add(key);
    }
  }
  return Array.from(missing);
}


function resolveBaseUrl(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}


function hasContextValue(value: string) {
  return value !== "";
}


function isActionVisible(action: ActionConfig, context: WorkbenchContext) {
  if (!action.visibleWhen || action.visibleWhen.length === 0) {
    return true;
  }

  return action.visibleWhen.every((rule) => {
    const value = context[rule.key];
    if (rule.present && !hasContextValue(value)) {
      return false;
    }
    if (rule.absent && hasContextValue(value)) {
      return false;
    }
    if (rule.equals !== undefined && value !== rule.equals) {
      return false;
    }
    if (rule.oneOf && !rule.oneOf.includes(value)) {
      return false;
    }
    return true;
  });
}


function readPath(payload: unknown, path: string): unknown {
  const parts = path.split(".").filter(Boolean);
  let current: unknown = payload;
  for (const part of parts) {
    if (current === null || current === undefined) {
      return undefined;
    }
    if (Array.isArray(current)) {
      const index = Number(part);
      if (Number.isNaN(index)) {
        return undefined;
      }
      current = current[index];
      continue;
    }
    if (typeof current === "object") {
      current = (current as Record<string, unknown>)[part];
      continue;
    }
    return undefined;
  }
  return current;
}


function inferFilename(headers: Headers, fallback: string) {
  const contentDisposition = headers.get("content-disposition");
  if (!contentDisposition) {
    return fallback;
  }
  const match = contentDisposition.match(/filename="([^"]+)"/i);
  return match?.[1] ?? fallback;
}


function triggerDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
}


function ResultPreview({ result }: { result: ExecutionResult | null }) {
  if (!result) {
    return <p className="workbench-placeholder">No request executed yet.</p>;
  }

  return (
    <div className="result-box">
      <div className="result-meta">
        <span className="status-chip">{result.statusLabel}</span>
        {result.contextUpdates.length > 0 ? <span className="status-chip">Context: {result.contextUpdates.join(", ")}</span> : null}
      </div>
      <pre>{result.body}</pre>
    </div>
  );
}


function JsonRequestCard({ action, context, onContextUpdate }: RequestCardProps) {
  const [pathDraft, setPathDraft] = useState(action.pathTemplate);
  const [bodyDraft, setBodyDraft] = useState(action.kind === "json" ? action.defaultBody ?? "" : "");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ExecutionResult | null>(null);

  const missing = [
    ...findMissingPlaceholders(pathDraft, context),
    ...findMissingPlaceholders(bodyDraft, context),
  ].filter((value, index, items) => items.indexOf(value) === index);

  async function execute() {
    const resolvedPath = resolveTemplate(pathDraft, context);
    const url = `${resolveBaseUrl(context.baseUrl)}${resolvedPath}`;
    const headers = new Headers();
    if (action.auth) {
      const token = context[action.auth];
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    }

    let requestBody: string | undefined;
    if (action.kind === "json" && action.method !== "GET" && bodyDraft.trim()) {
      try {
        requestBody = JSON.stringify(JSON.parse(resolveTemplate(bodyDraft, context)));
        headers.set("Content-Type", "application/json");
      } catch (error) {
        setResult({
          statusLabel: "Client error",
          responseKind: "error",
          body: error instanceof Error ? error.message : "Invalid JSON payload",
          contextUpdates: [],
        });
        return;
      }
    }

    setPending(true);
    try {
      const response = await fetch(url, {
        method: action.method,
        headers,
        body: requestBody,
      });

      if (action.responseType === "binary") {
        const blob = await response.blob();
        const filename = inferFilename(response.headers, `${action.title.toLowerCase().replace(/\s+/g, "-")}.bin`);
        triggerDownload(blob, filename);
        setResult({
          statusLabel: `${response.status} ${response.statusText}`,
          responseKind: "binary",
          body: `Downloaded file: ${filename}`,
          contextUpdates: [],
        });
        return;
      }

      const rawText = await response.text();
      const responseKind = action.responseType === "text" ? "text" : "json";
      let parsed: unknown = rawText;
      let pretty = rawText;

      if (responseKind === "json") {
        try {
          parsed = rawText ? JSON.parse(rawText) : {};
          pretty = JSON.stringify(parsed, null, 2);
        } catch {
          pretty = rawText;
        }
      }

      const contextUpdates: Array<{ target: ContextKey; value: string }> = [];
      if (response.ok && action.clearOnSuccess) {
        for (const key of action.clearOnSuccess) {
          contextUpdates.push({ target: key, value: "" });
        }
      }
      if (response.ok && action.capture && responseKind === "json") {
        for (const capture of action.capture) {
          const value = readPath(parsed, capture.path);
          if (value !== undefined && value !== null && value !== "") {
            contextUpdates.push({ target: capture.target, value: String(value) });
          }
        }
      }
      if (contextUpdates.length > 0) {
        onContextUpdate(contextUpdates);
      }

      setResult({
        statusLabel: `${response.status} ${response.statusText}`,
        responseKind,
        body: pretty || "(empty response)",
        contextUpdates: contextUpdates.map((item) => item.target),
      });
    } catch (error) {
      setResult({
        statusLabel: "Network error",
        responseKind: "error",
        body: error instanceof Error ? error.message : "Request failed",
        contextUpdates: [],
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <article className="panel request-card">
      <div className="panel-heading">
        <div>
          <span className={`method-chip method-chip-${action.method.toLowerCase()}`}>{action.method}</span>
          <h3>{action.title}</h3>
        </div>
      </div>
      <p>{action.description}</p>
      <label className="workbench-field">
        <span>Path</span>
        <input value={pathDraft} onChange={(event) => setPathDraft(event.target.value)} />
      </label>
      {action.kind === "json" && action.method !== "GET" ? (
        <label className="workbench-field">
          <span>JSON body</span>
          <textarea value={bodyDraft} onChange={(event) => setBodyDraft(event.target.value)} rows={12} />
        </label>
      ) : null}
      {missing.length > 0 ? <p className="workbench-warning">Missing context values: {missing.join(", ")}</p> : null}
      {action.notes && action.notes.length > 0 ? (
        <ul className="hint-list">
          {action.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      <div className="request-actions">
        <button className="button-link button-link-small" type="button" onClick={execute} disabled={pending}>
          {pending ? "Running..." : "Run request"}
        </button>
      </div>
      <ResultPreview result={result} />
    </article>
  );
}


function UploadRequestCard({ action, context, onContextUpdate }: RequestCardProps) {
  const [pathDraft, setPathDraft] = useState(action.pathTemplate);
  const [fieldDrafts, setFieldDrafts] = useState<Record<string, string>>(
    Object.fromEntries(action.kind === "upload" ? action.fields.map((field) => [field.name, field.valueTemplate]) : []),
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ExecutionResult | null>(null);

  const missing = [
    ...findMissingPlaceholders(pathDraft, context),
    ...Object.values(fieldDrafts).flatMap((value) => findMissingPlaceholders(value, context)),
  ].filter((value, index, items) => items.indexOf(value) === index);

  async function execute() {
    const resolvedPath = resolveTemplate(pathDraft, context);
    const url = `${resolveBaseUrl(context.baseUrl)}${resolvedPath}`;
    const headers = new Headers();
    if (action.auth) {
      const token = context[action.auth];
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    }
    if (!selectedFile) {
      setResult({
        statusLabel: "Client error",
        responseKind: "error",
        body: "Select a file before executing the upload request.",
        contextUpdates: [],
      });
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    for (const [key, value] of Object.entries(fieldDrafts)) {
      const resolvedValue = resolveTemplate(value, context);
      if (resolvedValue !== "") {
        formData.append(key, resolvedValue);
      }
    }

    setPending(true);
    try {
      const response = await fetch(url, {
        method: action.method,
        headers,
        body: formData,
      });
      const rawText = await response.text();
      let parsed: unknown = {};
      let pretty = rawText;
      try {
        parsed = rawText ? JSON.parse(rawText) : {};
        pretty = JSON.stringify(parsed, null, 2);
      } catch {
        pretty = rawText;
      }

      const contextUpdates: Array<{ target: ContextKey; value: string }> = [];
      if (response.ok && action.clearOnSuccess) {
        for (const key of action.clearOnSuccess) {
          contextUpdates.push({ target: key, value: "" });
        }
      }
      if (response.ok && action.capture) {
        for (const capture of action.capture) {
          const value = readPath(parsed, capture.path);
          if (value !== undefined && value !== null && value !== "") {
            contextUpdates.push({ target: capture.target, value: String(value) });
          }
        }
      }
      if (contextUpdates.length > 0) {
        onContextUpdate(contextUpdates);
      }

      setResult({
        statusLabel: `${response.status} ${response.statusText}`,
        responseKind: "json",
        body: pretty || "(empty response)",
        contextUpdates: contextUpdates.map((item) => item.target),
      });
    } catch (error) {
      setResult({
        statusLabel: "Network error",
        responseKind: "error",
        body: error instanceof Error ? error.message : "Upload failed",
        contextUpdates: [],
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <article className="panel request-card">
      <div className="panel-heading">
        <div>
          <span className={`method-chip method-chip-${action.method.toLowerCase()}`}>{action.method}</span>
          <h3>{action.title}</h3>
        </div>
      </div>
      <p>{action.description}</p>
      <label className="workbench-field">
        <span>Path</span>
        <input value={pathDraft} onChange={(event) => setPathDraft(event.target.value)} />
      </label>
      {action.kind === "upload" ? (
        <div className="upload-grid">
          {action.fields.map((field) => (
            <label className="workbench-field" key={field.name}>
              <span>{field.name}</span>
              <input
                value={fieldDrafts[field.name] ?? ""}
                onChange={(event) => setFieldDrafts((current) => ({ ...current, [field.name]: event.target.value }))}
              />
            </label>
          ))}
          <label className="workbench-field">
            <span>File</span>
            <input type="file" accept={action.accept} onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
          </label>
        </div>
      ) : null}
      {missing.length > 0 ? <p className="workbench-warning">Missing context values: {missing.join(", ")}</p> : null}
      <div className="request-actions">
        <button className="button-link button-link-small" type="button" onClick={execute} disabled={pending}>
          {pending ? "Uploading..." : "Run request"}
        </button>
      </div>
      <ResultPreview result={result} />
    </article>
  );
}


function RequestCard(props: RequestCardProps) {
  if (props.action.kind === "upload") {
    return <UploadRequestCard {...props} />;
  }
  return <JsonRequestCard {...props} />;
}


export function WorkbenchClient() {
  const [context, setContext] = useState<WorkbenchContext>(defaultWorkbenchContext);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const baseContext = createDefaultWorkbenchContext();
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as Partial<WorkbenchContext>;
        setContext({
          ...baseContext,
          ...parsed,
          baseUrl: resolveClientApiBaseUrl(parsed.baseUrl),
        });
      } catch {
        setContext({ ...baseContext, baseUrl: resolveClientApiBaseUrl() });
      }
    } else {
      setContext({ ...baseContext, baseUrl: resolveClientApiBaseUrl() });
    }
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded) {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(context));
  }, [context, loaded]);

  function updateContext(key: ContextKey, value: string) {
    startTransition(() => {
      setContext((current) => ({ ...current, [key]: value }));
    });
  }

  function applyContextUpdates(updates: Array<{ target: ContextKey; value: string }>) {
    if (updates.length === 0) {
      return;
    }
    startTransition(() => {
      setContext((current) => {
        const next = { ...current };
        for (const update of updates) {
          next[update.target] = update.value;
        }
        return next;
      });
    });
  }

  function resetContext() {
    startTransition(() => {
      setContext({ ...createDefaultWorkbenchContext(), baseUrl: resolveClientApiBaseUrl() });
    });
  }

  return (
    <main className="shell shell-workbench">
      <section className="hero hero-operations workbench-hero">
        <div className="hero-copy">
          <p className="eyebrow">Frontend Workbench</p>
          <h1>Directly test every implemented backend workflow from the browser.</h1>
          <p className="lede">
            This internal workbench replaces the Swagger-only testing path with a browser-accessible
            client shell. It keeps auth, company context, and workflow IDs in one place so you can
            drive the ledger, BAS, fixed asset, tax workpaper, and operational flows directly from
            the frontend.
          </p>
        </div>
        <div className="hero-actions">
          <Link className="button-link" href="/operations">
            Open operations dashboard
          </Link>
          <Link className="button-link button-link-secondary" href="/">
            Back to overview
          </Link>
        </div>
      </section>

      <section className="panel panel-wide context-panel">
        <div className="panel-heading">
          <h2>Persisted Context</h2>
          <div className="request-actions request-actions-inline">
            <button className="button-link button-link-small button-link-secondary" type="button" onClick={resetContext}>
              Reset context
            </button>
          </div>
        </div>
        <p>
          Values entered here are reused across the request cards below and saved in your browser
          for this workspace.
        </p>
        <div className="context-grid">
          {contextFieldGroups.map((group) => (
            <section className="context-group" key={group.title}>
              <h3>{group.title}</h3>
              <div className="context-fields">
                {group.fields.map((field) => (
                  <label className="workbench-field" key={field.key}>
                    <span>{field.label}</span>
                    <input
                      value={context[field.key]}
                      onChange={(event) => updateContext(field.key, event.target.value)}
                      placeholder={field.placeholder}
                    />
                  </label>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>

      <section className="sections-stack">
        {workbenchSections.map((section, index) => {
          const visibleCards = section.cards.filter((action) => isActionVisible(action, context));

          return (
            <details className="panel panel-wide workbench-section" key={section.title} open={index === 0}>
              <summary className="section-toggle">
                <div>
                  <h2>{section.title}</h2>
                  <p>{section.description}</p>
                </div>
                <span className="pill">{visibleCards.length} actions</span>
              </summary>
              <div className="workbench-grid">
                {visibleCards.length > 0 ? (
                  visibleCards.map((action) => (
                    <RequestCard
                      action={action}
                      context={context}
                      onContextUpdate={applyContextUpdates}
                      key={`${section.title}-${action.title}`}
                    />
                  ))
                ) : (
                  <p className="workbench-placeholder">No actions are available for the current context and workflow state.</p>
                )}
              </div>
            </details>
          );
        })}
      </section>
    </main>
  );
}
