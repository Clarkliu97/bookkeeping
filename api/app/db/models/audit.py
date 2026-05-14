from typing import Any

from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import ApprovalActionType, EntityType
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class ApprovalAction(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_actions"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_type: Mapped[ApprovalActionType] = mapped_column(Enum(ApprovalActionType), nullable=False)
    prepared_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)


class AuditEvent(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
