from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.companies.default_reference_data import seed_company_reference_data
from app.db.models.auth import User, UserCompanyAccess
from app.db.models.bas import BasPeriod, BasRun
from app.db.models.companies import Company, CompanyConfigurationVersion
from app.db.models.enums import BasFrequency, BasReportingBasis, EntityType, PeriodLockPolicy, SelfApprovalMode
from app.schemas.common import CompanyAccessRead, CompanyRead, ConfigurationVersionRead
from app.schemas.requests import (
    CompanyAccessUpdateRequest,
    CompanyConfigurationCreate,
    CompanyConfigurationUpdate,
    CompanyCreate,
    CompanyUpdate,
    GrantCompanyAccessRequest,
)


router = APIRouter(prefix="/companies", tags=["companies"])


def _load_company_or_404(db: Session, company_id: UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def _load_configuration_or_404(db: Session, company_id: UUID, configuration_id: UUID) -> CompanyConfigurationVersion:
    configuration = db.scalar(
        select(CompanyConfigurationVersion).where(
            CompanyConfigurationVersion.company_id == company_id,
            CompanyConfigurationVersion.id == configuration_id,
        )
    )
    if configuration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration version not found")
    return configuration


def _load_company_access_or_404(db: Session, company_id: UUID, user_id: UUID) -> UserCompanyAccess:
    access = db.scalar(
        select(UserCompanyAccess).where(
            UserCompanyAccess.company_id == company_id,
            UserCompanyAccess.user_id == user_id,
        )
    )
    if access is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company access not found")
    return access


def _ensure_configuration_editable(
    db: Session,
    company_id: UUID,
    configuration: CompanyConfigurationVersion,
) -> None:
    latest_version = db.scalar(
        select(CompanyConfigurationVersion)
        .where(CompanyConfigurationVersion.company_id == company_id)
        .order_by(CompanyConfigurationVersion.version_number.desc())
        .limit(1)
    )
    if latest_version is None or latest_version.id != configuration.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only the latest configuration version can be changed",
        )
    if db.scalar(select(BasPeriod.id).where(BasPeriod.configuration_version_id == configuration.id).limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration version is already referenced by BAS periods",
        )
    if db.scalar(select(BasRun.id).where(BasRun.configuration_version_id == configuration.id).limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration version is already referenced by BAS runs",
        )


def _create_configuration(
    *,
    db: Session,
    company_id: UUID,
    created_by_user_id: UUID,
    payload: CompanyConfigurationCreate,
) -> CompanyConfigurationVersion:
    latest_version = db.scalar(
        select(CompanyConfigurationVersion)
        .where(CompanyConfigurationVersion.company_id == company_id)
        .order_by(CompanyConfigurationVersion.version_number.desc())
        .limit(1)
    )
    version_number = 1 if latest_version is None else latest_version.version_number + 1
    config = CompanyConfigurationVersion(
        company_id=company_id,
        version_number=version_number,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        gst_registered=payload.gst_registered,
        bas_frequency=BasFrequency(payload.bas_frequency),
        bas_reporting_basis=BasReportingBasis(payload.bas_reporting_basis),
        financial_year_start_month=payload.financial_year_start_month,
        financial_year_start_day=payload.financial_year_start_day,
        allow_self_approval=payload.allow_self_approval,
        self_approval_mode=SelfApprovalMode(payload.self_approval_mode),
        period_lock_policy=PeriodLockPolicy(payload.period_lock_policy),
        created_by_user_id=created_by_user_id,
    )
    db.add(config)
    return config


@router.get("", response_model=list[CompanyRead])
def list_companies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Company]:
    if current_user.is_superuser:
        return list(db.scalars(select(Company).order_by(Company.legal_name.asc())).all())
    return list(
        db.scalars(
            select(Company)
            .join(UserCompanyAccess, UserCompanyAccess.company_id == Company.id)
            .where(UserCompanyAccess.user_id == current_user.id)
            .order_by(Company.legal_name.asc())
        ).all()
    )


