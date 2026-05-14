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


def login(client, email: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def create_user(client, admin_token: str, *, email: str, full_name: str, password: str) -> str:
    response = client.post(
        "/api/admin/users",
        headers=auth_header(admin_token),
        json={
            "email": email,
            "full_name": full_name,
            "password": password,
            "is_superuser": False,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def grant_company_access(
    client,
    admin_token: str,
    company_id: str,
    user_id: str,
    *,
    can_prepare: bool,
    can_review: bool,
    can_approve: bool,
    can_administer: bool = False,
):
    response = client.post(
        f"/api/companies/{company_id}/access",
        headers=auth_header(admin_token),
        json={
            "user_id": user_id,
            "can_prepare": can_prepare,
            "can_review": can_review,
            "can_approve": can_approve,
            "can_administer": can_administer,
        },
    )
    return response


def create_company(client, token: str, *, self_approval_mode: str = "warn"):
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
                "allow_self_approval": self_approval_mode != "block",
                "self_approval_mode": self_approval_mode,
                "period_lock_policy": "after_approval",
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_period(client, token: str, company_id: str):
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


def create_account(client, token: str, company_id: str, code: str, name: str, account_type: str):
    return upsert_test_account(
        client,
        token,
        company_id,
        account_code=code,
        name=name,
        account_type=account_type,
    )


def test_bootstrap_company_accounts_journal_and_trial_balance(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")

    journal_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-02",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Initial sale",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
                {"account_id": revenue_account_id, "debit_amount": "0.00", "credit_amount": "100.00"},
            ],
        },
    )
    assert journal_response.status_code == 201, journal_response.text
    journal_id = journal_response.json()["id"]

    post_response = client.post(
        f"/api/companies/{company_id}/journals/{journal_id}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text
    assert post_response.json()["status"] == "posted"

    trial_balance_response = client.get(
        f"/api/companies/{company_id}/journals/trial-balance",
        headers=auth_header(token),
    )
    assert trial_balance_response.status_code == 200, trial_balance_response.text
    rows = trial_balance_response.json()
    assert len(rows) >= 2
    balances = {row["account_code"]: row["balance"] for row in rows}
    assert balances["1000"] == "100.00"
    assert balances["4000"] == "-100.00"


def test_locked_period_blocks_new_journal_creation(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")

    lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Period finalized"},
    )
    assert lock_response.status_code == 200, lock_response.text

    journal_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-15",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Blocked sale",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "50.00", "credit_amount": "0.00"},
                {"account_id": revenue_account_id, "debit_amount": "0.00", "credit_amount": "50.00"},
            ],
        },
    )
    assert journal_response.status_code == 400, journal_response.text
    assert journal_response.json()["detail"] == "Accounting period is locked"


def test_self_approval_policy_block_is_enforced(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token, self_approval_mode="block")
    period_id = create_period(client, token, company_id)

    submit_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/submit",
        headers=auth_header(token),
        json={"note": "Ready for review"},
    )
    assert submit_response.status_code == 200, submit_response.text

    approve_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/approve",
        headers=auth_header(token),
        json={"note": "Approving own work"},
    )
    assert approve_response.status_code == 400, approve_response.text
    assert "self-approval" in approve_response.json()["detail"].lower()


