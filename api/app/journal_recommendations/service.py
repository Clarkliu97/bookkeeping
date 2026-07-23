from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from importlib import import_module
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, WithJsonSchema, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.accounting import Account, AccountingPeriod, JournalEntry
from app.db.models.companies import Company, CompanyConfigurationVersion
from app.db.models.documents import Document, DocumentLink
from app.db.models.enums import (
    DocumentLinkEntityType,
    JournalStatus,
    JournalRecommendationProposalStatus,
    JournalRecommendationProposalType,
    JournalRecommendationStatus,
    JournalSourceType,
)
from app.db.models.journal_recommendations import (
    JournalRecommendationEntry,
    JournalRecommendationEntryDocument,
    JournalRecommendationLine,
    JournalRecommendationProposal,
    JournalRecommendationRun,
    JournalRecommendationRunDocument,
)
from app.db.models.reference import ReportingCategory, TaxCode
from app.documents.service import resolve_document_path
from app.ledger.router import _apply_journal_payload, _ensure_period_not_locked, _next_entry_number, _validate_journal_lines
from app.schemas.requests import JournalEntryCreate, JournalLineCreate


PROMPT_VERSION = "journal-document-accrual-batch-v7"
PRICE_ESTIMATE_INPUT_TOKENS = 40000
PRICE_ESTIMATE_OUTPUT_TOKENS = 3500
RECOMMENDATION_MAX_OUTPUT_TOKENS = 30000
PRICE_ESTIMATE_NOTE = (
    "Planning estimate assumes approximately 40,000 uncached text or document-input tokens and 3,500 total billed "
    "output tokens, including reasoning tokens, for a moderate batch. Actual cost scales with file count, page count, "
    "image detail, reasoning effort, the number of recommended journals, and optional web-search calls. Stable company "
    "reference data uses a reusable prompt cache key, so repeated runs may have lower cached-input cost."
)
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
SUPPORTED_FILE_TYPES = {"application/pdf", *SUPPORTED_IMAGE_TYPES}
SUPPORTED_ANALYSIS_MODES = {"single", "multiple"}
LlmDecimal = Annotated[Decimal, WithJsonSchema({"type": "number"})]
MULTI_FILE_ACCRUAL_INSTRUCTION = (
    "The company uses accrual reporting. When the evidence shows a payment or bank-clearance date at least five "
    "calendar days after the invoice date, prefer accrual accounting when the documents support it: recommend an "
    "invoice-date recognition entry against trade creditors or another suitable existing liability, then a separate "
    "clearance-date entry that clears that liability against bank. Reuse the relevant invoice, remittance, and bank "
    "statement document numbers on every entry they support. Use only visible dates, do not invent a timing gap, and "
    "do not split the entries when the evidence is ambiguous."
)


@dataclass(frozen=True)
class ModelCatalogItem:
    id: str
    label: str
    input_cost_per_million_tokens_usd: Decimal
    output_cost_per_million_tokens_usd: Decimal
    supports_vision: bool = True
    supports_web_search: bool = False
    reasoning_effort: str | None = None
    prompt_cache_retention: str | None = "in_memory"


MODEL_CATALOG: tuple[ModelCatalogItem, ...] = (
    ModelCatalogItem(
        id="gpt-5.6-sol",
        label="GPT-5.6 Sol",
        input_cost_per_million_tokens_usd=Decimal("5.00"),
        output_cost_per_million_tokens_usd=Decimal("30.00"),
        supports_web_search=True,
        reasoning_effort="high",
        prompt_cache_retention=None,
    ),
    ModelCatalogItem(
        id="gpt-5.6-terra",
        label="GPT-5.6 Terra",
        input_cost_per_million_tokens_usd=Decimal("2.50"),
        output_cost_per_million_tokens_usd=Decimal("15.00"),
        supports_web_search=True,
        reasoning_effort="medium",
        prompt_cache_retention=None,
    ),
    ModelCatalogItem(
        id="gpt-5.6-luna",
        label="GPT-5.6 Luna",
        input_cost_per_million_tokens_usd=Decimal("1.00"),
        output_cost_per_million_tokens_usd=Decimal("6.00"),
        supports_web_search=True,
        reasoning_effort="low",
        prompt_cache_retention=None,
    ),
    ModelCatalogItem(
        id="gpt-5.5",
        label="GPT-5.5",
        input_cost_per_million_tokens_usd=Decimal("5.00"),
        output_cost_per_million_tokens_usd=Decimal("30.00"),
        supports_web_search=True,
        prompt_cache_retention="24h",
    ),
    ModelCatalogItem(
        id="gpt-5.4",
        label="GPT-5.4",
        input_cost_per_million_tokens_usd=Decimal("2.50"),
        output_cost_per_million_tokens_usd=Decimal("15.00"),
        supports_web_search=True,
    ),
    ModelCatalogItem(
        id="gpt-5.4-mini",
        label="GPT-5.4 mini",
        input_cost_per_million_tokens_usd=Decimal("0.75"),
        output_cost_per_million_tokens_usd=Decimal("4.50"),
    ),
    ModelCatalogItem(
        id="gpt-5",
        label="GPT-5",
        input_cost_per_million_tokens_usd=Decimal("1.25"),
        output_cost_per_million_tokens_usd=Decimal("10.00"),
        reasoning_effort="minimal",
    ),
    ModelCatalogItem(
        id="gpt-5-mini",
        label="GPT-5 mini",
        input_cost_per_million_tokens_usd=Decimal("0.25"),
        output_cost_per_million_tokens_usd=Decimal("2.00"),
        reasoning_effort="minimal",
    ),
    ModelCatalogItem(
        id="gpt-5-nano",
        label="GPT-5 nano",
        input_cost_per_million_tokens_usd=Decimal("0.05"),
        output_cost_per_million_tokens_usd=Decimal("0.40"),
        reasoning_effort="minimal",
    ),
)


class LlmRecommendedLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int
    description: str | None = Field(default=None, max_length=160)
    explanation: str | None = Field(default=None, max_length=240)
    account_code: str
    tax_code_code: str | None
    reporting_category_code: str | None
    debit_amount: LlmDecimal
    credit_amount: LlmDecimal


class LlmProposalAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_type: str | None = Field(default=None, max_length=64)
    reporting_category_id: str | None = Field(default=None, max_length=64)
    default_tax_code_id: str | None = Field(default=None, max_length=64)
    allow_manual_posting: bool | None = None
    description: str | None = Field(default=None, max_length=240)
    rate: LlmDecimal | None = None
    is_gst_applicable: bool | None = None
    bas_label: str | None = Field(default=None, max_length=32)
    input_output_type: str | None = Field(default=None, max_length=64)
    category_type: str | None = Field(default=None, max_length=64)


class LlmReferenceProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_type: JournalRecommendationProposalType
    suggested_code: str = Field(max_length=64)
    suggested_name: str = Field(max_length=160)
    rationale: str | None = Field(default=None, max_length=240)
    suggested_attributes_json: LlmProposalAttributes | None


class LlmJournalRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_number: int = Field(ge=1, le=50)
    source_document_numbers: list[int] = Field(max_length=50)
    summary: str = Field(max_length=240)
    entry_date: date | None = Field(
        description=(
            "The transaction, receipt, invoice, or payment date visible in the source documents. "
            "Do not use the upload date or today's date. Return null only when no source document date is visible."
        )
    )
    vendor_name: str | None = Field(default=None, max_length=160)
    total_amount: LlmDecimal | None
    gst_amount: LlmDecimal | None
    currency_code: str
    recommended_description: str = Field(max_length=240)
    recommended_reference: str | None = Field(default=None, max_length=128)
    confidence_summary: str | None = Field(default=None, max_length=240)
    warning_text: str | None = Field(default=None, max_length=300)
    lines: list[LlmRecommendedLine] = Field(min_length=2, max_length=12)


class LlmRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=240)
    confidence_summary: str | None = Field(default=None, max_length=240)
    warning_text: str | None = Field(default=None, max_length=300)
    journal_entries: list[LlmJournalRecommendation] = Field(min_length=1, max_length=50)
    proposals: list[LlmReferenceProposal] = Field(default_factory=list, max_length=5)

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_single_entry(cls, value: Any) -> Any:
        """Keep internal tests and older provider fixtures readable during the v5-to-v6 transition."""
        if not isinstance(value, dict) or "journal_entries" in value or "lines" not in value:
            return value
        upgraded = dict(value)
        entry = {
            "sequence_number": 1,
            "source_document_numbers": [],
            "summary": value.get("summary", "Journal recommendation"),
            "entry_date": upgraded.pop("entry_date", None),
            "vendor_name": upgraded.pop("vendor_name", None),
            "total_amount": upgraded.pop("total_amount", None),
            "gst_amount": upgraded.pop("gst_amount", None),
            "currency_code": upgraded.pop("currency_code", "AUD"),
            "recommended_description": upgraded.pop("recommended_description", "AI-assisted journal draft"),
            "recommended_reference": upgraded.pop("recommended_reference", None),
            "confidence_summary": value.get("confidence_summary"),
            "warning_text": value.get("warning_text"),
            "lines": upgraded.pop("lines"),
        }
        upgraded["journal_entries"] = [entry]
        return upgraded

    @property
    def lines(self) -> list[LlmRecommendedLine]:
        return self.journal_entries[0].lines

    @property
    def entry_date(self) -> date | None:
        return self.journal_entries[0].entry_date

    @property
    def recommended_description(self) -> str:
        return self.journal_entries[0].recommended_description

    @property
    def recommended_reference(self) -> str | None:
        return self.journal_entries[0].recommended_reference


def list_supported_models() -> list[dict[str, Any]]:
    settings = get_settings()
    return [
        {
            "id": item.id,
            "label": item.label,
            "provider": "openai",
            "supports_vision": item.supports_vision,
            "reasoning_effort": item.reasoning_effort,
            "input_cost_per_million_tokens_usd": item.input_cost_per_million_tokens_usd,
            "output_cost_per_million_tokens_usd": item.output_cost_per_million_tokens_usd,
            "estimated_cost_per_1000_calls_usd": estimate_cost_per_1000_calls(item),
            "estimated_input_tokens_per_call": PRICE_ESTIMATE_INPUT_TOKENS,
            "estimated_output_tokens_per_call": PRICE_ESTIMATE_OUTPUT_TOKENS,
            "pricing_note": PRICE_ESTIMATE_NOTE,
            "max_file_count": settings.journal_ai_max_file_count,
            "max_file_size_bytes": settings.journal_ai_max_file_size_bytes,
            "max_total_size_bytes": settings.journal_ai_max_total_size_bytes,
        }
        for item in MODEL_CATALOG
    ]


def ensure_supported_model(model_id: str) -> ModelCatalogItem:
    for item in MODEL_CATALOG:
        if item.id == model_id:
            return item
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported journal recommendation model")


def estimate_cost_per_1000_calls(item: ModelCatalogItem) -> Decimal:
    estimated_cost_per_call = (
        (Decimal(PRICE_ESTIMATE_INPUT_TOKENS) / Decimal("1000000")) * item.input_cost_per_million_tokens_usd
        + (Decimal(PRICE_ESTIMATE_OUTPUT_TOKENS) / Decimal("1000000")) * item.output_cost_per_million_tokens_usd
    )
    return (estimated_cost_per_call * Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_new_files(files: list[tuple[str, str | None, int]]) -> None:
    settings = get_settings()
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload at least one invoice or receipt file")
    if len(files) > settings.journal_ai_max_file_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload at most {settings.journal_ai_max_file_count} files per recommendation run",
        )
    total_size = sum(size for _, _, size in files)
    if total_size > settings.journal_ai_max_total_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded files exceed the configured total size limit for one recommendation run",
        )
    for filename, media_type, size in files:
        if size > settings.journal_ai_max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} exceeds the configured per-file size limit",
            )
        normalized_media_type = normalize_media_type(filename, media_type)
        if normalized_media_type not in SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} uses an unsupported file type for the first version",
            )


def validate_analysis_mode(analysis_mode: str, file_count: int) -> str:
    normalized_mode = analysis_mode.strip().lower()
    if normalized_mode not in SUPPORTED_ANALYSIS_MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Analysis mode must be single or multiple")
    if normalized_mode == "single" and file_count != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Single-file analysis requires exactly one uploaded file",
        )
    return normalized_mode


def normalize_media_type(filename: str, media_type: str | None) -> str:
    if media_type:
        lowered = media_type.lower()
        if lowered == "image/jpg":
            return "image/jpeg"
        return lowered
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "application/octet-stream"


