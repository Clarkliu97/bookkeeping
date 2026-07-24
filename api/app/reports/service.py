from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounting_periods.service import (
    current_earnings_start_date,
    period_rollover_journal_condition,
)
from app.db.models.accounting import Account, JournalEntry, JournalLine
from app.db.models.enums import AccountType, JournalStatus
from app.db.models.reference import ReportingCategory
from app.schemas.common import (
    BalanceSheetReportRead,
    CashFlowCashAccountLine,
    CashFlowLine,
    CashFlowReportRead,
    EquityMovementLine,
    FinancialReportLine,
    GeneralLedgerAccountRead,
    GeneralLedgerEntryRead,
    GeneralLedgerReportRead,
    ProfitAndLossReportRead,
    StatementOfChangesInEquityRead,
    TrialBalanceReportRead,
    TrialBalanceRow,
)

ZERO = Decimal("0.00")
POSTED_REPORT_STATUSES = (JournalStatus.POSTED,)
DRAFT_VISIBLE_REPORT_STATUSES = (JournalStatus.POSTED, JournalStatus.DRAFT)
CASH_REPORTING_CATEGORY = "BS_CA_CASH"
LOAN_RECEIVABLE_CATEGORY_CODES = {
    "BS_CA_LOANS_RECEIVABLE",
    "BS_NCA_LOANS_RECEIVABLE",
}
NON_CURRENT_ASSET_CATEGORY_CODES = {
    "BS_NCA_PPE",
    "BS_NCA_ROU_ASSETS",
    "BS_NCA_INVESTMENT_PROPERTY",
    "BS_NCA_INTANGIBLES",
    "BS_NCA_OTHER_ASSETS",
}
INVESTMENT_CATEGORY_CODES = {
    "BS_NCA_FINANCIAL_ASSETS",
    "BS_NCA_INVESTMENTS_SUBSIDIARIES",
}
BORROWING_CATEGORY_CODES = {
    "BS_CL_BORROWINGS",
    "BS_CL_RELATED_PARTY_PAYABLES",
    "BS_NCL_BORROWINGS",
}
LEASE_LIABILITY_CATEGORY_CODES = {
    "BS_CL_LEASE_LIABILITIES",
    "BS_NCL_LEASE_LIABILITIES",
}
EQUITY_CONTRIBUTION_CATEGORY_CODES = {
    "BS_EQ_SHARE_CAPITAL",
    "BS_EQ_CONTRIBUTIONS",
}
EQUITY_DISTRIBUTION_CATEGORY_CODES = {
    "BS_EQ_TREASURY_SHARES",
    "BS_EQ_DIVIDENDS_DISTRIBUTIONS",
}
CASH_FLOW_LINE_DEFINITIONS: dict[str, tuple[str, str]] = {
    "receipts_from_customers": ("operating", "Cash receipts from customers"),
    "refunds_paid_to_customers": ("operating", "Cash refunds paid to customers"),
    "refunds_received_from_suppliers": ("operating", "Cash refunds from suppliers"),
    "payments_to_suppliers": ("operating", "Cash paid to suppliers"),
    "payments_to_employees": ("operating", "Cash paid to employees"),
    "income_tax_refunds": ("operating", "Income tax refunds received"),
    "income_taxes_paid": ("operating", "Income taxes paid"),
    "other_tax_refunds": ("operating", "Other tax and statutory refunds received"),
    "other_taxes_paid": ("operating", "Other taxes and statutory payments"),
    "other_operating_receipts": ("operating", "Other operating cash receipts"),
    "other_operating_payments": ("operating", "Other operating cash payments"),
    "interest_received": ("investing", "Interest received"),
    "dividends_received": ("investing", "Dividends and distributions received"),
    "proceeds_from_non_current_assets": (
        "investing",
        "Proceeds from sale of property, plant, equipment and other non-current assets",
    ),
    "purchases_of_non_current_assets": (
        "investing",
        "Purchase of property, plant, equipment and other non-current assets",
    ),
    "proceeds_from_investments": ("investing", "Proceeds from sale of investments"),
    "purchases_of_investments": ("investing", "Purchase of investments"),
    "loan_repayments_received": ("investing", "Repayment of loans advanced received"),
    "loans_advanced": ("investing", "Loans advanced to other parties"),
    "other_investing_receipts": ("investing", "Other investing cash receipts"),
    "other_investing_payments": ("investing", "Other investing cash payments"),
    "proceeds_from_share_capital": (
        "financing",
        "Proceeds from issue of share capital and owner contributions",
    ),
    "payments_to_owners": (
        "financing",
        "Payments to owners for share redemptions and capital returns",
    ),
    "proceeds_from_borrowings": ("financing", "Proceeds from borrowings"),
    "repayment_of_borrowings": ("financing", "Repayment of borrowings"),
    "repayment_of_lease_liabilities": ("financing", "Payment of lease liabilities"),
    "interest_paid": ("financing", "Interest paid"),
    "dividends_paid": ("financing", "Dividends and distributions paid"),
    "other_financing_receipts": ("financing", "Other financing cash receipts"),
    "other_financing_payments": ("financing", "Other financing cash payments"),
}
CASH_FLOW_LINE_ORDER = tuple(CASH_FLOW_LINE_DEFINITIONS)
CASH_FLOW_POLICY = (
    "Major classes of gross cash receipts and payments are presented. "
    "Interest and dividends received are investing cash flows; interest paid, dividends paid, "
    "and lease-liability principal payments are financing cash flows."
)


