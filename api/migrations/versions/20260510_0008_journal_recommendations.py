"""add journal recommendation runs

Revision ID: 20260510_0008
Revises: 20260509_0007
Create Date: 2026-05-10 00:08:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260510_0008"
down_revision = "20260509_0007"
branch_labels = None
depends_on = None


journal_recommendation_status = postgresql.ENUM(
    "draft",
    "analyzing",
    "review_ready",
    "accepted",
    "rejected",
    "failed",
    name="journalrecommendationstatus",
    create_type=False,
)
journal_recommendation_proposal_status = postgresql.ENUM(
    "proposed",
    "accepted",
    "rejected",
    "created",
    name="journalrecommendationproposalstatus",
    create_type=False,
)
journal_recommendation_proposal_type = postgresql.ENUM(
    "account",
    "tax_code",
    "reporting_category",
    name="journalrecommendationproposaltype",
    create_type=False,
)
document_link_entity_type = postgresql.ENUM(
    "journal_entry",
    "journal_recommendation_run",
    "bank_import_session",
    "bank_import_row",
    "reconciliation_item",
    "accounting_period",
    name="documentlinkentitytype",
    create_type=False,
)
entity_type = postgresql.ENUM(
    "company",
    "company_configuration",
    "account",
    "accounting_period",
    "journal_entry",
    "journal_recommendation_run",
    "bas_run",
    "fixed_asset",
    "depreciation_run",
    "tax_workpaper_pack",
    name="entitytype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("ALTER TYPE documentlinkentitytype ADD VALUE IF NOT EXISTS 'journal_recommendation_run'")
    op.execute("ALTER TYPE entitytype ADD VALUE IF NOT EXISTS 'journal_recommendation_run'")
    journal_recommendation_status.create(bind, checkfirst=True)
    journal_recommendation_proposal_status.create(bind, checkfirst=True)
    journal_recommendation_proposal_type.create(bind, checkfirst=True)

    op.create_table(
        "journal_recommendation_runs",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", journal_recommendation_status, nullable=False),
        sa.Column("target_accounting_period_id", sa.Uuid(), sa.ForeignKey("accounting_periods.id"), nullable=True),
        sa.Column("target_journal_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("accepted_journal_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("user_context_note", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=128), nullable=False),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("confidence_summary", sa.Text(), nullable=True),
        sa.Column("warning_text", sa.Text(), nullable=True),
        sa.Column("raw_provider_response_json", sa.JSON(), nullable=True),
        sa.Column("normalized_result_json", sa.JSON(), nullable=True),
        sa.Column("provider_usage_json", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "journal_recommendation_run_documents",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_run_id", sa.Uuid(), sa.ForeignKey("journal_recommendation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_run_id", "document_id", name="uq_journal_recommendation_run_document"),
    )

    op.create_table(
        "journal_recommendation_lines",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_run_id", sa.Uuid(), sa.ForeignKey("journal_recommendation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("suggested_account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("suggested_account_code", sa.String(length=32), nullable=True),
        sa.Column("suggested_tax_code_id", sa.Uuid(), sa.ForeignKey("tax_codes.id"), nullable=True),
        sa.Column("suggested_tax_code_code", sa.String(length=32), nullable=True),
        sa.Column("suggested_reporting_category_id", sa.Uuid(), sa.ForeignKey("reporting_categories.id"), nullable=True),
        sa.Column("suggested_reporting_category_code", sa.String(length=64), nullable=True),
        sa.Column("debit_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("credit_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "((debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0))",
            name="ck_journal_recommendation_line_single_sided_amount",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_run_id", "line_number", name="uq_journal_recommendation_line_number"),
    )

    op.create_table(
        "journal_recommendation_proposals",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_run_id", sa.Uuid(), sa.ForeignKey("journal_recommendation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_type", journal_recommendation_proposal_type, nullable=False),
        sa.Column("status", journal_recommendation_proposal_status, nullable=False),
        sa.Column("suggested_code", sa.String(length=64), nullable=False),
        sa.Column("suggested_name", sa.String(length=255), nullable=False),
        sa.Column("suggested_attributes_json", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_entity_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("journal_recommendation_proposals")
    op.drop_table("journal_recommendation_lines")
    op.drop_table("journal_recommendation_run_documents")
    op.drop_table("journal_recommendation_runs")
    bind = op.get_bind()
    for enum_type in [
        journal_recommendation_proposal_type,
        journal_recommendation_proposal_status,
        journal_recommendation_status,
    ]:
        enum_type.drop(bind, checkfirst=True)