@router.post("", response_model=CompanyRead, status_code=201)
def create_company(
    payload: CompanyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    company = Company(
        legal_name=payload.legal_name,
        trading_name=payload.trading_name,
        abn=payload.abn,
        acn=payload.acn,
        entity_type=payload.entity_type,
    )
    db.add(company)
    db.flush()

    db.add(
        UserCompanyAccess(
            user_id=current_user.id,
            company_id=company.id,
            can_prepare=True,
            can_review=True,
            can_approve=True,
            can_administer=True,
        )
    )
    _create_configuration(
        db=db,
        company_id=company.id,
        created_by_user_id=current_user.id,
        payload=payload.initial_configuration,
    )
    seed_company_reference_data(db, company.id)
    log_audit_event(
        db,
        action="company.created",
        summary=f"Created company {company.legal_name}",
        entity_type=EntityType.COMPANY.value,
        entity_id=company.id,
        actor_user_id=current_user.id,
        company_id=company.id,
    )
    db.commit()
    db.refresh(company)
    return company


@router.put("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    require_company_permission(company_id, "can_administer", db, current_user)
    company = _load_company_or_404(db, company_id)
    before_state = CompanyRead.model_validate(company).model_dump(mode="json")
    company.legal_name = payload.legal_name
    company.trading_name = payload.trading_name
    company.abn = payload.abn
    company.acn = payload.acn
    company.entity_type = payload.entity_type
    company.is_active = payload.is_active
    company.base_currency = payload.base_currency.upper()
    company.country_code = payload.country_code.upper()
    log_audit_event(
        db,
        action="company.updated",
        summary=f"Updated company {company.legal_name}",
        entity_type=EntityType.COMPANY.value,
        entity_id=company.id,
        actor_user_id=current_user.id,
        company_id=company.id,
        before_state=before_state,
        after_state=CompanyRead.model_validate(company).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    company = _load_company_or_404(db, company_id)
    before_state = CompanyRead.model_validate(company).model_dump(mode="json")
    company.is_active = False
    log_audit_event(
        db,
        action="company.deactivated",
        summary=f"Deactivated company {company.legal_name}",
        entity_type=EntityType.COMPANY.value,
        entity_id=company.id,
        actor_user_id=current_user.id,
        company_id=company.id,
        before_state=before_state,
        after_state=CompanyRead.model_validate(company).model_dump(mode="json"),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    require_company_permission(company_id, "can_prepare", db, current_user)
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("/{company_id}/configurations", response_model=list[ConfigurationVersionRead])
def list_company_configurations(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CompanyConfigurationVersion]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(CompanyConfigurationVersion)
            .where(CompanyConfigurationVersion.company_id == company_id)
            .order_by(CompanyConfigurationVersion.version_number.desc())
        ).all()
    )


@router.post("/{company_id}/configurations", response_model=ConfigurationVersionRead, status_code=201)
def add_company_configuration(
    company_id: UUID,
    payload: CompanyConfigurationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyConfigurationVersion:
    require_company_permission(company_id, "can_administer", db, current_user)
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    config = _create_configuration(
        db=db,
        company_id=company_id,
        created_by_user_id=current_user.id,
        payload=payload,
    )
    db.flush()
    log_audit_event(
        db,
        action="company.configuration.created",
        summary=f"Created configuration version {config.version_number} for {company.legal_name}",
        entity_type=EntityType.COMPANY_CONFIGURATION.value,
        entity_id=config.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    db.refresh(config)
    return config


@router.put("/{company_id}/configurations/{configuration_id}", response_model=ConfigurationVersionRead)
def update_company_configuration(
    company_id: UUID,
    configuration_id: UUID,
    payload: CompanyConfigurationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyConfigurationVersion:
    require_company_permission(company_id, "can_administer", db, current_user)
    configuration = _load_configuration_or_404(db, company_id, configuration_id)
    _ensure_configuration_editable(db, company_id, configuration)
    before_state = ConfigurationVersionRead.model_validate(configuration).model_dump(mode="json")
    configuration.effective_from = payload.effective_from
    configuration.effective_to = payload.effective_to
    configuration.gst_registered = payload.gst_registered
    configuration.bas_frequency = BasFrequency(payload.bas_frequency)
    configuration.bas_reporting_basis = BasReportingBasis(payload.bas_reporting_basis)
    configuration.financial_year_start_month = payload.financial_year_start_month
    configuration.financial_year_start_day = payload.financial_year_start_day
    configuration.allow_self_approval = payload.allow_self_approval
    configuration.self_approval_mode = SelfApprovalMode(payload.self_approval_mode)
    configuration.period_lock_policy = PeriodLockPolicy(payload.period_lock_policy)
    log_audit_event(
        db,
        action="company.configuration.updated",
        summary=f"Updated configuration version {configuration.version_number}",
        entity_type=EntityType.COMPANY_CONFIGURATION.value,
        entity_id=configuration.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=ConfigurationVersionRead.model_validate(configuration).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(configuration)
    return configuration


@router.delete("/{company_id}/configurations/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_configuration(
    company_id: UUID,
    configuration_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    configuration = _load_configuration_or_404(db, company_id, configuration_id)
    _ensure_configuration_editable(db, company_id, configuration)
    log_audit_event(
        db,
        action="company.configuration.deleted",
        summary=f"Deleted configuration version {configuration.version_number}",
        entity_type=EntityType.COMPANY_CONFIGURATION.value,
        entity_id=configuration.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=ConfigurationVersionRead.model_validate(configuration).model_dump(mode="json"),
    )
    db.delete(configuration)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{company_id}/access", response_model=list[CompanyAccessRead])
def list_company_access(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserCompanyAccess]:
    require_company_permission(company_id, "can_administer", db, current_user)
    return list(
        db.scalars(
            select(UserCompanyAccess)
            .where(UserCompanyAccess.company_id == company_id)
            .order_by(UserCompanyAccess.created_at.asc())
        ).all()
    )


@router.post("/{company_id}/access", response_model=CompanyAccessRead, status_code=201)
def grant_company_access(
    company_id: UUID,
    payload: GrantCompanyAccessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserCompanyAccess:
    require_company_permission(company_id, "can_administer", db, current_user)
    access = db.scalar(
        select(UserCompanyAccess).where(
            UserCompanyAccess.company_id == company_id,
            UserCompanyAccess.user_id == payload.user_id,
        )
    )
    if access is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Access already exists")

    access = UserCompanyAccess(company_id=company_id, **payload.model_dump())
    db.add(access)
    log_audit_event(
        db,
        action="company.access.granted",
        summary=f"Granted access for user {payload.user_id} to company {company_id}",
        entity_type=EntityType.COMPANY.value,
        entity_id=company_id,
        actor_user_id=current_user.id,
        company_id=company_id,
        metadata=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(access)
    return access


@router.put("/{company_id}/access/{user_id}", response_model=CompanyAccessRead)
def update_company_access(
    company_id: UUID,
    user_id: UUID,
    payload: CompanyAccessUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserCompanyAccess:
    require_company_permission(company_id, "can_administer", db, current_user)
    access = _load_company_access_or_404(db, company_id, user_id)
    before_state = CompanyAccessRead.model_validate(access).model_dump(mode="json")
    access.can_prepare = payload.can_prepare
    access.can_review = payload.can_review
    access.can_approve = payload.can_approve
    access.can_administer = payload.can_administer
    log_audit_event(
        db,
        action="company.access.updated",
        summary=f"Updated access for user {user_id}",
        entity_type=EntityType.COMPANY.value,
        entity_id=UUID(str(company_id)),
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=CompanyAccessRead.model_validate(access).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(access)
    return access


@router.delete("/{company_id}/access/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_access(
    company_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    access = _load_company_access_or_404(db, company_id, user_id)
    log_audit_event(
        db,
        action="company.access.deleted",
        summary=f"Removed access for user {user_id}",
        entity_type=EntityType.COMPANY.value,
        entity_id=company_id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=CompanyAccessRead.model_validate(access).model_dump(mode="json"),
    )
    db.delete(access)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
