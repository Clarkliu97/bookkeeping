"""milestone d phase 11 tax workpapers

Revision ID: 20260508_0005
Revises: 20260508_0004
Create Date: 2026-05-08 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260508_0005"
down_revision = "20260508_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tax_workpaper_status = postgresql.ENUM(
        "DRAFT",
        "REVIEW",
        "APPROVED",
        "EXPORTED",
        name="taxworkpaperstatus",
        create_type=False,
    )
    tax_workpaper_note_type = postgresql.ENUM(
        "REVIEW",
        "SIGN_OFF",
        name="taxworkpapernotetype",
        create_type=False,
    )
    tax_workpaper_exception_status = postgresql.ENUM(
        "OPEN",
        "RESOLVED",
        name="taxworkpaperexceptionstatus",
        create_type=False,
    )
    tax_workpaper_export_format = postgresql.ENUM(
        "CSV",
        "PDF",
        name="taxworkpaperexportformat",
        create_type=False,
    )

    bind = op.get_bind()
    for enum_type in [
        tax_workpaper_status,
        tax_workpaper_note_type,
        tax_workpaper_exception_status,
        tax_workpaper_export_format,
    ]:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "tax_workpaper_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("accounting_period_id", sa.Uuid(), nullable=False),
        sa.Column("status", tax_workpaper_status, nullable=False),
        sa.Column("schedule_snapshot", sa.JSON(), nullable=False),
        sa.Column("generated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["accounting_period_id"], ["accounting_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "accounting_period_id", name="uq_tax_workpaper_pack_period"),
    )
    op.create_table(
        "tax_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("tax_workpaper_pack_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tax_workpaper_pack_id"], ["tax_workpaper_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tax_workpaper_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("tax_workpaper_pack_id", sa.Uuid(), nullable=False),
        sa.Column("note_type", tax_workpaper_note_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tax_workpaper_pack_id"], ["tax_workpaper_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tax_workpaper_exception_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("tax_workpaper_pack_id", sa.Uuid(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", tax_workpaper_exception_status, nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tax_workpaper_pack_id"], ["tax_workpaper_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tax_workpaper_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("tax_workpaper_pack_id", sa.Uuid(), nullable=False),
        sa.Column("format", tax_workpaper_export_format, nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("exported_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tax_workpaper_pack_id"], ["tax_workpaper_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exported_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for table in [
        "tax_workpaper_exports",
        "tax_workpaper_exception_items",
        "tax_workpaper_notes",
        "tax_adjustments",
        "tax_workpaper_packs",
    ]:
        op.drop_table(table)

    bind = op.get_bind()
    for enum_name in [
        "taxworkpaperexportformat",
        "taxworkpaperexceptionstatus",
        "taxworkpapernotetype",
        "taxworkpaperstatus",
    ]:
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)