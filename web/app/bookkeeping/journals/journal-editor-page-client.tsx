"use client";

import { JournalEditorSection } from "../../operator-sections/journal-editor-section";
import { OperatorClient } from "../../operator-workspace-client";


export function JournalEditorPageClient({ journalId }: { journalId?: string }) {
  return (
    <OperatorClient
      activeSection="bookkeeping"
      renderSectionContent={(operator) => <JournalEditorSection operator={operator} journalId={journalId} />}
    />
  );
}