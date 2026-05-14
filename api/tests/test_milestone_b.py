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


def create_company(client, token: str):
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


def create_posted_journal(client, token: str, company_id: str, period_id: str, debit_account_id: str, credit_account_id: str):
    response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-02",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Journal for reconciliation",
            "lines": [
                {"account_id": debit_account_id, "debit_amount": "100.00", "credit_amount": "0.00"},
                {"account_id": credit_account_id, "debit_amount": "0.00", "credit_amount": "100.00"},
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
    return journal_id


def create_bank_account(client, token: str, company_id: str):
    response = client.post(
        f"/api/companies/{company_id}/bank-accounts",
        headers=auth_header(token),
        json={
            "name": "Main Operating",
            "bank_name": "Example Bank",
            "bsb": "123-456",
            "account_number_masked": "xxxx1234",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_upload_document_and_link_to_journal(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_id = create_posted_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)

    upload_response = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("invoice.txt", b"invoice-support", "text/plain")},
        data={"note": "Invoice attachment"},
    )
    assert upload_response.status_code == 201, upload_response.text
    document_id = upload_response.json()["id"]

    link_response = client.post(
        f"/api/companies/{company_id}/documents/{document_id}/links",
        headers=auth_header(token),
        json={
            "entity_type": "journal_entry",
            "entity_id": journal_id,
            "note": "Supports the posted journal",
        },
    )
    assert link_response.status_code == 201, link_response.text
    assert link_response.json()["entity_type"] == "journal_entry"

    download_response = client.get(
        f"/api/companies/{company_id}/documents/{document_id}/download",
        headers=auth_header(token),
    )
    assert download_response.status_code == 200, download_response.text
    assert download_response.content == b"invoice-support"


def test_bank_import_stages_rows_and_flags_duplicates(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    bank_account_id = create_bank_account(client, token, company_id)
    csv_content = b"date,description,debit,credit,reference\n2026-07-01,Deposit,0.00,100.00,DEP001\n"

    first_import_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("import.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert first_import_response.status_code == 201, first_import_response.text
    first_session_id = first_import_response.json()["id"]

    first_rows_response = client.get(
        f"/api/companies/{company_id}/bank-imports/{first_session_id}/rows",
        headers=auth_header(token),
    )
    assert first_rows_response.status_code == 200, first_rows_response.text
    assert first_rows_response.json()[0]["status"] == "staged"

    second_import_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("import.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert second_import_response.status_code == 201, second_import_response.text
    second_session_id = second_import_response.json()["id"]

    second_rows_response = client.get(
        f"/api/companies/{company_id}/bank-imports/{second_session_id}/rows",
        headers=auth_header(token),
    )
    assert second_rows_response.status_code == 200, second_rows_response.text
    assert second_rows_response.json()[0]["status"] == "duplicate"


def test_reconciliation_session_matches_confirmed_bank_row(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_id = create_posted_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)
    bank_account_id = create_bank_account(client, token, company_id)
    csv_content = b"date,description,debit,credit,reference\n2026-07-02,Customer deposit,0.00,100.00,DEP100\n"

    upload_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("import.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert upload_response.status_code == 201, upload_response.text
    import_session_id = upload_response.json()["id"]

    confirm_response = client.post(
        f"/api/companies/{company_id}/bank-imports/{import_session_id}/confirm",
        headers=auth_header(token),
        json={"note": "Ready to reconcile"},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    assert confirm_response.json()["status"] == "confirmed"

    reconciliation_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id},
    )
    assert reconciliation_response.status_code == 201, reconciliation_response.text
    reconciliation_session_id = reconciliation_response.json()["id"]

    items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/items",
        headers=auth_header(token),
    )
    assert items_response.status_code == 200, items_response.text
    item_id = items_response.json()[0]["id"]

    match_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/items/{item_id}/match",
        headers=auth_header(token),
        json={"matched_journal_entry_id": journal_id, "note": "Matched to posted sale"},
    )
    assert match_response.status_code == 200, match_response.text
    assert match_response.json()["status"] == "matched"

    summary_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/summary",
        headers=auth_header(token),
    )
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["matched_items"] == 1
    assert summary_response.json()["unmatched_items"] == 0

    complete_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/complete",
        headers=auth_header(token),
        json={"note": "Completed cleanly"},
    )
    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "completed"