@dataclass(frozen=True)
class AccountAggregate:
    account_id: UUID
    account_code: str
    account_name: str
    account_type: AccountType
    debit_total: Decimal
    credit_total: Decimal

    @property
    def raw_balance(self) -> Decimal:
        return Decimal(self.debit_total or ZERO) - Decimal(self.credit_total or ZERO)


REPORT_SECTIONS: dict[AccountType, str] = {
    AccountType.ASSET: "asset",
    AccountType.CONTRA_ASSET: "asset",
    AccountType.LIABILITY: "liability",
    AccountType.CONTRA_LIABILITY: "liability",
    AccountType.EQUITY: "equity",
    AccountType.INCOME: "income",
    AccountType.REVENUE: "income",
    AccountType.OTHER_INCOME: "income",
    AccountType.CONTRA_INCOME: "income",
    AccountType.EXPENSE: "expense",
    AccountType.COST_OF_SALES: "expense",
    AccountType.OTHER_EXPENSE: "expense",
    AccountType.CONTRA_EXPENSE: "expense",
}


def _display_amount(account_type: AccountType, raw_balance: Decimal) -> Decimal:
    if account_type in {
        AccountType.ASSET,
        AccountType.EXPENSE,
        AccountType.COST_OF_SALES,
        AccountType.OTHER_EXPENSE,
        AccountType.CONTRA_ASSET,
        AccountType.CONTRA_EXPENSE,
    }:
        return raw_balance
    return -raw_balance


def _date_filters(query, *, start_date: date | None = None, end_date: date | None = None):
    if start_date is not None:
        query = query.where(JournalEntry.entry_date >= start_date)
    if end_date is not None:
        query = query.where(JournalEntry.entry_date <= end_date)
    return query


def _visible_statuses(*, include_draft: bool) -> tuple[JournalStatus, ...]:
    if include_draft:
        return DRAFT_VISIBLE_REPORT_STATUSES
    return POSTED_REPORT_STATUSES