def build_run_detail(db: Session, company_id: UUID, run_id: UUID) -> dict[str, Any]:
    run = _load_run_or_404(db, company_id, run_id)
    documents = db.execute(
        select(JournalRecommendationRunDocument, Document)
        .join(Document, Document.id == JournalRecommendationRunDocument.document_id)
        .where(JournalRecommendationRunDocument.recommendation_run_id == run.id)
        .order_by(JournalRecommendationRunDocument.display_order.asc(), Document.created_at.asc())
    ).all()
    lines = list(
        db.scalars(
            select(JournalRecommendationLine)
            .where(JournalRecommendationLine.recommendation_run_id == run.id)
            .order_by(JournalRecommendationLine.line_number.asc())
        ).all()
    )
    entries = list(
        db.scalars(
            select(JournalRecommendationEntry)
            .where(JournalRecommendationEntry.recommendation_run_id == run.id)
            .order_by(JournalRecommendationEntry.sequence_number.asc())
        ).all()
    )
    entry_documents = db.execute(
        select(JournalRecommendationEntryDocument, Document)
        .join(Document, Document.id == JournalRecommendationEntryDocument.document_id)
        .join(
            JournalRecommendationEntry,
            JournalRecommendationEntry.id == JournalRecommendationEntryDocument.recommendation_entry_id,
        )
        .join(
            JournalRecommendationRunDocument,
            (JournalRecommendationRunDocument.document_id == Document.id)
            & (JournalRecommendationRunDocument.recommendation_run_id == run.id),
        )
        .where(JournalRecommendationEntry.recommendation_run_id == run.id)
        .order_by(
            JournalRecommendationEntry.sequence_number.asc(),
            JournalRecommendationRunDocument.display_order.asc(),
        )
    ).all()
    proposals = list(
        db.scalars(
            select(JournalRecommendationProposal)
            .where(JournalRecommendationProposal.recommendation_run_id == run.id)
            .order_by(JournalRecommendationProposal.created_at.asc())
        ).all()
    )
    run_payload = {
        **run.__dict__,
        "extracted_entry_date": _extract_recommendation_entry_date(run, strict=False),
        "documents": [
            {
                "id": link.id,
                "document_id": document.id,
                "display_order": link.display_order,
                "original_filename": document.original_filename,
                "media_type": document.media_type,
                "byte_size": document.byte_size,
                "created_at": document.created_at,
            }
            for link, document in documents
        ],
        "lines": lines,
        "entries": [
            {
                **{key: value for key, value in entry.__dict__.items() if key != "_sa_instance_state"},
                "documents": [
                    {
                        "id": link.id,
                        "document_id": document.id,
                        "display_order": next(
                            (
                                run_link.display_order
                                for run_link, run_document in documents
                                if run_document.id == document.id
                            ),
                            0,
                        ),
                        "original_filename": document.original_filename,
                        "media_type": document.media_type,
                        "byte_size": document.byte_size,
                        "created_at": document.created_at,
                    }
                    for link, document in entry_documents
                    if link.recommendation_entry_id == entry.id
                ],
                "lines": [line for line in lines if line.recommendation_entry_id == entry.id],
            }
            for entry in entries
        ],
        "proposals": proposals,
        "search_sources": _extract_search_sources(run),
    }
    run_payload.pop("_sa_instance_state", None)
    return run_payload


def _extract_search_sources(run: JournalRecommendationRun) -> list[dict[str, str | None]]:
    raw_response = run.raw_provider_response_json or {}
    output_items = raw_response.get("output") if isinstance(raw_response, dict) else None
    if not isinstance(output_items, list):
        return []

    search_sources: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()
    for output_item in output_items:
        if not isinstance(output_item, dict):
            continue
        action = output_item.get("action")
        if not isinstance(action, dict):
            continue
        sources = action.get("sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if not isinstance(url, str) or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = source.get("title")
            search_sources.append(
                {
                    "title": title if isinstance(title, str) and title else None,
                    "url": url,
                    "domain": urlparse(url).netloc or None,
                }
            )
    return search_sources


def analyze_run(db: Session, *, company_id: UUID, run_id: UUID) -> JournalRecommendationRun:
    settings = get_settings()
    if not settings.journal_ai_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Journal AI workflow is disabled")
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured for journal recommendations",
        )

    run = _load_run_or_404(db, company_id, run_id)
    if run.status == JournalRecommendationStatus.ACCEPTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accepted recommendations cannot be re-analyzed")

    run.status = JournalRecommendationStatus.ANALYZING
    run.started_at = datetime.now(timezone.utc)
    run.completed_at = None
    run.failure_reason = None
    db.flush()

    try:
        documents = _load_run_documents(db, run.id)
        recommendation = _analyze_with_openai(db, run=run, documents=documents)
        _persist_recommendation(db, run=run, recommendation=recommendation, documents=documents)
        run.status = JournalRecommendationStatus.REVIEW_READY
        run.analysis_summary = recommendation.summary
        run.confidence_summary = recommendation.confidence_summary
        run.warning_text = recommendation.warning_text
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run
    except HTTPException:
        run.status = JournalRecommendationStatus.FAILED
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise
    except Exception as exc:  # pragma: no cover - guarded through route tests with monkeypatching
        run.status = JournalRecommendationStatus.FAILED
        run.failure_reason = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Journal recommendation analysis failed: {exc}") from exc


