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
from app.schemas.common import (
    BalanceSheetReportRead,
    FinancialReportLine,
    GeneralLedgerAccountRead,
    GeneralLedgerEntryRead,
    GeneralLedgerReportRead,
    ProfitAndLossReportRead,
    TrialBalanceReportRead,
    TrialBalanceRow,
)

ZERO = Decimal("0.00")
POSTED_REPORT_STATUSES = (JournalStatus.POSTED,)
DRAFT_VISIBLE_REPORT_STATUSES = (JournalStatus.POSTED, JournalStatus.DRAFT)


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
