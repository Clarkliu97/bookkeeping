import Link from "next/link";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import { formatDateTime, formatMoney, type GeneralLedgerReport, type OperatorState } from "../operator-state";
import { JournalEditorSection } from "./journal-editor-section";
import { Field, StatusPill } from "../operator-ui";


function buildGeneralLedgerQuery(filters: { start_date: string; end_date: string; account_id: string }) {
  const query = new URLSearchParams();
  if (filters.start_date) {
    query.set("start_date", filters.start_date);
  }
  if (filters.end_date) {
    query.set("end_date", filters.end_date);
  }
  if (filters.account_id) {
    query.set("account_id", filters.account_id);
  }
  query.set("include_draft", "true");
  return query.toString();
}


function countLedgerEntries(report: GeneralLedgerReport | null) {
  return (report?.accounts ?? []).reduce((total, account) => total + account.entries.length, 0);
}


function formatFileSize(byteSize: number) {
  if (byteSize < 1024) {
    return `${byteSize} B`;
  }
  return `${Math.round(byteSize / 1024)} KB`;
}


function normalizeSearchValue(value: string | null | undefined) {
  return (value ?? "").trim().toLowerCase();
}


function inferDocumentMediaType(mediaType: string | null | undefined, filename: string | null | undefined) {
  const normalizedMediaType = (mediaType ?? "").trim().toLowerCase();
  const normalizedFilename = (filename ?? "").trim().toLowerCase();

  if (normalizedMediaType.startsWith("image/")) {
    return normalizedMediaType;
  }

  if (
    normalizedMediaType === "application/pdf"
    || normalizedMediaType === "application/x-pdf"
    || normalizedMediaType === "application/acrobat"
    || normalizedMediaType === "applications/vnd.pdf"
    || normalizedMediaType === "text/pdf"
    || normalizedFilename.endsWith(".pdf")
  ) {
    return "application/pdf";
  }

  if (normalizedFilename.endsWith(".png")) {
    return "image/png";
  }
  if (normalizedFilename.endsWith(".jpg") || normalizedFilename.endsWith(".jpeg")) {
    return "image/jpeg";
  }
  if (normalizedFilename.endsWith(".webp")) {
    return "image/webp";
  }
  if (normalizedFilename.endsWith(".gif")) {
    return "image/gif";
  }

  return normalizedMediaType || null;
}


function isImageDocument(mediaType: string | null | undefined, filename?: string | null) {
  return (inferDocumentMediaType(mediaType, filename) ?? "").startsWith("image/");
}


function isPdfDocument(mediaType: string | null | undefined, filename?: string | null) {
  return inferDocumentMediaType(mediaType, filename) === "application/pdf";
}


function formatDocumentBadge(mediaType: string | null | undefined, filename?: string | null) {
  if (isImageDocument(mediaType, filename)) {
    return "Image";
  }
  if (isPdfDocument(mediaType, filename)) {
    return "PDF";
  }
  return "File";
}


let pdfJsModulePromise: Promise<typeof import("pdfjs-dist/legacy/webpack.mjs")> | null = null;


async function loadPdfJsModule() {
  pdfJsModulePromise ??= import("pdfjs-dist/legacy/webpack.mjs");
  return pdfJsModulePromise;
}


async function loadPdfDocument(previewBlob: Blob) {
  const pdfjs = await loadPdfJsModule();
  return pdfjs.getDocument({ data: new Uint8Array(await previewBlob.arrayBuffer()) }).promise;
}


type JournalRecommendationModel = {
  id: string;
  label: string;
  provider: string;
  supports_vision: boolean;
  input_cost_per_million_tokens_usd: string;
  output_cost_per_million_tokens_usd: string;
  estimated_cost_per_1000_calls_usd: string;
  estimated_input_tokens_per_call: number;
  estimated_output_tokens_per_call: number;
  pricing_note: string;
};


type JournalRecommendationDocument = {
  id: string;
  document_id: string;
  display_order: number;
  original_filename: string;
  media_type: string | null;
  byte_size: number;
  created_at: string;
};


type JournalRecommendationLine = {
  id: string;
  line_number: number;
  description: string | null;
  explanation: string | null;
  suggested_account_id: string | null;
  suggested_account_code: string | null;
  suggested_tax_code_id: string | null;
  suggested_tax_code_code: string | null;
  suggested_reporting_category_id: string | null;
  suggested_reporting_category_code: string | null;
  debit_amount: string;
  credit_amount: string;
};


type JournalRecommendationProposal = {
  id: string;
  proposal_type: string;
  status: string;
  suggested_code: string;
  suggested_name: string;
  suggested_attributes_json: Record<string, unknown> | null;
  rationale: string | null;
};


type JournalRecommendationSearchSource = {
  title: string | null;
  url: string;
  domain: string | null;
};


type JournalRecommendationDetail = {
  id: string;
  status: string;
  provider_name: string;
  provider_model: string;
  user_context_note: string | null;
  extracted_entry_date: string | null;
  target_accounting_period_id: string | null;
  accepted_journal_entry_id: string | null;
  analysis_summary: string | null;
  confidence_summary: string | null;
  warning_text: string | null;
  failure_reason: string | null;
  documents: JournalRecommendationDocument[];
  lines: JournalRecommendationLine[];
  proposals: JournalRecommendationProposal[];
  search_sources: JournalRecommendationSearchSource[];
};


type RemovableDocumentLink = {
  id: string;
};


type JournalEvidenceItem = OperatorState["journalEvidence"][number];


type DocumentPreviewState = {
  status: "loading" | "ready" | "error";
  url: string | null;
  error: string | null;
  filename: string;
  media_type: string | null;
};


type ActiveEvidenceViewer = {
  documentId: string;
  filename: string;
  media_type: string | null;
};


type PdfPreviewState = {
  thumbnailStatus: "idle" | "loading" | "ready" | "error";
  thumbnailUrl: string | null;
  fullStatus: "idle" | "loading" | "ready" | "error";
  pageImageUrls: string[];
  error: string | null;
};