def _aggregate_accounts(
    db: Session,
    *,
    company_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    account_types: set[AccountType] | None = None,
    include_draft: bool = False,
    exclude_period_rollovers: bool = False,
) -> list[AccountAggregate]:
    query = (
        select(
            Account.id,
            Account.account_code,
            Account.name,
            Account.account_type,
            func.coalesce(func.sum(JournalLine.debit_amount), 0).label("debit_total"),
            func.coalesce(func.sum(JournalLine.credit_amount), 0).label("credit_total"),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(Account.company_id == company_id)
        .where(JournalEntry.status.in_(_visible_statuses(include_draft=include_draft)))
    )
    query = _date_filters(query, start_date=start_date, end_date=end_date)
    if exclude_period_rollovers:
        query = query.where(~period_rollover_journal_condition())
    if account_types is not None:
        query = query.where(Account.account_type.in_(account_types))
    query = query.group_by(
        Account.id, Account.account_code, Account.name, Account.account_type
    ).order_by(Account.account_code.asc())
    rows = db.execute(query).all()
    return [
        AccountAggregate(
            account_id=row.id,
            account_code=row.account_code,
            account_name=row.name,
            account_type=row.account_type,
            debit_total=Decimal(row.debit_total or ZERO),
            credit_total=Decimal(row.credit_total or ZERO),
        )
        for row in rows
    ]


def build_trial_balance_report(
    db: Session,
    *,
    company_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    include_draft: bool = False,
) -> TrialBalanceReportRead:
    aggregates = _aggregate_accounts(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        include_draft=include_draft,
    )
    rows = [
        TrialBalanceRow(
            account_id=aggregate.account_id,
            account_code=aggregate.account_code,
            account_name=aggregate.account_name,
            debit_total=aggregate.debit_total,
            credit_total=aggregate.credit_total,
            balance=aggregate.raw_balance,
        )
        for aggregate in aggregates
    ]
    return TrialBalanceReportRead(start_date=start_date, end_date=end_date, rows=rows)


def build_profit_and_loss_report(
    db: Session,
    *,
    company_id: UUID,
    start_date: date,
    end_date: date,
    include_draft: bool = False,
) -> ProfitAndLossReportRead:
    pnl_types = {
        AccountType.INCOME,
        AccountType.REVENUE,
        AccountType.OTHER_INCOME,
        AccountType.CONTRA_INCOME,
        AccountType.EXPENSE,
        AccountType.COST_OF_SALES,
        AccountType.OTHER_EXPENSE,
        AccountType.CONTRA_EXPENSE,
    }
    aggregates = _aggregate_accounts(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        account_types=pnl_types,
        include_draft=include_draft,
        exclude_period_rollovers=True,
    )
    income_lines: list[FinancialReportLine] = []
    expense_lines: list[FinancialReportLine] = []
    total_income = ZERO
    total_expenses = ZERO
    for aggregate in aggregates:
        amount = _display_amount(aggregate.account_type, aggregate.raw_balance)
        line = FinancialReportLine(
            account_id=aggregate.account_id,
            account_code=aggregate.account_code,
            account_name=aggregate.account_name,
            account_type=aggregate.account_type.value,
            amount=amount,
        )
        section = REPORT_SECTIONS[aggregate.account_type]
        if section == "income":
            income_lines.append(line)
            total_income += amount
        else:
            expense_lines.append(line)
            total_expenses += amount
    return ProfitAndLossReportRead(
        start_date=start_date,
        end_date=end_date,
        income_lines=income_lines,
        expense_lines=expense_lines,
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=total_income - total_expenses,
    )


def build_balance_sheet_report(
    db: Session,
    *,
    company_id: UUID,
    as_of_date: date,
    include_draft: bool = False,
) -> BalanceSheetReportRead:
    balance_sheet_types = {
        AccountType.ASSET,
        AccountType.CONTRA_ASSET,
        AccountType.LIABILITY,
        AccountType.CONTRA_LIABILITY,
        AccountType.EQUITY,
    }
    aggregates = _aggregate_accounts(
        db,
        company_id=company_id,
        end_date=as_of_date,
        account_types=balance_sheet_types,
        include_draft=include_draft,
    )
    asset_lines: list[FinancialReportLine] = []
    liability_lines: list[FinancialReportLine] = []
    equity_lines: list[FinancialReportLine] = []
    total_assets = ZERO
    total_liabilities = ZERO
    total_equity = ZERO
    for aggregate in aggregates:
        amount = _display_amount(aggregate.account_type, aggregate.raw_balance)
        line = FinancialReportLine(
            account_id=aggregate.account_id,
            account_code=aggregate.account_code,
            account_name=aggregate.account_name,
            account_type=aggregate.account_type.value,
            amount=amount,
        )
        section = REPORT_SECTIONS[aggregate.account_type]
        if section == "asset":
            asset_lines.append(line)
            total_assets += amount
        elif section == "liability":
            liability_lines.append(line)
            total_liabilities += amount
        else:
            equity_lines.append(line)
            total_equity += amount

    earnings_report = build_profit_and_loss_report(
        db,
        company_id=company_id,
        start_date=current_earnings_start_date(
            db,
            company_id=company_id,
            as_of_date=as_of_date,
        ),
        end_date=as_of_date,
        include_draft=include_draft,
    )
    current_earnings = FinancialReportLine(
        account_id=None,
        account_code="CURRENT_EARNINGS",
        account_name="Current Earnings",
        account_type="equity",
        amount=earnings_report.net_profit,
    )
    total_equity += current_earnings.amount
    return BalanceSheetReportRead(
        as_of_date=as_of_date,
        asset_lines=asset_lines,
        liability_lines=liability_lines,
        equity_lines=equity_lines,
        current_earnings=current_earnings,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        total_liabilities_and_equity=total_liabilities + total_equity,
    )


def _cash_accounts(db: Session, *, company_id: UUID) -> list[Account]:
    rows = db.execute(
        select(Account, ReportingCategory.code)
        .outerjoin(ReportingCategory, ReportingCategory.id == Account.reporting_category_id)
        .where(Account.company_id == company_id)
        .where(Account.account_type.in_({AccountType.ASSET, AccountType.CONTRA_ASSET}))
        .order_by(Account.account_code.asc())
    ).all()
    cash_accounts: list[Account] = []
    for account, reporting_category_code in rows:
        normalized_name = account.name.casefold()
        is_name_fallback = "cash" in normalized_name or "bank" in normalized_name
        if reporting_category_code == CASH_REPORTING_CATEGORY or is_name_fallback:
            cash_accounts.append(account)
    return cash_accounts


def _account_balance_as_of(
    db: Session,
    *,
    company_id: UUID,
    account: Account,
    as_of_date: date,
    include_draft: bool,
) -> Decimal:
    query = (
        select(
            func.coalesce(func.sum(JournalLine.debit_amount), 0).label("debit_total"),
            func.coalesce(func.sum(JournalLine.credit_amount), 0).label("credit_total"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalLine.account_id == account.id)
        .where(JournalEntry.company_id == company_id)
        .where(JournalEntry.status.in_(_visible_statuses(include_draft=include_draft)))
        .where(JournalEntry.entry_date <= as_of_date)
    )
    row = db.execute(query).one()
    raw_balance = Decimal(row.debit_total or ZERO) - Decimal(row.credit_total or ZERO)
    return _display_amount(account.account_type, raw_balance)


def _cash_flow_statement_line(
    counterpart_rows: list,
    *,
    cash_movement: Decimal,
) -> tuple[str, str]:
    if not counterpart_rows:
        line_code = (
            "other_operating_receipts"
            if cash_movement > ZERO
            else "other_operating_payments"
        )
        return CASH_FLOW_LINE_DEFINITIONS[line_code][0], line_code

    dominant = max(
        counterpart_rows,
        key=lambda row: abs(Decimal(row.debit_amount or ZERO) - Decimal(row.credit_amount or ZERO)),
    )
    category_code = dominant.reporting_category_code
    normalized_name = dominant.account_name.casefold()
    is_receipt = cash_movement > ZERO

    if (
        category_code in {"PL_EXP_FX_OPERATING", "PL_OE_FX_NON_OPERATING"}
        or (
            any(keyword in normalized_name for keyword in ("foreign exchange", "fx "))
            and any(keyword in normalized_name for keyword in ("gain", "loss", "revaluation"))
        )
    ):
        return "exchange", "effect_of_exchange_rate_changes"

    if category_code == "PL_OI_INTEREST" or any(
        keyword in normalized_name for keyword in ("interest income", "interest receivable")
    ):
        return "investing", "interest_received"
    if category_code == "PL_OI_DIVIDEND_DISTRIBUTION" or any(
        keyword in normalized_name
        for keyword in ("dividend income", "dividend receivable", "distribution receivable")
    ):
        return "investing", "dividends_received"
    if category_code == "PL_EXP_FINANCE_COSTS" or any(
        keyword in normalized_name
        for keyword in ("interest expense", "interest payable", "borrowing cost")
    ):
        return "financing", "interest_paid"

    is_loan_receivable = category_code in LOAN_RECEIVABLE_CATEGORY_CODES or (
        "loan receivable" in normalized_name or "mortgage receivable" in normalized_name
    )
    if is_loan_receivable:
        line_code = "loan_repayments_received" if is_receipt else "loans_advanced"
        return "investing", line_code

    is_property_purchase_deposit = category_code == "BS_CA_DEPOSITS" and any(
        keyword in normalized_name
        for keyword in ("property purchase", "investment deposit", "acquisition deposit")
    )
    is_property_acquisition_clearing = any(
        keyword in normalized_name
        for keyword in ("property settlement", "conveyancer trust", "acquisition clearing")
    )
    if (
        category_code in NON_CURRENT_ASSET_CATEGORY_CODES
        or is_property_purchase_deposit
        or is_property_acquisition_clearing
    ):
        line_code = (
            "proceeds_from_non_current_assets"
            if is_receipt
            else "purchases_of_non_current_assets"
        )
        return "investing", line_code
    if category_code in INVESTMENT_CATEGORY_CODES:
        line_code = "proceeds_from_investments" if is_receipt else "purchases_of_investments"
        return "investing", line_code

    if category_code in LEASE_LIABILITY_CATEGORY_CODES or "lease liability" in normalized_name:
        line_code = (
            "other_financing_receipts" if is_receipt else "repayment_of_lease_liabilities"
        )
        return "financing", line_code
    is_borrowing = category_code in BORROWING_CATEGORY_CODES or any(
        keyword in normalized_name
        for keyword in ("loan payable", "borrowings", "mortgage payable")
    )
    if is_borrowing:
        line_code = "proceeds_from_borrowings" if is_receipt else "repayment_of_borrowings"
        return "financing", line_code

    if category_code in EQUITY_DISTRIBUTION_CATEGORY_CODES or any(
        keyword in normalized_name
        for keyword in ("dividend paid", "dividend payable", "distribution to owner", "drawings")
    ):
        line_code = "other_financing_receipts" if is_receipt else "dividends_paid"
        return "financing", line_code
    if (
        category_code in EQUITY_CONTRIBUTION_CATEGORY_CODES
        or dominant.account_type == AccountType.EQUITY
    ):
        line_code = "proceeds_from_share_capital" if is_receipt else "payments_to_owners"
        return "financing", line_code

    is_employee_related = category_code in {"PL_EXP_EMPLOYEE", "BS_CL_EMPLOYEE_BENEFITS"} or any(
        keyword in normalized_name
        for keyword in ("wages", "salary", "salaries", "payroll", "superannuation payable")
    )
    if is_employee_related and not is_receipt:
        return "operating", "payments_to_employees"

    is_income_tax = any(
        keyword in normalized_name for keyword in ("income tax", "company tax", "payg instalment")
    )
    if is_income_tax:
        line_code = "income_tax_refunds" if is_receipt else "income_taxes_paid"
        return "operating", line_code
    is_other_tax = category_code in {
        "BS_CA_TAX_RECEIVABLES",
        "BS_CL_TAX_PAYABLES",
        "PL_EXP_TAX_GOVERNMENT",
    }
    if is_other_tax:
        line_code = "other_tax_refunds" if is_receipt else "other_taxes_paid"
        return "operating", line_code

    income_types = {
        AccountType.INCOME,
        AccountType.REVENUE,
        AccountType.OTHER_INCOME,
        AccountType.CONTRA_INCOME,
    }
    customer_balance_categories = {
        "BS_CA_TRADE_RECEIVABLES",
        "BS_CA_CONTRACT_ASSETS",
        "BS_CL_CONTRACT_LIABILITIES",
    }
    is_customer_balance = category_code in customer_balance_categories or any(
        keyword in normalized_name
        for keyword in ("accounts receivable", "trade receivable", "contract asset")
    )
    if dominant.account_type in income_types or is_customer_balance:
        line_code = "receipts_from_customers" if is_receipt else "refunds_paid_to_customers"
        return "operating", line_code

    supplier_balance_categories = {
        "BS_CA_INVENTORY",
        "BS_CA_PREPAYMENTS",
        "BS_CL_TRADE_PAYABLES",
    }
    expense_types = {
        AccountType.EXPENSE,
        AccountType.COST_OF_SALES,
        AccountType.OTHER_EXPENSE,
        AccountType.CONTRA_EXPENSE,
    }
    is_supplier_balance = category_code in supplier_balance_categories or any(
        keyword in normalized_name
        for keyword in ("accounts payable", "trade payable", "supplier payable")
    )
    if dominant.account_type in expense_types or is_supplier_balance:
        line_code = "refunds_received_from_suppliers" if is_receipt else "payments_to_suppliers"
        return "operating", line_code

    line_code = "other_operating_receipts" if is_receipt else "other_operating_payments"
    return "operating", line_code


def _cash_flow_allocations(
    counterpart_rows: list,
    *,
    cash_movement: Decimal,
) -> list[tuple[str, str, Decimal]]:
    row_allocations: list[tuple[str, str, Decimal]] = []
    for row in counterpart_rows:
        row_cash_effect = Decimal(row.credit_amount or ZERO) - Decimal(
            row.debit_amount or ZERO
        )
        if row_cash_effect == ZERO:
            continue
        activity_type, line_code = _cash_flow_statement_line(
            [row],
            cash_movement=row_cash_effect,
        )
        row_allocations.append((activity_type, line_code, row_cash_effect))

    allocation_codes = {line_code for _, line_code, _ in row_allocations}
    interest_codes = {"interest_received", "interest_paid"}
    principal_codes = {
        "loan_repayments_received",
        "loans_advanced",
        "proceeds_from_borrowings",
        "repayment_of_borrowings",
        "repayment_of_lease_liabilities",
    }
    allocation_total = sum((amount for _, _, amount in row_allocations), ZERO)
    has_interest_and_principal = bool(allocation_codes & interest_codes) and bool(
        allocation_codes & principal_codes
    )
    if has_interest_and_principal and allocation_total == cash_movement:
        return row_allocations

    activity_type, line_code = _cash_flow_statement_line(
        counterpart_rows,
        cash_movement=cash_movement,
    )
    return [(activity_type, line_code, cash_movement)]


def build_cash_flow_report(
    db: Session,
    *,
    company_id: UUID,
    start_date: date,
    end_date: date,
    include_draft: bool = False,
) -> CashFlowReportRead:
    cash_accounts = _cash_accounts(db, company_id=company_id)
    if not cash_accounts:
        return CashFlowReportRead(
            start_date=start_date,
            end_date=end_date,
            method="direct",
            classification_policy=CASH_FLOW_POLICY,
            cash_accounts=[],
            operating_lines=[],
            investing_lines=[],
            financing_lines=[],
            opening_cash=ZERO,
            total_operating=ZERO,
            total_investing=ZERO,
            total_financing=ZERO,
            net_cash_change=ZERO,
            effect_of_exchange_rate_changes=ZERO,
            calculated_closing_cash=ZERO,
            closing_cash=ZERO,
            reconciliation_difference=ZERO,
        )

    previous_day = start_date - timedelta(days=1)
    all_cash_account_lines = [
        CashFlowCashAccountLine(
            account_id=account.id,
            account_code=account.account_code,
            account_name=account.name,
            opening_balance=_account_balance_as_of(
                db,
                company_id=company_id,
                account=account,
                as_of_date=previous_day,
                include_draft=include_draft,
            ),
            closing_balance=_account_balance_as_of(
                db,
                company_id=company_id,
                account=account,
                as_of_date=end_date,
                include_draft=include_draft,
            ),
        )
        for account in cash_accounts
    ]
    cash_account_lines = [
        line
        for line in all_cash_account_lines
        if line.opening_balance != ZERO or line.closing_balance != ZERO
    ]
    cash_account_ids = {account.id for account in cash_accounts}
    cash_movements = db.execute(
        select(
            JournalEntry.id.label("journal_entry_id"),
            func.coalesce(
                func.sum(JournalLine.debit_amount - JournalLine.credit_amount),
                0,
            ).label("cash_movement"),
        )
        .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
        .where(JournalEntry.company_id == company_id)
        .where(JournalEntry.status.in_(_visible_statuses(include_draft=include_draft)))
        .where(JournalEntry.entry_date >= start_date)
        .where(JournalEntry.entry_date <= end_date)
        .where(JournalLine.account_id.in_(cash_account_ids))
        .group_by(JournalEntry.id)
        .order_by(JournalEntry.id.asc())
    ).all()
    movement_journal_ids = [
        row.journal_entry_id
        for row in cash_movements
        if Decimal(row.cash_movement or ZERO) != ZERO
    ]
    counterpart_by_journal: dict[UUID, list] = defaultdict(list)
    if movement_journal_ids:
        counterpart_rows = db.execute(
            select(
                JournalEntry.id.label("journal_entry_id"),
                Account.account_code,
                Account.name.label("account_name"),
                Account.account_type,
                ReportingCategory.code.label("reporting_category_code"),
                JournalLine.debit_amount,
                JournalLine.credit_amount,
            )
            .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, Account.id == JournalLine.account_id)
            .outerjoin(ReportingCategory, ReportingCategory.id == Account.reporting_category_id)
            .where(JournalEntry.id.in_(movement_journal_ids))
            .where(~Account.id.in_(cash_account_ids))
            .order_by(JournalEntry.id.asc(), JournalLine.line_number.asc())
        ).all()
        for row in counterpart_rows:
            counterpart_by_journal[row.journal_entry_id].append(row)

    aggregated_amounts: dict[str, Decimal] = defaultdict(lambda: ZERO)
    transaction_counts: dict[str, int] = defaultdict(int)
    effect_of_exchange_rate_changes = ZERO
    for movement in cash_movements:
        amount = Decimal(movement.cash_movement or ZERO)
        if amount == ZERO:
            continue
        allocations = _cash_flow_allocations(
            counterpart_by_journal[movement.journal_entry_id],
            cash_movement=amount,
        )
        for activity_type, line_code, allocated_amount in allocations:
            if activity_type == "exchange":
                effect_of_exchange_rate_changes += allocated_amount
                continue
            aggregated_amounts[line_code] += allocated_amount
            transaction_counts[line_code] += 1

    lines_by_activity: dict[str, list[CashFlowLine]] = {
        "operating": [],
        "investing": [],
        "financing": [],
    }
    for line_code in CASH_FLOW_LINE_ORDER:
        amount = aggregated_amounts[line_code]
        if amount == ZERO:
            continue
        activity_type, label = CASH_FLOW_LINE_DEFINITIONS[line_code]
        lines_by_activity[activity_type].append(
            CashFlowLine(
                line_code=line_code,
                label=label,
                activity_type=activity_type,
                amount=amount,
                transaction_count=transaction_counts[line_code],
            )
        )

    opening_cash = sum((line.opening_balance for line in all_cash_account_lines), ZERO)
    closing_cash = sum((line.closing_balance for line in all_cash_account_lines), ZERO)
    total_operating = sum(
        (line.amount for line in lines_by_activity["operating"]),
        ZERO,
    )
    total_investing = sum(
        (line.amount for line in lines_by_activity["investing"]),
        ZERO,
    )
    total_financing = sum(
        (line.amount for line in lines_by_activity["financing"]),
        ZERO,
    )
    net_cash_change = total_operating + total_investing + total_financing
    calculated_closing_cash = (
        opening_cash + net_cash_change + effect_of_exchange_rate_changes
    )
    return CashFlowReportRead(
        start_date=start_date,
        end_date=end_date,
        method="direct",
        classification_policy=CASH_FLOW_POLICY,
        cash_accounts=cash_account_lines,
        operating_lines=lines_by_activity["operating"],
        investing_lines=lines_by_activity["investing"],
        financing_lines=lines_by_activity["financing"],
        opening_cash=opening_cash,
        total_operating=total_operating,
        total_investing=total_investing,
        total_financing=total_financing,
        net_cash_change=net_cash_change,
        effect_of_exchange_rate_changes=effect_of_exchange_rate_changes,
        calculated_closing_cash=calculated_closing_cash,
        closing_cash=closing_cash,
        reconciliation_difference=closing_cash - calculated_closing_cash,
    )


def _equity_movement_type(
    account: Account,
    reporting_category_code: str | None,
) -> str:
    normalized_name = account.name.casefold()
    if reporting_category_code in {"BS_EQ_SHARE_CAPITAL", "BS_EQ_CONTRIBUTIONS"} or any(
        keyword in normalized_name
        for keyword in ("share capital", "owner capital", "capital contribution", "paid-in capital")
    ):
        return "contribution"
    if reporting_category_code in {
        "BS_EQ_DIVIDENDS_DISTRIBUTIONS",
        "BS_EQ_TREASURY_SHARES",
    } or any(
        keyword in normalized_name
        for keyword in ("drawing", "dividend", "distribution", "treasury share")
    ):
        return "distribution"
    return "other"


def build_statement_of_changes_in_equity_report(
    db: Session,
    *,
    company_id: UUID,
    start_date: date,
    end_date: date,
    include_draft: bool = False,
) -> StatementOfChangesInEquityRead:
    opening_balance_sheet = build_balance_sheet_report(
        db,
        company_id=company_id,
        as_of_date=start_date - timedelta(days=1),
        include_draft=include_draft,
    )
    closing_balance_sheet = build_balance_sheet_report(
        db,
        company_id=company_id,
        as_of_date=end_date,
        include_draft=include_draft,
    )
    opening_equity_lines = [
        *opening_balance_sheet.equity_lines,
        opening_balance_sheet.current_earnings,
    ]
    equity_aggregates = _aggregate_accounts(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        account_types={AccountType.EQUITY},
        include_draft=include_draft,
        exclude_period_rollovers=True,
    )
    accounts_by_id = {
        account.id: (account, reporting_category_code)
        for account, reporting_category_code in db.execute(
            select(Account, ReportingCategory.code)
            .outerjoin(ReportingCategory, ReportingCategory.id == Account.reporting_category_id)
            .where(Account.id.in_({aggregate.account_id for aggregate in equity_aggregates}))
        ).all()
    }
    movement_lines: list[EquityMovementLine] = []
    for aggregate in equity_aggregates:
        account, reporting_category_code = accounts_by_id[aggregate.account_id]
        movement_lines.append(
            EquityMovementLine(
                account_id=aggregate.account_id,
                account_code=aggregate.account_code,
                account_name=aggregate.account_name,
                movement_type=_equity_movement_type(account, reporting_category_code),
                amount=_display_amount(aggregate.account_type, aggregate.raw_balance),
            )
        )

    profit_or_loss = build_profit_and_loss_report(
        db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        include_draft=include_draft,
    ).net_profit
    opening_equity = opening_balance_sheet.total_equity
    closing_equity = closing_balance_sheet.total_equity
    total_contributions = sum(
        (line.amount for line in movement_lines if line.movement_type == "contribution"),
        ZERO,
    )
    total_distributions = sum(
        (line.amount for line in movement_lines if line.movement_type == "distribution"),
        ZERO,
    )
    total_other_movements = sum(
        (line.amount for line in movement_lines if line.movement_type == "other"),
        ZERO,
    )
    total_changes = (
        profit_or_loss
        + total_contributions
        + total_distributions
        + total_other_movements
    )
    calculated_closing_equity = opening_equity + total_changes
    return StatementOfChangesInEquityRead(
        start_date=start_date,
        end_date=end_date,
        opening_equity_lines=opening_equity_lines,
        movement_lines=movement_lines,
        opening_equity=opening_equity,
        profit_or_loss=profit_or_loss,
        total_contributions=total_contributions,
        total_distributions=total_distributions,
        total_other_movements=total_other_movements,
        total_changes=total_changes,
        calculated_closing_equity=calculated_closing_equity,
        closing_equity=closing_equity,
        reconciliation_difference=closing_equity - calculated_closing_equity,
    )


def _opening_balance(
    db: Session,
    *,
    company_id: UUID,
    account_id: UUID,
    account_type: AccountType,
    start_date: date,
    include_draft: bool = False,
) -> Decimal:
    previous_day = start_date - timedelta(days=1)
    query = (
        select(
            func.coalesce(func.sum(JournalLine.debit_amount), 0).label("debit_total"),
            func.coalesce(func.sum(JournalLine.credit_amount), 0).label("credit_total"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(JournalLine.account_id == account_id)
        .where(JournalEntry.company_id == company_id)
        .where(JournalEntry.status.in_(_visible_statuses(include_draft=include_draft)))
        .where(JournalEntry.entry_date <= previous_day)
    )
    row = db.execute(query).one()
    raw_balance = Decimal(row.debit_total or ZERO) - Decimal(row.credit_total or ZERO)
    return _display_amount(account_type, raw_balance)


def build_general_ledger_report(
    db: Session,
    *,
    company_id: UUID,
    start_date: date,
    end_date: date,
    account_id: UUID | None = None,
    include_draft: bool = False,
) -> GeneralLedgerReportRead:
    query = (
        select(
            Account.id,
            Account.account_code,
            Account.name,
            Account.account_type,
            JournalEntry.id.label("journal_entry_id"),
            JournalEntry.entry_number,
            JournalEntry.status.label("journal_status"),
            JournalEntry.entry_date,
            JournalEntry.description.label("journal_description"),
            JournalEntry.reference,
            JournalLine.line_number,
            JournalLine.description.label("line_description"),
            JournalLine.debit_amount,
            JournalLine.credit_amount,
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(Account.company_id == company_id)
        .where(JournalEntry.status.in_(_visible_statuses(include_draft=include_draft)))
        .where(JournalEntry.entry_date >= start_date)
        .where(JournalEntry.entry_date <= end_date)
    )
    if account_id is not None:
        query = query.where(Account.id == account_id)
    query = query.order_by(
        Account.account_code.asc(),
        JournalEntry.entry_date.asc(),
        JournalEntry.entry_number.asc(),
        JournalLine.line_number.asc(),
    )
    rows = db.execute(query).all()

    grouped_entries: dict[UUID, list[GeneralLedgerEntryRead]] = defaultdict(list)
    meta_by_account: dict[UUID, tuple[str, str, AccountType]] = {}
    running_by_account: dict[UUID, Decimal] = {}
    for row in rows:
        account_uuid = row.id
        account_type = row.account_type
        if account_uuid not in running_by_account:
            running_by_account[account_uuid] = _opening_balance(
                db,
                company_id=company_id,
                account_id=account_uuid,
                account_type=account_type,
                start_date=start_date,
                include_draft=include_draft,
            )
            meta_by_account[account_uuid] = (row.account_code, row.name, account_type)
        line_raw_balance = Decimal(row.debit_amount or ZERO) - Decimal(row.credit_amount or ZERO)
        running_by_account[account_uuid] += _display_amount(account_type, line_raw_balance)
        grouped_entries[account_uuid].append(
            GeneralLedgerEntryRead(
                journal_entry_id=row.journal_entry_id,
                entry_number=row.entry_number,
                journal_status=row.journal_status.value
                if hasattr(row.journal_status, "value")
                else str(row.journal_status),
                entry_date=row.entry_date,
                line_number=row.line_number,
                journal_description=row.journal_description,
                line_description=row.line_description,
                reference=row.reference,
                debit_amount=Decimal(row.debit_amount or ZERO),
                credit_amount=Decimal(row.credit_amount or ZERO),
                running_balance=running_by_account[account_uuid],
            )
        )

    accounts: list[GeneralLedgerAccountRead] = []
    for account_uuid, entries in grouped_entries.items():
        account_code, account_name, account_type = meta_by_account[account_uuid]
        opening_balance = _opening_balance(
            db,
            company_id=company_id,
            account_id=account_uuid,
            account_type=account_type,
            start_date=start_date,
            include_draft=include_draft,
        )
        closing_balance = entries[-1].running_balance if entries else opening_balance
        accounts.append(
            GeneralLedgerAccountRead(
                account_id=account_uuid,
                account_code=account_code,
                account_name=account_name,
                account_type=account_type.value,
                opening_balance=opening_balance,
                closing_balance=closing_balance,
                entries=entries,
            )
        )
    accounts.sort(key=lambda item: item.account_code)
    return GeneralLedgerReportRead(start_date=start_date, end_date=end_date, accounts=accounts)


def build_trial_balance_csv(report: TrialBalanceReportRead) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Account Code", "Account Name", "Debit Total", "Credit Total", "Balance"])
    for row in report.rows:
        writer.writerow(
            [
                row.account_code,
                row.account_name,
                f"{row.debit_total:.2f}",
                f"{row.credit_total:.2f}",
                f"{row.balance:.2f}",
            ]
        )
    return output.getvalue().encode("utf-8")


def build_profit_and_loss_csv(report: ProfitAndLossReportRead) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Section", "Account Code", "Account Name", "Amount"])
    for line in report.income_lines:
        writer.writerow(["income", line.account_code, line.account_name, f"{line.amount:.2f}"])
    for line in report.expense_lines:
        writer.writerow(["expense", line.account_code, line.account_name, f"{line.amount:.2f}"])
    writer.writerow([])
    writer.writerow(["Total Income", "", "", f"{report.total_income:.2f}"])
    writer.writerow(["Total Expenses", "", "", f"{report.total_expenses:.2f}"])
    writer.writerow(["Net Profit", "", "", f"{report.net_profit:.2f}"])
    return output.getvalue().encode("utf-8")


def build_balance_sheet_csv(report: BalanceSheetReportRead) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Section", "Account Code", "Account Name", "Amount"])
    for line in report.asset_lines:
        writer.writerow(["asset", line.account_code, line.account_name, f"{line.amount:.2f}"])
    for line in report.liability_lines:
        writer.writerow(["liability", line.account_code, line.account_name, f"{line.amount:.2f}"])
    for line in report.equity_lines:
        writer.writerow(["equity", line.account_code, line.account_name, f"{line.amount:.2f}"])
    writer.writerow(
        [
            "equity",
            report.current_earnings.account_code,
            report.current_earnings.account_name,
            f"{report.current_earnings.amount:.2f}",
        ]
    )
    writer.writerow([])
    writer.writerow(["Total Assets", "", "", f"{report.total_assets:.2f}"])
    writer.writerow(["Total Liabilities", "", "", f"{report.total_liabilities:.2f}"])
    writer.writerow(["Total Equity", "", "", f"{report.total_equity:.2f}"])
    writer.writerow(
        ["Total Liabilities and Equity", "", "", f"{report.total_liabilities_and_equity:.2f}"]
    )
    return output.getvalue().encode("utf-8")


def build_cash_flow_csv(report: CashFlowReportRead) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Statement of Cash Flows"])
    writer.writerow(["Period", report.start_date.isoformat(), report.end_date.isoformat()])
    writer.writerow(["Method", report.method.title()])
    writer.writerow(["Classification Policy", report.classification_policy])
    writer.writerow([])
    writer.writerow(["Section", "Cash Flow", "Source Transactions", "Amount"])
    for section, lines, total_label, total in (
        (
            "Operating activities",
            report.operating_lines,
            "Net cash from operating activities",
            report.total_operating,
        ),
        (
            "Investing activities",
            report.investing_lines,
            "Net cash from investing activities",
            report.total_investing,
        ),
        (
            "Financing activities",
            report.financing_lines,
            "Net cash from financing activities",
            report.total_financing,
        ),
    ):
        if lines:
            for line in lines:
                writer.writerow(
                    [
                        section,
                        line.label,
                        line.transaction_count,
                        f"{line.amount:.2f}",
                    ]
                )
        else:
            writer.writerow(
                [
                    section,
                    "No cash flows",
                    0,
                    "0.00",
                ]
            )
        writer.writerow([section, total_label, "", f"{total:.2f}"])
    writer.writerow([])
    writer.writerow(["Cash reconciliation", "Net change in cash and cash equivalents", "", f"{report.net_cash_change:.2f}"])
    writer.writerow(
        [
            "Cash reconciliation",
            "Effect of exchange rate changes",
            "",
            f"{report.effect_of_exchange_rate_changes:.2f}",
        ]
    )
    writer.writerow(
        [
            "Cash reconciliation",
            "Cash and cash equivalents at beginning of period",
            "",
            f"{report.opening_cash:.2f}",
        ]
    )
    writer.writerow(
        [
            "Cash reconciliation",
            "Cash and cash equivalents at end of period",
            "",
            f"{report.closing_cash:.2f}",
        ]
    )
    writer.writerow(
        [
            "Cash reconciliation",
            "Reconciliation difference",
            "",
            f"{report.reconciliation_difference:.2f}",
        ]
    )
    writer.writerow([])
    writer.writerow(["Cash and cash equivalents", "Account", "Opening balance", "Closing balance"])
    for account in report.cash_accounts:
        writer.writerow(
            [
                account.account_code,
                account.account_name,
                f"{account.opening_balance:.2f}",
                f"{account.closing_balance:.2f}",
            ]
        )
    return output.getvalue().encode("utf-8")


def build_statement_of_changes_in_equity_csv(
    report: StatementOfChangesInEquityRead,
) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Movement Type", "Account Code", "Account Name", "Amount"])
    writer.writerow(["opening", "", "Opening equity", f"{report.opening_equity:.2f}"])
    writer.writerow(["profit_or_loss", "", "Profit or loss", f"{report.profit_or_loss:.2f}"])
    for line in report.movement_lines:
        writer.writerow(
            [
                line.movement_type,
                line.account_code,
                line.account_name,
                f"{line.amount:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["Total Changes", "", "", f"{report.total_changes:.2f}"])
    writer.writerow(["Closing Equity", "", "", f"{report.closing_equity:.2f}"])
    writer.writerow(
        ["Reconciliation Difference", "", "", f"{report.reconciliation_difference:.2f}"]
    )
    return output.getvalue().encode("utf-8")


def build_general_ledger_csv(report: GeneralLedgerReportRead) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Account Code",
            "Account Name",
            "Entry Number",
            "Status",
            "Entry Date",
            "Line Number",
            "Journal Description",
            "Line Description",
            "Reference",
            "Debit",
            "Credit",
            "Running Balance",
        ]
    )
    for account in report.accounts:
        for entry in account.entries:
            writer.writerow(
                [
                    account.account_code,
                    account.account_name,
                    entry.entry_number,
                    entry.journal_status,
                    entry.entry_date.isoformat(),
                    entry.line_number,
                    entry.journal_description,
                    entry.line_description or "",
                    entry.reference or "",
                    f"{entry.debit_amount:.2f}",
                    f"{entry.credit_amount:.2f}",
                    f"{entry.running_balance:.2f}",
                ]
            )
    return output.getvalue().encode("utf-8")
