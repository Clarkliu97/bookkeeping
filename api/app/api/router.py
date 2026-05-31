from fastapi import APIRouter

from app.accounting_periods.router import router as accounting_periods_router
from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.bas.router import router as bas_router
from app.bank_imports.router import router as bank_imports_router
from app.chart_of_accounts.router import router as chart_of_accounts_router
from app.companies.router import router as companies_router
from app.documents.router import router as documents_router
from app.employment.router import router as employment_router
from app.fixed_assets.router import router as fixed_assets_router
from app.journal_recommendations.router import router as journal_recommendations_router
from app.ledger.router import router as ledger_router
from app.reports.router import router as reports_router
from app.reconciliation.router import router as reconciliation_router
from app.tax_workpapers.router import router as tax_workpapers_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(companies_router)
api_router.include_router(chart_of_accounts_router)
api_router.include_router(accounting_periods_router)
api_router.include_router(ledger_router)
api_router.include_router(journal_recommendations_router)
api_router.include_router(employment_router)
api_router.include_router(fixed_assets_router)
api_router.include_router(reports_router)
api_router.include_router(tax_workpapers_router)
api_router.include_router(bas_router)
api_router.include_router(documents_router)
api_router.include_router(bank_imports_router)
api_router.include_router(reconciliation_router)


@api_router.get("/meta")
def get_meta() -> dict[str, str]:
    return {
        "product": "internal-bookkeeping-tax-support",
        "scope": "internal-review-only",
        "jurisdiction": "AU",
        "currency": "AUD",
    }
