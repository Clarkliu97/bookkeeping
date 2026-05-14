"""milestone b documents banking reconciliation

Revision ID: 20260508_0002
Revises: 20260507_0001
Create Date: 2026-05-08 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260508_0002"
down_revision = "20260507_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    document_link_entity_type = postgresql.ENUM(
        "JOURNAL_ENTRY",
        "BANK_IMPORT_SESSION",
        "BANK_IMPORT_ROW",
        "RECONCILIATION_ITEM",
        "ACCOUNTING_PERIOD",
        name="documentlinkentitytype",
        create_type=False,
    )
    bank_import_session_status = postgresql.ENUM(
        "DRAFT",
        "STAGED",
        "CONFIRMED",
        "FAILED",
        name="bankimportsessionstatus",
        create_type=False,
    )
    bank_import_row_status = postgresql.ENUM(
        "STAGED",
        "DUPLICATE",
        "MATCHED",
        "IGNORED",
        name="bankimportrowstatus",
        create_type=False,
    )
    reconciliation_session_status = postgresql.ENUM(
        "DRAFT",
        "IN_PROGRESS",
        "COMPLETED",
        name="reconciliationsessionstatus",
        create_type=False,
    )
    reconciliation_item_status = postgresql.ENUM(
        "UNMATCHED",
        "MATCHED",
        "SUGGESTED",
        "IGNORED",
        name="reconciliationitemstatus",
        create_type=False,
    )

    bind = op.get_bind()
    for enum_type in [
        document_link_entity_type,
        bank_import_session_status,
        bank_import_row_status,
        reconciliation_session_status,
        reconciliation_item_status,
    ]:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "document_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", document_link_entity_type, nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("linked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column("bsb", sa.String(length=16), nullable=True),
        sa.Column("account_number_masked", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_bank_account_name"),
    )
    op.create_table(
        "bank_import_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_document_id", sa.Uuid(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("header_mapping", sa.JSON(), nullable=True),
        sa.Column("status", bank_import_session_status, nullable=False),
        sa.Column("imported_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["uploaded_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "bank_import_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("bank_import_session_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("debit_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("credit_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", bank_import_row_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bank_import_session_id"], ["bank_import_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reconciliation_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("accounting_period_id", sa.Uuid(), nullable=True),
        sa.Column("status", reconciliation_session_status, nullable=False),
        sa.Column("started_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["accounting_period_id"], ["accounting_periods.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reconciliation_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("reconciliation_session_id", sa.Uuid(), nullable=False),
        sa.Column("bank_import_row_id", sa.Uuid(), nullable=False),
        sa.Column("matched_journal_entry_id", sa.Uuid(), nullable=True),
        sa.Column("status", reconciliation_item_status, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bank_import_row_id"], ["bank_import_rows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reconciliation_session_id"], ["reconciliation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_session_id",
            "bank_import_row_id",
            name="uq_reconciliation_item_row_per_session",
        ),
    )


def downgrade() -> None:
    for table in [
        "reconciliation_items",
        "reconciliation_sessions",
        "bank_import_rows",
        "bank_import_sessions",
        "bank_accounts",
        "document_links",
        "documents",
    ]:
        op.drop_table(table)

    bind = op.get_bind()
    for enum_name in [
        "reconciliationitemstatus",
        "reconciliationsessionstatus",
        "bankimportrowstatus",
        "bankimportsessionstatus",
        "documentlinkentitytype",
    ]:
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
