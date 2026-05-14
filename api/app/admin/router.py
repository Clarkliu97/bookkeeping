from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_superuser
from app.audit.service import log_audit_event
from app.core.security import hash_password
from app.db.models.accounting import Account, AccountingPeriod, JournalEntry
from app.db.models.auth import User
from app.db.models.companies import Company
from app.schemas.common import UserRead
from app.schemas.requests import CreateUserRequest, UpdateUserRequest


router = APIRouter(prefix="/admin", tags=["admin"])


def _load_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _active_superuser_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(User.is_superuser.is_(True), User.is_active.is_(True))
    ) or 0


@router.get("/overview")
def overview(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "companies": db.scalar(select(func.count()).select_from(Company)) or 0,
        "accounts": db.scalar(select(func.count()).select_from(Account)) or 0,
        "periods": db.scalar(select(func.count()).select_from(AccountingPeriod)) or 0,
        "journals": db.scalar(select(func.count()).select_from(JournalEntry)) or 0,
    }


@router.get("/users", response_model=list[UserRead])
def list_users(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.post("/users", response_model=UserRead, status_code=201)
def create_user(
    payload: CreateUserRequest,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> User:
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_superuser=payload.is_superuser,
    )
    db.add(user)
    db.flush()
    log_audit_event(
        db,
        action="user.created",
        summary=f"Created user {user.email}",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=current_user.id,
        after_state=UserRead.model_validate(user).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    payload: UpdateUserRequest,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> User:
    user = _load_user_or_404(db, user_id)
    if user.is_superuser and not payload.is_superuser and _active_superuser_count(db) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one active superuser is required")
    if user.is_superuser and not payload.is_active and _active_superuser_count(db) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one active superuser is required")

    before_state = UserRead.model_validate(user).model_dump(mode="json")
    user.email = payload.email.lower()
    user.full_name = payload.full_name
    if payload.password:
        user.password_hash = hash_password(payload.password)
    user.is_superuser = payload.is_superuser
    user.is_active = payload.is_active
    log_audit_event(
        db,
        action="user.updated",
        summary=f"Updated user {user.email}",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=current_user.id,
        before_state=before_state,
        after_state=UserRead.model_validate(user).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> Response:
    user = _load_user_or_404(db, user_id)
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate the current user")
    if user.is_superuser and _active_superuser_count(db) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one active superuser is required")

    before_state = UserRead.model_validate(user).model_dump(mode="json")
    user.is_active = False
    log_audit_event(
        db,
        action="user.deactivated",
        summary=f"Deactivated user {user.email}",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=current_user.id,
        before_state=before_state,
        after_state=UserRead.model_validate(user).model_dump(mode="json"),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
