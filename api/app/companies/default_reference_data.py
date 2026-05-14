import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.accounting import Account
from app.db.models.enums import AccountType, ReportingCategoryType, TaxInputOutputType
from app.db.models.reference import ReportingCategory, TaxCode


REFERENCE_TEMPLATE_DIR = Path(__file__).with_name("reference_templates")


def _load_template(name: str) -> list[dict[str, Any]]:
    with (REFERENCE_TEMPLATE_DIR / name).open(encoding="utf-8") as template_file:
        return json.load(template_file)


def seed_company_reference_data(db: Session, company_id: UUID) -> None:
    reporting_categories = _load_template("reporting_categories.json")
    tax_codes = _load_template("tax_codes.json")
    accounts = _load_template("chart_of_accounts.json")

    category_ids_by_code: dict[str, UUID] = {}
    for category_data in reporting_categories:
        category = ReportingCategory(
            company_id=company_id,
            code=category_data["code"],
            name=category_data["name"],
            category_type=ReportingCategoryType(category_data["category_type"]),
            is_active=True,
        )
        db.add(category)
        db.flush()
        category_ids_by_code[category.code] = category.id

    tax_code_ids_by_code: dict[str, UUID] = {}
    for tax_code_data in tax_codes:
        tax_code = TaxCode(
            company_id=company_id,
            code=tax_code_data["code"],
            name=tax_code_data["name"],
            description=tax_code_data.get("description"),
            rate=Decimal(tax_code_data["rate"]),
            is_gst_applicable=tax_code_data["is_gst_applicable"],
            bas_label=tax_code_data.get("bas_label"),
            input_output_type=TaxInputOutputType(tax_code_data["input_output_type"]),
            is_active=True,
        )
        db.add(tax_code)
        db.flush()
        tax_code_ids_by_code[tax_code.code] = tax_code.id

    for account_data in accounts:
        default_tax_code = account_data.get("default_tax_code_code")
        account = Account(
            company_id=company_id,
            account_code=account_data["account_code"],
            name=account_data["name"],
            account_type=AccountType(account_data["account_type"]),
            reporting_category_id=category_ids_by_code[account_data["reporting_category_code"]],
            default_tax_code_id=tax_code_ids_by_code[default_tax_code] if default_tax_code else None,
            is_active=True,
            allow_manual_posting=account_data["allow_manual_posting"],
        )
        db.add(account)
