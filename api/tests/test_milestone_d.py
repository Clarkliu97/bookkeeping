from conftest import upsert_test_account


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


def create_account(client, token: str, company_id: str, code: str, name: str, account_type: str) -> str:
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
            {"account_id": account_ids["equity"], "debit_amount": "0.00", "credit_amount": "1000.00"},
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
            {"account_id": account_ids["revenue"], "debit_amount": "0.00", "credit_amount": "100.00"},
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
            {"account_id": account_ids["expense"], "debit_amount": "30.00", "credit_amount": "0.00"},
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
            {"account_id": account_ids["revenue"], "debit_amount": "0.00", "credit_amount": "50.00"},
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
    assert b"Account Code,Account Name,Debit Total,Credit Total,Balance" in trial_balance_export.content

    pnl_export = client.get(
        f"/api/companies/{company_id}/reports/profit-and-loss/export",
        headers=auth_header(token),
        params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
    )
    assert pnl_export.status_code == 200, pnl_export.text
    assert b"Total Income" in pnl_export.content
    assert b"Net Profit" in pnl_export.content


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
            {"account_id": account_ids["expense"], "debit_amount": "25.00", "credit_amount": "0.00"},
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
    assert [entry["journal_status"] for entry in draft_account_payload["entries"]] == ["posted", "draft"]
    assert [entry["running_balance"] for entry in draft_account_payload["entries"]] == ["1100.00", "1075.00"]

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
            {"account_id": account_ids["expense"], "debit_amount": "25.00", "credit_amount": "0.00"},
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
