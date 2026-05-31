"""add employment support module

Revision ID: 20260531_0010
Revises: 20260510_0009
Create Date: 2026-05-31 00:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260531_0010"
down_revision = "20260510_0009"
branch_labels = None
depends_on = None


employment_worker_kind = postgresql.ENUM("INDIVIDUAL", "ENTITY", name="employmentworkerkind", create_type=False)
employment_engagement_type = postgresql.ENUM(
    "EMPLOYEE",
    "DIRECTOR",
    "INDIVIDUAL_CONTRACTOR",
    "CONTRACTOR_ENTITY",
    "LABOUR_HIRE",
    "INTERN",
    name="employmentengagementtype",
    create_type=False,
)
employment_status = postgresql.ENUM(
    "DRAFT",
    "ONBOARDING",
    "ACTIVE",
    "ACTIVE_WITH_RESTRICTIONS",
    "ON_PAID_LEAVE",
    "ON_UNPAID_LEAVE",
    "SUSPENDED",
    "ON_NOTICE",
    "ENDED",
    "ARCHIVED",
    name="employmentstatus",
    create_type=False,
)
work_rights_basis = postgresql.ENUM(
    "AUSTRALIAN_CITIZEN",
    "PERMANENT_RESIDENT",
    "NEW_ZEALAND_CITIZEN",
    "EMPLOYER_SPONSORED_TEMPORARY_VISA",
    "OTHER_TEMPORARY_VISA",
    "STUDENT_VISA",
    "WORKING_HOLIDAY_VISA",
    "BRIDGING_VISA",
    "UNKNOWN_REVIEW_REQUIRED",
    "NO_VERIFIED_WORK_RIGHT",
    name="workrightsbasis",
    create_type=False,
)
work_rights_status = postgresql.ENUM(
    "NOT_REQUIRED",
    "PENDING_EVIDENCE",
    "PENDING_REVIEW",
    "VERIFIED",
    "VERIFIED_WITH_RESTRICTIONS",
    "EXPIRING_SOON",
    "EXPIRED",
    "BLOCKED_PENDING_REVIEW",
    name="workrightsstatus",
    create_type=False,
)
remuneration_basis = postgresql.ENUM(
    "SALARY",
    "HOURLY",
    "DAY_RATE",
    "COMMISSION",
    "CONTRACTOR_FEE",
    "DIRECTOR_FEE",
    "UNPAID",
    name="remunerationbasis",
    create_type=False,
)
employment_reimbursement_status = postgresql.ENUM(
    "DRAFT",
    "SUBMITTED",
    "REVIEWED",
    "PAID",
    "REJECTED",
    name="employmentreimbursementstatus",
    create_type=False,
)
employment_asset_status = postgresql.ENUM(
    "ISSUED",
    "RETURNED",
    "LOST",
    "DAMAGED",
    name="employmentassetstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("ALTER TYPE entitytype ADD VALUE IF NOT EXISTS 'EMPLOYMENT_WORKER'")
    op.execute("ALTER TYPE documentlinkentitytype ADD VALUE IF NOT EXISTS 'EMPLOYMENT_WORKER'")
    for enum_type in [
        employment_worker_kind,
        employment_engagement_type,
        employment_status,
        work_rights_basis,
        work_rights_status,
        remuneration_basis,
        employment_reimbursement_status,
        employment_asset_status,
    ]:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "employment_workers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("worker_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("worker_kind", employment_worker_kind, nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("primary_email", sa.String(length=320), nullable=True),
        sa.Column("primary_phone", sa.String(length=64), nullable=True),
        sa.Column("address_summary", sa.Text(), nullable=True),
        sa.Column("emergency_contact_summary", sa.Text(), nullable=True),
        sa.Column("privacy_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "worker_code", name="uq_employment_worker_code"),
    )
    op.create_table(
        "employment_engagements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_type", employment_engagement_type, nullable=False),
        sa.Column("employment_basis", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("expected_end_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("role_name", sa.String(length=255), nullable=False),
        sa.Column("manager_name", sa.String(length=255), nullable=True),
        sa.Column("primary_work_location", sa.String(length=255), nullable=True),
        sa.Column("pay_cycle_reference", sa.String(length=64), nullable=True),
        sa.Column("status", employment_status, nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["employment_workers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employment_work_rights_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=True),
        sa.Column("work_rights_basis", work_rights_basis, nullable=False),
        sa.Column("review_status", work_rights_status, nullable=False),
        sa.Column("visa_subclass", sa.String(length=64), nullable=True),
        sa.Column("visa_label", sa.String(length=255), nullable=True),
        sa.Column("visa_grant_date", sa.Date(), nullable=True),
        sa.Column("visa_expiry_date", sa.Date(), nullable=True),
        sa.Column("work_condition_summary", sa.Text(), nullable=True),
        sa.Column("hours_restriction_summary", sa.Text(), nullable=True),
        sa.Column("sponsorship_required", sa.Boolean(), nullable=False),
        sa.Column("sponsoring_entity_note", sa.Text(), nullable=True),
        sa.Column("vevo_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_due_at", sa.Date(), nullable=True),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["employment_workers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engagement_id"], ["employment_engagements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employment_compensation_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("remuneration_basis", remuneration_basis, nullable=False),
        sa.Column("expected_base_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("tax_profile", sa.String(length=64), nullable=True),
        sa.Column("superannuation_category", sa.String(length=64), nullable=True),
        sa.Column("workers_comp_category", sa.String(length=64), nullable=True),
        sa.Column("payroll_tax_in_scope", sa.Boolean(), nullable=False),
        sa.Column("leave_profile", sa.String(length=64), nullable=True),
        sa.Column("reimbursement_allowed", sa.Boolean(), nullable=False),
        sa.Column("asset_issue_allowed", sa.Boolean(), nullable=False),
        sa.Column("expense_account_id", sa.Uuid(), nullable=True),
        sa.Column("liability_account_id", sa.Uuid(), nullable=True),
        sa.Column("tfn_declaration_received", sa.Boolean(), nullable=False),
        sa.Column("super_choice_received", sa.Boolean(), nullable=False),
        sa.Column("abn_provided", sa.Boolean(), nullable=False),
        sa.Column("gst_registered_known", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engagement_id"], ["employment_engagements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["expense_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["liability_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engagement_id", name="uq_employment_compensation_engagement"),
    )
    op.create_table(
        "employment_leave_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("annual_leave_hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("personal_leave_hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("long_service_leave_hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("leave_value_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("current_lsl_value_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("non_current_lsl_value_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("annual_leave_hours >= 0", name="ck_employment_leave_annual_non_negative"),
        sa.CheckConstraint("personal_leave_hours >= 0", name="ck_employment_leave_personal_non_negative"),
        sa.CheckConstraint("long_service_leave_hours >= 0", name="ck_employment_leave_lsl_non_negative"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engagement_id"], ["employment_engagements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engagement_id", "snapshot_date", name="uq_employment_leave_snapshot_date"),
    )
    op.create_table(
        "employment_reimbursement_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=True),
        sa.Column("reimbursement_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", employment_reimbursement_status, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_employment_reimbursement_amount_non_negative"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["employment_workers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engagement_id"], ["employment_engagements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employment_issued_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=True),
        sa.Column("asset_name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=64), nullable=True),
        sa.Column("serial_number", sa.String(length=128), nullable=True),
        sa.Column("assigned_on", sa.Date(), nullable=False),
        sa.Column("due_back_on", sa.Date(), nullable=True),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.Column("status", employment_asset_status, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["employment_workers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engagement_id"], ["employment_engagements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for table in [
        "employment_issued_assets",
        "employment_reimbursement_items",
        "employment_leave_snapshots",
        "employment_compensation_profiles",
        "employment_work_rights_records",
        "employment_engagements",
        "employment_workers",
    ]:
        op.drop_table(table)

    bind = op.get_bind()
    for enum_type in [
        employment_asset_status,
        employment_reimbursement_status,
        remuneration_basis,
        work_rights_status,
        work_rights_basis,
        employment_status,
        employment_engagement_type,
        employment_worker_kind,
    ]:
        enum_type.drop(bind, checkfirst=True)