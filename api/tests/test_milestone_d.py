from datetime import UTC, datetime
from uuid import UUID

from conftest import TestingSessionLocal, upsert_test_account
from sqlalchemy import select

from app.db.models.accounting import AccountingPeriod, PeriodLock
from app.db.models.auth import User
from app.db.models.enums import WorkflowStatus


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def bootstrap_superuser(client):
    response = client.post(
        "/api/auth/bootstrap",
        json={
            "email": "admin@example.com",
            "full_name": "Initial Admin",
            "password": "StrongPass123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_company(client, token: str) -> str:
    response = client.post(
        "/api/companies",
        headers=auth_header(token),
        json={
            "legal_name": "Example Pty Ltd",
            "entity_type": "company",
            "initial_configuration": {
                "effective_from": "2026-07-01",
                "gst_registered": True,
                "bas_frequency": "quarterly",
                "bas_reporting_basis": "accrual",
                "financial_year_start_month": 7,
                "financial_year_start_day": 1,
                "allow_self_approval": True,
                "self_approval_mode": "warn",
                "period_lock_policy": "after_approval",
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_period(client, token: str, company_id: str) -> str:
    response = client.post(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
        json={
            "name": "FY26-Q1",
            "period_type": "quarter",
            "start_date": "2026-07-01",
            "end_date": "2026-09-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_account(
    client, token: str, company_id: str, code: str, name: str, account_type: str
) -> str:
    return upsert_test_account(
        client,
        token,
        company_id,
        account_code=code,
        name=name,
        account_type=account_type,
    )


def create_posted_journal(
    client,
    token: str,
    company_id: str,
    period_id: str,
    *,
    entry_date: str,
    description: str,
    lines: list[dict],
) -> str:
    response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": entry_date,
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": description,
            "lines": lines,
        },
    )
    assert response.status_code == 201, response.text
    journal_id = response.json()["id"]
    post_response = client.post(
        f"/api/companies/{company_id}/journals/{journal_id}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text
    return journal_id


def create_draft_journal(
    client,
    token: str,
    company_id: str,
    period_id: str,
    *,
    entry_date: str,
    description: str,
    lines: list[dict],
) -> str:
    response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": entry_date,
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": description,
            "lines": lines,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def seed_reporting_ledger(client, token: str, company_id: str, period_id: str) -> dict[str, str]:
    account_ids = {
        "cash": create_account(client, token, company_id, "1000", "Cash", "asset"),
        "ap": create_account(client, token, company_id, "2000", "Accounts Payable", "liability"),
        "equity": create_account(client, token, company_id, "3000", "Owner Capital", "equity"),
        "revenue": create_account(client, token, company_id, "4000", "Sales Revenue", "income"),
        "expense": create_account(client, token, company_id, "5000", "Rent Expense", "expense"),
    }

    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-01",
        description="Capital injection",
        lines=[
            {"account_id": account_ids["cash"], "debit_amount": "1000.00", "credit_amount": "0.00"},
            {
                "account_id": account_ids["equity"],
                "debit_amount": "0.00",
                "credit_amount": "1000.00",
            },
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-10",
        description="Cash sale",
        lines=[
            {"account_id": account_ids["cash"], "debit_amount": "100.00", "credit_amount": "0.00"},
            {
                "account_id": account_ids["revenue"],
                "debit_amount": "0.00",
                "credit_amount": "100.00",
            },
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-15",
        description="Expense on account",
        lines=[
            {
                "account_id": account_ids["expense"],
                "debit_amount": "30.00",
                "credit_amount": "0.00",
            },
            {"account_id": account_ids["ap"], "debit_amount": "0.00", "credit_amount": "30.00"},
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-08-01",
        description="August sale",
        lines=[
            {"account_id": account_ids["cash"], "debit_amount": "50.00", "credit_amount": "0.00"},
            {
                "account_id": account_ids["revenue"],
                "debit_amount": "0.00",
                "credit_amount": "50.00",
            },
        ],
    )
    return account_ids


def test_trial_balance_and_profit_and_loss_reports_with_exports(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    seed_reporting_ledger(client, token, company_id, period_id)

    trial_balance_response = client.get(
        f"/api/companies/{company_id}/reports/trial-balance",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
    )
    assert trial_balance_response.status_code == 200, trial_balance_response.text
    trial_balance_rows = {row["account_code"]: row for row in trial_balance_response.json()["rows"]}
    assert trial_balance_rows["1000"]["balance"] == "1100.00"
    assert trial_balance_rows["2000"]["balance"] == "-30.00"
    assert trial_balance_rows["3000"]["balance"] == "-1000.00"
    assert trial_balance_rows["4000"]["balance"] == "-100.00"
    assert trial_balance_rows["5000"]["balance"] == "30.00"

    pnl_response = client.get(
        f"/api/companies/{company_id}/reports/profit-and-loss",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
    )
    assert pnl_response.status_code == 200, pnl_response.text
    pnl_payload = pnl_response.json()
    assert pnl_payload["total_income"] == "100.00"
    assert pnl_payload["total_expenses"] == "30.00"
    assert pnl_payload["net_profit"] == "70.00"
    assert [line["account_code"] for line in pnl_payload["income_lines"]] == ["4000"]
    assert [line["account_code"] for line in pnl_payload["expense_lines"]] == ["5000"]

    trial_balance_export = client.get(
        f"/api/companies/{company_id}/reports/trial-balance/export",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
    )
    assert trial_balance_export.status_code == 200, trial_balance_export.text
    assert trial_balance_export.headers["content-type"].startswith("text/csv")
    assert (
        b"Account Code,Account Name,Debit Total,Credit Total,Balance"
        in trial_balance_export.content
    )

    pnl_export = client.get(
        f"/api/companies/{company_id}/reports/profit-and-loss/export",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
    )
    assert pnl_export.status_code == 200, pnl_export.text
    assert b"Total Income" in pnl_export.content
    assert b"Net Profit" in pnl_export.content


def test_cash_flow_changes_in_equity_and_archive_pdf_exports(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    account_ids = seed_reporting_ledger(client, token, company_id, period_id)
    reporting_categories = client.get(
        f"/api/companies/{company_id}/reporting-categories",
        headers=auth_header(token),
    ).json()
    ppe_category_id = next(
        category["id"]
        for category in reporting_categories
        if category["code"] == "BS_NCA_PPE"
    )
    equipment_response = client.post(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
        json={
            "account_code": "E2E-PPE-1500",
            "name": "E2E Plant and Equipment",
            "account_type": "asset",
            "reporting_category_id": ppe_category_id,
            "default_tax_code_id": None,
            "is_active": True,
            "allow_manual_posting": True,
        },
    )
    assert equipment_response.status_code == 201, equipment_response.text
    equipment_account_id = equipment_response.json()["id"]
    settlement_clearing_account_id = create_account(
        client,
        token,
        company_id,
        "E2E-CLR-2760",
        "Property Settlement Clearing",
        "asset",
    )
    borrowing_account_id = create_account(
        client,
        token,
        company_id,
        "E2E-LOAN-2500",
        "Bank Loan Payable",
        "liability",
    )
    interest_expense_account_id = create_account(
        client,
        token,
        company_id,
        "E2E-INT-7410",
        "Interest Expense",
        "expense",
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-16",
        description="Payment to supplier",
        lines=[
            {
                "account_id": account_ids["ap"],
                "debit_amount": "30.00",
                "credit_amount": "0.00",
            },
            {
                "account_id": account_ids["cash"],
                "debit_amount": "0.00",
                "credit_amount": "30.00",
            },
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-22",
        description="Loan proceeds received",
        lines=[
            {
                "account_id": account_ids["cash"],
                "debit_amount": "500.00",
                "credit_amount": "0.00",
            },
            {
                "account_id": borrowing_account_id,
                "debit_amount": "0.00",
                "credit_amount": "500.00",
            },
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-23",
        description="Loan principal and interest payment",
        lines=[
            {
                "account_id": borrowing_account_id,
                "debit_amount": "100.00",
                "credit_amount": "0.00",
            },
            {
                "account_id": interest_expense_account_id,
                "debit_amount": "10.00",
                "credit_amount": "0.00",
            },
            {
                "account_id": account_ids["cash"],
                "debit_amount": "0.00",
                "credit_amount": "110.00",
            },
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-21",
        description="Property settlement funds paid to conveyancer",
        lines=[
            {
                "account_id": settlement_clearing_account_id,
                "debit_amount": "50.00",
                "credit_amount": "0.00",
            },
            {
                "account_id": account_ids["cash"],
                "debit_amount": "0.00",
                "credit_amount": "50.00",
            },
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-20",
        description="Equipment purchase",
        lines=[
            {
                "account_id": equipment_account_id,
                "debit_amount": "200.00",
                "credit_amount": "0.00",
            },
            {
                "account_id": account_ids["cash"],
                "debit_amount": "0.00",
                "credit_amount": "200.00",
            },
        ],
    )

    date_params = {"start_date": "2026-07-01", "end_date": "2026-07-31"}
    cash_flow_response = client.get(
        f"/api/companies/{company_id}/reports/cash-flow",
        headers=auth_header(token),
        params=date_params,
    )
    assert cash_flow_response.status_code == 200, cash_flow_response.text
    cash_flow = cash_flow_response.json()
    assert cash_flow["method"] == "direct"
    assert (
        "major classes of gross cash receipts and payments"
        in cash_flow["classification_policy"].lower()
    )
    assert cash_flow["opening_cash"] == "0.00"
    assert cash_flow["total_operating"] == "70.00"
    assert cash_flow["total_investing"] == "-250.00"
    assert cash_flow["total_financing"] == "1390.00"
    assert cash_flow["net_cash_change"] == "1210.00"
    assert cash_flow["effect_of_exchange_rate_changes"] == "0.00"
    assert cash_flow["calculated_closing_cash"] == "1210.00"
    assert cash_flow["closing_cash"] == "1210.00"
    assert cash_flow["reconciliation_difference"] == "0.00"
    assert [
        (line["line_code"], line["amount"], line["transaction_count"])
        for line in cash_flow["operating_lines"]
    ] == [
        ("receipts_from_customers", "100.00", 1),
        ("payments_to_suppliers", "-30.00", 1),
    ]
    assert cash_flow["investing_lines"][0]["line_code"] == "purchases_of_non_current_assets"
    assert cash_flow["investing_lines"][0]["amount"] == "-250.00"
    assert cash_flow["investing_lines"][0]["transaction_count"] == 2
    assert [
        (line["line_code"], line["amount"], line["transaction_count"])
        for line in cash_flow["financing_lines"]
    ] == [
        ("proceeds_from_share_capital", "1000.00", 1),
        ("proceeds_from_borrowings", "500.00", 1),
        ("repayment_of_borrowings", "-100.00", 1),
        ("interest_paid", "-10.00", 1),
    ]

    changes_response = client.get(
        f"/api/companies/{company_id}/reports/statement-of-changes-in-equity",
        headers=auth_header(token),
        params=date_params,
    )
    assert changes_response.status_code == 200, changes_response.text
    changes = changes_response.json()
    assert changes["opening_equity"] == "0.00"
    assert changes["profit_or_loss"] == "60.00"
    assert changes["total_contributions"] == "1000.00"
    assert changes["total_distributions"] == "0.00"
    assert changes["total_changes"] == "1060.00"
    assert changes["calculated_closing_equity"] == "1060.00"
    assert changes["closing_equity"] == "1060.00"
    assert changes["reconciliation_difference"] == "0.00"
    assert changes["movement_lines"][0]["movement_type"] == "contribution"

    cash_flow_csv = client.get(
        f"/api/companies/{company_id}/reports/cash-flow/export",
        headers=auth_header(token),
        params=date_params,
    )
    assert cash_flow_csv.status_code == 200, cash_flow_csv.text
    assert b"Cash receipts from customers" in cash_flow_csv.content
    assert b"Cash paid to suppliers" in cash_flow_csv.content
    assert b"Net cash from operating activities" in cash_flow_csv.content
    assert b"Cash and cash equivalents at end of period" in cash_flow_csv.content
    equity_csv = client.get(
        f"/api/companies/{company_id}/reports/statement-of-changes-in-equity/export",
        headers=auth_header(token),
        params=date_params,
    )
    assert equity_csv.status_code == 200, equity_csv.text
    assert b"Profit or loss" in equity_csv.content
    assert b"Closing Equity" in equity_csv.content

    pdf_exports = [
        ("trial-balance", date_params),
        ("profit-and-loss", date_params),
        ("balance-sheet", {"as_of_date": "2026-07-31"}),
        ("cash-flow", date_params),
        ("statement-of-changes-in-equity", date_params),
        ("general-ledger", date_params),
    ]
    for report_path, params in pdf_exports:
        pdf_response = client.get(
            f"/api/companies/{company_id}/reports/{report_path}/export/pdf",
            headers=auth_header(token),
            params=params,
        )
        assert pdf_response.status_code == 200, pdf_response.text
        assert pdf_response.headers["content-type"] == "application/pdf"
        assert pdf_response.headers["cache-control"] == "private, no-store"
        assert pdf_response.headers["content-disposition"].endswith(f'{report_path}.pdf"')
        assert pdf_response.content.startswith(b"%PDF-")
        assert len(pdf_response.content) > 2000


def test_balance_sheet_report_balances_with_current_earnings_and_export(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    seed_reporting_ledger(client, token, company_id, period_id)

    balance_sheet_response = client.get(
        f"/api/companies/{company_id}/reports/balance-sheet",
        headers=auth_header(token),
        params={"as_of_date": "2026-07-31"},
    )
    assert balance_sheet_response.status_code == 200, balance_sheet_response.text
    payload = balance_sheet_response.json()
    assert payload["total_assets"] == "1100.00"
    assert payload["total_liabilities"] == "30.00"
    assert payload["current_earnings"]["amount"] == "70.00"
    assert payload["total_equity"] == "1070.00"
    assert payload["total_liabilities_and_equity"] == "1100.00"
    assert payload["total_assets"] == payload["total_liabilities_and_equity"]

    equity_codes = [line["account_code"] for line in payload["equity_lines"]]
    assert equity_codes == ["3000"]

    balance_sheet_export = client.get(
        f"/api/companies/{company_id}/reports/balance-sheet/export",
        headers=auth_header(token),
        params={"as_of_date": "2026-07-31"},
    )
    assert balance_sheet_export.status_code == 200, balance_sheet_export.text
    assert b"Current Earnings" in balance_sheet_export.content
    assert b"Total Liabilities and Equity" in balance_sheet_export.content


def test_balance_sheet_current_earnings_uses_the_configured_financial_year_start(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    seed_reporting_ledger(client, token, company_id, period_id)

    balance_sheet_response = client.get(
        f"/api/companies/{company_id}/reports/balance-sheet",
        headers=auth_header(token),
        params={"as_of_date": "2027-02-28"},
    )
    assert balance_sheet_response.status_code == 200, balance_sheet_response.text
    balance_sheet = balance_sheet_response.json()
    assert balance_sheet["current_earnings"]["amount"] == "120.00"
    assert balance_sheet["total_assets"] == "1150.00"
    assert balance_sheet["total_liabilities_and_equity"] == "1150.00"


def test_period_lock_rejects_draft_journals_until_they_are_posted(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_id = create_draft_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-15",
        description="Unreviewed revenue",
        lines=[
            {
                "account_id": cash_account_id,
                "debit_amount": "100.00",
                "credit_amount": "0.00",
            },
            {
                "account_id": revenue_account_id,
                "debit_amount": "0.00",
                "credit_amount": "100.00",
            },
        ],
    )

    blocked_lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Attempted close with drafts"},
    )
    assert blocked_lock_response.status_code == 400, blocked_lock_response.text
    assert "1 draft journal remains" in blocked_lock_response.json()["detail"]
    periods = client.get(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
    ).json()
    assert next(period for period in periods if period["id"] == period_id)["status"] == "draft"

    post_response = client.post(
        f"/api/companies/{company_id}/journals/{journal_id}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text
    lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Draft reviewed and posted"},
    )
    assert lock_response.status_code == 200, lock_response.text
    rollover = next(
        journal
        for journal in client.get(
            f"/api/companies/{company_id}/journals",
            headers=auth_header(token),
        ).json()
        if journal["reference"] == f"PERIOD-ROLLOVER:{period_id}"
    )
    assert rollover["status"] == "posted"


def test_bulk_post_journals_preserves_order_and_is_atomic(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_ids = [
        create_draft_journal(
            client,
            token,
            company_id,
            period_id,
            entry_date=f"2026-07-{day:02d}",
            description=f"Bulk post draft {day}",
            lines=[
                {
                    "account_id": cash_account_id,
                    "debit_amount": f"{amount}.00",
                    "credit_amount": "0.00",
                },
                {
                    "account_id": revenue_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": f"{amount}.00",
                },
            ],
        )
        for day, amount in ((10, 100), (11, 200), (12, 300))
    ]

    bulk_response = client.post(
        f"/api/companies/{company_id}/journals/bulk-post",
        headers=auth_header(token),
        json={"journal_ids": [journal_ids[1], journal_ids[0]]},
    )
    assert bulk_response.status_code == 200, bulk_response.text
    posted = bulk_response.json()
    assert [journal["id"] for journal in posted] == [journal_ids[1], journal_ids[0]]
    assert [journal["status"] for journal in posted] == ["posted", "posted"]
    assert posted[0]["posted_at"] == posted[1]["posted_at"]

    atomic_failure = client.post(
        f"/api/companies/{company_id}/journals/bulk-post",
        headers=auth_header(token),
        json={"journal_ids": [journal_ids[2], journal_ids[0]]},
    )
    assert atomic_failure.status_code == 400, atomic_failure.text
    assert "Only draft journals can be posted" in atomic_failure.json()["detail"]
    journals = client.get(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
    ).json()
    journal_by_id = {journal["id"]: journal for journal in journals}
    assert journal_by_id[journal_ids[2]]["status"] == "draft"

    duplicate_response = client.post(
        f"/api/companies/{company_id}/journals/bulk-post",
        headers=auth_header(token),
        json={"journal_ids": [journal_ids[2], journal_ids[2]]},
    )
    assert duplicate_response.status_code == 400, duplicate_response.text
    assert duplicate_response.json()["detail"] == "Each journal can only be selected once"


def test_period_lock_rolls_profit_and_loss_into_retained_earnings_and_unlock_voids_it(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    seed_reporting_ledger(client, token, company_id, period_id)

    lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Quarter finalized"},
    )
    assert lock_response.status_code == 200, lock_response.text
    assert lock_response.json()["status"] == "locked"

    accounts_response = client.get(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
    )
    assert accounts_response.status_code == 200, accounts_response.text
    retained_earnings = next(
        item for item in accounts_response.json() if item["name"] == "Retained Earnings"
    )
    assert retained_earnings["account_code"] == "3110"
    assert retained_earnings["account_type"] == "equity"
    assert retained_earnings["allow_manual_posting"] is False

    journals_response = client.get(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
    )
    assert journals_response.status_code == 200, journals_response.text
    rollover = next(
        item
        for item in journals_response.json()
        if item["reference"] == f"PERIOD-ROLLOVER:{period_id}"
    )
    assert rollover["status"] == "posted"
    assert rollover["source_type"] == "system"
    assert rollover["entry_date"] == "2026-09-30"
    rollover_lines = {
        next(
            account["account_code"]
            for account in accounts_response.json()
            if account["id"] == line["account_id"]
        ): line
        for line in rollover["lines"]
    }
    assert rollover_lines["4000"]["debit_amount"] == "150.00"
    assert rollover_lines["5000"]["credit_amount"] == "30.00"
    assert rollover_lines["3110"]["credit_amount"] == "120.00"

    profit_and_loss_response = client.get(
        f"/api/companies/{company_id}/reports/profit-and-loss",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert profit_and_loss_response.status_code == 200, profit_and_loss_response.text
    assert profit_and_loss_response.json()["net_profit"] == "120.00"

    trial_balance_response = client.get(
        f"/api/companies/{company_id}/reports/trial-balance",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert trial_balance_response.status_code == 200, trial_balance_response.text
    trial_balance = {
        item["account_code"]: item["balance"] for item in trial_balance_response.json()["rows"]
    }
    assert trial_balance["4000"] == "0.00"
    assert trial_balance["5000"] == "0.00"
    assert trial_balance["3110"] == "-120.00"

    balance_sheet_response = client.get(
        f"/api/companies/{company_id}/reports/balance-sheet",
        headers=auth_header(token),
        params={"as_of_date": "2026-09-30"},
    )
    assert balance_sheet_response.status_code == 200, balance_sheet_response.text
    balance_sheet = balance_sheet_response.json()
    assert balance_sheet["current_earnings"]["amount"] == "0.00"
    assert balance_sheet["total_assets"] == "1150.00"
    assert balance_sheet["total_liabilities_and_equity"] == "1150.00"

    changes_response = client.get(
        f"/api/companies/{company_id}/reports/statement-of-changes-in-equity",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert changes_response.status_code == 200, changes_response.text
    changes = changes_response.json()
    assert changes["opening_equity"] == "0.00"
    assert changes["profit_or_loss"] == "120.00"
    assert changes["total_contributions"] == "1000.00"
    assert changes["closing_equity"] == "1120.00"
    assert changes["reconciliation_difference"] == "0.00"

    duplicate_lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Duplicate lock"},
    )
    assert duplicate_lock_response.status_code == 200, duplicate_lock_response.text
    rollover_versions_while_locked = [
        item
        for item in client.get(
            f"/api/companies/{company_id}/journals",
            headers=auth_header(token),
        ).json()
        if item["reference"] == f"PERIOD-ROLLOVER:{period_id}"
    ]
    assert [item["id"] for item in rollover_versions_while_locked] == [rollover["id"]]

    unlock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/unlock",
        headers=auth_header(token),
        json={"reason": "Correction required"},
    )
    assert unlock_response.status_code == 200, unlock_response.text
    assert unlock_response.json()["status"] == "approved"

    journals_after_unlock = client.get(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
    )
    rollover_after_unlock = next(
        item for item in journals_after_unlock.json() if item["id"] == rollover["id"]
    )
    assert rollover_after_unlock["status"] == "voided"

    reopened_balance_sheet_response = client.get(
        f"/api/companies/{company_id}/reports/balance-sheet",
        headers=auth_header(token),
        params={"as_of_date": "2026-09-30"},
    )
    reopened_balance_sheet = reopened_balance_sheet_response.json()
    assert reopened_balance_sheet["current_earnings"]["amount"] == "120.00"
    assert reopened_balance_sheet["total_assets"] == "1150.00"
    assert reopened_balance_sheet["total_liabilities_and_equity"] == "1150.00"

    relock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Corrections complete"},
    )
    assert relock_response.status_code == 200, relock_response.text
    journals_after_relock = client.get(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
    ).json()
    rollover_versions = [
        item
        for item in journals_after_relock
        if item["reference"] == f"PERIOD-ROLLOVER:{period_id}"
    ]
    assert {item["status"] for item in rollover_versions} == {"posted", "voided"}
    assert len(rollover_versions) == 2


def test_period_lock_rolls_a_net_loss_to_the_debit_side_of_retained_earnings(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    capital_account_id = create_account(
        client, token, company_id, "3000", "Owner Capital", "equity"
    )
    expense_account_id = create_account(
        client, token, company_id, "5000", "Operating Expense", "expense"
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-01",
        description="Capital injection",
        lines=[
            {"account_id": cash_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
            {"account_id": capital_account_id, "debit_amount": "0.00", "credit_amount": "100.00"},
        ],
    )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-10",
        description="Operating loss",
        lines=[
            {"account_id": expense_account_id, "debit_amount": "30.00", "credit_amount": "0.00"},
            {"account_id": cash_account_id, "debit_amount": "0.00", "credit_amount": "30.00"},
        ],
    )

    lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Loss period finalized"},
    )
    assert lock_response.status_code == 200, lock_response.text
    journals = client.get(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
    ).json()
    rollover = next(
        item for item in journals if item["reference"] == f"PERIOD-ROLLOVER:{period_id}"
    )
    retained_earnings_account = next(
        item
        for item in client.get(
            f"/api/companies/{company_id}/accounts",
            headers=auth_header(token),
        ).json()
        if item["name"] == "Retained Earnings"
    )
    retained_earnings_line = next(
        line for line in rollover["lines"] if line["account_id"] == retained_earnings_account["id"]
    )
    assert retained_earnings_line["debit_amount"] == "30.00"
    assert retained_earnings_line["credit_amount"] == "0.00"

    balance_sheet_response = client.get(
        f"/api/companies/{company_id}/reports/balance-sheet",
        headers=auth_header(token),
        params={"as_of_date": "2026-09-30"},
    )
    balance_sheet = balance_sheet_response.json()
    assert balance_sheet["current_earnings"]["amount"] == "0.00"
    assert balance_sheet["total_assets"] == "70.00"
    assert balance_sheet["total_equity"] == "70.00"
    assert balance_sheet["total_assets"] == balance_sheet["total_liabilities_and_equity"]


def test_period_lock_reuses_an_existing_retained_earnings_account(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    initial_accounts = client.get(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
    ).json()
    retained_earnings_account_id = next(
        account["id"] for account in initial_accounts if account["account_code"] == "3110"
    )
    seed_reporting_ledger(client, token, company_id, period_id)

    lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Use configured retained earnings"},
    )
    assert lock_response.status_code == 200, lock_response.text

    accounts = client.get(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
    ).json()
    assert sum(account["account_code"] == "3110" for account in accounts) == 1
    rollover = next(
        journal
        for journal in client.get(
            f"/api/companies/{company_id}/journals",
            headers=auth_header(token),
        ).json()
        if journal["reference"] == f"PERIOD-ROLLOVER:{period_id}"
    )
    retained_earnings_line = next(
        line for line in rollover["lines"] if line["account_id"] == retained_earnings_account_id
    )
    assert retained_earnings_line["credit_amount"] == "120.00"


def test_lock_backfills_a_rollover_for_a_period_locked_before_the_feature(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    seed_reporting_ledger(client, token, company_id, period_id)
    company_uuid = UUID(company_id)
    period_uuid = UUID(period_id)

    with TestingSessionLocal() as db:
        period = db.get(AccountingPeriod, period_uuid)
        actor_user_id = db.scalar(select(User.id).where(User.email == "admin@example.com"))
        assert period is not None
        assert actor_user_id is not None
        period.status = WorkflowStatus.LOCKED
        db.add(
            PeriodLock(
                company_id=company_uuid,
                accounting_period_id=period_uuid,
                lock_reason="Legacy lock before rollover support",
                locked_by_user_id=actor_user_id,
                locked_at=datetime.now(UTC),
            )
        )
        db.commit()

    backfill_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Backfill missing rollover"},
    )
    assert backfill_response.status_code == 200, backfill_response.text
    assert backfill_response.json()["status"] == "locked"
    rollover_journals = [
        journal
        for journal in client.get(
            f"/api/companies/{company_id}/journals",
            headers=auth_header(token),
        ).json()
        if journal["reference"] == f"PERIOD-ROLLOVER:{period_id}"
    ]
    assert len(rollover_journals) == 1
    assert rollover_journals[0]["status"] == "posted"

    with TestingSessionLocal() as db:
        lock_records = list(
            db.scalars(
                select(PeriodLock).where(PeriodLock.accounting_period_id == period_uuid)
            ).all()
        )
    assert len(lock_records) == 1


def test_general_ledger_report_uses_opening_balance_and_account_filter(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    account_ids = seed_reporting_ledger(client, token, company_id, period_id)

    gl_response = client.get(
        f"/api/companies/{company_id}/reports/general-ledger",
        headers=auth_header(token),
        params={
            "start_date": "2026-07-10",
            "end_date": "2026-07-31",
            "account_id": account_ids["cash"],
        },
    )
    assert gl_response.status_code == 200, gl_response.text
    payload = gl_response.json()
    assert len(payload["accounts"]) == 1
    account_payload = payload["accounts"][0]
    assert account_payload["account_code"] == "1000"
    assert account_payload["opening_balance"] == "1000.00"
    assert account_payload["closing_balance"] == "1100.00"
    assert len(account_payload["entries"]) == 1
    assert account_payload["entries"][0]["entry_date"] == "2026-07-10"
    assert account_payload["entries"][0]["running_balance"] == "1100.00"

    gl_export = client.get(
        f"/api/companies/{company_id}/reports/general-ledger/export",
        headers=auth_header(token),
        params={
            "start_date": "2026-07-10",
            "end_date": "2026-07-31",
            "account_id": account_ids["cash"],
        },
    )
    assert gl_export.status_code == 200, gl_export.text
    assert b"Running Balance" in gl_export.content
    assert b"1000,Cash" in gl_export.content


def test_general_ledger_report_includes_draft_entries_with_status(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    account_ids = seed_reporting_ledger(client, token, company_id, period_id)

    create_draft_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-15",
        description="Draft rent accrual",
        lines=[
            {
                "account_id": account_ids["expense"],
                "debit_amount": "25.00",
                "credit_amount": "0.00",
            },
            {"account_id": account_ids["cash"], "debit_amount": "0.00", "credit_amount": "25.00"},
        ],
    )

    gl_response = client.get(
        f"/api/companies/{company_id}/reports/general-ledger",
        headers=auth_header(token),
        params={
            "start_date": "2026-07-10",
            "end_date": "2026-07-31",
            "account_id": account_ids["cash"],
        },
    )
    assert gl_response.status_code == 200, gl_response.text
    payload = gl_response.json()
    account_payload = payload["accounts"][0]
    assert account_payload["opening_balance"] == "1000.00"
    assert account_payload["closing_balance"] == "1100.00"
    assert [entry["journal_status"] for entry in account_payload["entries"]] == ["posted"]
    assert [entry["running_balance"] for entry in account_payload["entries"]] == ["1100.00"]

    draft_gl_response = client.get(
        f"/api/companies/{company_id}/reports/general-ledger",
        headers=auth_header(token),
        params={
            "start_date": "2026-07-10",
            "end_date": "2026-07-31",
            "account_id": account_ids["cash"],
            "include_draft": True,
        },
    )
    assert draft_gl_response.status_code == 200, draft_gl_response.text
    draft_payload = draft_gl_response.json()
    draft_account_payload = draft_payload["accounts"][0]
    assert draft_account_payload["opening_balance"] == "1000.00"
    assert draft_account_payload["closing_balance"] == "1075.00"
    assert [entry["journal_status"] for entry in draft_account_payload["entries"]] == [
        "posted",
        "draft",
    ]
    assert [entry["running_balance"] for entry in draft_account_payload["entries"]] == [
        "1100.00",
        "1075.00",
    ]

    gl_export = client.get(
        f"/api/companies/{company_id}/reports/general-ledger/export",
        headers=auth_header(token),
        params={
            "start_date": "2026-07-10",
            "end_date": "2026-07-31",
            "account_id": account_ids["cash"],
            "include_draft": True,
        },
    )
    assert gl_export.status_code == 200, gl_export.text
    assert b"Status" in gl_export.content
    assert b",draft," in gl_export.content


def test_financial_reports_can_include_draft_entries_when_requested(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    account_ids = seed_reporting_ledger(client, token, company_id, period_id)

    create_draft_journal(
        client,
        token,
        company_id,
        period_id,
        entry_date="2026-07-15",
        description="Draft rent accrual",
        lines=[
            {
                "account_id": account_ids["expense"],
                "debit_amount": "25.00",
                "credit_amount": "0.00",
            },
            {"account_id": account_ids["cash"], "debit_amount": "0.00", "credit_amount": "25.00"},
        ],
    )

    trial_balance_response = client.get(
        f"/api/companies/{company_id}/reports/trial-balance",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31", "include_draft": True},
    )
    assert trial_balance_response.status_code == 200, trial_balance_response.text
    trial_balance_rows = {row["account_code"]: row for row in trial_balance_response.json()["rows"]}
    assert trial_balance_rows["1000"]["balance"] == "1075.00"
    assert trial_balance_rows["5000"]["balance"] == "55.00"

    pnl_response = client.get(
        f"/api/companies/{company_id}/reports/profit-and-loss",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31", "include_draft": True},
    )
    assert pnl_response.status_code == 200, pnl_response.text
    pnl_payload = pnl_response.json()
    assert pnl_payload["total_income"] == "100.00"
    assert pnl_payload["total_expenses"] == "55.00"
    assert pnl_payload["net_profit"] == "45.00"

    balance_sheet_response = client.get(
        f"/api/companies/{company_id}/reports/balance-sheet",
        headers=auth_header(token),
        params={"as_of_date": "2026-07-31", "include_draft": True},
    )
    assert balance_sheet_response.status_code == 200, balance_sheet_response.text
    balance_sheet_payload = balance_sheet_response.json()
    assert balance_sheet_payload["total_assets"] == "1075.00"
    assert balance_sheet_payload["total_liabilities"] == "30.00"
    assert balance_sheet_payload["current_earnings"]["amount"] == "45.00"
    assert balance_sheet_payload["total_equity"] == "1045.00"
    assert balance_sheet_payload["total_liabilities_and_equity"] == "1075.00"

    pnl_export = client.get(
        f"/api/companies/{company_id}/reports/profit-and-loss/export",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31", "include_draft": True},
    )
    assert pnl_export.status_code == 200, pnl_export.text
    assert b"Total Expenses,,,55.00" in pnl_export.content
    assert b"Net Profit,,,45.00" in pnl_export.content
