"""milestone a core schema

Revision ID: 20260507_0001
Revises:
Create Date: 2026-05-07 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    approval_action_type = postgresql.ENUM(
        "PREPARED",
        "SUBMITTED_FOR_REVIEW",
        "REVIEWED",
        "APPROVED",
        "REJECTED",
        "LOCKED",
        "UNLOCKED",
        name="approvalactiontype",
        create_type=False,
    )
    entity_type = postgresql.ENUM(
        "COMPANY",
        "COMPANY_CONFIGURATION",
        "ACCOUNT",
        "ACCOUNTING_PERIOD",
        "JOURNAL_ENTRY",
        "BAS_RUN",
        "TAX_WORKPAPER_PACK",
        name="entitytype",
        create_type=False,
    )
    bas_frequency = postgresql.ENUM(
        "MONTHLY",
        "QUARTERLY",
        "ANNUALLY",
        "OTHER",
        name="basfrequency",
        create_type=False,
    )
    bas_reporting_basis = postgresql.ENUM("CASH", "ACCRUAL", name="basreportingbasis", create_type=False)
    period_lock_policy = postgresql.ENUM(
        "MANUAL_ONLY",
        "AFTER_APPROVAL",
        "AFTER_EXPORT",
        name="periodlockpolicy",
        create_type=False,
    )
    self_approval_mode = postgresql.ENUM("ALLOW", "WARN", "BLOCK", name="selfapprovalmode", create_type=False)
    reporting_category_type = postgresql.ENUM(
        "PNL",
        "BALANCE_SHEET",
        "GST",
        "BAS",
        "TAX_SUPPORT",
        "OTHER",
        name="reportingcategorytype",
        create_type=False,
    )
    tax_input_output_type = postgresql.ENUM(
        "INPUT_TAXED",
        "OUTPUT_TAXED",
        "GST_FREE",
        "INPUT_TAX_CREDIT",
        "NONE",
        name="taxinputoutputtype",
        create_type=False,
    )
    account_type = postgresql.ENUM(
        "ASSET",
        "LIABILITY",
        "EQUITY",
        "INCOME",
        "EXPENSE",
        "CONTRA_ASSET",
        "CONTRA_LIABILITY",
        "CONTRA_INCOME",
        "CONTRA_EXPENSE",
        name="accounttype",
        create_type=False,
    )
    accounting_period_type = postgresql.ENUM(
        "MONTH",
        "QUARTER",
        "YEAR",
        "CUSTOM",
        name="accountingperiodtype",
        create_type=False,
    )
    workflow_status = postgresql.ENUM(
        "DRAFT",
        "IN_REVIEW",
        "APPROVED",
        "LOCKED",
        name="workflowstatus",
        create_type=False,
    )
    journal_status = postgresql.ENUM(
        "DRAFT",
        "POSTED",
        "REVERSED",
        "VOIDED",
        name="journalstatus",
        create_type=False,
    )
    journal_source_type = postgresql.ENUM(
        "MANUAL",
        "OPENING_BALANCE",
        "BANK_IMPORT",
        "ADJUSTMENT",
        "DEPRECIATION",
        "BAS_ADJUSTMENT",
        "TAX_ADJUSTMENT",
        "SYSTEM",
        name="journalsourcetype",
        create_type=False,
    )

    bind = op.get_bind()
    enum_types = [
        approval_action_type,
        entity_type,
        bas_frequency,
        bas_reporting_basis,
        period_lock_policy,
        self_approval_mode,
        reporting_category_type,
        tax_input_output_type,
        account_type,
        accounting_period_type,
        workflow_status,
        journal_status,
        journal_source_type,
    ]
    for enum_type in enum_types:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trading_name", sa.String(length=255), nullable=True),
        sa.Column("abn", sa.String(length=32), nullable=True),
        sa.Column("acn", sa.String(length=32), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", "company_id", name="uq_user_role_scope"),
    )
    op.create_table(
        "user_company_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("can_prepare", sa.Boolean(), nullable=False),
        sa.Column("can_review", sa.Boolean(), nullable=False),
        sa.Column("can_approve", sa.Boolean(), nullable=False),
        sa.Column("can_administer", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_company_access"),
    )
    op.create_table(
        "company_configuration_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("gst_registered", sa.Boolean(), nullable=False),
        sa.Column("bas_frequency", bas_frequency, nullable=False),
        sa.Column("bas_reporting_basis", bas_reporting_basis, nullable=False),
        sa.Column("financial_year_start_month", sa.SmallInteger(), nullable=False),
        sa.Column("financial_year_start_day", sa.SmallInteger(), nullable=False),
        sa.Column("allow_self_approval", sa.Boolean(), nullable=False),
        sa.Column("self_approval_mode", self_approval_mode, nullable=False),
        sa.Column("period_lock_policy", period_lock_policy, nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "version_number", name="uq_company_config_version"),
    )
    op.create_table(
        "reporting_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category_type", reporting_category_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_reporting_category_code"),
    )
    op.create_table(
        "tax_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rate", sa.Numeric(9, 4), nullable=False),
        sa.Column("is_gst_applicable", sa.Boolean(), nullable=False),
        sa.Column("bas_label", sa.String(length=32), nullable=True),
        sa.Column("input_output_type", tax_input_output_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_tax_code"),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("account_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("account_type", account_type, nullable=False),
        sa.Column("reporting_category_id", sa.Uuid(), nullable=True),
        sa.Column("default_tax_code_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("allow_manual_posting", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["default_tax_code_id"], ["tax_codes.id"]),
        sa.ForeignKeyConstraint(["reporting_category_id"], ["reporting_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "account_code", name="uq_account_code"),
    )
    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("period_type", accounting_period_type, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "start_date", "end_date", name="uq_accounting_period_range"),
    )
    op.create_table(
        "period_locks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("accounting_period_id", sa.Uuid(), nullable=False),
        sa.Column("lock_reason", sa.Text(), nullable=False),
        sa.Column("locked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unlocked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlock_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["accounting_period_id"], ["accounting_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locked_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["unlocked_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("entry_number", sa.String(length=64), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("accounting_period_id", sa.Uuid(), nullable=False),
        sa.Column("status", journal_status, nullable=False),
        sa.Column("source_type", journal_source_type, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_of_entry_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["accounting_period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["posted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reversal_of_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "entry_number", name="uq_journal_entry_number"),
    )
    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("journal_entry_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("debit_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("credit_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_code_id", sa.Uuid(), nullable=True),
        sa.Column("reporting_category_id", sa.Uuid(), nullable=True),
        sa.Column("source_document_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0))",
            name="ck_journal_line_single_sided_amount",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporting_category_id"], ["reporting_categories.id"]),
        sa.ForeignKeyConstraint(["tax_code_id"], ["tax_codes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_entry_id", "line_number", name="uq_journal_line_number"),
    )
    op.create_table(
        "approval_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", entity_type, nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", approval_action_type, nullable=False),
        sa.Column("prepared_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prepared_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for table in [
        "audit_events",
        "approval_actions",
        "journal_lines",
        "journal_entries",
        "period_locks",
        "accounting_periods",
        "accounts",
        "tax_codes",
        "reporting_categories",
        "company_configuration_versions",
        "user_company_access",
        "user_roles",
        "companies",
        "roles",
        "users",
    ]:
        op.drop_table(table)

    bind = op.get_bind()
    for enum_name in [
        "journalsourcetype",
        "journalstatus",
        "workflowstatus",
        "accountingperiodtype",
        "accounttype",
        "taxinputoutputtype",
        "reportingcategorytype",
        "selfapprovalmode",
        "periodlockpolicy",
        "basreportingbasis",
        "basfrequency",
        "entitytype",
        "approvalactiontype",
    ]:
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
