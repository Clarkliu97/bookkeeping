from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_company_permission
from app.audit.service import log_audit_event
from app.db.models.accounting import Account, JournalLine
from app.db.models.auth import User
from app.db.models.enums import AccountType, EntityType, ReportingCategoryType, TaxInputOutputType
from app.db.models.reference import ReportingCategory, TaxCode
from app.schemas.common import AccountRead, ReportingCategoryRead, TaxCodeRead
from app.schemas.requests import (
    AccountCreate,
    AccountUpdate,
    ReportingCategoryCreate,
    ReportingCategoryUpdate,
    TaxCodeCreate,
    TaxCodeUpdate,
)


router = APIRouter(prefix="/companies/{company_id}", tags=["chart-of-accounts"])


def _load_reporting_category_or_404(db: Session, company_id: UUID, category_id: UUID) -> ReportingCategory:
    category = db.scalar(
        select(ReportingCategory).where(
            ReportingCategory.id == category_id,
            ReportingCategory.company_id == company_id,
        )
    )
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporting category not found")
    return category


def _load_tax_code_or_404(db: Session, company_id: UUID, tax_code_id: UUID) -> TaxCode:
    tax_code = db.scalar(
        select(TaxCode).where(
            TaxCode.id == tax_code_id,
            TaxCode.company_id == company_id,
        )
    )
    if tax_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax code not found")
    return tax_code


def _load_account_or_404(db: Session, company_id: UUID, account_id: UUID) -> Account:
    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            Account.company_id == company_id,
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def _validate_account_payload(payload: AccountCreate | AccountUpdate) -> None:
    if payload.account_type == AccountType.NON_POSTING and payload.allow_manual_posting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non-posting accounts cannot allow manual posting",
        )


@router.get("/reporting-categories", response_model=list[ReportingCategoryRead])
def list_reporting_categories(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReportingCategory]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(ReportingCategory)
            .where((ReportingCategory.company_id == company_id) | (ReportingCategory.company_id.is_(None)))
            .order_by(ReportingCategory.code.asc())
        ).all()
    )


