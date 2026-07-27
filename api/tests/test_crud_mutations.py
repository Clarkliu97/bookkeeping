from conftest import upsert_test_account


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def bootstrap_superuser(client) -> str:
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


def create_company(client, token: str) -> tuple[str, str]:
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
    company_id = response.json()["id"]
    configurations = client.get(
        f"/api/companies/{company_id}/configurations",
        headers=auth_header(token),
    )
    assert configurations.status_code == 200, configurations.text
    return company_id, configurations.json()[0]["id"]


def create_period(client, token: str, company_id: str, *, name: str, period_type: str, start_date: str, end_date: str) -> str:
    response = client.post(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
        json={
            "name": name,
            "period_type": period_type,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_reporting_category(client, token: str, company_id: str, *, code: str, name: str = "Sales") -> str:
    response = client.post(
        f"/api/companies/{company_id}/reporting-categories",
        headers=auth_header(token),
        json={"code": code, "name": name, "category_type": "pnl"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_reporting_category_invalid_type_returns_422(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)

    response = client.post(
        f"/api/companies/{company_id}/reporting-categories",
        headers=auth_header(token),
        json={"code": "BADTYPE", "name": "Bad Type", "category_type": "123"},
    )

    assert response.status_code == 422, response.text
    assert "category_type" in response.text


def test_tax_code_invalid_input_output_type_returns_422(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)

    response = client.post(
        f"/api/companies/{company_id}/tax-codes",
        headers=auth_header(token),
        json={
            "code": "BADGST",
            "name": "Bad GST",
            "description": "Bad GST",
            "rate": "0.10",
            "is_gst_applicable": True,
            "bas_label": "G1",
            "input_output_type": "bad",
        },
    )

    assert response.status_code == 422, response.text
    assert "input_output_type" in response.text


def test_company_creation_seeds_default_reference_data_and_supports_disabling(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)

    category_list = client.get(f"/api/companies/{company_id}/reporting-categories", headers=auth_header(token))
    tax_code_list = client.get(f"/api/companies/{company_id}/tax-codes", headers=auth_header(token))
    account_list = client.get(f"/api/companies/{company_id}/accounts", headers=auth_header(token))

    assert category_list.status_code == 200, category_list.text
    assert tax_code_list.status_code == 200, tax_code_list.text
    assert account_list.status_code == 200, account_list.text

    categories = {item["code"]: item for item in category_list.json()}
    tax_codes = {item["code"]: item for item in tax_code_list.json()}
    accounts = {item["account_code"]: item for item in account_list.json()}

    assert len(categories) >= 80
    assert len(tax_codes) >= 35
    assert len(accounts) >= 675
    assert categories["PL_REV_TECHNOLOGY"]["is_active"] is True
    assert categories["BS_NCA_FINANCIAL_ASSETS"]["is_active"] is True
    assert tax_codes["GST_SALE_10"]["is_active"] is True
    assert tax_codes["NO_TAX"]["is_active"] is True
    assert accounts["1021"]["is_active"] is True
    assert accounts["8021"]["is_active"] is True

    disable_category = client.put(
        f"/api/companies/{company_id}/reporting-categories/{categories['PL_REV_TECHNOLOGY']['id']}",
        headers=auth_header(token),
        json={
            "code": categories["PL_REV_TECHNOLOGY"]["code"],
            "name": categories["PL_REV_TECHNOLOGY"]["name"],
            "category_type": categories["PL_REV_TECHNOLOGY"]["category_type"],
            "is_active": False,
        },
    )
    assert disable_category.status_code == 200, disable_category.text
    assert disable_category.json()["is_active"] is False

    disable_tax_code = client.put(
        f"/api/companies/{company_id}/tax-codes/{tax_codes['GST_SALE_10']['id']}",
        headers=auth_header(token),
        json={
            "code": tax_codes["GST_SALE_10"]["code"],
            "name": tax_codes["GST_SALE_10"]["name"],
            "description": tax_codes["GST_SALE_10"]["description"],
            "rate": tax_codes["GST_SALE_10"]["rate"],
            "is_gst_applicable": tax_codes["GST_SALE_10"]["is_gst_applicable"],
            "bas_label": tax_codes["GST_SALE_10"]["bas_label"],
            "input_output_type": tax_codes["GST_SALE_10"]["input_output_type"],
            "is_active": False,
        },
    )
    assert disable_tax_code.status_code == 200, disable_tax_code.text
    assert disable_tax_code.json()["is_active"] is False


def test_account_invalid_type_returns_422(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)

    response = client.post(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
        json={
            "account_code": "1000",
            "name": "Bad Account",
            "account_type": "bad",
        },
    )

    assert response.status_code == 422, response.text
    assert "account_type" in response.text


def test_non_posting_account_rejects_manual_posting_and_journal_use(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)
    period_id = create_period(
        client,
        token,
        company_id,
        name="Working Quarter",
        period_type="quarter",
        start_date="2026-07-01",
        end_date="2026-09-30",
    )

    create_response = client.post(
        f"/api/companies/{company_id}/accounts",
        headers=auth_header(token),
        json={
            "account_code": "9500",
            "name": "Memo Tracking",
            "account_type": "non_posting",
            "allow_manual_posting": True,
        },
    )
    assert create_response.status_code == 400, create_response.text

    non_posting_account_id = create_account(
        client,
        token,
        company_id,
        code="9500",
        name="Memo Tracking",
        account_type="non_posting",
        allow_manual_posting=False,
    )
    balancing_account_id = create_account(client, token, company_id, code="1000", name="Cash", account_type="asset")

    journal_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-10",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Memo journal",
            "reference": "MEMO-1",
            "lines": [
                {"account_id": non_posting_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
                {"account_id": balancing_account_id, "debit_amount": "0.00", "credit_amount": "100.00"},
            ],
        },
    )

    assert journal_response.status_code == 400, journal_response.text
    assert "do not allow manual posting" in journal_response.text


def create_tax_code(client, token: str, company_id: str, *, code: str, bas_label: str) -> str:
    response = client.post(
        f"/api/companies/{company_id}/tax-codes",
        headers=auth_header(token),
        json={
            "code": code,
            "name": code,
            "description": f"{code} description",
            "rate": "0.10",
            "is_gst_applicable": True,
            "bas_label": bas_label,
            "input_output_type": "output_taxed",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_account(
    client,
    token: str,
    company_id: str,
    *,
    code: str,
    name: str,
    account_type: str,
    reporting_category_id: str | None = None,
    default_tax_code_id: str | None = None,
    allow_manual_posting: bool = True,
) -> str:
    return upsert_test_account(
        client,
        token,
        company_id,
        account_code=code,
        name=name,
        account_type=account_type,
        reporting_category_id=reporting_category_id,
        default_tax_code_id=default_tax_code_id,
        allow_manual_posting=allow_manual_posting,
    )


def create_draft_journal(client, token: str, company_id: str, period_id: str, debit_account_id: str, credit_account_id: str) -> str:
    response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-10",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Draft journal",
            "reference": "DRAFT-1",
            "lines": [
                {"account_id": debit_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
                {"account_id": credit_account_id, "debit_amount": "0.00", "credit_amount": "100.00"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_posted_bas_journal(
    client,
    token: str,
    company_id: str,
    period_id: str,
    cash_account_id: str,
    revenue_account_id: str,
    gst_account_id: str,
    sale_tax_code_id: str,
    gst_tax_code_id: str,
) -> None:
    response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-15",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "GST sale",
            "reference": "INV-001",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "110.00", "credit_amount": "0.00"},
                {
                    "account_id": revenue_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": "100.00",
                    "tax_code_id": sale_tax_code_id,
                },
                {
                    "account_id": gst_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": "10.00",
                    "tax_code_id": gst_tax_code_id,
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    journal_id = response.json()["id"]
    post_response = client.post(
        f"/api/companies/{company_id}/journals/{journal_id}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text


def create_bank_account(client, token: str, company_id: str, *, name: str = "Operating") -> str:
    response = client.post(
        f"/api/companies/{company_id}/bank-accounts",
        headers=auth_header(token),
        json={
            "name": name,
            "bank_name": "Example Bank",
            "bsb": "123-456",
            "account_number_masked": "xxxx1234",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload_bank_import(client, token: str, company_id: str, bank_account_id: str, *, note: str = "Import") -> str:
    response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={
            "file": (
                "import.csv",
                b"date,description,debit,credit,reference\n2026-07-01,Deposit,0.00,100.00,DEP-001\n",
                "text/csv",
            )
        },
        data={"bank_account_id": bank_account_id, "note": note},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_core_update_delete_endpoints(client):
    token = bootstrap_superuser(client)

    create_user = client.post(
        "/api/admin/users",
        headers=auth_header(token),
        json={
            "email": "reviewer@example.com",
            "full_name": "Reviewer User",
            "password": "StrongPass123",
            "is_superuser": False,
        },
    )
    assert create_user.status_code == 201, create_user.text
    reviewer_user_id = create_user.json()["id"]

    update_user = client.put(
        f"/api/admin/users/{reviewer_user_id}",
        headers=auth_header(token),
        json={
            "email": "reviewer.updated@example.com",
            "full_name": "Reviewer Updated",
            "password": "NewStrongPass123",
            "is_superuser": False,
            "is_active": True,
        },
    )
    assert update_user.status_code == 200, update_user.text
    assert update_user.json()["email"] == "reviewer.updated@example.com"

    delete_user = client.delete(f"/api/admin/users/{reviewer_user_id}", headers=auth_header(token))
    assert delete_user.status_code == 204, delete_user.text

    company_id, configuration_id = create_company(client, token)
    update_company = client.put(
        f"/api/companies/{company_id}",
        headers=auth_header(token),
        json={
            "legal_name": "Updated Example Pty Ltd",
            "trading_name": "Updated Trading",
            "abn": "51824753556",
            "acn": "824753556",
            "entity_type": "company",
            "is_active": True,
            "base_currency": "AUD",
            "country_code": "AU",
        },
    )
    assert update_company.status_code == 200, update_company.text
    assert update_company.json()["legal_name"] == "Updated Example Pty Ltd"

    update_configuration = client.put(
        f"/api/companies/{company_id}/configurations/{configuration_id}",
        headers=auth_header(token),
        json={
            "effective_from": "2026-07-01",
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
    assert update_configuration.status_code == 200, update_configuration.text
    assert update_configuration.json()["bas_frequency"] == "monthly"

    access_response = client.post(
        f"/api/companies/{company_id}/access",
        headers=auth_header(token),
        json={
            "user_id": reviewer_user_id,
            "can_prepare": True,
            "can_review": True,
            "can_approve": False,
            "can_administer": False,
        },
    )
    assert access_response.status_code == 201, access_response.text

    update_access = client.put(
        f"/api/companies/{company_id}/access/{reviewer_user_id}",
        headers=auth_header(token),
        json={
            "can_prepare": True,
            "can_review": True,
            "can_approve": True,
            "can_administer": False,
        },
    )
    assert update_access.status_code == 200, update_access.text
    assert update_access.json()["can_approve"] is True

    category_id = create_reporting_category(client, token, company_id, code="TMP_CAT")
    update_category = client.put(
        f"/api/companies/{company_id}/reporting-categories/{category_id}",
        headers=auth_header(token),
        json={"code": "TMP_CAT_2", "name": "Temporary Category", "category_type": "pnl"},
    )
    assert update_category.status_code == 200, update_category.text
    delete_category = client.delete(
        f"/api/companies/{company_id}/reporting-categories/{category_id}",
        headers=auth_header(token),
    )
    assert delete_category.status_code == 204, delete_category.text

    tax_code_id = create_tax_code(client, token, company_id, code="TMP_TAX", bas_label="G1")
    update_tax_code = client.put(
        f"/api/companies/{company_id}/tax-codes/{tax_code_id}",
        headers=auth_header(token),
        json={
            "code": "TMP_TAX_2",
            "name": "Temp Tax Updated",
            "description": "Updated",
            "rate": "0.10",
            "is_gst_applicable": True,
            "bas_label": "G1",
            "input_output_type": "output_taxed",
        },
    )
    assert update_tax_code.status_code == 200, update_tax_code.text
    delete_tax_code = client.delete(f"/api/companies/{company_id}/tax-codes/{tax_code_id}", headers=auth_header(token))
    assert delete_tax_code.status_code == 204, delete_tax_code.text

    account_id = create_account(client, token, company_id, code="1000", name="Cash", account_type="asset")
    update_account = client.put(
        f"/api/companies/{company_id}/accounts/{account_id}",
        headers=auth_header(token),
        json={
            "account_code": "1000",
            "name": "Cash Updated",
            "account_type": "asset",
            "is_active": True,
            "allow_manual_posting": True,
        },
    )
    assert update_account.status_code == 200, update_account.text
    delete_account = client.delete(f"/api/companies/{company_id}/accounts/{account_id}", headers=auth_header(token))
    assert delete_account.status_code == 204, delete_account.text

    deletable_period_id = create_period(
        client,
        token,
        company_id,
        name="Draft Month",
        period_type="month",
        start_date="2026-10-01",
        end_date="2026-10-31",
    )
    update_period = client.put(
        f"/api/companies/{company_id}/periods/{deletable_period_id}",
        headers=auth_header(token),
        json={
            "name": "Draft Month Updated",
            "period_type": "month",
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
        },
    )
    assert update_period.status_code == 200, update_period.text
    delete_period = client.delete(f"/api/companies/{company_id}/periods/{deletable_period_id}", headers=auth_header(token))
    assert delete_period.status_code == 204, delete_period.text

    journal_period_id = create_period(
        client,
        token,
        company_id,
        name="Draft Quarter",
        period_type="quarter",
        start_date="2026-07-01",
        end_date="2026-09-30",
    )
    debit_account_id = create_account(client, token, company_id, code="1100", name="Debit", account_type="asset")
    credit_account_id = create_account(client, token, company_id, code="4100", name="Credit", account_type="income")
    journal_id = create_draft_journal(client, token, company_id, journal_period_id, debit_account_id, credit_account_id)
    update_journal = client.put(
        f"/api/companies/{company_id}/journals/{journal_id}",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-11",
            "accounting_period_id": journal_period_id,
            "source_type": "manual",
            "description": "Draft journal updated",
            "reference": "DRAFT-2",
            "lines": [
                {"account_id": debit_account_id, "debit_amount": "150.00", "credit_amount": "0.00"},
                {"account_id": credit_account_id, "debit_amount": "0.00", "credit_amount": "150.00"},
            ],
        },
    )
    assert update_journal.status_code == 200, update_journal.text
    delete_journal = client.delete(f"/api/companies/{company_id}/journals/{journal_id}", headers=auth_header(token))
    assert delete_journal.status_code == 204, delete_journal.text

    delete_access = client.delete(f"/api/companies/{company_id}/access/{reviewer_user_id}", headers=auth_header(token))
    assert delete_access.status_code == 204, delete_access.text

    delete_configuration = client.delete(
        f"/api/companies/{company_id}/configurations/{configuration_id}",
        headers=auth_header(token),
    )
    assert delete_configuration.status_code == 204, delete_configuration.text

    delete_company = client.delete(f"/api/companies/{company_id}", headers=auth_header(token))
    assert delete_company.status_code == 204, delete_company.text


def test_document_bank_and_reconciliation_update_delete_endpoints(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)
    period_id = create_period(
        client,
        token,
        company_id,
        name="Working Quarter",
        period_type="quarter",
        start_date="2026-07-01",
        end_date="2026-09-30",
    )
    cash_account_id = create_account(client, token, company_id, code="1000", name="Cash", account_type="asset")
    revenue_account_id = create_account(client, token, company_id, code="4000", name="Revenue", account_type="income")
    journal_id = create_draft_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)

    upload_document = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("invoice.txt", b"invoice-support", "text/plain")},
        data={"note": "Attachment"},
    )
    assert upload_document.status_code == 201, upload_document.text
    document_id = upload_document.json()["id"]

    update_document = client.put(
        f"/api/companies/{company_id}/documents/{document_id}",
        headers=auth_header(token),
        json={"original_filename": "invoice-updated.txt", "media_type": "text/plain"},
    )
    assert update_document.status_code == 200, update_document.text
    assert update_document.json()["original_filename"] == "invoice-updated.txt"

    create_link = client.post(
        f"/api/companies/{company_id}/documents/{document_id}/links",
        headers=auth_header(token),
        json={"entity_type": "journal_entry", "entity_id": journal_id, "note": "Initial note"},
    )
    assert create_link.status_code == 201, create_link.text
    link_id = create_link.json()["id"]

    update_link = client.put(
        f"/api/companies/{company_id}/documents/{document_id}/links/{link_id}",
        headers=auth_header(token),
        json={"entity_type": "journal_entry", "entity_id": journal_id, "note": "Updated note"},
    )
    assert update_link.status_code == 200, update_link.text
    assert update_link.json()["note"] == "Updated note"

    delete_link = client.delete(
        f"/api/companies/{company_id}/documents/{document_id}/links/{link_id}",
        headers=auth_header(token),
    )
    assert delete_link.status_code == 204, delete_link.text

    delete_document = client.delete(
        f"/api/companies/{company_id}/documents/{document_id}",
        headers=auth_header(token),
    )
    assert delete_document.status_code == 204, delete_document.text

    bank_account_id = create_bank_account(client, token, company_id, name="Operating")
    update_bank_account = client.put(
        f"/api/companies/{company_id}/bank-accounts/{bank_account_id}",
        headers=auth_header(token),
        json={
            "name": "Operating Updated",
            "bank_name": "Example Bank",
            "bsb": "123-456",
            "account_number_masked": "xxxx5678",
            "is_active": True,
        },
    )
    assert update_bank_account.status_code == 200, update_bank_account.text

    staged_bank_account_id = create_bank_account(client, token, company_id, name="Staged Import")
    staged_session_id = upload_bank_import(client, token, company_id, staged_bank_account_id, note="Stage 1")
    update_import = client.put(
        f"/api/companies/{company_id}/bank-imports/{staged_session_id}",
        headers=auth_header(token),
        json={"note": "Stage 1 updated"},
    )
    assert update_import.status_code == 200, update_import.text
    assert update_import.json()["note"] == "Stage 1 updated"
    delete_import = client.delete(
        f"/api/companies/{company_id}/bank-imports/{staged_session_id}",
        headers=auth_header(token),
    )
    assert delete_import.status_code == 204, delete_import.text

    reconcile_bank_account_id = create_bank_account(client, token, company_id, name="Recon Account")
    confirmed_session_id = upload_bank_import(client, token, company_id, reconcile_bank_account_id, note="Ready")
    confirm_import = client.post(
        f"/api/companies/{company_id}/bank-imports/{confirmed_session_id}/confirm",
        headers=auth_header(token),
        json={"note": "Confirmed"},
    )
    assert confirm_import.status_code == 200, confirm_import.text

    reconciliation_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": reconcile_bank_account_id, "accounting_period_id": period_id, "note": "Initial"},
    )
    assert reconciliation_response.status_code == 201, reconciliation_response.text
    reconciliation_session_id = reconciliation_response.json()["id"]

    update_reconciliation = client.put(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}",
        headers=auth_header(token),
        json={"accounting_period_id": period_id, "note": "Updated reconciliation"},
    )
    assert update_reconciliation.status_code == 200, update_reconciliation.text
    assert update_reconciliation.json()["note"] == "Updated reconciliation"

    delete_reconciliation = client.delete(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}",
        headers=auth_header(token),
    )
    assert delete_reconciliation.status_code == 204, delete_reconciliation.text

    rows_after_delete = client.get(
        f"/api/companies/{company_id}/bank-imports/{confirmed_session_id}/rows",
        headers=auth_header(token),
    )
    assert rows_after_delete.status_code == 200, rows_after_delete.text
    assert rows_after_delete.json()[0]["status"] == "staged"

    delete_bank_account = client.delete(
        f"/api/companies/{company_id}/bank-accounts/{bank_account_id}",
        headers=auth_header(token),
    )
    assert delete_bank_account.status_code == 204, delete_bank_account.text

    bank_accounts_after_delete = client.get(
        f"/api/companies/{company_id}/bank-accounts",
        headers=auth_header(token),
    )
    assert bank_accounts_after_delete.status_code == 200, bank_accounts_after_delete.text
    deleted_bank_account = next(
        account for account in bank_accounts_after_delete.json() if account["id"] == bank_account_id
    )
    assert deleted_bank_account["is_active"] is False

    inactive_account_upload = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={
            "file": (
                "inactive-account.csv",
                b"date,description,debit,credit,reference\n2026-07-01,Deposit,0.00,100.00,DEP-002\n",
                "text/csv",
            )
        },
        data={"bank_account_id": bank_account_id, "note": "Must be rejected"},
    )
    assert inactive_account_upload.status_code == 409, inactive_account_upload.text
    assert inactive_account_upload.json()["detail"] == "Bank account is inactive"

    inactive_account_reconciliation = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id, "note": "Must be rejected"},
    )
    assert inactive_account_reconciliation.status_code == 409, inactive_account_reconciliation.text
    assert inactive_account_reconciliation.json()["detail"] == "Bank account is inactive"


def test_journal_evidence_routes_expose_n_to_n_document_links(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)
    period_id = create_period(
        client,
        token,
        company_id,
        name="Working Quarter",
        period_type="quarter",
        start_date="2026-07-01",
        end_date="2026-09-30",
    )
    cash_account_id = create_account(client, token, company_id, code="1000", name="Cash", account_type="asset")
    revenue_account_id = create_account(client, token, company_id, code="4000", name="Revenue", account_type="income")
    journal_one_id = create_draft_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)
    journal_two_id = create_draft_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)

    first_document = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("invoice-one.txt", b"invoice-one", "text/plain")},
        data={"note": "Invoice one"},
    )
    assert first_document.status_code == 201, first_document.text
    first_document_id = first_document.json()["id"]

    second_document = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("invoice-two.txt", b"invoice-two", "text/plain")},
        data={"note": "Invoice two"},
    )
    assert second_document.status_code == 201, second_document.text
    second_document_id = second_document.json()["id"]

    link_first = client.post(
        f"/api/companies/{company_id}/journals/{journal_one_id}/documents/{first_document_id}",
        headers=auth_header(token),
        json={"note": "Primary invoice evidence"},
    )
    assert link_first.status_code == 201, link_first.text
    first_link_id = link_first.json()["link_id"]

    link_second = client.post(
        f"/api/companies/{company_id}/journals/{journal_one_id}/documents/{second_document_id}",
        headers=auth_header(token),
        json={"note": "Supplementary support"},
    )
    assert link_second.status_code == 201, link_second.text

    reuse_first = client.post(
        f"/api/companies/{company_id}/journals/{journal_two_id}/documents/{first_document_id}",
        headers=auth_header(token),
        json={"note": "Shared evidence"},
    )
    assert reuse_first.status_code == 201, reuse_first.text

    duplicate = client.post(
        f"/api/companies/{company_id}/journals/{journal_one_id}/documents/{first_document_id}",
        headers=auth_header(token),
        json={"note": "Duplicate"},
    )
    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["detail"] == "Document is already linked to this journal"

    journal_one_evidence = client.get(
        f"/api/companies/{company_id}/journals/{journal_one_id}/documents",
        headers=auth_header(token),
    )
    assert journal_one_evidence.status_code == 200, journal_one_evidence.text
    assert len(journal_one_evidence.json()) == 2
    assert {item["document_id"] for item in journal_one_evidence.json()} == {first_document_id, second_document_id}

    unlink_first = client.delete(
        f"/api/companies/{company_id}/journals/{journal_one_id}/documents/{first_document_id}/links/{first_link_id}",
        headers=auth_header(token),
    )
    assert unlink_first.status_code == 204, unlink_first.text

    journal_one_evidence_after_unlink = client.get(
        f"/api/companies/{company_id}/journals/{journal_one_id}/documents",
        headers=auth_header(token),
    )
    assert journal_one_evidence_after_unlink.status_code == 200, journal_one_evidence_after_unlink.text
    assert len(journal_one_evidence_after_unlink.json()) == 1
    assert journal_one_evidence_after_unlink.json()[0]["document_id"] == second_document_id