def accept_run(
    db: Session,
    *,
    company_id: UUID,
    run_id: UUID,
    created_by_user_id: UUID,
    accepted_proposal_ids: list[UUID],
) -> list[JournalEntry]:
    run = _load_run_or_404(db, company_id, run_id)
    entries = list(
        db.scalars(
            select(JournalRecommendationEntry)
            .where(JournalRecommendationEntry.recommendation_run_id == run.id)
            .order_by(JournalRecommendationEntry.sequence_number.asc())
        ).all()
    )
    if run.status == JournalRecommendationStatus.ACCEPTED:
        accepted_journals = [
            journal
            for entry in entries
            if entry.accepted_journal_entry_id
            and (journal := db.get(JournalEntry, entry.accepted_journal_entry_id)) is not None
        ]
        if accepted_journals:
            return accepted_journals
    if run.status != JournalRecommendationStatus.REVIEW_READY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only review-ready recommendations can create draft journals")
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This legacy recommendation has no journal groups; re-analyze it before acceptance",
        )

    created_entity_map = _create_accepted_proposals(
        db,
        company_id=company_id,
        run=run,
        accepted_proposal_ids=accepted_proposal_ids,
    )
    journals: list[JournalEntry] = []
    for entry in entries:
        lines = list(
            db.scalars(
                select(JournalRecommendationLine)
                .where(JournalRecommendationLine.recommendation_entry_id == entry.id)
                .order_by(JournalRecommendationLine.line_number.asc())
            ).all()
        )
        if not lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Journal recommendation {entry.sequence_number} has no lines to accept",
            )
        if entry.entry_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Journal recommendation {entry.sequence_number} did not include a document transaction date. "
                    "Re-analyze with readable dates, add date context, or create that journal manually."
                ),
            )
        period_id = _resolve_recommendation_period_id(
            db,
            company_id=company_id,
            entry_date_value=entry.entry_date,
            fallback_period_id=run.target_accounting_period_id,
        )
        _ensure_period_not_locked(db, company_id, period_id)

        payload = JournalEntryCreate(
            entry_date=entry.entry_date,
            accounting_period_id=period_id,
            source_type=JournalSourceType.MANUAL.value,
            description=entry.recommended_description,
            reference=entry.recommended_reference,
            lines=[
                JournalLineCreate(
                    account_id=_resolve_line_account_id(line, created_entity_map),
                    description=line.description,
                    debit_amount=line.debit_amount,
                    credit_amount=line.credit_amount,
                    tax_code_id=_resolve_line_tax_code_id(line, created_entity_map),
                    reporting_category_id=_resolve_line_reporting_category_id(line, created_entity_map),
                    source_document_reference=None,
                )
                for line in lines
            ],
        )
        journal = JournalEntry(
            company_id=company_id,
            entry_number=_next_entry_number(db, company_id),
            entry_date=payload.entry_date,
            accounting_period_id=payload.accounting_period_id,
            status=JournalStatus.DRAFT,
            source_type=JournalSourceType(payload.source_type),
            description=payload.description,
            reference=payload.reference,
            created_by_user_id=created_by_user_id,
        )
        _apply_journal_payload(journal, payload, replace_lines=False)
        _validate_journal_lines(db, company_id, journal.lines)
        db.add(journal)
        db.flush()

        entry_documents = list(
            db.scalars(
                select(Document)
                .join(
                    JournalRecommendationEntryDocument,
                    JournalRecommendationEntryDocument.document_id == Document.id,
                )
                .join(
                    JournalRecommendationRunDocument,
                    (JournalRecommendationRunDocument.document_id == Document.id)
                    & (JournalRecommendationRunDocument.recommendation_run_id == run.id),
                )
                .where(JournalRecommendationEntryDocument.recommendation_entry_id == entry.id)
                .order_by(JournalRecommendationRunDocument.display_order.asc())
            ).all()
        )
        for document_index, document in enumerate(entry_documents, start=1):
            db.add(
                DocumentLink(
                    company_id=company_id,
                    document_id=document.id,
                    entity_type=DocumentLinkEntityType.JOURNAL_ENTRY,
                    entity_id=str(journal.id),
                    note=f"AI recommendation evidence #{document_index}",
                    linked_by_user_id=created_by_user_id,
                )
            )
        entry.accepted_journal_entry_id = journal.id
        journals.append(journal)

    run.status = JournalRecommendationStatus.ACCEPTED
    run.accepted_journal_entry_id = journals[0].id
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    for journal in journals:
        db.refresh(journal)
    return journals


def _resolve_recommendation_period_id(
    db: Session,
    *,
    company_id: UUID,
    entry_date_value: date,
    fallback_period_id: UUID | None,
) -> UUID:
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.company_id == company_id,
            AccountingPeriod.start_date <= entry_date_value,
            AccountingPeriod.end_date >= entry_date_value,
        )
    )
    if period is not None:
        return period.id
    fallback_period = db.get(AccountingPeriod, fallback_period_id) if fallback_period_id else None
    if (
        fallback_period is None
        or fallback_period.company_id != company_id
        or not (fallback_period.start_date <= entry_date_value <= fallback_period.end_date)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Create or choose an accounting period that contains the document transaction date "
                f"{entry_date_value.isoformat()} before accepting the recommendation"
            ),
        )
    return fallback_period.id


def reject_run(db: Session, *, company_id: UUID, run_id: UUID) -> JournalRecommendationRun:
    run = _load_run_or_404(db, company_id, run_id)
    if run.status == JournalRecommendationStatus.ACCEPTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accepted recommendations cannot be rejected")
    run.status = JournalRecommendationStatus.REJECTED
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def _load_run_or_404(db: Session, company_id: UUID, run_id: UUID) -> JournalRecommendationRun:
    run = db.get(JournalRecommendationRun, run_id)
    if run is None or run.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal recommendation run not found")
    return run


def _load_run_documents(db: Session, run_id: UUID) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .join(JournalRecommendationRunDocument, JournalRecommendationRunDocument.document_id == Document.id)
            .where(JournalRecommendationRunDocument.recommendation_run_id == run_id)
            .order_by(JournalRecommendationRunDocument.display_order.asc(), Document.created_at.asc())
        ).all()
    )