def test_document_listing_link_listing_and_invalid_link_target(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_id = create_posted_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)

    initial_documents = client.get(f"/api/companies/{company_id}/documents", headers=auth_header(token))
    assert initial_documents.status_code == 200, initial_documents.text
    assert initial_documents.json() == []

    upload_response = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("invoice.txt", b"invoice-support", "text/plain")},
        data={"note": "Invoice attachment"},
    )
    assert upload_response.status_code == 201, upload_response.text
    document_id = upload_response.json()["id"]

    documents_after_upload = client.get(f"/api/companies/{company_id}/documents", headers=auth_header(token))
    assert documents_after_upload.status_code == 200, documents_after_upload.text
    assert [document["id"] for document in documents_after_upload.json()] == [document_id]

    invalid_link_response = client.post(
        f"/api/companies/{company_id}/documents/{document_id}/links",
        headers=auth_header(token),
        json={
            "entity_type": "journal_entry",
            "entity_id": "11111111-1111-1111-1111-111111111111",
            "note": "Missing link target",
        },
    )
    assert invalid_link_response.status_code == 404, invalid_link_response.text
    assert invalid_link_response.json()["detail"] == "Link target not found"

    link_response = client.post(
        f"/api/companies/{company_id}/documents/{document_id}/links",
        headers=auth_header(token),
        json={
            "entity_type": "journal_entry",
            "entity_id": journal_id,
            "note": "Supports the posted journal",
        },
    )
    assert link_response.status_code == 201, link_response.text

    links_response = client.get(
        f"/api/companies/{company_id}/documents/{document_id}/links",
        headers=auth_header(token),
    )
    assert links_response.status_code == 200, links_response.text
    assert len(links_response.json()) == 1
    assert links_response.json()[0]["entity_type"] == "journal_entry"