def test_bas_fixed_asset_and_tax_workpaper_update_delete_endpoints(client):
    token = bootstrap_superuser(client)
    company_id, _ = create_company(client, token)
    quarter_period_id = create_period(
        client,
        token,
        company_id,
        name="FY26-Q1",
        period_type="quarter",
        start_date="2026-07-01",
        end_date="2026-09-30",
    )
    year_period_id = create_period(
        client,
        token,
        company_id,
        name="FY27",
        period_type="year",
        start_date="2026-07-01",
        end_date="2027-06-30",
    )
    cash_account_id = create_account(client, token, company_id, code="1000", name="Cash", account_type="asset")
    revenue_account_id = create_account(client, token, company_id, code="4000", name="Revenue", account_type="income")
    gst_account_id = create_account(client, token, company_id, code="2200", name="GST Payable", account_type="liability")
    sale_tax_code_id = create_tax_code(client, token, company_id, code="SALE_G1", bas_label="G1")
    gst_tax_code_id = create_tax_code(client, token, company_id, code="GST_1A", bas_label="1A")
    create_posted_bas_journal(
        client,
        token,
        company_id,
        quarter_period_id,
        cash_account_id,
        revenue_account_id,
        gst_account_id,
        sale_tax_code_id,
        gst_tax_code_id,
    )

    generate_periods = client.post(
        f"/api/companies/{company_id}/bas/periods/generate",
        headers=auth_header(token),
        json={"start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert generate_periods.status_code == 201, generate_periods.text
    bas_period_id = generate_periods.json()[0]["id"]

    update_bas_period = client.put(
        f"/api/companies/{company_id}/bas/periods/{bas_period_id}",
        headers=auth_header(token),
        json={"note": "Quarter ready"},
    )
    assert update_bas_period.status_code == 200, update_bas_period.text

    generate_bas_run = client.post(
        f"/api/companies/{company_id}/bas/runs",
        headers=auth_header(token),
        json={"bas_period_id": bas_period_id},
    )
    assert generate_bas_run.status_code == 201, generate_bas_run.text
    bas_run_id = generate_bas_run.json()["id"]

    update_bas_run = client.put(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}",
        headers=auth_header(token),
        json={"bas_period_id": bas_period_id},
    )
    assert update_bas_run.status_code == 200, update_bas_run.text

    create_adjustment = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments",
        headers=auth_header(token),
        json={"label": "G1", "amount": "5.00", "note": "Manual adjustment"},
    )
    assert create_adjustment.status_code == 201, create_adjustment.text
    list_adjustments = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments",
        headers=auth_header(token),
    )
    adjustment_id = list_adjustments.json()[0]["id"]
    update_adjustment = client.put(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments/{adjustment_id}",
        headers=auth_header(token),
        json={"label": "G1", "amount": "7.50", "note": "Updated adjustment"},
    )
    assert update_adjustment.status_code == 200, update_adjustment.text
    delete_adjustment = client.delete(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments/{adjustment_id}",
        headers=auth_header(token),
    )
    assert delete_adjustment.status_code == 204, delete_adjustment.text

    create_review_note = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes",
        headers=auth_header(token),
        json={"severity": "warning", "message": "Check GST coding", "related_label": "G1"},
    )
    assert create_review_note.status_code == 201, create_review_note.text
    review_note_id = create_review_note.json()["id"]
    update_review_note = client.put(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes/{review_note_id}",
        headers=auth_header(token),
        json={"severity": "warning", "message": "Updated note", "related_label": "G1"},
    )
    assert update_review_note.status_code == 200, update_review_note.text
    delete_review_note = client.delete(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes/{review_note_id}",
        headers=auth_header(token),
    )
    assert delete_review_note.status_code == 204, delete_review_note.text

    delete_bas_run = client.delete(f"/api/companies/{company_id}/bas/runs/{bas_run_id}", headers=auth_header(token))
    assert delete_bas_run.status_code == 204, delete_bas_run.text
    delete_bas_period = client.delete(
        f"/api/companies/{company_id}/bas/periods/{bas_period_id}",
        headers=auth_header(token),
    )
    assert delete_bas_period.status_code == 204, delete_bas_period.text

    asset_account_id = create_account(client, token, company_id, code="1500", name="Plant Equipment", account_type="asset")
    accumulated_dep_account_id = create_account(
        client,
        token,
        company_id,
        code="1590",
        name="Accumulated Depreciation",
        account_type="contra_asset",
    )
    dep_expense_account_id = create_account(
        client,
        token,
        company_id,
        code="6100",
        name="Depreciation Expense",
        account_type="expense",
    )
    create_asset = client.post(
        f"/api/companies/{company_id}/fixed-assets",
        headers=auth_header(token),
        json={
            "asset_code": "LAPTOP-01",
            "name": "Laptop",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "2400.00",
            "salvage_value": "0.00",
            "useful_life_months": 24,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_dep_account_id,
            "depreciation_expense_account_id": dep_expense_account_id,
            "note": "Initial asset"
        },
    )
    assert create_asset.status_code == 201, create_asset.text
    fixed_asset_id = create_asset.json()["id"]

    update_asset = client.put(
        f"/api/companies/{company_id}/fixed-assets/{fixed_asset_id}",
        headers=auth_header(token),
        json={
            "asset_code": "LAPTOP-01",
            "name": "Laptop Updated",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "2400.00",
            "salvage_value": "0.00",
            "useful_life_months": 24,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_dep_account_id,
            "depreciation_expense_account_id": dep_expense_account_id,
            "note": "Updated asset"
        },
    )
    assert update_asset.status_code == 200, update_asset.text
    delete_asset = client.delete(f"/api/companies/{company_id}/fixed-assets/{fixed_asset_id}", headers=auth_header(token))
    assert delete_asset.status_code == 204, delete_asset.text

    create_run_asset = client.post(
        f"/api/companies/{company_id}/fixed-assets",
        headers=auth_header(token),
        json={
            "asset_code": "LAPTOP-02",
            "name": "Laptop Run",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "2400.00",
            "salvage_value": "0.00",
            "useful_life_months": 24,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_dep_account_id,
            "depreciation_expense_account_id": dep_expense_account_id,
            "note": "Run asset"
        },
    )
    assert create_run_asset.status_code == 201, create_run_asset.text
    create_dep_run = client.post(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs",
        headers=auth_header(token),
        json={
            "accounting_period_id": year_period_id,
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "note": "Initial run"
        },
    )
    assert create_dep_run.status_code == 201, create_dep_run.text
    depreciation_run_id = create_dep_run.json()["id"]
    update_dep_run = client.put(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs/{depreciation_run_id}",
        headers=auth_header(token),
        json={
            "accounting_period_id": year_period_id,
            "start_date": "2026-07-01",
            "end_date": "2026-08-31",
            "note": "Updated run"
        },
    )
    assert update_dep_run.status_code == 200, update_dep_run.text
    delete_dep_run = client.delete(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs/{depreciation_run_id}",
        headers=auth_header(token),
    )
    assert delete_dep_run.status_code == 204, delete_dep_run.text

    create_tax_pack = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs",
        headers=auth_header(token),
        json={"accounting_period_id": year_period_id, "note": "Initial pack"},
    )
    assert create_tax_pack.status_code == 201, create_tax_pack.text
    tax_pack_id = create_tax_pack.json()["id"]
    update_tax_pack = client.put(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}",
        headers=auth_header(token),
        json={"accounting_period_id": year_period_id, "note": "Updated pack"},
    )
    assert update_tax_pack.status_code == 200, update_tax_pack.text

    create_tax_adjustment = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/adjustments",
        headers=auth_header(token),
        json={"label": "Non-deductible", "amount": "25.00", "note": "Initial adjustment"},
    )
    assert create_tax_adjustment.status_code == 201, create_tax_adjustment.text
    list_tax_adjustments = client.get(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/adjustments",
        headers=auth_header(token),
    )
    tax_adjustment_id = list_tax_adjustments.json()[0]["id"]
    update_tax_adjustment = client.put(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/adjustments/{tax_adjustment_id}",
        headers=auth_header(token),
        json={"label": "Non-deductible", "amount": "30.00", "note": "Updated adjustment"},
    )
    assert update_tax_adjustment.status_code == 200, update_tax_adjustment.text
    delete_tax_adjustment = client.delete(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/adjustments/{tax_adjustment_id}",
        headers=auth_header(token),
    )
    assert delete_tax_adjustment.status_code == 204, delete_tax_adjustment.text

    create_tax_note = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/notes",
        headers=auth_header(token),
        json={"note_type": "review", "message": "Initial review note"},
    )
    assert create_tax_note.status_code == 201, create_tax_note.text
    tax_note_id = create_tax_note.json()["id"]
    update_tax_note = client.put(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/notes/{tax_note_id}",
        headers=auth_header(token),
        json={"note_type": "review", "message": "Updated review note"},
    )
    assert update_tax_note.status_code == 200, update_tax_note.text
    delete_tax_note = client.delete(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/notes/{tax_note_id}",
        headers=auth_header(token),
    )
    assert delete_tax_note.status_code == 204, delete_tax_note.text

    create_tax_exception = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/exceptions",
        headers=auth_header(token),
        json={"severity": "warning", "message": "Initial exception"},
    )
    assert create_tax_exception.status_code == 201, create_tax_exception.text
    tax_exception_id = create_tax_exception.json()["id"]
    update_tax_exception = client.put(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/exceptions/{tax_exception_id}",
        headers=auth_header(token),
        json={"severity": "warning", "message": "Updated exception"},
    )
    assert update_tax_exception.status_code == 200, update_tax_exception.text
    delete_tax_exception = client.delete(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}/exceptions/{tax_exception_id}",
        headers=auth_header(token),
    )
    assert delete_tax_exception.status_code == 204, delete_tax_exception.text

    delete_tax_pack = client.delete(
        f"/api/companies/{company_id}/tax-workpapers/packs/{tax_pack_id}",
        headers=auth_header(token),
    )
    assert delete_tax_pack.status_code == 204, delete_tax_pack.text
