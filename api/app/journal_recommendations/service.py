from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from importlib import import_module
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
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
    JournalRecommendationLine,
    JournalRecommendationProposal,
    JournalRecommendationRun,
    JournalRecommendationRunDocument,
)
from app.db.models.reference import ReportingCategory, TaxCode
from app.documents.service import resolve_document_path
from app.ledger.router import _apply_journal_payload, _ensure_period_not_locked, _next_entry_number, _validate_journal_lines
from app.schemas.requests import JournalEntryCreate, JournalLineCreate


PROMPT_VERSION = "journal-document-v5"
PRICE_ESTIMATE_INPUT_TOKENS = 24000
PRICE_ESTIMATE_OUTPUT_TOKENS = 1400
RECOMMENDATION_MAX_OUTPUT_TOKENS = 5000
PRICE_ESTIMATE_NOTE = (
    "Estimate assumes approximately 24,000 uncached text input tokens and 1,400 output tokens per run "
    "after loading the expanded company reference-data pack with compact account context. Repeated runs "
    "for unchanged company reference data may be lower when prompt caching is applied. The request allows "
    "a higher output cap to avoid truncated structured JSON from smaller models, and the estimate now reflects "
    "the expanded GST or bundle-separation instructions plus optional search-capable verification. Actual PDF, "
    "image, and live web-search usage can still be materially higher because file inputs and provider tool calls "
    "add tokenized content beyond this planning estimate."
)
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
SUPPORTED_FILE_TYPES = {"application/pdf", *SUPPORTED_IMAGE_TYPES}


@dataclass(frozen=True)
class ModelCatalogItem:
    id: str
    label: str
    input_cost_per_million_tokens_usd: Decimal
    output_cost_per_million_tokens_usd: Decimal
    supports_vision: bool = True
    supports_web_search: bool = False
    reasoning_effort: str | None = None
    prompt_cache_retention: str = "in_memory"


MODEL_CATALOG: tuple[ModelCatalogItem, ...] = (
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
    debit_amount: Decimal
    credit_amount: Decimal


class LlmProposalAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_type: str | None = Field(default=None, max_length=64)
    reporting_category_id: str | None = Field(default=None, max_length=64)
    default_tax_code_id: str | None = Field(default=None, max_length=64)
    allow_manual_posting: bool | None = None
    description: str | None = Field(default=None, max_length=240)
    rate: Decimal | None = None
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


class LlmRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=240)
    entry_date: date | None = Field(
        description=(
            "The transaction, receipt, invoice, or payment date visible in the source documents. "
            "Do not use the upload date or today's date. Return null only when no source document date is visible."
        )
    )
    vendor_name: str | None = Field(default=None, max_length=160)
    total_amount: Decimal | None
    gst_amount: Decimal | None
    currency_code: str
    recommended_description: str = Field(max_length=240)
    recommended_reference: str | None = Field(default=None, max_length=128)
    confidence_summary: str | None = Field(default=None, max_length=240)
    warning_text: str | None = Field(default=None, max_length=300)
    lines: list[LlmRecommendedLine] = Field(min_length=2, max_length=12)
    proposals: list[LlmReferenceProposal] = Field(default_factory=list, max_length=5)