def _analyze_with_openai(db: Session, *, run: JournalRecommendationRun, documents: list[Document]) -> LlmRecommendation:
    settings = get_settings()
    model_config = ensure_supported_model(run.provider_model)
    company = db.get(Company, run.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    try:
        openai_module = import_module("openai")
        openai_client = getattr(openai_module, "OpenAI")
    except (ImportError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Journal AI dependencies are not available in the current API runtime",
        ) from exc

    client = openai_client(api_key=settings.openai_api_key, timeout=settings.journal_ai_request_timeout_seconds)
    reference_context = _build_reference_context(db, run.company_id)
    cached_reference_prefix = _build_cached_reference_prefix(company=company, reference_context=reference_context)
    request_suffix = _build_recommendation_request_suffix(
        run=run,
        documents=documents,
        reference_context=reference_context,
    )
    reference_context_hash = _hash_prompt_prefix(cached_reference_prefix)
    prompt_cache_key = _build_prompt_cache_key(
        company_id=run.company_id,
        prompt_version=run.prompt_version,
        reference_context_hash=reference_context_hash,
    )
    content_items: list[dict[str, Any]] = [
        {"type": "input_text", "text": cached_reference_prefix},
        {"type": "input_text", "text": request_suffix},
    ]
    content_items.extend(_build_document_content_items(documents))
    retry_feedback: str | None = None
    parse_retry_used = False
    balance_retry_used = False
    disable_web_search_tools = False

    for _attempt in range(3):
        request_input = [{"role": "user", "content": content_items}]
        if retry_feedback:
            request_input.append(
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": retry_feedback}],
                }
            )

        parse_kwargs = {
            "model": run.provider_model,
            "instructions": _build_system_prompt(),
            "input": request_input,
            "text_format": LlmRecommendation,
            "max_output_tokens": RECOMMENDATION_MAX_OUTPUT_TOKENS,
            "prompt_cache_key": prompt_cache_key,
            "metadata": {
                "company_id": str(run.company_id),
                "run_id": str(run.id),
                "prompt_version": run.prompt_version,
                "reference_context_hash": reference_context_hash,
            },
        }
        prompt_cache_retention = getattr(model_config, "prompt_cache_retention", "in_memory")
        if prompt_cache_retention:
            parse_kwargs["prompt_cache_retention"] = prompt_cache_retention
        if model_config.reasoning_effort:
            parse_kwargs["reasoning"] = {"effort": model_config.reasoning_effort}
        web_search_kwargs = _build_openai_web_search_kwargs(
            settings=settings,
            model_config=model_config,
            disabled=disable_web_search_tools,
        )
        if web_search_kwargs:
            parse_kwargs.update(web_search_kwargs)
        try:
            response = client.responses.parse(**parse_kwargs)
        except ValidationError as exc:
            if not parse_retry_used:
                parse_retry_used = True
                retry_feedback = _build_structured_output_retry_text(exc)
                # Keep schema-repair retries deterministic by removing optional tool calls.
                disable_web_search_tools = True
                continue
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"The model returned invalid structured JSON after retry: {_summarize_validation_error(exc)}",
            ) from exc
        _capture_provider_response(run, response)

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            refusal_message = None
            for output_item in getattr(response, "output", []) or []:
                for content in getattr(output_item, "content", []) or []:
                    refusal_message = getattr(content, "refusal", None)
                    if refusal_message:
                        break
                if refusal_message:
                    break
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=refusal_message or _build_unstructured_response_detail(response),
            )

        try:
            _validate_recommendation_batch(
                parsed,
                document_count=len(documents),
                analysis_mode=getattr(run, "analysis_mode", "multiple"),
            )
        except HTTPException as exc:
            if not balance_retry_used and exc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
                balance_retry_used = True
                retry_feedback = _build_balance_retry_text(parsed)
                continue
            raise

        return parsed

    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The model did not return a valid journal recommendation")


def _capture_provider_response(run: JournalRecommendationRun, response: Any) -> None:
    run.raw_provider_response_json = response.model_dump(mode="json") if hasattr(response, "model_dump") else None
    usage = getattr(response, "usage", None)
    run.provider_usage_json = usage.model_dump(mode="json") if hasattr(usage, "model_dump") else None


def _build_openai_web_search_kwargs(
    *, settings: Any, model_config: ModelCatalogItem | Any, disabled: bool = False
) -> dict[str, Any]:
    if disabled:
        return {}
    if not getattr(settings, "journal_ai_web_search_enabled", True):
        return {}
    if not getattr(model_config, "supports_web_search", False):
        return {}
    return {
        "tools": [{"type": "web_search", "search_context_size": "low"}],
        "tool_choice": "auto",
        "max_tool_calls": 3,
        "include": ["web_search_call.action.sources"],
    }


def _build_unstructured_response_detail(response: Any) -> str:
    details = []
    response_status = getattr(response, "status", None)
    if response_status:
        details.append(f"provider status={response_status}")
    incomplete_details = getattr(response, "incomplete_details", None)
    incomplete_reason = getattr(incomplete_details, "reason", None)
    if incomplete_reason:
        details.append(f"reason={incomplete_reason}")
    output_items = getattr(response, "output", []) or []
    if output_items:
        output_types = [getattr(output_item, "type", None) for output_item in output_items]
        output_types = [item for item in output_types if item]
        if output_types:
            details.append(f"output_types={','.join(output_types)}")

    if not details:
        return "The model did not return a structured journal recommendation"
    return f"The model did not return a structured journal recommendation ({'; '.join(details)})"


def _build_reference_context(db: Session, company_id: UUID) -> dict[str, Any]:
    configuration = db.scalar(
        select(CompanyConfigurationVersion)
        .where(CompanyConfigurationVersion.company_id == company_id)
        .order_by(CompanyConfigurationVersion.version_number.desc())
    )
    accounts = list(
        db.scalars(
            select(Account)
            .where(Account.company_id == company_id, Account.is_active.is_(True))
            .order_by(Account.account_code.asc())
        ).all()
    )
    tax_codes = list(
        db.scalars(
            select(TaxCode)
            .where(((TaxCode.company_id == company_id) | (TaxCode.company_id.is_(None))), TaxCode.is_active.is_(True))
            .order_by(TaxCode.code.asc())
        ).all()
    )
    reporting_categories = list(
        db.scalars(
            select(ReportingCategory)
            .where(
                ((ReportingCategory.company_id == company_id) | (ReportingCategory.company_id.is_(None))),
                ReportingCategory.is_active.is_(True),
            )
            .order_by(ReportingCategory.code.asc())
        ).all()
    )
    tax_code_codes_by_id = {str(tax_code.id): tax_code.code for tax_code in tax_codes}
    return {
        "configuration": {
            "gst_registered": configuration.gst_registered if configuration else None,
            "bas_frequency": str(configuration.bas_frequency) if configuration else None,
            "bas_reporting_basis": str(configuration.bas_reporting_basis) if configuration else None,
            "allow_self_approval": configuration.allow_self_approval if configuration else None,
            "period_lock_policy": str(configuration.period_lock_policy) if configuration else None,
        },
        "accounts": [
            {
                "code": account.account_code,
                "name": account.name,
                "type": str(account.account_type),
                "tax": tax_code_codes_by_id.get(str(account.default_tax_code_id)) if account.default_tax_code_id else None,
                "posting": account.allow_manual_posting,
            }
            for account in accounts
        ],
        "tax_codes": [
            {
                "code": tax_code.code,
                "name": tax_code.name,
                "rate": str(tax_code.rate),
                "bas_label": tax_code.bas_label,
                "input_output_type": str(tax_code.input_output_type),
            }
            for tax_code in tax_codes
        ],
        "reporting_categories": [
            {
                "code": category.code,
                "name": category.name,
                "category_type": str(category.category_type),
            }
            for category in reporting_categories
        ],
    }


