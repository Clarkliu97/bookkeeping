from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import (
    JournalRecommendationProposalStatus,
    JournalRecommendationProposalType,
    JournalRecommendationStatus,
)
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


def _enum_values(enum_cls: type) -> list[str]:
    return [member.value for member in enum_cls]


class JournalRecommendationRun(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journal_recommendation_runs"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[JournalRecommendationStatus] = mapped_column(
        Enum(JournalRecommendationStatus, values_callable=_enum_values),
        nullable=False,
        default=JournalRecommendationStatus.DRAFT,
    )
    target_accounting_period_id: Mapped[str | None] = mapped_column(ForeignKey("accounting_periods.id"))
    target_journal_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id"))
    accepted_journal_entry_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id"))
    user_context_note: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(128), nullable=False)
    analysis_summary: Mapped[str | None] = mapped_column(Text)
    confidence_summary: Mapped[str | None] = mapped_column(Text)
    warning_text: Mapped[str | None] = mapped_column(Text)
    raw_provider_response_json: Mapped[dict | None] = mapped_column(JSON)
    normalized_result_json: Mapped[dict | None] = mapped_column(JSON)
    provider_usage_json: Mapped[dict | None] = mapped_column(JSON)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class JournalRecommendationRunDocument(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journal_recommendation_run_documents"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_run_id",
            "document_id",
            name="uq_journal_recommendation_run_document",
        ),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    recommendation_run_id: Mapped[str] = mapped_column(
        ForeignKey("journal_recommendation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class JournalRecommendationLine(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journal_recommendation_lines"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_run_id",
            "line_number",
            name="uq_journal_recommendation_line_number",
        ),
        CheckConstraint(
            "((debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0))",
            name="ck_journal_recommendation_line_single_sided_amount",
        ),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    recommendation_run_id: Mapped[str] = mapped_column(
        ForeignKey("journal_recommendation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    suggested_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    suggested_account_code: Mapped[str | None] = mapped_column(String(32))
    suggested_tax_code_id: Mapped[str | None] = mapped_column(ForeignKey("tax_codes.id"))
    suggested_tax_code_code: Mapped[str | None] = mapped_column(String(32))
    suggested_reporting_category_id: Mapped[str | None] = mapped_column(ForeignKey("reporting_categories.id"))
    suggested_reporting_category_code: Mapped[str | None] = mapped_column(String(64))
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))


class JournalRecommendationProposal(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "journal_recommendation_proposals"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    recommendation_run_id: Mapped[str] = mapped_column(
        ForeignKey("journal_recommendation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposal_type: Mapped[JournalRecommendationProposalType] = mapped_column(
        Enum(JournalRecommendationProposalType, values_callable=_enum_values),
        nullable=False,
    )
    status: Mapped[JournalRecommendationProposalStatus] = mapped_column(
        Enum(JournalRecommendationProposalStatus, values_callable=_enum_values),
        nullable=False,
        default=JournalRecommendationProposalStatus.PROPOSED,
    )
    suggested_code: Mapped[str] = mapped_column(String(64), nullable=False)
    suggested_name: Mapped[str] = mapped_column(String(255), nullable=False)
    suggested_attributes_json: Mapped[dict | None] = mapped_column(JSON)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_entity_id: Mapped[str | None] = mapped_column(String(36))