from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.auth.service import authenticate_user, bootstrap_user
from app.db.models.auth import User
from app.schemas.requests import BootstrapResponse, BootstrapUserRequest, LoginRequest, LoginResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap(payload: BootstrapUserRequest, db: Session = Depends(get_db)) -> BootstrapResponse:
    user, token = bootstrap_user(
        db,
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
    )
    return BootstrapResponse(user=user, access_token=token)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user, token = authenticate_user(db, email=payload.email, password=payload.password)
    return LoginResponse(user=user, access_token=token)


@router.get("/me", response_model=LoginResponse)
def me(current_user: User = Depends(get_current_user)) -> LoginResponse:
    return LoginResponse(user=current_user, access_token="")