def test_auth_admin_company_reference_and_configuration_flows(client):
    token = bootstrap_superuser(client)

    me_response = client.get("/api/auth/me", headers=auth_header(token))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["user"]["email"] == "admin@example.com"
    assert me_response.json()["access_token"] == ""

    login_token = login(client, "admin@example.com", "StrongPass123")
    assert login_token

    overview_before = client.get("/api/admin/overview", headers=auth_header(token))
    assert overview_before.status_code == 200, overview_before.text
    assert overview_before.json() == {
        "users": 1,
        "companies": 0,
        "accounts": 0,
        "periods": 0,
        "journals": 0,
    }

    reviewer_user_id = create_user(
        client,
        token,
        email="reviewer@example.com",
        full_name="Reviewer User",
        password="StrongPass123",
    )
    users_response = client.get("/api/admin/users", headers=auth_header(token))
    assert users_response.status_code == 200, users_response.text
    user_emails = {user["email"] for user in users_response.json()}
    assert user_emails == {"admin@example.com", "reviewer@example.com"}

    company_id = create_company(client, token)

    companies_response = client.get("/api/companies", headers=auth_header(token))
    assert companies_response.status_code == 200, companies_response.text
    assert [company["id"] for company in companies_response.json()] == [company_id]

    company_response = client.get(f"/api/companies/{company_id}", headers=auth_header(token))
    assert company_response.status_code == 200, company_response.text
    assert company_response.json()["legal_name"] == "Example Pty Ltd"

    configuration_list = client.get(
        f"/api/companies/{company_id}/configurations",
        headers=auth_header(token),
    )
    assert configuration_list.status_code == 200, configuration_list.text
    assert len(configuration_list.json()) == 1
    assert configuration_list.json()[0]["version_number"] == 1

    new_configuration = client.post(
        f"/api/companies/{company_id}/configurations",
        headers=auth_header(token),
        json={
            "effective_from": "2026-10-01",
            "gst_registered": True,
            "bas_frequency": "monthly",
            "bas_reporting_basis": "accrual",
            "financial_year_start_month": 7,
            "financial_year_start_day": 1,
            "allow_self_approval": True,
            "self_approval_mode": "warn",
            "period_lock_policy": "after_export",
        },
    )
    assert new_configuration.status_code == 201, new_configuration.text
    assert new_configuration.json()["version_number"] == 2

    configuration_list_after = client.get(
        f"/api/companies/{company_id}/configurations",
        headers=auth_header(token),
    )
    assert configuration_list_after.status_code == 200, configuration_list_after.text
    assert [item["version_number"] for item in configuration_list_after.json()] == [2, 1]

    access_grant = grant_company_access(
        client,
        token,
        company_id,
        reviewer_user_id,
        can_prepare=True,
        can_review=True,
        can_approve=False,
    )
    assert access_grant.status_code == 201, access_grant.text

    duplicate_access_grant = grant_company_access(
        client,
        token,
        company_id,
        reviewer_user_id,
        can_prepare=True,
        can_review=True,
        can_approve=False,
    )
    assert duplicate_access_grant.status_code == 409, duplicate_access_grant.text
    assert duplicate_access_grant.json()["detail"] == "Access already exists"

    access_list = client.get(f"/api/companies/{company_id}/access", headers=auth_header(token))
    assert access_list.status_code == 200, access_list.text
    assert len(access_list.json()) == 2

    reviewer_token = login(client, "reviewer@example.com", "StrongPass123")
    reviewer_companies = client.get("/api/companies", headers=auth_header(reviewer_token))
    assert reviewer_companies.status_code == 200, reviewer_companies.text
    assert [company["id"] for company in reviewer_companies.json()] == [company_id]

    reporting_category = client.post(
        f"/api/companies/{company_id}/reporting-categories",
        headers=auth_header(token),
        json={"code": "SALES", "name": "Sales", "category_type": "pnl"},
    )
    assert reporting_category.status_code == 201, reporting_category.text

    reporting_category_list = client.get(
        f"/api/companies/{company_id}/reporting-categories",
        headers=auth_header(reviewer_token),
    )
    assert reporting_category_list.status_code == 200, reporting_category_list.text
    assert any(item["code"] == "SALES" for item in reporting_category_list.json())

    tax_code = client.post(
        f"/api/companies/{company_id}/tax-codes",
        headers=auth_header(token),
        json={
            "code": "GST_SALES",
            "name": "GST Sales",
            "rate": "0.10",
            "is_gst_applicable": True,
            "bas_label": "G1",
            "input_output_type": "output_taxed",
        },
    )
    assert tax_code.status_code == 201, tax_code.text

    tax_code_list = client.get(f"/api/companies/{company_id}/tax-codes", headers=auth_header(reviewer_token))
    assert tax_code_list.status_code == 200, tax_code_list.text
    assert any(item["code"] == "GST_SALES" for item in tax_code_list.json())

    cash_account = client.post(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
        json={"account_code": "9910", "name": "Test Cash", "account_type": "asset"},
    )
    assert cash_account.status_code == 201, cash_account.text

    duplicate_account = client.post(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
        json={"account_code": "9910", "name": "Cash Duplicate", "account_type": "asset"},
    )
    assert duplicate_account.status_code == 409, duplicate_account.text
    assert duplicate_account.json()["detail"] == "Account code already exists"

    account_list = client.get(f"/api/companies/{company_id}/accounts", headers=auth_header(reviewer_token))
    assert account_list.status_code == 200, account_list.text
    assert any(account["account_code"] == "9910" for account in account_list.json())

    overview_after = client.get("/api/admin/overview", headers=auth_header(token))
    assert overview_after.status_code == 200, overview_after.text
    assert overview_after.json()["users"] == 2
    assert overview_after.json()["companies"] == 1
    assert overview_after.json()["accounts"] == len(account_list.json())


