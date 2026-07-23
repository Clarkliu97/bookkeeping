import Link from "next/link";
import type { ReactNode } from "react";

import type { SectionKey } from "./operator-routes";


export function SectionButton({
  active,
  sectionKey,
  label,
  detail,
  href,
}: {
  active: boolean;
  sectionKey: SectionKey;
  label: string;
  detail: string;
  href: string;
}) {
  return (
    <Link className={`section-nav-button${active ? " is-active" : ""}`} href={href} data-testid={`section-link-${sectionKey}`}>
      <strong>{label}</strong>
      <span>{detail}</span>
    </Link>
  );
}


export function StatusPill({ value }: { value: string | null | undefined }) {
  const normalized = (value ?? "unknown").toLowerCase();
  let tone = "pill";
  if (["approved", "active", "posted", "confirmed", "completed", "matched", "resolved"].includes(normalized)) {
    tone = "pill pill-ok";
  } else if (["warning", "review", "draft", "in_progress", "staged", "locked", "superuser"].includes(normalized)) {
    tone = "pill pill-warn";
  }
  return <span className={tone}>{normalized.replaceAll("_", " ")}</span>;
}


export function Field({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={`app-field${wide ? " app-field-wide" : ""}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}


export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

export function WorkspaceTabs<T extends string>({
  label,
  activeTab,
  options,
  onChange,
}: {
  label: string;
  activeTab: T;
  options: Array<{ key: T; label: string; detail: string; count?: number }>;
  onChange: (tab: T) => void;
}) {
  return (
    <nav className="workspace-tabs" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.key}
          className={`workspace-tab${activeTab === option.key ? " is-active" : ""}`}
          type="button"
          aria-label={option.label}
          aria-current={activeTab === option.key ? "page" : undefined}
          onClick={() => onChange(option.key)}
        >
          <span className="workspace-tab-label">
            <strong>{option.label}</strong>
            {option.count !== undefined ? <span className="workspace-tab-count">{option.count}</span> : null}
          </span>
          <small>{option.detail}</small>
        </button>
      ))}
    </nav>
  );
}


export function ProcessingVeil({ label }: { label: string | null }) {
  if (!label) {
    return null;
  }

  return (
    <div className="processing-veil" role="status" aria-live="polite" aria-label={label}>
      <div className="processing-indicator" aria-hidden="true">
        {Array.from({ length: 8 }, (_, index) => <span key={index} />)}
      </div>
      <div className="processing-label">{label}</div>
    </div>
  );
}