def list_supported_models() -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "label": item.label,
            "provider": "openai",
            "supports_vision": item.supports_vision,
            "input_cost_per_million_tokens_usd": item.input_cost_per_million_tokens_usd,
            "output_cost_per_million_tokens_usd": item.output_cost_per_million_tokens_usd,
            "estimated_cost_per_1000_calls_usd": estimate_cost_per_1000_calls(item),
            "estimated_input_tokens_per_call": PRICE_ESTIMATE_INPUT_TOKENS,
            "estimated_output_tokens_per_call": PRICE_ESTIMATE_OUTPUT_TOKENS,
            "pricing_note": PRICE_ESTIMATE_NOTE,
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
        _persist_recommendation(db, run=run, recommendation=recommendation)
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
) -> JournalEntry:
    run = _load_run_or_404(db, company_id, run_id)
    if run.status != JournalRecommendationStatus.REVIEW_READY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only review-ready recommendations can create draft journals")
    if run.accepted_journal_entry_id is not None:
        journal = db.get(JournalEntry, run.accepted_journal_entry_id)
        if journal is not None:
            return journal

    created_entity_map = _create_accepted_proposals(
        db,
        company_id=company_id,
        run=run,
        accepted_proposal_ids=accepted_proposal_ids,
    )
    lines = list(
        db.scalars(
            select(JournalRecommendationLine)
            .where(JournalRecommendationLine.recommendation_run_id == run.id)
            .order_by(JournalRecommendationLine.line_number.asc())
        ).all()
    )
    if not lines:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recommendation has no journal lines to accept")

    entry_date_value = _extract_recommendation_entry_date(run, strict=True)
    if entry_date_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The recommendation did not include a document transaction date. Re-analyze with a readable "
                "invoice or receipt date, add the date in the transaction context, or create the journal manually."
            ),
        )

    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.company_id == company_id,
            AccountingPeriod.start_date <= entry_date_value,
            AccountingPeriod.end_date >= entry_date_value,
        )
    )
    period_id = period.id if period is not None else run.target_accounting_period_id
    if period_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Create or choose an accounting period that contains the document transaction date {entry_date_value.isoformat()} before accepting the recommendation",
        )

    _ensure_period_not_locked(db, company_id, period_id)

    payload = JournalEntryCreate(
        entry_date=entry_date_value,
        accounting_period_id=period_id,
        source_type=JournalSourceType.MANUAL.value,
        description=run.normalized_result_json.get("recommended_description") if run.normalized_result_json else run.analysis_summary or "AI-assisted journal draft",
        reference=run.normalized_result_json.get("recommended_reference") if run.normalized_result_json else None,
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

    run_documents = _load_run_documents(db, run.id)
    for index, document in enumerate(run_documents, start=1):
        existing_link = db.scalar(
            select(DocumentLink).where(
                DocumentLink.company_id == company_id,
                DocumentLink.document_id == document.id,
                DocumentLink.entity_type == DocumentLinkEntityType.JOURNAL_ENTRY,
                DocumentLink.entity_id == str(journal.id),
            )
        )
        if existing_link is None:
            db.add(
                DocumentLink(
                    company_id=company_id,
                    document_id=document.id,
                    entity_type=DocumentLinkEntityType.JOURNAL_ENTRY,
                    entity_id=str(journal.id),
                    note=f"AI recommendation evidence #{index}",
                    linked_by_user_id=created_by_user_id,
                )
            )

    run.status = JournalRecommendationStatus.ACCEPTED
    run.accepted_journal_entry_id = journal.id
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(journal)
    return journal


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
    request_suffix = _build_recommendation_request_suffix(run=run, documents=documents)
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
            _validate_recommendation_balance(parsed.lines)
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
        "You prepare internal bookkeeping support recommendations for an Australian internal finance system. "
        "Analyze one transaction bundle that may contain multiple invoices or receipts. "
        "Return only one structured JSON object via the supplied schema. "
        "Do not copy reference_context, prompt instructions, schemas, source text, or markdown into the answer. "
        "Use only the schema fields; do not invent fields such as notes, debit_tax_amount, or credit_tax_amount. "
        "Keep all summaries, explanations, warnings, and proposal rationales concise. "
        "Separate materially distinct bundle components when they reflect different adjustments, settlement items, fees, revenue or expense classes, or different GST treatment; do not collapse them into one line if that would hide the accounting substance. "
        "Recommend a draft journal entry for review, not a posted journal. "
        "Set entry_date to the transaction, receipt, invoice, or payment date visible in the documents. "
        "Never set entry_date to the upload date, analysis date, or today's date unless that is also the visible document date. "
        "Prefer existing reference data by account_code, tax_code_code, and reporting_category_code when suitable. "
        "When GST is visible on source documents, recommend separate GST input or output lines where appropriate. "
        "When GST is not visible and the user has not provided related context, determine whether the transaction would ordinarily involve GST; if the model has access to web search or browsing tools, use them to verify the supplier, product, or service when needed, otherwise state the uncertainty and avoid inventing GST. "
        "Assess GST involvement separately for each materially distinct bundle component rather than assuming one GST outcome for the whole bundle. "
        "Only propose new reference data when the existing list is insufficient, and explain why. "
        "Do not claim that anything is ready to lodge, filed, or final. "
        "If uncertain, populate warning_text and confidence_summary conservatively."
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
        "instructions": {
            "bundle_scope": "All attached files relate to one transaction bundle and should be analyzed together.",
            "required_behavior": [
                "Recommend a balanced double-entry journal draft.",
                (
                    "Extract entry_date from the receipt, invoice, transaction, payment, issue, or sale date shown "
                    "in the attached source files. Use ISO format YYYY-MM-DD. Do not use the file upload date, "
                    "system date, analysis date, or current date as a fallback."
                ),
                "Keep text fields short; do not quote or transcribe long invoice or receipt passages.",
                "Do not return this reference_context or instructions object in the answer.",
                (
                    "Each line object must contain only line_number, description, explanation, account_code, "
                    "tax_code_code, reporting_category_code, debit_amount, and credit_amount. Do not add notes, "
                    "tax amount, quantity, unit price, or source text fields."
                ),
                (
                    "Use one-sided journal lines only: each line must have either a positive debit_amount or a "
                    "positive credit_amount, never both. Include a separate balancing bank, cash, credit-card, "
                    "payable, or receivable line when the document indicates payment or settlement."
                ),
                (
                    "Prefer 2 to 4 lines for a simple single-item receipt: net expense or revenue, separate GST "
                    "input/output when visible, and the balancing payment or receivable/payable line. For bundles "
                    "with multiple adjustments, pre-settlement items, charges, credits, or materially different "
                    "accounting or GST treatment, split the recommendation into separate component-level lines or "
                    "line groups so each component remains reviewable."
                ),
                "Use existing account codes from reference_context.accounts[].code where possible.",
                "Return selected account codes in the output field lines[].account_code.",
                "Use existing tax_code_code and reporting_category_code where appropriate.",
                (
                    "If an invoice or receipt visibly identifies GST and the company is GST registered, separate the GST "
                    "component from the net revenue or expense using appropriate existing GST input-credit, GST collected, "
                    "GST payable, or GST clearing accounts from reference_context.accounts. For purchases, GST should "
                    "normally be a debit/input-credit style line; for sales, GST should normally be a credit/output style "
                    "line. If GST is not visible or the treatment is uncertain, do not invent GST; explain the uncertainty."
                ),
                (
                    "If GST is not visible and no related context is provided, determine whether the transaction would "
                    "ordinarily involve GST. If the model has access to web search or browsing tools, use them to verify "
                    "the supplier, product, or service when needed; otherwise state the uncertainty and avoid inventing GST."
                ),
                (
                    "Assess GST separately for each materially distinct component in the bundle. Different adjustments, "
                    "fees, products, services, credits, or settlement items may have different GST outcomes and should "
                    "not be forced into one shared GST assumption."
                ),
                "Only propose new reference items when no existing code is suitable.",
                "Always include the proposals field; use an empty list when no new reference item is proposed.",
                "If a line depends on a newly proposed reference item, still return the suggested code in the line.",
            ],
        },
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


def _build_recommendation_request_suffix(*, run: JournalRecommendationRun, documents: list[Document]) -> str:
    payload = {
        "recommendation_request": {
            "operator_note": run.user_context_note,
            "target_accounting_period_id": str(run.target_accounting_period_id) if run.target_accounting_period_id else None,
            "documents": [
                {
                    "original_filename": document.original_filename,
                    "media_type": document.media_type,
                    "byte_size": document.byte_size,
                }
                for document in documents
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
            _build_recommendation_request_suffix(run=run, documents=documents)
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
    debit_total, credit_total = _sum_line_totals(recommendation.lines)
    serialized = json.dumps(recommendation.model_dump(mode="json"), separators=(",", ":"), default=str)
    return (
        "Your previous recommendation did not satisfy the accounting validation rules. "
        f"It returned {len(recommendation.lines)} lines, debit_total={debit_total}, and credit_total={credit_total}. "
        "Return a corrected recommendation with at least two journal lines and exactly equal total debits and credits. "
        "Preserve the source-document facts, vendor details, and overall accounting intent where possible. "
        f"Previous invalid recommendation JSON: {serialized}"
    )


def _extract_recommendation_entry_date(run: JournalRecommendationRun, *, strict: bool) -> date | None:
    value = (run.normalized_result_json or {}).get("entry_date")
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
    for document in documents:
        path = resolve_document_path(document.storage_path)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        media_type = normalize_media_type(document.original_filename, document.media_type)
        data_url = f"data:{media_type};base64,{encoded}"
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


def _persist_recommendation(db: Session, *, run: JournalRecommendationRun, recommendation: LlmRecommendation) -> None:
    _validate_recommendation_balance(recommendation.lines)
    db.execute(delete(JournalRecommendationLine).where(JournalRecommendationLine.recommendation_run_id == run.id))
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

    for line in recommendation.lines:
        account = accounts_by_code.get(line.account_code)
        tax_code = tax_codes_by_code.get(line.tax_code_code) if line.tax_code_code else None
        category = categories_by_code.get(line.reporting_category_code) if line.reporting_category_code else None
        db.add(
            JournalRecommendationLine(
                company_id=run.company_id,
                recommendation_run_id=run.id,
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


def _validate_recommendation_balance(lines: list[LlmRecommendedLine]) -> None:
    if len(lines) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Model returned fewer than two journal lines")
    debit_total, credit_total = _sum_line_totals(lines)
    if debit_total != credit_total:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Model returned an unbalanced recommendation")


def _sum_line_totals(lines: list[LlmRecommendedLine]) -> tuple[Decimal, Decimal]:
    debit_total = sum((line.debit_amount for line in lines), Decimal("0.00"))
    credit_total = sum((line.credit_amount for line in lines), Decimal("0.00"))
    return debit_total, credit_total
    for line in lines:
        valid_line = (
            (line.debit_amount > Decimal("0.00") and line.credit_amount == Decimal("0.00"))
            or (line.credit_amount > Decimal("0.00") and line.debit_amount == Decimal("0.00"))
        )
        if not valid_line:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Model returned an invalid journal line shape")


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