export function BookkeepingSection({ operator }: { operator: OperatorState }) {
  const {
    categories,
    periods,
    selectedPeriodId,
    setSelectedPeriodId,
    selectedPeriod,
    periodDraft,
    setPeriodDraft,
    periodActionNote,
    setPeriodActionNote,
    runAction,
    request,
    selectedCompanyId,
    showMessage,
    refreshAll,
    journals,
    selectedJournalId,
    setSelectedJournalId,
    selectedJournal,
    journalEvidence,
    generalLedgerFilters,
    setGeneralLedgerFilters,
    reportState,
    setReportState,
    periodOptionList,
    accounts,
    accountOptionList,
    activeAccountOptionList,
    taxCodes,
    taxCodeOptionList,
    activeTaxCodeOptionList,
    documents,
    selectedDocumentId,
    setSelectedDocumentId,
    documentFile,
    setDocumentFile,
    documentNote,
    setDocumentNote,
    selectedDocument,
    documentDraft,
    setDocumentDraft,
    documentLinkDraft,
    setDocumentLinkDraft,
    selectedDocumentLink,
    documentLinks,
    selectedDocumentLinkId,
    setSelectedDocumentLinkId,
    selectedBasRunId,
    selectedTaxPackId,
    downloadFromApi,
    loadJournalEvidence,
    confirmDanger,
    busyLabel,
  } = operator;

  const generalLedgerEntryCount = countLedgerEntries(reportState.generalLedger);
  const [expandedJournalId, setExpandedJournalId] = useState("");
  const [ledgerPreviewJournalId, setLedgerPreviewJournalId] = useState("");
  const [journalEditorJournalId, setJournalEditorJournalId] = useState<string | undefined>(undefined);
  const [isJournalEditorOpen, setIsJournalEditorOpen] = useState(false);
  const [journalSearchQuery, setJournalSearchQuery] = useState("");
  const [journalStatusFilter, setJournalStatusFilter] = useState("");
  const [ledgerSearchQuery, setLedgerSearchQuery] = useState("");
  const [ledgerStatusFilter, setLedgerStatusFilter] = useState("");
  const [recommendationModels, setRecommendationModels] = useState<JournalRecommendationModel[]>([]);
  const [recommendationModelId, setRecommendationModelId] = useState("gpt-5.4-mini");
  const [recommendationFiles, setRecommendationFiles] = useState<File[]>([]);
  const [recommendationNote, setRecommendationNote] = useState("");
  const [recommendationTargetPeriodId, setRecommendationTargetPeriodId] = useState("");
  const [recommendationResult, setRecommendationResult] = useState<JournalRecommendationDetail | null>(null);
  const [acceptedProposalIds, setAcceptedProposalIds] = useState<string[]>([]);
  const [recommendationUploadKey, setRecommendationUploadKey] = useState(0);
  const [journalEvidenceCache, setJournalEvidenceCache] = useState<Record<string, JournalEvidenceItem[]>>({});
  const [journalEvidenceLoadingIds, setJournalEvidenceLoadingIds] = useState<Record<string, boolean>>({});
  const [journalEvidenceErrorById, setJournalEvidenceErrorById] = useState<Record<string, string | null>>({});
  const [documentPreviewById, setDocumentPreviewById] = useState<Record<string, DocumentPreviewState>>({});
  const [pdfPreviewById, setPdfPreviewById] = useState<Record<string, PdfPreviewState>>({});
  const [activeEvidenceViewer, setActiveEvidenceViewer] = useState<ActiveEvidenceViewer | null>(null);
  const documentBlobByIdRef = useRef<Record<string, Blob>>({});
  const documentPreviewUrlsRef = useRef<Record<string, string>>({});
  const documentPreviewRequestsRef = useRef<Record<string, Promise<boolean>>>({});
  const pdfThumbnailRequestsRef = useRef<Record<string, Promise<void>>>({});
  const pdfFullRenderRequestsRef = useRef<Record<string, Promise<void>>>({});
  const isRecommendationProcessing = busyLabel === "Analyzing documents";
  const fallbackPeriodId = selectedPeriodId || periodOptionList[0]?.value || "";

  async function ensureJournalEvidenceLoaded(journalId: string) {
    if (!selectedCompanyId || !journalId || journalId === selectedJournalId || journalId in journalEvidenceCache || journalEvidenceLoadingIds[journalId]) {
      return;
    }

    setJournalEvidenceLoadingIds((current) => ({ ...current, [journalId]: true }));
    setJournalEvidenceErrorById((current) => ({ ...current, [journalId]: null }));
    try {
      const evidence = await request<JournalEvidenceItem[]>(`/api/companies/${selectedCompanyId}/journals/${journalId}/documents`);
      setJournalEvidenceCache((current) => ({ ...current, [journalId]: evidence }));
    } catch (error) {
      setJournalEvidenceErrorById((current) => ({
        ...current,
        [journalId]: error instanceof Error ? error.message : "Could not load journal evidence.",
      }));
    } finally {
      setJournalEvidenceLoadingIds((current) => ({ ...current, [journalId]: false }));
    }
  }

  function setPdfPreviewError(documentId: string, message: string) {
    setPdfPreviewById((current) => ({
      ...current,
      [documentId]: {
        thumbnailStatus: current[documentId]?.thumbnailStatus === "ready" ? "ready" : "error",
        thumbnailUrl: current[documentId]?.thumbnailUrl ?? null,
        fullStatus: "error",
        pageImageUrls: current[documentId]?.pageImageUrls ?? [],
        error: message,
      },
    }));
  }

  async function ensureDocumentPreview(documentId: string, filename: string, mediaType: string | null, options?: { force?: boolean }) {
    if (!selectedCompanyId) {
      return false;
    }

    const existingPreview = documentPreviewById[documentId];
    if (existingPreview?.status === "ready") {
      return true;
    }
    if (existingPreview?.status === "error" && !options?.force) {
      return false;
    }

    const activeRequest = documentPreviewRequestsRef.current[documentId];
    if (activeRequest) {
      await activeRequest;
      return Boolean(documentBlobByIdRef.current[documentId]);
    }

    const requestPromise = (async () => {
      setDocumentPreviewById((current) => ({
        ...current,
        [documentId]: {
          status: "loading",
          url: current[documentId]?.url ?? null,
          error: null,
          filename,
          media_type: mediaType,
        },
      }));
      if (isPdfDocument(mediaType, filename)) {
        setPdfPreviewById((current) => ({
          ...current,
          [documentId]: {
            thumbnailStatus: current[documentId]?.thumbnailStatus === "ready" ? "ready" : "idle",
            thumbnailUrl: current[documentId]?.thumbnailUrl ?? null,
            fullStatus: "idle",
            pageImageUrls: current[documentId]?.pageImageUrls ?? [],
            error: null,
          },
        }));
      }

      try {
        const response = await request<{ blob: Blob; headers: Headers }>(`/api/companies/${selectedCompanyId}/documents/${documentId}/download`, "GET", undefined, "blob");
        const normalizedMediaType = inferDocumentMediaType(response.blob.type || mediaType, filename);
        const previewBlob = normalizedMediaType && response.blob.type !== normalizedMediaType
          ? new Blob([response.blob], { type: normalizedMediaType })
          : response.blob;
        documentBlobByIdRef.current[documentId] = previewBlob;
        let nextUrl: string | null = null;
        if (isImageDocument(normalizedMediaType, filename)) {
          nextUrl = URL.createObjectURL(previewBlob);
          const previousUrl = documentPreviewUrlsRef.current[documentId];
          if (previousUrl && previousUrl !== nextUrl) {
            URL.revokeObjectURL(previousUrl);
          }
          documentPreviewUrlsRef.current[documentId] = nextUrl;
        }
        setDocumentPreviewById((current) => ({
          ...current,
          [documentId]: {
            status: "ready",
            url: nextUrl,
            error: null,
            filename,
            media_type: normalizedMediaType,
          },
        }));
        return true;
      } catch (error) {
        delete documentBlobByIdRef.current[documentId];
        setDocumentPreviewById((current) => ({
          ...current,
          [documentId]: {
            status: "error",
            url: null,
            error: error instanceof Error ? error.message : "Could not load the document preview.",
            filename,
            media_type: mediaType,
          },
        }));
        if (isPdfDocument(mediaType, filename)) {
          setPdfPreviewError(documentId, error instanceof Error ? error.message : `Could not render ${filename}.`);
        }
        return false;
      } finally {
        delete documentPreviewRequestsRef.current[documentId];
      }
    })();

    documentPreviewRequestsRef.current[documentId] = requestPromise;
    return await requestPromise;
  }

  async function renderPdfThumbnail(documentId: string, filename: string) {
    const previewBlob = documentBlobByIdRef.current[documentId];
    if (!previewBlob) {
      setPdfPreviewError(documentId, `Could not load ${filename} for preview.`);
      return;
    }

    const currentState = pdfPreviewById[documentId];
    if (currentState?.thumbnailStatus === "ready") {
      return;
    }
    const activeRequest = pdfThumbnailRequestsRef.current[documentId];
    if (activeRequest) {
      await activeRequest;
      return;
    }

    const requestPromise = (async () => {
      setPdfPreviewById((current) => ({
        ...current,
        [documentId]: {
          thumbnailStatus: "loading",
          thumbnailUrl: current[documentId]?.thumbnailUrl ?? null,
          fullStatus: current[documentId]?.fullStatus ?? "idle",
          pageImageUrls: current[documentId]?.pageImageUrls ?? [],
          error: null,
        },
      }));

      try {
        const pdf = await loadPdfDocument(previewBlob);
        const page = await pdf.getPage(1);
        const initialViewport = page.getViewport({ scale: 1 });
        const scale = Math.min(1.1, 220 / initialViewport.width);
        const viewport = page.getViewport({ scale });
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        if (!context) {
          throw new Error("Could not create PDF thumbnail canvas.");
        }
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        await page.render({ canvas, canvasContext: context, viewport }).promise;
        const thumbnailUrl = canvas.toDataURL("image/png");
        page.cleanup();
        await pdf.destroy();
        setPdfPreviewById((current) => ({
          ...current,
          [documentId]: {
            thumbnailStatus: "ready",
            thumbnailUrl,
            fullStatus: current[documentId]?.fullStatus ?? "idle",
            pageImageUrls: current[documentId]?.pageImageUrls ?? [],
            error: null,
          },
        }));
      } catch (error) {
        setPdfPreviewById((current) => ({
          ...current,
          [documentId]: {
            thumbnailStatus: "error",
            thumbnailUrl: null,
            fullStatus: current[documentId]?.fullStatus ?? "idle",
            pageImageUrls: current[documentId]?.pageImageUrls ?? [],
            error: error instanceof Error ? error.message : `Could not render ${filename}.`,
          },
        }));
      } finally {
        delete pdfThumbnailRequestsRef.current[documentId];
      }
    })();

    pdfThumbnailRequestsRef.current[documentId] = requestPromise;
    await requestPromise;
  }

  async function renderPdfFullDocument(documentId: string, filename: string) {
    const previewBlob = documentBlobByIdRef.current[documentId];
    if (!previewBlob) {
      setPdfPreviewError(documentId, `Could not load ${filename} for preview.`);
      return;
    }

    const currentState = pdfPreviewById[documentId];
    if (currentState?.fullStatus === "ready") {
      return;
    }
    const activeRequest = pdfFullRenderRequestsRef.current[documentId];
    if (activeRequest) {
      await activeRequest;
      return;
    }

    const requestPromise = (async () => {
      setPdfPreviewById((current) => ({
        ...current,
        [documentId]: {
          thumbnailStatus: current[documentId]?.thumbnailStatus ?? "idle",
          thumbnailUrl: current[documentId]?.thumbnailUrl ?? null,
          fullStatus: "loading",
          pageImageUrls: current[documentId]?.pageImageUrls ?? [],
          error: null,
        },
      }));

      try {
        const pdf = await loadPdfDocument(previewBlob);
        const pageImageUrls: string[] = [];

        for (let pageIndex = 1; pageIndex <= pdf.numPages; pageIndex += 1) {
          const page = await pdf.getPage(pageIndex);
          const initialViewport = page.getViewport({ scale: 1 });
          const scale = Math.min(1.35, 960 / initialViewport.width);
          const viewport = page.getViewport({ scale });
          const canvas = document.createElement("canvas");
          const context = canvas.getContext("2d");
          if (!context) {
            throw new Error("Could not create PDF page canvas.");
          }
          canvas.width = Math.ceil(viewport.width);
          canvas.height = Math.ceil(viewport.height);
          await page.render({ canvas, canvasContext: context, viewport }).promise;
          pageImageUrls.push(canvas.toDataURL("image/png"));
          page.cleanup();
        }

        await pdf.destroy();
        setPdfPreviewById((current) => ({
          ...current,
          [documentId]: {
            thumbnailStatus: current[documentId]?.thumbnailStatus ?? "idle",
            thumbnailUrl: current[documentId]?.thumbnailUrl ?? null,
            fullStatus: "ready",
            pageImageUrls,
            error: null,
          },
        }));
      } catch (error) {
        setPdfPreviewById((current) => ({
          ...current,
          [documentId]: {
            thumbnailStatus: current[documentId]?.thumbnailStatus ?? "idle",
            thumbnailUrl: current[documentId]?.thumbnailUrl ?? null,
            fullStatus: "error",
            pageImageUrls: [],
            error: error instanceof Error ? error.message : `Could not render ${filename}.`,
          },
        }));
      } finally {
        delete pdfFullRenderRequestsRef.current[documentId];
      }
    })();

    pdfFullRenderRequestsRef.current[documentId] = requestPromise;
    await requestPromise;
  }

  function getJournalEvidenceForDetail(journalId: string) {
    if (journalId === selectedJournalId) {
      return {
        items: journalEvidence,
        loading: false,
        error: null,
      };
    }

    return {
      items: journalEvidenceCache[journalId] ?? [],
      loading: journalEvidenceLoadingIds[journalId] ?? false,
      error: journalEvidenceErrorById[journalId] ?? null,
    };
  }

  function openEvidenceViewer(item: JournalEvidenceItem) {
    setActiveEvidenceViewer({
      documentId: item.document_id,
      filename: item.original_filename,
      media_type: item.media_type,
    });
    void ensureDocumentPreview(item.document_id, item.original_filename, item.media_type, { force: true })
      .then(async (previewReady) => {
        if (previewReady && isPdfDocument(item.media_type, item.original_filename)) {
          await renderPdfFullDocument(item.document_id, item.original_filename);
        }
      });
  }

  function renderJournalEvidencePreview(journal: { id: string; entry_number: string }) {
    const evidenceState = getJournalEvidenceForDetail(journal.id);

    return (
      <section className="journal-evidence-preview" aria-label={`Evidence for ${journal.entry_number}`}>
        <div className="journal-evidence-preview-header">
          <strong>Evidence</strong>
          <span className="pill">{evidenceState.items.length} linked</span>
        </div>
        {evidenceState.loading ? <p className="summary-line">Loading linked evidence...</p> : null}
        {evidenceState.error ? <p className="summary-line">Could not load linked evidence: {evidenceState.error}</p> : null}
        {!evidenceState.loading && !evidenceState.error && evidenceState.items.length === 0 ? (
          <p className="summary-line">No evidence linked to this journal.</p>
        ) : null}
        {evidenceState.items.length > 0 ? (
          <div className="journal-evidence-gallery">
            {evidenceState.items.map((item) => {
              const preview = documentPreviewById[item.document_id];
              const pdfPreview = pdfPreviewById[item.document_id];
              const resolvedMediaType = inferDocumentMediaType(item.media_type, item.original_filename);
              const showImageThumbnail = isImageDocument(resolvedMediaType, item.original_filename) && preview?.status === "ready" && preview.url;
              const showPdfThumbnail = isPdfDocument(resolvedMediaType, item.original_filename) && pdfPreview?.thumbnailStatus === "ready" && pdfPreview.thumbnailUrl;
              return (
                <button
                  key={item.link_id}
                  className="journal-evidence-thumb"
                  type="button"
                  onClick={() => openEvidenceViewer(item)}
                >
                  <div className="journal-evidence-thumb-media">
                    {showImageThumbnail ? (
                      <img className="journal-evidence-thumb-image" src={preview.url ?? ""} alt={`Preview of ${item.original_filename}`} />
                    ) : showPdfThumbnail ? (
                      <img className="journal-evidence-thumb-image" src={pdfPreview.thumbnailUrl ?? ""} alt={`Preview of ${item.original_filename}`} />
                    ) : (
                      <div className={`journal-evidence-thumb-placeholder${isPdfDocument(resolvedMediaType, item.original_filename) ? " is-pdf" : ""}`}>
                        <strong>{formatDocumentBadge(resolvedMediaType, item.original_filename)}</strong>
                        <span>{resolvedMediaType ?? item.media_type ?? "Unknown type"}</span>
                      </div>
                    )}
                  </div>
                  <div className="journal-evidence-thumb-copy">
                    <span className="journal-evidence-thumb-name">{item.original_filename}</span>
                    <span className="table-meta">{formatFileSize(item.byte_size)}{item.note ? ` · ${item.note}` : ""}</span>
                  </div>
                </button>
              );
            })}
          </div>
        ) : null}
      </section>
    );
  }

  async function deleteDocumentRecord(documentId: string) {
    await request(`/api/companies/${selectedCompanyId}/documents/${documentId}`, "DELETE", undefined, "void");
  }

  async function deleteDocument(documentId: string, originalFilename: string) {
    if (!confirmDanger(`Delete document ${originalFilename}?`)) {
      return;
    }
    try {
      await deleteDocumentRecord(documentId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (!message.includes("Document is linked to other records")) {
        throw error;
      }

      const links = await request<RemovableDocumentLink[]>(`/api/companies/${selectedCompanyId}/documents/${documentId}/links`);
      if (links.length === 0) {
        throw error;
      }
      if (!confirmDanger(`Document ${originalFilename} is linked to ${links.length} record(s). Remove those link(s) and delete the document?`)) {
        return;
      }
      for (const link of links) {
        await request(`/api/companies/${selectedCompanyId}/documents/${documentId}/links/${link.id}`, "DELETE", undefined, "void");
      }
      await deleteDocumentRecord(documentId);
    }
    setSelectedDocumentId("");
    setSelectedDocumentLinkId("");
    showMessage("success", "Deleted document.");
    await refreshAll();
  }

  const categoryNameById = useMemo(() => new Map(categories.map((item) => [item.id, item.name])), [categories]);
  const accountLabelById = useMemo(() => new Map(accounts.map((item) => [item.id, `${item.account_code} ${item.name}`])), [accounts]);
  const taxCodeLabelById = useMemo(() => new Map(taxCodes.map((item) => [item.id, `${item.code} ${item.name}`])), [taxCodes]);
  const selectedRecommendationModel = useMemo(
    () => recommendationModels.find((item) => item.id === recommendationModelId) ?? null,
    [recommendationModelId, recommendationModels],
  );
  const journalById = useMemo(() => new Map(journals.map((item) => [item.id, item])), [journals]);
  const expandedJournal = expandedJournalId ? journalById.get(expandedJournalId) ?? null : null;
  const ledgerPreviewJournal = ledgerPreviewJournalId ? journalById.get(ledgerPreviewJournalId) ?? null : null;
  const activeEvidencePreview = activeEvidenceViewer ? documentPreviewById[activeEvidenceViewer.documentId] ?? null : null;
  const activePdfPreview = activeEvidenceViewer ? pdfPreviewById[activeEvidenceViewer.documentId] ?? null : null;
  const activeEvidenceMediaType = activeEvidenceViewer
    ? inferDocumentMediaType(activeEvidencePreview?.media_type ?? activeEvidenceViewer.media_type, activeEvidenceViewer.filename)
    : null;
  const activeEvidenceIsPdf = Boolean(activeEvidenceViewer && activeEvidenceMediaType && isPdfDocument(activeEvidenceMediaType, activeEvidenceViewer.filename));
  const activeEvidenceIsImage = Boolean(activeEvidenceViewer && activeEvidenceMediaType && isImageDocument(activeEvidenceMediaType, activeEvidenceViewer.filename));
  const activeEvidenceHasError = Boolean(
    activeEvidencePreview?.status === "error"
    || activePdfPreview?.fullStatus === "error"
    || activePdfPreview?.error,
  );
  const activeEvidenceIsLoading = activeEvidenceIsPdf
    ? !activeEvidenceHasError && (!activePdfPreview || activePdfPreview.fullStatus === "idle" || activePdfPreview.fullStatus === "loading")
    : !activeEvidenceHasError && (!activeEvidencePreview || activeEvidencePreview.status === "loading");
  const activeEvidenceCanRender = activeEvidenceIsPdf
    ? !activeEvidenceHasError && activePdfPreview?.fullStatus === "ready"
    : !activeEvidenceHasError && activeEvidencePreview?.status === "ready";
  const journalTableRef = useRef<HTMLDivElement | null>(null);
  const visibleEvidenceJournalIds = useMemo(
    () => Array.from(new Set([selectedJournal?.id, expandedJournal?.id, ledgerPreviewJournal?.id].filter((value): value is string => Boolean(value)))),
    [expandedJournal?.id, ledgerPreviewJournal?.id, selectedJournal?.id],
  );
  const allJournalDateRange = useMemo(() => {
    const datedJournals = journals.filter((item) => item.entry_date);
    if (datedJournals.length === 0) {
      return null;
    }
    return datedJournals.reduce<{ start_date: string; end_date: string }>((range, item) => ({
      start_date: item.entry_date < range.start_date ? item.entry_date : range.start_date,
      end_date: item.entry_date > range.end_date ? item.entry_date : range.end_date,
    }), {
      start_date: datedJournals[0].entry_date,
      end_date: datedJournals[0].entry_date,
    });
  }, [journals]);
  const journalStatusOptions = useMemo(
    () => Array.from(new Set(journals.map((item) => item.status))).sort(),
    [journals],
  );
  const filteredJournals = useMemo(() => {
    const query = normalizeSearchValue(journalSearchQuery);
    return journals.filter((item) => {
      if (journalStatusFilter && item.status !== journalStatusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [
        item.entry_number,
        item.entry_date,
        item.description,
        item.reference,
        item.source_type,
        ...item.lines.map((line) => line.description ?? ""),
      ].some((value) => normalizeSearchValue(value).includes(query));
    });
  }, [journalSearchQuery, journalStatusFilter, journals]);
  const ledgerStatusOptions = useMemo(
    () => Array.from(new Set((reportState.generalLedger?.accounts ?? []).flatMap((account) => account.entries.map((entry) => entry.journal_status)))).sort(),
    [reportState.generalLedger],
  );
  const filteredLedgerAccounts = useMemo(() => {
    const query = normalizeSearchValue(ledgerSearchQuery);
    return (reportState.generalLedger?.accounts ?? [])
      .map((account) => ({
        ...account,
        entries: account.entries.filter((entry) => {
          if (ledgerStatusFilter && entry.journal_status !== ledgerStatusFilter) {
            return false;
          }
          if (!query) {
            return true;
          }
          return [
            account.account_code,
            account.account_name,
            entry.entry_number,
            entry.entry_date,
            entry.journal_status,
            entry.reference,
            entry.journal_description,
            entry.line_description,
          ].some((value) => normalizeSearchValue(value).includes(query));
        }),
      }))
      .filter((account) => account.entries.length > 0);
  }, [ledgerSearchQuery, ledgerStatusFilter, reportState.generalLedger]);
  const filteredLedgerEntryCount = useMemo(
    () => filteredLedgerAccounts.reduce((total, account) => total + account.entries.length, 0),
    [filteredLedgerAccounts],
  );

  function openCreateJournalPopup() {
    setJournalEditorJournalId(undefined);
    setIsJournalEditorOpen(true);
  }

  function openUpdateJournalPopup(journalId: string) {
    setJournalEditorJournalId(journalId);
    setIsJournalEditorOpen(true);
  }

  function closeJournalEditorPopup() {
    setIsJournalEditorOpen(false);
    setJournalEditorJournalId(undefined);
  }

  useEffect(() => {
    if (!selectedJournalId) {
      return;
    }
    setJournalEvidenceCache((current) => ({ ...current, [selectedJournalId]: journalEvidence }));
    setJournalEvidenceLoadingIds((current) => ({ ...current, [selectedJournalId]: false }));
    setJournalEvidenceErrorById((current) => ({ ...current, [selectedJournalId]: null }));
  }, [journalEvidence, selectedJournalId]);

  useEffect(() => {
    for (const journalId of visibleEvidenceJournalIds) {
      if (journalId === selectedJournalId || journalId in journalEvidenceCache || journalEvidenceLoadingIds[journalId]) {
        continue;
      }
      void ensureJournalEvidenceLoaded(journalId);
    }
  }, [journalEvidenceCache, journalEvidenceLoadingIds, selectedJournalId, selectedCompanyId, visibleEvidenceJournalIds]);

  useEffect(() => {
    for (const journalId of visibleEvidenceJournalIds) {
        const evidenceItems = getJournalEvidenceForDetail(journalId).items;
      for (const item of evidenceItems) {
        const preview = documentPreviewById[item.document_id];
        if (
          (!isImageDocument(item.media_type, item.original_filename) && !isPdfDocument(item.media_type, item.original_filename))
          || preview?.status === "ready"
          || preview?.status === "loading"
          || preview?.status === "error"
        ) {
          continue;
        }
        void ensureDocumentPreview(item.document_id, item.original_filename, item.media_type)
          .then(async (previewReady) => {
            if (previewReady && isPdfDocument(item.media_type, item.original_filename)) {
              await renderPdfThumbnail(item.document_id, item.original_filename);
            }
          });
      }
    }
  }, [documentPreviewById, journalEvidence, journalEvidenceCache, pdfPreviewById, selectedJournalId, visibleEvidenceJournalIds]);

  useEffect(() => {
    return () => {
      Object.values(documentPreviewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
      documentPreviewUrlsRef.current = {};
    };
  }, []);

  useEffect(() => {
    Object.values(documentPreviewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
    documentPreviewUrlsRef.current = {};
    documentPreviewRequestsRef.current = {};
    pdfThumbnailRequestsRef.current = {};
    pdfFullRenderRequestsRef.current = {};
    documentBlobByIdRef.current = {};
    setJournalEvidenceCache({});
    setJournalEvidenceLoadingIds({});
    setJournalEvidenceErrorById({});
    setDocumentPreviewById({});
    setPdfPreviewById({});
    setActiveEvidenceViewer(null);
  }, [selectedCompanyId]);

  useEffect(() => {
    if (!selectedCompanyId) {
      setRecommendationModels([]);
      setRecommendationResult(null);
      setAcceptedProposalIds([]);
      return;
    }
    let ignore = false;
    request<JournalRecommendationModel[]>(`/api/companies/${selectedCompanyId}/journal-recommendations/models`)
      .then((models) => {
        if (ignore) {
          return;
        }
        setRecommendationModels(models);
        if (!models.some((item) => item.id === recommendationModelId)) {
          setRecommendationModelId(models[0]?.id ?? "gpt-5.4-mini");
        }
      })
      .catch(() => {
        if (!ignore) {
          setRecommendationModels([]);
        }
      });
    return () => {
      ignore = true;
    };
  }, [request, recommendationModelId, selectedCompanyId]);

  useEffect(() => {
    setRecommendationTargetPeriodId((current) => current || fallbackPeriodId || "");
  }, [fallbackPeriodId]);

  useEffect(() => {
    if (!expandedJournalId) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }
      if (journalTableRef.current?.contains(target)) {
        return;
      }
      setExpandedJournalId("");
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [expandedJournalId]);

  useEffect(() => {
    if (!ledgerPreviewJournalId || activeEvidenceViewer) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setLedgerPreviewJournalId("");
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [activeEvidenceViewer, ledgerPreviewJournalId]);

  useEffect(() => {
    if (!activeEvidenceViewer) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setActiveEvidenceViewer(null);
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [activeEvidenceViewer]);

  useEffect(() => {
    if (expandedJournalId && !filteredJournals.some((item) => item.id === expandedJournalId)) {
      setExpandedJournalId("");
    }
  }, [expandedJournalId, filteredJournals]);

  useEffect(() => {
    if (!ledgerPreviewJournalId) {
      return;
    }
    const isVisible = filteredLedgerAccounts.some((account) => account.entries.some((entry) => entry.journal_entry_id === ledgerPreviewJournalId));
    if (!isVisible) {
      setLedgerPreviewJournalId("");
    }
  }, [filteredLedgerAccounts, ledgerPreviewJournalId]);

  async function loadGeneralLedger(filters = generalLedgerFilters) {
    const query = buildGeneralLedgerQuery(filters);
    const report = await request<GeneralLedgerReport>(`/api/companies/${selectedCompanyId}/reports/general-ledger?${query}`);
    setReportState((current) => ({ ...current, generalLedger: report }));
  }

  return (
    <section className="sections-stack">
      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Accounting periods</h2><span className="pill">{periods.length} periods</span></div>
        <div className="workspace-split">
          <div className="table-shell">
            <table className="data-table">
              <thead><tr><th>Name</th><th>Range</th><th>Status</th></tr></thead>
              <tbody>
                {periods.map((item) => (
                  <tr key={item.id} className={selectedPeriodId === item.id ? "is-selected" : ""} onClick={() => setSelectedPeriodId(item.id)}>
                    <td>{item.name}</td>
                    <td>{item.start_date} to {item.end_date}</td>
                    <td><StatusPill value={item.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>{selectedPeriod ? "Update selected period" : "Create period"}</h3>
              <div className="form-grid two-up">
                <Field label="Name"><input value={periodDraft.name} onChange={(event) => setPeriodDraft((current) => ({ ...current, name: event.target.value }))} /></Field>
                <Field label="Period type"><select value={periodDraft.period_type} onChange={(event) => setPeriodDraft((current) => ({ ...current, period_type: event.target.value }))}><option value="month">Month</option><option value="quarter">Quarter</option><option value="year">Year</option></select></Field>
                <Field label="Start date"><input type="date" value={periodDraft.start_date} onChange={(event) => setPeriodDraft((current) => ({ ...current, start_date: event.target.value }))} /></Field>
                <Field label="End date"><input type="date" value={periodDraft.end_date} onChange={(event) => setPeriodDraft((current) => ({ ...current, end_date: event.target.value }))} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" data-testid="save-period" onClick={() => runAction("Saving period", async () => {
                  if (selectedPeriodId) {
                    await request(`/api/companies/${selectedCompanyId}/periods/${selectedPeriodId}`, "PUT", periodDraft);
                  } else {
                    await request(`/api/companies/${selectedCompanyId}/periods`, "POST", periodDraft);
                  }
                  showMessage("success", "Saved accounting period.");
                  await refreshAll();
                })}>Save period</button>
              </div>
            </div>
            {selectedPeriod ? (
              <div className="mini-card">
                <h3>Workflow actions</h3>
                <Field label="Note or reason"><input value={periodActionNote} onChange={(event) => setPeriodActionNote(event.target.value)} /></Field>
                <div className="request-actions">
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Submitting period", async () => {
                    await request(`/api/companies/${selectedCompanyId}/periods/${selectedPeriod.id}/submit`, "POST", { note: periodActionNote });
                    await refreshAll();
                    showMessage("success", "Submitted period for review.");
                  })}>Submit</button>
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Approving period", async () => {
                    await request(`/api/companies/${selectedCompanyId}/periods/${selectedPeriod.id}/approve`, "POST", { note: periodActionNote });
                    await refreshAll();
                    showMessage("success", "Approved period.");
                  })}>Approve</button>
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Locking period", async () => {
                    await request(`/api/companies/${selectedCompanyId}/periods/${selectedPeriod.id}/lock`, "POST", { reason: periodActionNote });
                    await refreshAll();
                    showMessage("success", "Locked period.");
                  })}>Lock</button>
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Unlocking period", async () => {
                    await request(`/api/companies/${selectedCompanyId}/periods/${selectedPeriod.id}/unlock`, "POST", { reason: periodActionNote });
                    await refreshAll();
                    showMessage("success", "Unlocked period.");
                  })}>Unlock</button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading">
          <h2>Journals</h2>
          <div className="request-actions-inline">
            <span className="pill">{journals.length} journals</span>
            <button className="button-link button-link-small" type="button" onClick={openCreateJournalPopup}>Create journal</button>
          </div>
        </div>
        <div className="stacked-cards table-panel-stack">
            <div className="mini-card table-filter-card">
              <div className="form-grid two-up">
                <Field label="Search journals"><input value={journalSearchQuery} onChange={(event) => setJournalSearchQuery(event.target.value)} placeholder="Entry, date, description, reference, source" /></Field>
                <Field label="Filter by status"><select value={journalStatusFilter} onChange={(event) => setJournalStatusFilter(event.target.value)}><option value="">All statuses</option>{journalStatusOptions.map((status) => <option key={status} value={status}>{status}</option>)}</select></Field>
              </div>
              <div className="table-filter-footer">
                <p className="summary-line">Showing {filteredJournals.length} of {journals.length} journals.</p>
                {journalSearchQuery || journalStatusFilter ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
                  setJournalSearchQuery("");
                  setJournalStatusFilter("");
                }}>Clear journal filters</button> : null}
              </div>
            </div>
            {filteredJournals.length > 0 ? (
              <div className="table-shell journal-table-shell" ref={journalTableRef}>
                <table className="data-table">
                  <thead><tr><th>Entry</th><th>Date</th><th>Status</th></tr></thead>
                  <tbody>
                    {filteredJournals.map((item) => {
                      const isExpanded = expandedJournalId === item.id;
                      const isSelected = selectedJournalId === item.id;
                      return (
                        <Fragment key={item.id}>
                          <tr className={isSelected ? "is-selected" : ""} onClick={() => {
                            setSelectedJournalId(item.id);
                            setExpandedJournalId((current) => current === item.id ? "" : item.id);
                          }}>
                            <td>{item.entry_number}<div className="table-meta">{item.description}</div></td>
                            <td>{item.entry_date}</td>
                            <td><StatusPill value={item.status} /></td>
                          </tr>
                          {isExpanded ? (
                            <tr className="journal-preview-row row-static">
                              <td colSpan={3}>
                                <div className="journal-preview-card">
                                  <div className="journal-preview-meta">
                                    <span><strong>Reference</strong> {item.reference || "-"}</span>
                                    <span><strong>Source</strong> {item.source_type || "-"}</span>
                                    <span><strong>Lines</strong> {item.lines.length}</span>
                                  </div>
                                  <div className="request-actions-inline">
                                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => openUpdateJournalPopup(item.id)}>Update journal</button>
                                  </div>
                                  {renderJournalEvidencePreview(item)}
                                  <div className="table-shell compact-table-shell journal-preview-lines-shell">
                                    <table className="data-table journal-preview-lines-table">
                                      <thead><tr><th>Line</th><th>Account</th><th>Note</th><th className="amount-cell">Debit</th><th className="amount-cell">Credit</th></tr></thead>
                                      <tbody>
                                        {item.lines.map((line, index) => (
                                          <tr key={`${item.id}-${line.id ?? index}`} className="row-static">
                                            <td>{line.line_number ?? index + 1}</td>
                                            <td>{line.account_id ? accountLabelById.get(line.account_id) ?? "Unknown account" : "-"}</td>
                                            <td>{line.description || "No line note"}</td>
                                            <td className="amount-cell">{formatMoney(line.debit_amount)}</td>
                                            <td className="amount-cell">{formatMoney(line.credit_amount)}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          ) : null}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state table-empty-state">
                <strong>No journals match the current search and filter.</strong>
                <p>Adjust the journal search text or status filter to bring more review items back into view.</p>
              </div>
            )}
          </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading"><h2>AI journal drafting</h2><span className="pill">Review first</span></div>
        <div className="workspace-split journal-workspace-split">
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Analyze invoices or receipts</h3>
              <p className="summary-line">Upload one or more files for the same transaction bundle, add optional context, and generate a review-only journal draft recommendation.</p>
              <div className="form-grid two-up">
                <Field label="ChatGPT model">
                  <select value={recommendationModelId} disabled={isRecommendationProcessing} onChange={(event) => setRecommendationModelId(event.target.value)}>
                    {recommendationModels.map((item) => <option key={item.id} value={item.id}>{item.label} · est. ${item.estimated_cost_per_1000_calls_usd}/1,000 calls</option>)}
                  </select>
                </Field>
                <Field label="Target accounting period">
                  <select value={recommendationTargetPeriodId} disabled={isRecommendationProcessing} onChange={(event) => setRecommendationTargetPeriodId(event.target.value)}>
                    <option value="">Choose period</option>
                    {periodOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                <Field label="Transaction context" wide>
                  <textarea rows={4} value={recommendationNote} disabled={isRecommendationProcessing} onChange={(event) => setRecommendationNote(event.target.value)} placeholder="Optional details for the model, for example: paid immediately from the operating bank and relates to office stationery." />
                </Field>
                <Field label="Files" wide>
                  <input key={recommendationUploadKey} type="file" multiple accept=".pdf,image/png,image/jpeg,image/webp,image/gif" disabled={isRecommendationProcessing} onChange={(event) => setRecommendationFiles(Array.from(event.target.files ?? []))} />
                </Field>
              </div>
              {selectedRecommendationModel ? <p className="summary-line">{selectedRecommendationModel.label} is estimated at ${selectedRecommendationModel.estimated_cost_per_1000_calls_usd} per 1,000 calls. {selectedRecommendationModel.pricing_note}</p> : null}
              {recommendationFiles.length > 0 ? (
                <div className="table-shell compact-table-shell evidence-table-shell">
                  <table className="data-table">
                    <thead><tr><th>Selected file</th><th>Size</th></tr></thead>
                    <tbody>
                      {recommendationFiles.map((file) => (
                        <tr key={`${file.name}-${file.size}`} className="row-static">
                          <td>{file.name}<div className="table-meta">{file.type || "Unknown type"}</div></td>
                          <td>{formatFileSize(file.size)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" disabled={isRecommendationProcessing} onClick={() => runAction("Analyzing documents", async () => {
                  if (!selectedCompanyId) {
                    throw new Error("Select a company before generating a journal recommendation.");
                  }
                  if (recommendationFiles.length === 0) {
                    throw new Error("Upload at least one invoice or receipt before analysis.");
                  }
                  const formData = new FormData();
                  recommendationFiles.forEach((file) => formData.append("files", file));
                  formData.append("model", recommendationModelId || "gpt-5.4-mini");
                  if (recommendationNote.trim()) {
                    formData.append("user_context_note", recommendationNote.trim());
                  }
                  if (recommendationTargetPeriodId) {
                    formData.append("target_accounting_period_id", recommendationTargetPeriodId);
                  }
                  const createdRun = await request<JournalRecommendationDetail>(`/api/companies/${selectedCompanyId}/journal-recommendations`, "POST", formData);
                  const analyzedRun = await request<JournalRecommendationDetail>(`/api/companies/${selectedCompanyId}/journal-recommendations/${createdRun.id}/analyze`, "POST");
                  setRecommendationResult(analyzedRun);
                  setAcceptedProposalIds([]);
                  showMessage("success", "Generated a review-only journal recommendation.");
                })}>{isRecommendationProcessing ? "Analyzing..." : "Analyze bundle"}</button>
                <button className="button-link button-link-small button-link-secondary" type="button" disabled={isRecommendationProcessing} onClick={() => {
                  setRecommendationFiles([]);
                  setRecommendationNote("");
                  setRecommendationResult(null);
                  setAcceptedProposalIds([]);
                  setRecommendationUploadKey((current) => current + 1);
                }}>Clear</button>
              </div>
            </div>
          </div>

          <div className="stacked-cards">
            <div className="mini-card">
              <div className="mini-card-heading">
                <h3>Recommendation review</h3>
                <span className="pill">{recommendationResult ? recommendationResult.lines.length : 0} lines</span>
              </div>
              {!recommendationResult ? <p className="summary-line">No recommendation yet. Upload supporting files and analyze them to generate a draft journal recommendation.</p> : null}
              {recommendationResult ? (
                <>
                  <div className="summary-grid two-up">
                    <div><strong>Status</strong><div><StatusPill value={recommendationResult.status} /></div></div>
                    <div><strong>Model</strong><div>{recommendationResult.provider_model}</div></div>
                    <div><strong>Transaction date</strong><div>{recommendationResult.extracted_entry_date || "Not extracted"}</div></div>
                    <div><strong>Summary</strong><div>{recommendationResult.analysis_summary || "-"}</div></div>
                    <div><strong>Confidence</strong><div>{recommendationResult.confidence_summary || "-"}</div></div>
                  </div>
                  {recommendationResult.warning_text ? <p className="summary-line">Warning: {recommendationResult.warning_text}</p> : null}
                  {recommendationResult.failure_reason ? <p className="summary-line">Failure: {recommendationResult.failure_reason}</p> : null}
                  {recommendationResult.search_sources.length > 0 ? (
                    <div className="table-shell compact-table-shell evidence-table-shell" data-testid="recommendation-search-sources">
                      <table className="data-table">
                        <thead><tr><th>Search verification</th><th>Source</th></tr></thead>
                        <tbody>
                          {recommendationResult.search_sources.map((source) => (
                            <tr key={source.url} className="row-static">
                              <td>{source.title || source.domain || "Search source"}<div className="table-meta">Review-only provider verification</div></td>
                              <td><a href={source.url} target="_blank" rel="noreferrer">{source.domain || source.url}</a><div className="table-meta">{source.url}</div></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  {recommendationResult.documents.length > 0 ? (
                    <div className="table-shell compact-table-shell evidence-table-shell">
                      <table className="data-table">
                        <thead><tr><th>Evidence</th><th>Attached</th></tr></thead>
                        <tbody>
                          {recommendationResult.documents.map((item) => (
                            <tr key={item.id} className="row-static">
                              <td>{item.original_filename}<div className="table-meta">{item.media_type ?? "Unknown type"} · {formatFileSize(item.byte_size)}</div></td>
                              <td>{formatDateTime(item.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  <div className="table-shell compact-table-shell evidence-table-shell">
                    <table className="data-table">
                      <thead><tr><th>Line</th><th>Account</th><th>Tax</th><th>Reporting</th><th>Debit</th><th>Credit</th></tr></thead>
                      <tbody>
                        {recommendationResult.lines.map((line) => (
                          <tr key={line.id} className="row-static">
                            <td>{line.line_number}<div className="table-meta">{line.description || line.explanation || "No line note"}</div></td>
                            <td>{line.suggested_account_id ? accountLabelById.get(line.suggested_account_id) ?? line.suggested_account_code ?? "-" : line.suggested_account_code ?? "-"}</td>
                            <td>{line.suggested_tax_code_id ? taxCodeLabelById.get(line.suggested_tax_code_id) ?? line.suggested_tax_code_code ?? "-" : line.suggested_tax_code_code ?? "-"}</td>
                            <td>{line.suggested_reporting_category_id ? categoryNameById.get(line.suggested_reporting_category_id) ?? line.suggested_reporting_category_code ?? "-" : line.suggested_reporting_category_code ?? "-"}</td>
                            <td>{formatMoney(line.debit_amount)}</td>
                            <td>{formatMoney(line.credit_amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {recommendationResult.proposals.length > 0 ? (
                    <div className="table-shell compact-table-shell evidence-table-shell">
                      <table className="data-table">
                        <thead><tr><th>Create</th><th>Proposal</th><th>Reason</th><th>Status</th></tr></thead>
                        <tbody>
                          {recommendationResult.proposals.map((proposal) => (
                            <tr key={proposal.id} className="row-static">
                              <td><input type="checkbox" checked={acceptedProposalIds.includes(proposal.id)} onChange={(event) => setAcceptedProposalIds((current) => event.target.checked ? [...current, proposal.id] : current.filter((item) => item !== proposal.id))} /></td>
                              <td>{proposal.proposal_type}<div className="table-meta">{proposal.suggested_code} · {proposal.suggested_name}</div></td>
                              <td>{proposal.rationale || "No rationale provided"}</td>
                              <td><StatusPill value={proposal.status} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  <div className="request-actions">
                    <button className="button-link button-link-small" type="button" onClick={() => runAction("Creating recommended draft", async () => {
                      if (!selectedCompanyId || !recommendationResult) {
                        throw new Error("Generate a recommendation before creating a draft journal.");
                      }
                      const journal = await request<{ id: string; entry_number: string }>(`/api/companies/${selectedCompanyId}/journal-recommendations/${recommendationResult.id}/accept`, "POST", { accepted_proposal_ids: acceptedProposalIds });
                      await refreshAll();
                      setSelectedJournalId(journal.id);
                      await loadJournalEvidence(journal.id);
                      showMessage("success", `Created draft journal ${journal.entry_number} from the recommendation.`);
                    })}>Create draft journal</button>
                    <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Rejecting recommendation", async () => {
                      if (!selectedCompanyId || !recommendationResult) {
                        throw new Error("No recommendation selected to reject.");
                      }
                      const rejected = await request<JournalRecommendationDetail>(`/api/companies/${selectedCompanyId}/journal-recommendations/${recommendationResult.id}/reject`, "POST");
                      setRecommendationResult(rejected);
                      setAcceptedProposalIds([]);
                      showMessage("success", "Marked the recommendation as rejected.");
                    })}>Reject recommendation</button>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading">
          <div className="panel-heading-copy">
            <h2>Ledger explorer</h2>
            <p>Review draft and posted journal lines without leaving Bookkeeping. Draft rows stay visible here so you can inspect unposted work before it reaches the ledger proper.</p>
          </div>
          <span className="pill">Draft and posted lines</span>
        </div>
        <div className="mini-card ledger-toolbar">
          <div className="form-grid three-up">
            <Field label="Start date"><input type="date" value={generalLedgerFilters.start_date} onChange={(event) => setGeneralLedgerFilters((current) => ({ ...current, start_date: event.target.value }))} /></Field>
            <Field label="End date"><input type="date" value={generalLedgerFilters.end_date} onChange={(event) => setGeneralLedgerFilters((current) => ({ ...current, end_date: event.target.value }))} /></Field>
            <Field label="Account"><select value={generalLedgerFilters.account_id} onChange={(event) => setGeneralLedgerFilters((current) => ({ ...current, account_id: event.target.value }))}><option value="">All accounts</option>{accountOptionList.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
          </div>
          <div className="form-grid two-up">
            <Field label="Search loaded ledger"><input value={ledgerSearchQuery} onChange={(event) => setLedgerSearchQuery(event.target.value)} placeholder="Account, entry, date, status, reference, description" /></Field>
            <Field label="Filter by status"><select value={ledgerStatusFilter} onChange={(event) => setLedgerStatusFilter(event.target.value)}><option value="">All statuses</option>{ledgerStatusOptions.map((status) => <option key={status} value={status}>{status}</option>)}</select></Field>
          </div>
          <div className="table-filter-footer">
            <p className="summary-line">{reportState.generalLedger ? `Showing ${filteredLedgerEntryCount} of ${generalLedgerEntryCount} loaded ledger lines.` : "Load the ledger before searching and filtering visible lines."}</p>
            {ledgerSearchQuery || ledgerStatusFilter ? <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => {
              setLedgerSearchQuery("");
              setLedgerStatusFilter("");
            }}>Clear ledger filters</button> : null}
          </div>
          <div className="ledger-actions">
            <button className="button-link button-link-small" type="button" onClick={() => runAction("Loading ledger", async () => {
              await loadGeneralLedger();
            })}>Load ledger</button>
            <button className="button-link button-link-small button-link-secondary" type="button" disabled={!allJournalDateRange} onClick={() => runAction("Using all journal dates for ledger", async () => {
              if (!allJournalDateRange) {
                throw new Error("No journal dates are available yet for the ledger time window.");
              }
              const nextLedgerFilters = {
                ...generalLedgerFilters,
                start_date: allJournalDateRange.start_date,
                end_date: allJournalDateRange.end_date,
              };
              setGeneralLedgerFilters(nextLedgerFilters);
              await loadGeneralLedger(nextLedgerFilters);
            })}>Use all time</button>
            <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Using selected period for ledger", async () => {
              if (!selectedPeriod) {
                throw new Error("Select an accounting period before using its date range for the ledger.");
              }
              const nextLedgerFilters = {
                ...generalLedgerFilters,
                start_date: selectedPeriod.start_date,
                end_date: selectedPeriod.end_date,
              };
              setGeneralLedgerFilters(nextLedgerFilters);
              await loadGeneralLedger(nextLedgerFilters);
            })}>Use selected period</button>
            <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Focusing ledger on selected journal date", async () => {
              if (!selectedJournal) {
                throw new Error("Select a journal before focusing the ledger on its entry date.");
              }
              const nextLedgerFilters = {
                ...generalLedgerFilters,
                start_date: selectedJournal.entry_date,
                end_date: selectedJournal.entry_date,
              };
              setGeneralLedgerFilters(nextLedgerFilters);
              await loadGeneralLedger(nextLedgerFilters);
            })}>Focus selected journal date</button>
            <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Exporting general ledger", async () => {
              const query = buildGeneralLedgerQuery(generalLedgerFilters);
              await downloadFromApi(`/api/companies/${selectedCompanyId}/reports/general-ledger/export?${query}`, "general-ledger.csv");
            })}>Export CSV</button>
          </div>
          <div className="stats-grid ledger-summary-grid">
            <div className="stat-card">
              <span>Accounts shown</span>
              <strong>{reportState.generalLedger?.accounts.length ?? 0}</strong>
            </div>
            <div className="stat-card">
              <span>Ledger lines</span>
              <strong>{generalLedgerEntryCount}</strong>
            </div>
            <div className="stat-card">
              <span>Window</span>
              <strong>{generalLedgerFilters.start_date || "-"} to {generalLedgerFilters.end_date || "-"}</strong>
            </div>
          </div>
        </div>
        {reportState.generalLedger ? (
          filteredLedgerAccounts.length > 0 ? (
          <div className="table-shell ledger-table-shell">
            <table className="data-table ledger-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Date</th>
                  <th>Entry</th>
                  <th>Status</th>
                  <th>Reference</th>
                  <th>Description</th>
                  <th className="amount-cell">Debit</th>
                  <th className="amount-cell">Credit</th>
                  <th className="amount-cell">Running balance</th>
                </tr>
              </thead>
              {filteredLedgerAccounts.map((account) => (
                <tbody className="ledger-account-group" key={account.account_id}>
                  <tr className="ledger-group-row">
                    <td colSpan={9}>
                      <strong>{account.account_code} · {account.account_name}</strong>
                      <div className="ledger-group-meta">
                        <span>Type: {account.account_type.replaceAll("_", " ")}</span>
                        <span>Opening: {formatMoney(account.opening_balance)}</span>
                        <span>Closing: {formatMoney(account.closing_balance)}</span>
                        <span>{account.entries.length} lines</span>
                      </div>
                    </td>
                  </tr>
                  {account.entries.map((entry) => (
                    <tr
                      key={`${account.account_id}-${entry.journal_entry_id}-${entry.line_number}`}
                      className={(ledgerPreviewJournalId || selectedJournalId) === entry.journal_entry_id ? "is-selected" : ""}
                      onClick={() => setLedgerPreviewJournalId(entry.journal_entry_id)}
                    >
                      <td>{account.account_code}<div className="table-meta">{account.account_name}</div></td>
                      <td>{entry.entry_date}</td>
                      <td>{entry.entry_number}<div className="table-meta">Line {entry.line_number}</div></td>
                      <td><StatusPill value={entry.journal_status} /></td>
                      <td>{entry.reference ?? "-"}</td>
                      <td className="ledger-description">{entry.journal_description}<div className="table-meta">{entry.line_description || "No line note"}</div></td>
                      <td className="amount-cell">{formatMoney(entry.debit_amount)}</td>
                      <td className="amount-cell">{formatMoney(entry.credit_amount)}</td>
                      <td className="amount-cell">{formatMoney(entry.running_balance)}</td>
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
          </div>
          ) : (
            <div className="empty-state ledger-empty-state table-empty-state">
              <strong>No ledger lines match the current search and filter.</strong>
              <p>Change the loaded-ledger search text or status filter to widen the visible review set.</p>
            </div>
          )
        ) : (
          <div className="empty-state ledger-empty-state">
            <strong>No ledger loaded yet.</strong>
            <p>Run the ledger for a selected period or journal date to inspect draft and posted lines in a full-size table.</p>
          </div>
        )}
        {ledgerPreviewJournal ? (
          <div className="journal-popup-backdrop" role="presentation" onClick={() => setLedgerPreviewJournalId("")}>
            <div className="journal-popup-card" role="dialog" aria-modal="true" aria-label={`Journal ${ledgerPreviewJournal.entry_number}`} onClick={(event) => event.stopPropagation()}>
              <div className="journal-popup-header">
                <div>
                  <h3>{ledgerPreviewJournal.entry_number}</h3>
                  <p className="summary-line">Review-only journal detail from the ledger explorer.</p>
                </div>
                <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => setLedgerPreviewJournalId("")}>Close</button>
              </div>
              <div className="journal-preview-meta journal-popup-meta">
                <span><strong>Date</strong> {ledgerPreviewJournal.entry_date}</span>
                <span><strong>Status</strong> {ledgerPreviewJournal.status}</span>
                <span><strong>Reference</strong> {ledgerPreviewJournal.reference || "-"}</span>
                <span><strong>Source</strong> {ledgerPreviewJournal.source_type || "-"}</span>
              </div>
              <p className="summary-line journal-popup-description">{ledgerPreviewJournal.description || "No journal description provided."}</p>
              {renderJournalEvidencePreview(ledgerPreviewJournal)}
              <div className="table-shell journal-popup-lines-shell">
                <table className="data-table journal-preview-lines-table">
                  <thead><tr><th>Line</th><th>Account</th><th>Note</th><th className="amount-cell">Debit</th><th className="amount-cell">Credit</th></tr></thead>
                  <tbody>
                    {ledgerPreviewJournal.lines.map((line, index) => (
                      <tr key={`${ledgerPreviewJournal.id}-${line.id ?? index}`} className="row-static">
                        <td>{line.line_number ?? index + 1}</td>
                        <td>{line.account_id ? accountLabelById.get(line.account_id) ?? "Unknown account" : "-"}</td>
                        <td>{line.description || "No line note"}</td>
                        <td className="amount-cell">{formatMoney(line.debit_amount)}</td>
                        <td className="amount-cell">{formatMoney(line.credit_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : null}
        {isJournalEditorOpen ? (
          <div className="journal-popup-backdrop" role="presentation" onClick={closeJournalEditorPopup}>
            <div className="journal-popup-card journal-editor-popup-card" role="dialog" aria-modal="true" aria-label={journalEditorJournalId ? "Update journal" : "Create journal"} onClick={(event) => event.stopPropagation()}>
              <JournalEditorSection operator={operator} journalId={journalEditorJournalId} mode="modal" onClose={closeJournalEditorPopup} />
            </div>
          </div>
        ) : null}
        {activeEvidenceViewer ? (
          <div className="document-viewer-backdrop" role="presentation" onClick={() => setActiveEvidenceViewer(null)}>
            <div className="document-viewer-card" role="dialog" aria-modal="true" aria-label={`Document ${activeEvidenceViewer.filename}`} onClick={(event) => event.stopPropagation()}>
              <div className="document-viewer-header">
                <div>
                  <h3>{activeEvidenceViewer.filename}</h3>
                  <p className="summary-line">Full evidence preview. Click outside this card to close.</p>
                </div>
                <div className="request-actions-inline evidence-row-actions">
                  <button
                    className="button-link button-link-small button-link-secondary"
                    type="button"
                    onClick={() => runAction("Downloading evidence", async () => {
                      await downloadFromApi(`/api/companies/${selectedCompanyId}/documents/${activeEvidenceViewer.documentId}/download`, activeEvidenceViewer.filename);
                    })}
                  >
                    Download
                  </button>
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => setActiveEvidenceViewer(null)}>Close</button>
                </div>
              </div>
              {activeEvidencePreview?.status === "error" || activePdfPreview?.error ? (
                <div className="empty-state document-viewer-empty-state">
                  <strong>Preview unavailable.</strong>
                  <p>{activeEvidencePreview?.error || activePdfPreview?.error || "The document could not be loaded for preview."}</p>
                </div>
              ) : null}
              {activeEvidenceIsLoading ? (
                <div className="empty-state document-viewer-empty-state">
                  <strong>Loading document preview...</strong>
                  <p>The full evidence view will appear here once the file finishes loading.</p>
                </div>
              ) : null}
              {activeEvidenceCanRender ? (
                activeEvidenceIsImage && activeEvidencePreview?.status === "ready" && activeEvidencePreview.url ? (
                  <div className="document-viewer-body">
                    <img className="document-viewer-image" src={activeEvidencePreview.url} alt={activeEvidenceViewer.filename} />
                  </div>
                ) : activeEvidenceIsPdf ? (
                  <div className="document-viewer-body">
                    <div className="document-viewer-pdf-pages">
                      {(activePdfPreview?.pageImageUrls ?? []).map((pageUrl, index) => (
                        <img key={`${activeEvidenceViewer.documentId}-${index + 1}`} className="document-viewer-pdf-page" src={pageUrl} alt={`${activeEvidenceViewer.filename} page ${index + 1}`} />
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="empty-state document-viewer-empty-state">
                    <strong>Inline preview is not available for this file type.</strong>
                    <p>Use Download to open the full document in the system viewer for this format.</p>
                  </div>
                )
              ) : null}
            </div>
          </div>
        ) : null}
      </article>

      <article className="panel panel-wide">
        <div className="panel-heading"><h2>Documents</h2><span className="pill">{documents.length} files</span></div>
        <div className="workspace-split">
          <div className="table-shell document-table-shell">
            <table className="data-table">
              <thead><tr><th>File</th><th>Size</th><th>Uploaded</th><th>Actions</th></tr></thead>
              <tbody>
                {documents.map((item) => (
                  <tr key={item.id} className={selectedDocumentId === item.id ? "is-selected" : ""} onClick={() => setSelectedDocumentId(item.id)}>
                    <td>{item.original_filename}<div className="table-meta">{item.media_type ?? "Unknown type"}</div></td>
                    <td>{Math.round(item.byte_size / 1024)} KB</td>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td className="table-actions">
                      <button className="button-link button-link-small button-link-danger" type="button" onClick={(event) => {
                        event.stopPropagation();
                        runAction("Deleting document", async () => {
                          await deleteDocument(item.id, item.original_filename);
                        });
                      }}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="stacked-cards">
            <div className="mini-card">
              <h3>Upload document</h3>
              <div className="form-grid">
                <Field label="Attachment file"><input type="file" onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)} /></Field>
                <Field label="Note"><input value={documentNote} onChange={(event) => setDocumentNote(event.target.value)} /></Field>
              </div>
              <div className="request-actions">
                <button className="button-link button-link-small" type="button" onClick={() => runAction("Uploading document", async () => {
                  if (!documentFile) {
                    throw new Error("Choose a file before uploading.");
                  }
                  const formData = new FormData();
                  formData.append("file", documentFile);
                  formData.append("note", documentNote);
                  await request(`/api/companies/${selectedCompanyId}/documents`, "POST", formData);
                  setDocumentFile(null);
                  showMessage("success", "Uploaded document.");
                  await refreshAll();
                })}>Upload</button>
              </div>
            </div>
            {selectedDocument ? (
              <div className="mini-card">
                <h3>Document actions</h3>
                <div className="form-grid two-up">
                  <Field label="Filename"><input value={documentDraft.original_filename} onChange={(event) => setDocumentDraft((current) => ({ ...current, original_filename: event.target.value }))} /></Field>
                  <Field label="Media type"><input value={documentDraft.media_type} onChange={(event) => setDocumentDraft((current) => ({ ...current, media_type: event.target.value }))} /></Field>
                </div>
                <div className="request-actions">
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Updating document", async () => {
                    await request(`/api/companies/${selectedCompanyId}/documents/${selectedDocument.id}`, "PUT", { ...documentDraft, media_type: documentDraft.media_type || null });
                    showMessage("success", "Updated document metadata.");
                    await refreshAll();
                  })}>Save document</button>
                  <button className="button-link button-link-small" type="button" onClick={() => runAction("Downloading document", async () => {
                    await downloadFromApi(`/api/companies/${selectedCompanyId}/documents/${selectedDocument.id}/download`, selectedDocument.original_filename);
                  })}>Download</button>
                  <button className="button-link button-link-small button-link-danger" type="button" onClick={() => runAction("Deleting document", async () => {
                    await deleteDocument(selectedDocument.id, selectedDocument.original_filename);
                  })}>Delete document</button>
                </div>
                <div className="form-grid two-up">
                  <Field label="Link entity type"><select value={documentLinkDraft.entity_type} onChange={(event) => setDocumentLinkDraft((current) => ({ ...current, entity_type: event.target.value }))}><option value="journal_entry">Journal entry</option><option value="bas_run">BAS run</option><option value="tax_workpaper_pack">Tax pack</option></select></Field>
                  <Field label="Entity ID"><input value={documentLinkDraft.entity_id} onChange={(event) => setDocumentLinkDraft((current) => ({ ...current, entity_id: event.target.value }))} placeholder={selectedJournalId || selectedBasRunId || selectedTaxPackId || "UUID"} /></Field>
                  <Field label="Link note" wide><input value={documentLinkDraft.note} onChange={(event) => setDocumentLinkDraft((current) => ({ ...current, note: event.target.value }))} /></Field>
                </div>
                <div className="request-actions">
                  <button className="button-link button-link-small button-link-secondary" type="button" onClick={() => runAction("Saving document link", async () => {
                    if (selectedDocumentLink) {
                      await request(`/api/companies/${selectedCompanyId}/documents/${selectedDocument.id}/links/${selectedDocumentLink.id}`, "PUT", { ...documentLinkDraft, note: documentLinkDraft.note || null });
                    } else {
                      await request(`/api/companies/${selectedCompanyId}/documents/${selectedDocument.id}/links`, "POST", { ...documentLinkDraft, note: documentLinkDraft.note || null });
                    }
                    showMessage("success", "Saved document link.");
                    await refreshAll();
                  })}>Save link</button>
                </div>
                <div className="compact-list">
                  {documentLinks.map((item) => (
                    <div className="list-row-action" key={item.id}>
                      <button className={`list-row-button${selectedDocumentLinkId === item.id ? " is-active" : ""}`} type="button" onClick={() => setSelectedDocumentLinkId(item.id)}>{item.entity_type} · {item.entity_id}</button>
                      <button className="button-link button-link-small button-link-danger" type="button" onClick={() => runAction("Deleting document link", async () => {
                        if (!confirmDanger(`Remove link to ${item.entity_type}?`)) {
                          return;
                        }
                        await request(`/api/companies/${selectedCompanyId}/documents/${selectedDocument.id}/links/${item.id}`, "DELETE", undefined, "void");
                        setSelectedDocumentLinkId("");
                        showMessage("success", "Removed document link.");
                        await refreshAll();
                      })}>Remove link</button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </article>
    </section>
  );
}
