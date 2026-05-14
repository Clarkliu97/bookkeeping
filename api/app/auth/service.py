from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.auth import Role, User


DEFAULT_ROLES = [
    ("system_admin", "System Admin", "Global administrative access"),
    ("finance_admin", "Finance Admin", "Company administration and finance controls"),
    ("bookkeeper", "Bookkeeper", "Preparation and bookkeeping workflow access"),
    ("reviewer", "Reviewer", "Review and approval workflow access"),
    ("read_only", "Read Only", "Read-only access"),
]


def ensure_default_roles(db: Session) -> None:
    existing_codes = set(db.scalars(select(Role.code)).all())
    for code, name, description in DEFAULT_ROLES:
        if code in existing_codes:
            continue
        db.add(Role(code=code, name=name, description=description))


def bootstrap_user(db: Session, *, email: str, full_name: str, password: str) -> tuple[User, str]:
    existing_user = db.scalar(select(User.id).limit(1))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bootstrap is only available before the first user is created",
        )

    ensure_default_roles(db)
    user = User(
        email=email.lower(),
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, create_access_token(str(user.id))


def authenticate_user(db: Session, *, email: str, password: str) -> tuple[User, str]:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, create_access_token(str(user.id))