def _build_system_prompt() -> str:
    return (
        "Prepare review-only Australian bookkeeping journal recommendations from the numbered source documents. "
        "In multiple mode, group documents by economic transaction: several files may support one journal, while "
        "unrelated invoices, receipts, payments, credits, or settlements must become separate journal_entries. "
        "One source document may support several journal entries; for example, repeat a monthly bank statement's "
        "document number on every recommendation containing a transaction evidenced by that statement. "
        "Assign every source document number to at least one journal entry and never merge transactions merely because "
        "they were uploaded together. In single mode return exactly one journal entry and assign every uploaded "
        "document to it. "
        "Each journal entry must independently balance, contain at least two one-sided lines, and preserve materially "
        "different fees, adjustments, account classes, and GST treatments as reviewable lines. Use visible document "
        "transaction dates only; never substitute upload, analysis, system, or current dates. Prefer existing account, "
        "tax, and reporting codes. Separate visible GST when appropriate; when GST is absent or uncertain, do not invent "
        "it, and use concise warnings. Use web search only when available and needed to verify uncertain supplier or GST "
        "treatment. Propose reference data only when no existing code fits. Return only the supplied structured schema, "
        "keep text concise, do not transcribe source documents, and never describe a recommendation as posted, lodged, "
        "filed, or final."
    )