def test_period_unlock_and_journal_reversal_and_validation(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)

    invalid_period_response = client.post(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
        json={
            "name": "Invalid",
            "period_type": "quarter",
            "start_date": "2026-09-30",
            "end_date": "2026-07-01",
        },
    )
    assert invalid_period_response.status_code == 400, invalid_period_response.text
    assert invalid_period_response.json()["detail"] == "Period dates are invalid"

    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")

    unbalanced_journal_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-03",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Unbalanced journal",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
                {"account_id": revenue_account_id, "debit_amount": "0.00", "credit_amount": "90.00"},
            ],
        },
    )
    assert unbalanced_journal_response.status_code == 400, unbalanced_journal_response.text
    assert unbalanced_journal_response.json()["detail"] == "Journal is not balanced"

    invalid_line_amount_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-03",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Invalid line amounts",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "0.00", "credit_amount": "0.00"},
                {"account_id": revenue_account_id, "debit_amount": "0.00", "credit_amount": "0.00"},
            ],
        },
    )
    assert invalid_line_amount_response.status_code == 400, invalid_line_amount_response.text
    assert invalid_line_amount_response.json()["detail"] == "Journal line 1 must have exactly one positive amount"

    invalid_account_journal_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-03",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Invalid account journal",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
                {"account_id": "11111111-1111-1111-1111-111111111111", "debit_amount": "0.00", "credit_amount": "100.00"},
            ],
        },
    )
    assert invalid_account_journal_response.status_code == 400, invalid_account_journal_response.text
    assert invalid_account_journal_response.json()["detail"] == "Journal references invalid account ids"

    draft_journal_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-02",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Initial sale",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
                {"account_id": revenue_account_id, "debit_amount": "0.00", "credit_amount": "100.00"},
            ],
        },
    )
    assert draft_journal_response.status_code == 201, draft_journal_response.text
    draft_journal_id = draft_journal_response.json()["id"]

    reverse_draft_response = client.post(
        f"/api/companies/{company_id}/journals/{draft_journal_id}/reverse",
        headers=auth_header(token),
    )
    assert reverse_draft_response.status_code == 400, reverse_draft_response.text
    assert reverse_draft_response.json()["detail"] == "Only posted journals can be reversed"

    post_response = client.post(
        f"/api/companies/{company_id}/journals/{draft_journal_id}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text
    assert post_response.json()["status"] == "posted"

    journal_list_after_post = client.get(f"/api/companies/{company_id}/journals", headers=auth_header(token))
    assert journal_list_after_post.status_code == 200, journal_list_after_post.text
    assert len(journal_list_after_post.json()) == 1
    assert journal_list_after_post.json()[0]["status"] == "posted"

    reversal_response = client.post(
        f"/api/companies/{company_id}/journals/{draft_journal_id}/reverse",
        headers=auth_header(token),
    )
    assert reversal_response.status_code == 201, reversal_response.text
    assert reversal_response.json()["reversal_of_entry_id"] == draft_journal_id
    assert reversal_response.json()["status"] == "posted"

    journal_list_after_reversal = client.get(f"/api/companies/{company_id}/journals", headers=auth_header(token))
    assert journal_list_after_reversal.status_code == 200, journal_list_after_reversal.text
    statuses_by_id = {journal["id"]: journal["status"] for journal in journal_list_after_reversal.json()}
    assert statuses_by_id[draft_journal_id] == "reversed"
    assert statuses_by_id[reversal_response.json()["id"]] == "posted"

    trial_balance_response = client.get(
        f"/api/companies/{company_id}/journals/trial-balance",
        headers=auth_header(token),
    )
    assert trial_balance_response.status_code == 200, trial_balance_response.text
    balances = {row["account_code"]: row["balance"] for row in trial_balance_response.json()}
    assert balances["1000"] == "-100.00"
    assert balances["4000"] == "100.00"

    lock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/lock",
        headers=auth_header(token),
        json={"reason": "Period finalized"},
    )
    assert lock_response.status_code == 200, lock_response.text
    assert lock_response.json()["status"] == "locked"

    unlock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/unlock",
        headers=auth_header(token),
        json={"reason": "Need correction"},
    )
    assert unlock_response.status_code == 200, unlock_response.text
    assert unlock_response.json()["status"] == "approved"

    second_unlock_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/unlock",
        headers=auth_header(token),
        json={"reason": "Already unlocked"},
    )
    assert second_unlock_response.status_code == 400, second_unlock_response.text
    assert second_unlock_response.json()["detail"] == "Period is not currently locked"

    period_list = client.get(f"/api/companies/{company_id}/periods", headers=auth_header(token))
    assert period_list.status_code == 200, period_list.text
    assert period_list.json()[0]["status"] == "approved"
