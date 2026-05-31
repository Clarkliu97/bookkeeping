import { JournalEditorPageClient } from "../journal-editor-page-client";


export const dynamic = "force-dynamic";


export default async function JournalDetailPage({ params }: { params: Promise<{ journalId: string }> }) {
  const { journalId } = await params;
  return <JournalEditorPageClient journalId={journalId} />;
}