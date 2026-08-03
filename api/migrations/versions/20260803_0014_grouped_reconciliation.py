"""add grouped reconciliation allocations

Revision ID: 20260803_0014
Revises: 20260727_0013
Create Date: 2026-08-03 23:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260803_0014"
down_revision = "20260727_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_accounts", sa.Column("ledger_account_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_bank_accounts_ledger_account_id_accounts",
        "bank_accounts",
        "accounts",
        ["ledger_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_bank_accounts_ledger_account_id", "bank_accounts", ["ledger_account_id"])

    op.create_table(
        "reconciliation_match_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_session_id",
            sa.Uuid(),
            sa.ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("bank_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("journal_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("difference_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tolerance_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "tolerance_amount >= 0", name="ck_reconciliation_group_tolerance_nonnegative"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recon_groups_company", "reconciliation_match_groups", ["company_id"])
    op.create_index(
        "ix_recon_groups_session",
        "reconciliation_match_groups",
        ["reconciliation_session_id"],
    )

    op.create_table(
        "reconciliation_bank_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_match_group_id",
            sa.Uuid(),
            sa.ForeignKey("reconciliation_match_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_item_id",
            sa.Uuid(),
            sa.ForeignKey("reconciliation_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "allocated_amount <> 0", name="ck_reconciliation_bank_allocation_nonzero"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_match_group_id",
            "reconciliation_item_id",
            name="uq_reconciliation_group_bank_item",
        ),
    )
    op.create_index(
        "ix_recon_bank_alloc_group",
        "reconciliation_bank_allocations",
        ["reconciliation_match_group_id"],
    )
    op.create_index(
        "ix_recon_bank_alloc_item",
        "reconciliation_bank_allocations",
        ["reconciliation_item_id"],
    )

    op.create_table(
        "reconciliation_journal_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_match_group_id",
            sa.Uuid(),
            sa.ForeignKey("reconciliation_match_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "journal_entry_id",
            sa.Uuid(),
            sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "ledger_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "allocated_amount <> 0", name="ck_reconciliation_journal_allocation_nonzero"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reconciliation_match_group_id",
            "journal_entry_id",
            name="uq_reconciliation_group_journal_entry",
        ),
    )
    op.create_index(
        "ix_recon_journal_alloc_group",
        "reconciliation_journal_allocations",
        ["reconciliation_match_group_id"],
    )
    op.create_index(
        "ix_recon_journal_alloc_journal",
        "reconciliation_journal_allocations",
        ["journal_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recon_journal_alloc_journal",
        table_name="reconciliation_journal_allocations",
    )
    op.drop_index(
        "ix_recon_journal_alloc_group",
        table_name="reconciliation_journal_allocations",
    )
    op.drop_table("reconciliation_journal_allocations")
    op.drop_index(
        "ix_recon_bank_alloc_item",
        table_name="reconciliation_bank_allocations",
    )
    op.drop_index(
        "ix_recon_bank_alloc_group",
        table_name="reconciliation_bank_allocations",
    )
    op.drop_table("reconciliation_bank_allocations")
    op.drop_index(
        "ix_recon_groups_session",
        table_name="reconciliation_match_groups",
    )
    op.drop_index("ix_recon_groups_company", table_name="reconciliation_match_groups")
    op.drop_table("reconciliation_match_groups")
    op.drop_index("ix_bank_accounts_ledger_account_id", table_name="bank_accounts")
    op.drop_constraint(
        "fk_bank_accounts_ledger_account_id_accounts", "bank_accounts", type_="foreignkey"
    )
    op.drop_column("bank_accounts", "ledger_account_id")