@router.post("/reporting-categories", response_model=ReportingCategoryRead, status_code=201)
def create_reporting_category(
    company_id: UUID,
    payload: ReportingCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportingCategory:
    require_company_permission(company_id, "can_administer", db, current_user)
    category = ReportingCategory(
        company_id=company_id,
        code=payload.code,
        name=payload.name,
        is_active=payload.is_active,
        category_type=payload.category_type,
    )
    db.add(category)
    db.flush()
    log_audit_event(
        db,
        action="reporting-category.created",
        summary=f"Created reporting category {payload.code}",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=category.id,
        actor_user_id=current_user.id,
        company_id=company_id,
    )
    db.commit()
    db.refresh(category)
    return category


@router.put("/reporting-categories/{category_id}", response_model=ReportingCategoryRead)
def update_reporting_category(
    company_id: UUID,
    category_id: UUID,
    payload: ReportingCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportingCategory:
    require_company_permission(company_id, "can_administer", db, current_user)
    category = _load_reporting_category_or_404(db, company_id, category_id)
    before_state = ReportingCategoryRead.model_validate(category).model_dump(mode="json")
    category.code = payload.code
    category.name = payload.name
    category.is_active = payload.is_active
    category.category_type = payload.category_type
    log_audit_event(
        db,
        action="reporting-category.updated",
        summary=f"Updated reporting category {category.code}",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=category.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=ReportingCategoryRead.model_validate(category).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(category)
    return category


@router.delete("/reporting-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reporting_category(
    company_id: UUID,
    category_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    category = _load_reporting_category_or_404(db, company_id, category_id)
    if db.scalar(select(Account.id).where(Account.reporting_category_id == category.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reporting category is in use by accounts")
    if db.scalar(select(JournalLine.id).where(JournalLine.reporting_category_id == category.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reporting category is in use by journals")
    log_audit_event(
        db,
        action="reporting-category.deleted",
        summary=f"Deleted reporting category {category.code}",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=category.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=ReportingCategoryRead.model_validate(category).model_dump(mode="json"),
    )
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tax-codes", response_model=list[TaxCodeRead])
def list_tax_codes(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxCode]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(TaxCode)
            .where((TaxCode.company_id == company_id) | (TaxCode.company_id.is_(None)))
            .order_by(TaxCode.code.asc())
        ).all()
    )


@router.post("/tax-codes", response_model=TaxCodeRead, status_code=201)
def create_tax_code(
    company_id: UUID,
    payload: TaxCodeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxCode:
    require_company_permission(company_id, "can_administer", db, current_user)
    tax_code = TaxCode(
        company_id=company_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        rate=payload.rate,
        is_gst_applicable=payload.is_gst_applicable,
        is_active=payload.is_active,
        bas_label=payload.bas_label,
        input_output_type=payload.input_output_type,
    )
    db.add(tax_code)
    db.commit()
    db.refresh(tax_code)
    return tax_code


@router.put("/tax-codes/{tax_code_id}", response_model=TaxCodeRead)
def update_tax_code(
    company_id: UUID,
    tax_code_id: UUID,
    payload: TaxCodeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxCode:
    require_company_permission(company_id, "can_administer", db, current_user)
    tax_code = _load_tax_code_or_404(db, company_id, tax_code_id)
    before_state = TaxCodeRead.model_validate(tax_code).model_dump(mode="json")
    tax_code.code = payload.code
    tax_code.name = payload.name
    tax_code.description = payload.description
    tax_code.rate = payload.rate
    tax_code.is_gst_applicable = payload.is_gst_applicable
    tax_code.is_active = payload.is_active
    tax_code.bas_label = payload.bas_label
    tax_code.input_output_type = payload.input_output_type
    log_audit_event(
        db,
        action="tax-code.updated",
        summary=f"Updated tax code {tax_code.code}",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=tax_code.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=TaxCodeRead.model_validate(tax_code).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(tax_code)
    return tax_code


@router.delete("/tax-codes/{tax_code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tax_code(
    company_id: UUID,
    tax_code_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    tax_code = _load_tax_code_or_404(db, company_id, tax_code_id)
    if db.scalar(select(Account.id).where(Account.default_tax_code_id == tax_code.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tax code is in use by accounts")
    if db.scalar(select(JournalLine.id).where(JournalLine.tax_code_id == tax_code.id).limit(1)) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tax code is in use by journals")
    log_audit_event(
        db,
        action="tax-code.deleted",
        summary=f"Deleted tax code {tax_code.code}",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=tax_code.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=TaxCodeRead.model_validate(tax_code).model_dump(mode="json"),
    )
    db.delete(tax_code)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/accounts", response_model=list[AccountRead])
def list_accounts(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Account]:
    require_company_permission(company_id, "can_prepare", db, current_user)
    return list(
        db.scalars(
            select(Account)
            .where(Account.company_id == company_id)
            .order_by(Account.account_code.asc())
        ).all()
    )


@router.post("/accounts", response_model=AccountRead, status_code=201)
def create_account(
    company_id: UUID,
    payload: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Account:
    require_company_permission(company_id, "can_administer", db, current_user)
    _validate_account_payload(payload)
    existing = db.scalar(
        select(Account).where(Account.company_id == company_id, Account.account_code == payload.account_code)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account code already exists")

    account = Account(
        company_id=company_id,
        account_code=payload.account_code,
        name=payload.name,
        account_type=payload.account_type,
        reporting_category_id=payload.reporting_category_id,
        default_tax_code_id=payload.default_tax_code_id,
        is_active=payload.is_active,
        allow_manual_posting=payload.allow_manual_posting,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.put("/accounts/{account_id}", response_model=AccountRead)
def update_account(
    company_id: UUID,
    account_id: UUID,
    payload: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Account:
    require_company_permission(company_id, "can_administer", db, current_user)
    _validate_account_payload(payload)
    account = _load_account_or_404(db, company_id, account_id)
    has_history = db.scalar(select(JournalLine.id).where(JournalLine.account_id == account.id).limit(1)) is not None
    if has_history and account.account_type != payload.account_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account type cannot be changed after journals reference the account",
        )
    before_state = AccountRead.model_validate(account).model_dump(mode="json")
    account.account_code = payload.account_code
    account.name = payload.name
    account.account_type = payload.account_type
    account.reporting_category_id = payload.reporting_category_id
    account.default_tax_code_id = payload.default_tax_code_id
    account.is_active = payload.is_active
    account.allow_manual_posting = payload.allow_manual_posting
    log_audit_event(
        db,
        action="account.updated",
        summary=f"Updated account {account.account_code}",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=account.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=AccountRead.model_validate(account).model_dump(mode="json"),
    )
    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    company_id: UUID,
    account_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    require_company_permission(company_id, "can_administer", db, current_user)
    account = _load_account_or_404(db, company_id, account_id)
    before_state = AccountRead.model_validate(account).model_dump(mode="json")
    account.is_active = False
    log_audit_event(
        db,
        action="account.deactivated",
        summary=f"Deactivated account {account.account_code}",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=account.id,
        actor_user_id=current_user.id,
        company_id=company_id,
        before_state=before_state,
        after_state=AccountRead.model_validate(account).model_dump(mode="json"),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
