from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.audit import ApprovalAction, AuditEvent
from app.db.models.enums import ApprovalActionType, EntityType


def log_audit_event(
    db: Session,
    *,
    action: str,
    summary: str,
    entity_type: str,
    entity_id: UUID | None,
    actor_user_id: UUID | None,
    company_id: UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        company_id=company_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        action=action,
        summary=summary,
        before_state=before_state,
        after_state=after_state,
        metadata_json=metadata,
    )
    db.add(event)
    return event


def log_approval_action(
    db: Session,
    *,
    company_id: UUID,
    entity_type: EntityType,
    entity_id: UUID,
    action_type: ApprovalActionType,
    prepared_by_user_id: UUID | None = None,
    approved_by_user_id: UUID | None = None,
    note: str | None = None,
) -> ApprovalAction:
    action = ApprovalAction(
        company_id=company_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action_type=action_type,
        prepared_by_user_id=prepared_by_user_id,
        approved_by_user_id=approved_by_user_id,
        note=note,
    )
    db.add(action)
    return action