def _build_cached_reference_prefix(*, company: Company, reference_context: dict[str, Any]) -> str:
    payload = {
        "company": {
            "legal_name": company.legal_name,
            "entity_type": company.entity_type,
            "base_currency": company.base_currency,
            "country_code": company.country_code,
        },
        "reference_context": reference_context,
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


def _build_recommendation_request_suffix(
    *,
    run: JournalRecommendationRun,
    documents: list[Document],
    reference_context: dict[str, Any] | None = None,
) -> str:
    configuration = (reference_context or {}).get("configuration")
    reporting_basis = configuration.get("bas_reporting_basis") if isinstance(configuration, dict) else None
    accrual_timing_instruction = (
        MULTI_FILE_ACCRUAL_INSTRUCTION
        if run.analysis_mode == "multiple" and len(documents) > 1 and str(reporting_basis).lower() == "accrual"
        else None
    )
    payload = {
        "recommendation_request": {
            "analysis_mode": run.analysis_mode,
            "accounting_policy_instruction": accrual_timing_instruction,
            "operator_note": run.user_context_note,
            "target_accounting_period_id": str(run.target_accounting_period_id) if run.target_accounting_period_id else None,
            "documents": [
                {
                    "document_number": index,
                    "original_filename": document.original_filename,
                    "media_type": document.media_type,
                    "byte_size": document.byte_size,
                }
                for index, document in enumerate(documents, start=1)
            ],
        }
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


def _build_user_text(
    *,
    run: JournalRecommendationRun,
    company: Company,
    reference_context: dict[str, Any],
    documents: list[Document],
) -> str:
    payload = {
        "cached_reference_prefix": json.loads(
            _build_cached_reference_prefix(company=company, reference_context=reference_context)
        ),
        "recommendation_request_suffix": json.loads(
            _build_recommendation_request_suffix(
                run=run,
                documents=documents,
                reference_context=reference_context,
            )
        ),
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


def _hash_prompt_prefix(prompt_prefix: str) -> str:
    return hashlib.sha256(prompt_prefix.encode("utf-8")).hexdigest()


def _build_prompt_cache_key(
    *,
    company_id: UUID,
    prompt_version: str,
    reference_context_hash: str,
) -> str:
    company_prompt_hash = hashlib.sha256(f"{company_id}:{prompt_version}".encode("utf-8")).hexdigest()[:16]
    return f"jr:{company_prompt_hash}:{reference_context_hash[:32]}"


def _build_balance_retry_text(recommendation: LlmRecommendation) -> str:
    entry_totals = [
        {
            "sequence_number": entry.sequence_number,
            "line_count": len(entry.lines),
            "debit_total": str(sum((line.debit_amount for line in entry.lines), Decimal("0.00"))),
            "credit_total": str(sum((line.credit_amount for line in entry.lines), Decimal("0.00"))),
            "source_document_numbers": entry.source_document_numbers,
        }
        for entry in recommendation.journal_entries
    ]
    serialized = json.dumps(recommendation.model_dump(mode="json"), separators=(",", ":"), default=str)
    return (
        "Your previous batch did not satisfy the accounting or document-grouping validation rules. "
        f"Per-entry diagnostics: {json.dumps(entry_totals, separators=(',', ':'))}. "
        "Return sequentially numbered journal entries; each must have sequential line numbers, at least two one-sided "
        "lines, and exactly equal debit and credit totals. Assign every source document number to at least one entry. "
        "Preserve source facts, transaction boundaries, vendor details, and accounting intent where possible. "
        f"Previous invalid recommendation JSON: {serialized}"
    )


def _extract_recommendation_entry_date(run: JournalRecommendationRun, *, strict: bool) -> date | None:
    normalized = run.normalized_result_json or {}
    journal_entries = normalized.get("journal_entries")
    value = (
        journal_entries[0].get("entry_date")
        if isinstance(journal_entries, list) and len(journal_entries) == 1 and isinstance(journal_entries[0], dict)
        else normalized.get("entry_date")
    )
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        if strict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The recommendation returned an invalid document transaction date",
            ) from exc
        return None


def _build_structured_output_retry_text(exc: ValidationError) -> str:
    return (
        "Your previous response was not valid structured JSON and could not be parsed. "
        f"Parser summary: {_summarize_validation_error(exc)}. "
        "Return exactly one JSON object matching the supplied schema. "
        "Do not include markdown, code fences, trailing commentary, source-document transcripts, schemas, "
        "reference_context, or prompt instructions. Do not add fields outside the schema. "
        "Always include proposals, using an empty list if none are needed. Keep all text fields concise."
    )


def _summarize_validation_error(exc: ValidationError) -> str:
    text = str(exc)
    for line in text.splitlines():
        stripped = line.strip()
        if "Invalid JSON:" in stripped:
            return stripped[:240]
    return text.splitlines()[0][:240] if text else "invalid structured output"


def _build_document_content_items(documents: list[Document]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for document_number, document in enumerate(documents, start=1):
        path = resolve_document_path(document.storage_path)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        media_type = normalize_media_type(document.original_filename, document.media_type)
        data_url = f"data:{media_type};base64,{encoded}"
        items.append(
            {
                "type": "input_text",
                "text": json.dumps(
                    {
                        "source_document": {
                            "document_number": document_number,
                            "original_filename": document.original_filename,
                            "media_type": media_type,
                        }
                    },
                    separators=(",", ":"),
                ),
            }
        )
        if media_type in SUPPORTED_IMAGE_TYPES:
            items.append(
                {
                    "type": "input_image",
                    "image_url": data_url,
                    "detail": "high",
                }
            )
        else:
            items.append(
                {
                    "type": "input_file",
                    "filename": document.original_filename,
                    "file_data": data_url,
                }
            )
    return items


def _persist_recommendation(
    db: Session,
    *,
    run: JournalRecommendationRun,
    recommendation: LlmRecommendation,
    documents: list[Document],
) -> None:
    _validate_recommendation_batch(
        recommendation,
        document_count=len(documents),
        analysis_mode=run.analysis_mode,
    )
    db.execute(delete(JournalRecommendationLine).where(JournalRecommendationLine.recommendation_run_id == run.id))
    existing_entry_ids = select(JournalRecommendationEntry.id).where(
        JournalRecommendationEntry.recommendation_run_id == run.id
    )
    db.execute(
        delete(JournalRecommendationEntryDocument).where(
            JournalRecommendationEntryDocument.recommendation_entry_id.in_(existing_entry_ids)
        )
    )
    db.execute(delete(JournalRecommendationEntry).where(JournalRecommendationEntry.recommendation_run_id == run.id))
    db.execute(delete(JournalRecommendationProposal).where(JournalRecommendationProposal.recommendation_run_id == run.id))

    accounts_by_code = {
        account.account_code: account
        for account in db.scalars(select(Account).where(Account.company_id == run.company_id)).all()
    }
    tax_codes_by_code = {
        tax_code.code: tax_code
        for tax_code in db.scalars(
            select(TaxCode).where((TaxCode.company_id == run.company_id) | (TaxCode.company_id.is_(None)))
        ).all()
    }
    categories_by_code = {
        category.code: category
        for category in db.scalars(
            select(ReportingCategory).where(
                (ReportingCategory.company_id == run.company_id) | (ReportingCategory.company_id.is_(None))
            )
        ).all()
    }

    for recommended_entry in recommendation.journal_entries:
        entry = JournalRecommendationEntry(
            company_id=run.company_id,
            recommendation_run_id=run.id,
            sequence_number=recommended_entry.sequence_number,
            summary=recommended_entry.summary,
            entry_date=recommended_entry.entry_date,
            vendor_name=recommended_entry.vendor_name,
            total_amount=recommended_entry.total_amount,
            gst_amount=recommended_entry.gst_amount,
            currency_code=recommended_entry.currency_code,
            recommended_description=recommended_entry.recommended_description,
            recommended_reference=recommended_entry.recommended_reference,
            confidence_summary=recommended_entry.confidence_summary,
            warning_text=recommended_entry.warning_text,
        )
        db.add(entry)
        db.flush()

        for document_number in recommended_entry.source_document_numbers:
            db.add(
                JournalRecommendationEntryDocument(
                    company_id=run.company_id,
                    recommendation_entry_id=entry.id,
                    document_id=documents[document_number - 1].id,
                )
            )

        for line in recommended_entry.lines:
            account = accounts_by_code.get(line.account_code)
            tax_code = tax_codes_by_code.get(line.tax_code_code) if line.tax_code_code else None
            category = categories_by_code.get(line.reporting_category_code) if line.reporting_category_code else None
            db.add(
                JournalRecommendationLine(
                    company_id=run.company_id,
                    recommendation_run_id=run.id,
                    recommendation_entry_id=entry.id,
                    line_number=line.line_number,
                    description=line.description,
                    explanation=line.explanation,
                    suggested_account_id=account.id if account else None,
                    suggested_account_code=line.account_code,
                    suggested_tax_code_id=tax_code.id if tax_code else None,
                    suggested_tax_code_code=line.tax_code_code,
                    suggested_reporting_category_id=category.id if category else None,
                    suggested_reporting_category_code=line.reporting_category_code,
                    debit_amount=line.debit_amount,
                    credit_amount=line.credit_amount,
                )
            )

    for proposal in recommendation.proposals:
        proposal_type = JournalRecommendationProposalType(proposal.proposal_type)
        db.add(
            JournalRecommendationProposal(
                company_id=run.company_id,
                recommendation_run_id=run.id,
                proposal_type=proposal_type,
                status=JournalRecommendationProposalStatus.PROPOSED,
                suggested_code=proposal.suggested_code,
                suggested_name=proposal.suggested_name,
                suggested_attributes_json=(
                    proposal.suggested_attributes_json.model_dump(exclude_none=True)
                    if proposal.suggested_attributes_json
                    else None
                ),
                rationale=proposal.rationale,
            )
        )

    run.normalized_result_json = recommendation.model_dump(mode="json")


def _validate_recommendation_batch(
    recommendation: LlmRecommendation,
    *,
    document_count: int,
    analysis_mode: str,
) -> None:
    entries = recommendation.journal_entries
    if analysis_mode == "single" and len(entries) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Single-file analysis must return exactly one journal entry",
        )

    expected_sequences = list(range(1, len(entries) + 1))
    actual_sequences = [entry.sequence_number for entry in entries]
    if actual_sequences != expected_sequences:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Model returned journal entries with invalid sequence numbers",
        )

    assigned_documents: set[int] = set()
    for entry in entries:
        _validate_recommendation_balance(entry.lines)
        line_numbers = [line.line_number for line in entry.lines]
        if line_numbers != list(range(1, len(entry.lines) + 1)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Journal recommendation {entry.sequence_number} has invalid line numbers",
            )
        if document_count == 0:
            entry.source_document_numbers = []
            continue
        if not entry.source_document_numbers and len(entries) == 1:
            entry.source_document_numbers = list(range(1, document_count + 1))
        unique_document_numbers = list(dict.fromkeys(entry.source_document_numbers))
        if not unique_document_numbers or any(number < 1 or number > document_count for number in unique_document_numbers):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Journal recommendation {entry.sequence_number} has invalid source-document assignments",
            )
        entry.source_document_numbers = unique_document_numbers
        assigned_documents.update(unique_document_numbers)

    expected_documents = set(range(1, document_count + 1))
    if assigned_documents != expected_documents:
        missing = sorted(expected_documents - assigned_documents)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Model did not analyze every source document; missing document numbers: {missing}",
        )


