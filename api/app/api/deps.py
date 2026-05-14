from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models.auth import User, UserCompanyAccess
from app.db.session import get_db_session


bearer_scheme = HTTPBearer(auto_error=False)


def get_db(db: Session = Depends(get_db_session)) -> Session:
    return db


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_access_token(credentials.credentials)
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.get(User, UUID(subject))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    return current_user


def require_company_permission(company_id: UUID, permission: str, db: Session, current_user: User) -> None:
    if current_user.is_superuser:
        return

    access = (
        db.query(UserCompanyAccess)
        .filter(
            UserCompanyAccess.user_id == current_user.id,
            UserCompanyAccess.company_id == company_id,
        )
        .one_or_none()
    )
    if access is None or not getattr(access, permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Company access denied")
