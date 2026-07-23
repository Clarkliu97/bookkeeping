"""support multi-journal recommendation batches

Revision ID: 20260722_0011
Revises: 20260531_0010
Create Date: 2026-07-22 00:11:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260722_0011"
down_revision = "20260531_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "journal_recommendation_runs",
        sa.Column("analysis_mode", sa.String(length=16), nullable=False, server_default="single"),
    )

    op.create_table(
        "journal_recommendation_entries",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "recommendation_run_id",
            sa.Uuid(),
            sa.ForeignKey("journal_recommendation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=True),
        sa.Column("vendor_name", sa.String(length=160), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("gst_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("recommended_description", sa.String(length=240), nullable=False),
        sa.Column("recommended_reference", sa.String(length=128), nullable=True),
        sa.Column("confidence_summary", sa.String(length=240), nullable=True),
        sa.Column("warning_text", sa.String(length=300), nullable=True),
        sa.Column("accepted_journal_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recommendation_run_id",
            "sequence_number",
            name="uq_journal_recommendation_entry_sequence",
        ),
    )

    op.create_table(
        "journal_recommendation_entry_documents",
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "recommendation_entry_id",
            sa.Uuid(),
            sa.ForeignKey("journal_recommendation_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recommendation_entry_id",
            "document_id",
            name="uq_journal_recommendation_entry_document",
        ),
    )

    op.drop_constraint(
        "uq_journal_recommendation_line_number",
        "journal_recommendation_lines",
        type_="unique",
    )
    op.add_column(
        "journal_recommendation_lines",
        sa.Column("recommendation_entry_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_journal_recommendation_line_entry",
        "journal_recommendation_lines",
        "journal_recommendation_entries",
        ["recommendation_entry_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_journal_recommendation_entry_line_number",
        "journal_recommendation_lines",
        ["recommendation_entry_id", "line_number"],
    )


def downgrade() -> None:
    op.execute(
        """
        WITH renumbered AS (
            SELECT lines.id,
                   row_number() OVER (
                       PARTITION BY lines.recommendation_run_id
                       ORDER BY entries.sequence_number NULLS FIRST, lines.line_number, lines.id
                   ) AS new_line_number
            FROM journal_recommendation_lines AS lines
            LEFT JOIN journal_recommendation_entries AS entries
              ON entries.id = lines.recommendation_entry_id
        )
        UPDATE journal_recommendation_lines AS lines
        SET line_number = renumbered.new_line_number
        FROM renumbered
        WHERE renumbered.id = lines.id
        """
    )
    op.drop_constraint(
        "uq_journal_recommendation_entry_line_number",
        "journal_recommendation_lines",
        type_="unique",
    )
    op.drop_constraint(
        "fk_journal_recommendation_line_entry",
        "journal_recommendation_lines",
        type_="foreignkey",
    )
    op.drop_column("journal_recommendation_lines", "recommendation_entry_id")
    op.create_unique_constraint(
        "uq_journal_recommendation_line_number",
        "journal_recommendation_lines",
        ["recommendation_run_id", "line_number"],
    )
    op.drop_table("journal_recommendation_entry_documents")
    op.drop_table("journal_recommendation_entries")
    op.drop_column("journal_recommendation_runs", "analysis_mode")