def _validate_recommendation_balance(lines: list[LlmRecommendedLine]) -> None:
    if len(lines) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Model returned fewer than two journal lines")
    debit_total, credit_total = _sum_line_totals(lines)
    if debit_total != credit_total:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Model returned an unbalanced recommendation")


def _sum_line_totals(lines: list[LlmRecommendedLine]) -> tuple[Decimal, Decimal]:
    debit_total = sum((line.debit_amount for line in lines), Decimal("0.00"))
    credit_total = sum((line.credit_amount for line in lines), Decimal("0.00"))
    for line in lines:
        valid_line = (
            (line.debit_amount > Decimal("0.00") and line.credit_amount == Decimal("0.00"))
            or (line.credit_amount > Decimal("0.00") and line.debit_amount == Decimal("0.00"))
        )
        if not valid_line:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Model returned an invalid journal line shape")
    return debit_total, credit_total


def _create_accepted_proposals(
    db: Session,
    *,
    company_id: UUID,
    run: JournalRecommendationRun,
    accepted_proposal_ids: list[UUID],
) -> dict[tuple[str, str], UUID]:
    if not accepted_proposal_ids:
        return {}
    proposals = list(
        db.scalars(
            select(JournalRecommendationProposal).where(
                JournalRecommendationProposal.recommendation_run_id == run.id,
                JournalRecommendationProposal.id.in_(accepted_proposal_ids),
            )
        ).all()
    )
    if len(proposals) != len(set(accepted_proposal_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more accepted proposal ids are invalid")

    created_entity_map: dict[tuple[str, str], UUID] = {}
    for proposal in proposals:
        if proposal.status == JournalRecommendationProposalStatus.CREATED and proposal.created_entity_id:
            created_entity_map[(proposal.proposal_type.value, proposal.suggested_code)] = UUID(proposal.created_entity_id)
            continue
        attributes = proposal.suggested_attributes_json or {}
        if proposal.proposal_type == JournalRecommendationProposalType.ACCOUNT:
            account = db.scalar(
                select(Account).where(Account.company_id == company_id, Account.account_code == proposal.suggested_code)
            )
            if account is None:
                account = Account(
                    company_id=company_id,
                    account_code=proposal.suggested_code,
                    name=proposal.suggested_name,
                    account_type=attributes.get("account_type", "expense"),
                    reporting_category_id=attributes.get("reporting_category_id"),
                    default_tax_code_id=attributes.get("default_tax_code_id"),
                    is_active=True,
                    allow_manual_posting=attributes.get("allow_manual_posting", True),
                )
                db.add(account)
                db.flush()
            proposal.created_entity_id = str(account.id)
            created_entity_map[(proposal.proposal_type.value, proposal.suggested_code)] = account.id
        elif proposal.proposal_type == JournalRecommendationProposalType.TAX_CODE:
            tax_code = db.scalar(
                select(TaxCode).where(TaxCode.company_id == company_id, TaxCode.code == proposal.suggested_code)
            )
            if tax_code is None:
                tax_code = TaxCode(
                    company_id=company_id,
                    code=proposal.suggested_code,
                    name=proposal.suggested_name,
                    description=attributes.get("description"),
                    rate=Decimal(str(attributes.get("rate", "0.00"))),
                    is_gst_applicable=attributes.get("is_gst_applicable", True),
                    is_active=True,
                    bas_label=attributes.get("bas_label"),
                    input_output_type=attributes.get("input_output_type", "none"),
                )
                db.add(tax_code)
                db.flush()
            proposal.created_entity_id = str(tax_code.id)
            created_entity_map[(proposal.proposal_type.value, proposal.suggested_code)] = tax_code.id
        else:
            category = db.scalar(
                select(ReportingCategory).where(
                    ReportingCategory.company_id == company_id,
                    ReportingCategory.code == proposal.suggested_code,
                )
            )
            if category is None:
                category = ReportingCategory(
                    company_id=company_id,
                    code=proposal.suggested_code,
                    name=proposal.suggested_name,
                    is_active=True,
                    category_type=attributes.get("category_type", "other"),
                )
                db.add(category)
                db.flush()
            proposal.created_entity_id = str(category.id)
            created_entity_map[(proposal.proposal_type.value, proposal.suggested_code)] = category.id
        proposal.status = JournalRecommendationProposalStatus.CREATED
    return created_entity_map


def _resolve_line_account_id(line: JournalRecommendationLine, created_entity_map: dict[tuple[str, str], UUID]) -> UUID:
    if line.suggested_account_id:
        return line.suggested_account_id
    if line.suggested_account_code:
        created = created_entity_map.get((JournalRecommendationProposalType.ACCOUNT.value, line.suggested_account_code))
        if created:
            return created
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Line {line.line_number} still has no resolved account")


def _resolve_line_tax_code_id(line: JournalRecommendationLine, created_entity_map: dict[tuple[str, str], UUID]) -> UUID | None:
    if line.suggested_tax_code_id:
        return line.suggested_tax_code_id
    if line.suggested_tax_code_code:
        return created_entity_map.get((JournalRecommendationProposalType.TAX_CODE.value, line.suggested_tax_code_code))
    return None


def _resolve_line_reporting_category_id(line: JournalRecommendationLine, created_entity_map: dict[tuple[str, str], UUID]) -> UUID | None:
    if line.suggested_reporting_category_id:
        return line.suggested_reporting_category_id
    if line.suggested_reporting_category_code:
        return created_entity_map.get(
            (JournalRecommendationProposalType.REPORTING_CATEGORY.value, line.suggested_reporting_category_code)
        )
    return None