def test_bank_account_import_listing_and_csv_validation(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)

    initial_bank_accounts = client.get(f"/api/companies/{company_id}/bank-accounts", headers=auth_header(token))
    assert initial_bank_accounts.status_code == 200, initial_bank_accounts.text
    assert initial_bank_accounts.json() == []

    bank_account_id = create_bank_account(client, token, company_id)

    bank_accounts_after_create = client.get(
        f"/api/companies/{company_id}/bank-accounts",
        headers=auth_header(token),
    )
    assert bank_accounts_after_create.status_code == 200, bank_accounts_after_create.text
    assert [account["id"] for account in bank_accounts_after_create.json()] == [bank_account_id]

    invalid_csv_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("invalid.csv", b"date,debit,credit\n2026-07-01,0.00,100.00\n", "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert invalid_csv_response.status_code == 400, invalid_csv_response.text
    assert invalid_csv_response.json()["detail"] == "CSV is missing required columns"

    empty_csv_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("empty.csv", b"", "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert empty_csv_response.status_code == 400, empty_csv_response.text
    assert empty_csv_response.json()["detail"] == "Uploaded CSV is empty"

    csv_content = b"date,description,debit,credit,reference\n2026-07-01,Deposit,0.00,100.00,DEP001\n"
    import_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("import.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert import_response.status_code == 201, import_response.text
    import_session_id = import_response.json()["id"]

    import_list_response = client.get(
        f"/api/companies/{company_id}/bank-imports",
        headers=auth_header(token),
    )
    assert import_list_response.status_code == 200, import_list_response.text
    assert [session["id"] for session in import_list_response.json()] == [import_session_id]

    rows_response = client.get(
        f"/api/companies/{company_id}/bank-imports/{import_session_id}/rows",
        headers=auth_header(token),
    )
    assert rows_response.status_code == 200, rows_response.text
    assert len(rows_response.json()) == 1
    assert rows_response.json()[0]["description"] == "Deposit"


def test_commonwealth_bank_csv_without_headers_is_auto_converted_on_upload(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    bank_account_id = create_bank_account(client, token, company_id)
    commbank_csv = (
        b'08/05/2026,"-314529.94","Wdl Branch PORT MELBOURNE","+36994.67"\n'
        b'08/05/2026,"+330000.00","Transfer from CommBank app","+351524.61"\n'
    )

    import_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("commbank.csv", commbank_csv, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert import_response.status_code == 201, import_response.text
    import_session_id = import_response.json()["id"]

    rows_response = client.get(
        f"/api/companies/{company_id}/bank-imports/{import_session_id}/rows",
        headers=auth_header(token),
    )
    assert rows_response.status_code == 200, rows_response.text
    rows = rows_response.json()
    assert len(rows) == 2
    assert rows[0]["transaction_date"] == "2026-05-08"
    assert rows[0]["description"] == "Wdl Branch PORT MELBOURNE"
    assert rows[0]["debit_amount"] == "314529.94"
    assert rows[0]["credit_amount"] == "0.00"
    assert rows[1]["description"] == "Transfer from CommBank app"
    assert rows[1]["debit_amount"] == "0.00"
    assert rows[1]["credit_amount"] == "330000.00"


def test_reconciliation_ignore_and_completion_block_until_resolved(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_id = create_posted_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)
    bank_account_id = create_bank_account(client, token, company_id)
    csv_content = (
        b"date,description,debit,credit,reference\n"
        b"2026-07-02,Customer deposit,0.00,100.00,DEP100\n"
        b"2026-07-03,Unknown receipt,0.00,50.00,DEP050\n"
    )

    upload_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("import.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert upload_response.status_code == 201, upload_response.text
    import_session_id = upload_response.json()["id"]

    confirm_response = client.post(
        f"/api/companies/{company_id}/bank-imports/{import_session_id}/confirm",
        headers=auth_header(token),
        json={"note": "Ready to reconcile"},
    )
    assert confirm_response.status_code == 200, confirm_response.text

    reconciliation_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id},
    )
    assert reconciliation_response.status_code == 201, reconciliation_response.text
    reconciliation_session_id = reconciliation_response.json()["id"]

    reconciliation_sessions = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
    )
    assert reconciliation_sessions.status_code == 200, reconciliation_sessions.text
    assert [session["id"] for session in reconciliation_sessions.json()] == [reconciliation_session_id]

    items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/items",
        headers=auth_header(token),
    )
    assert items_response.status_code == 200, items_response.text
    first_item_id = items_response.json()[0]["id"]
    second_item_id = items_response.json()[1]["id"]

    match_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/items/{first_item_id}/match",
        headers=auth_header(token),
        json={"matched_journal_entry_id": journal_id, "note": "Matched to posted sale"},
    )
    assert match_response.status_code == 200, match_response.text
    assert match_response.json()["status"] == "matched"

    blocked_complete_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/complete",
        headers=auth_header(token),
        json={"note": "Should fail while unmatched remains"},
    )
    assert blocked_complete_response.status_code == 400, blocked_complete_response.text
    assert blocked_complete_response.json()["detail"] == "Unmatched reconciliation items remain"

    ignore_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/items/{second_item_id}/ignore",
        headers=auth_header(token),
        json={"reason": "Not a ledger item"},
    )
    assert ignore_response.status_code == 200, ignore_response.text
    assert ignore_response.json()["status"] == "ignored"

    summary_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/summary",
        headers=auth_header(token),
    )
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json() == {
        "total_items": 2,
        "unmatched_items": 0,
        "matched_items": 1,
        "ignored_items": 1,
    }

    complete_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/complete",
        headers=auth_header(token),
        json={"note": "Completed after resolving all items"},
    )
    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "completed"
