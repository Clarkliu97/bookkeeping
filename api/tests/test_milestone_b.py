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


def create_posted_journal(
    client,
    token: str,
    company_id: str,
    period_id: str,
    debit_account_id: str,
    credit_account_id: str,
    *,
    entry_date: str = "2026-07-02",
    description: str = "Journal for reconciliation",
    amount: str = "100.00",
):
    response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": entry_date,
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": description,
            "lines": [
                {"account_id": debit_account_id, "debit_amount": amount, "credit_amount": "0.00"},
                {
                    "account_id": credit_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": amount,
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
    return journal_id


def create_bank_account(
    client,
    token: str,
    company_id: str,
    *,
    ledger_account_id: str | None = None,
):
    response = client.post(
        f"/api/companies/{company_id}/bank-accounts",
        headers=auth_header(token),
        json={
            "name": "Main Operating",
            "bank_name": "Example Bank",
            "bsb": "123-456",
            "account_number_masked": "xxxx1234",
            "ledger_account_id": ledger_account_id,
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
    journal_id = create_posted_journal(
        client, token, company_id, period_id, cash_account_id, revenue_account_id
    )

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
    csv_content = (
        b"date,description,debit,credit,reference\n2026-07-01,Deposit,0.00,100.00,DEP001\n"
    )

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
    journal_id = create_posted_journal(
        client, token, company_id, period_id, cash_account_id, revenue_account_id
    )
    bank_account_id = create_bank_account(client, token, company_id)
    csv_content = (
        b"date,description,debit,credit,reference\n2026-07-02,Customer deposit,0.00,100.00,DEP100\n"
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
    first_item = items_response.json()[0]
    assert first_item["bank_row"]["description"] == "Customer deposit"
    assert first_item["bank_row"]["credit_amount"] == "100.00"
    item_id = first_item["id"]

    match_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/items/{item_id}/match",
        headers=auth_header(token),
        json={"matched_journal_entry_id": journal_id, "note": "Matched to posted sale"},
    )
    assert match_response.status_code == 200, match_response.text
    assert match_response.json()["status"] == "matched"
    assert (
        match_response.json()["matched_journal_entry"]["description"]
        == "Journal for reconciliation"
    )

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


def test_reconciliation_period_scopes_statement_rows_and_posted_journals(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    first_period_id = create_period(client, token, company_id)
    second_period_response = client.post(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
        json={
            "name": "FY26-Q2",
            "period_type": "quarter",
            "start_date": "2026-10-01",
            "end_date": "2026-12-31",
        },
    )
    assert second_period_response.status_code == 201, second_period_response.text
    second_period_id = second_period_response.json()["id"]
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    first_period_journal_id = create_posted_journal(
        client,
        token,
        company_id,
        first_period_id,
        cash_account_id,
        revenue_account_id,
        description="July receipt",
    )
    second_period_journal_id = create_posted_journal(
        client,
        token,
        company_id,
        second_period_id,
        cash_account_id,
        revenue_account_id,
        entry_date="2026-10-02",
        description="October receipt",
    )
    bank_account_id = create_bank_account(client, token, company_id)
    csv_content = (
        b"date,description,debit,credit,reference\n"
        b"2026-07-02,July customer deposit,0.00,100.00,JUL100\n"
        b"2026-10-02,October customer deposit,0.00,100.00,OCT100\n"
    )
    upload_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("two-periods.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert upload_response.status_code == 201, upload_response.text
    confirm_response = client.post(
        f"/api/companies/{company_id}/bank-imports/{upload_response.json()['id']}/confirm",
        headers=auth_header(token),
        json={"note": "Ready for period-scoped reconciliation"},
    )
    assert confirm_response.status_code == 200, confirm_response.text

    session_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": first_period_id},
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]
    first_items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    )
    assert first_items_response.status_code == 200, first_items_response.text
    first_items = first_items_response.json()
    assert [item["bank_row"]["description"] for item in first_items] == ["July customer deposit"]

    out_of_period_match = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items/{first_items[0]['id']}/match",
        headers=auth_header(token),
        json={"matched_journal_entry_id": second_period_journal_id},
    )
    assert out_of_period_match.status_code == 400, out_of_period_match.text
    assert (
        out_of_period_match.json()["detail"]
        == "Posted journal entry is outside the reconciliation accounting period"
    )

    update_period_response = client.put(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}",
        headers=auth_header(token),
        json={"accounting_period_id": second_period_id, "note": "Moved to Q2 before matching"},
    )
    assert update_period_response.status_code == 200, update_period_response.text
    second_items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    )
    assert second_items_response.status_code == 200, second_items_response.text
    second_items = second_items_response.json()
    assert [item["bank_row"]["description"] for item in second_items] == [
        "October customer deposit"
    ]

    second_out_of_period_match = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items/{second_items[0]['id']}/match",
        headers=auth_header(token),
        json={"matched_journal_entry_id": first_period_journal_id},
    )
    assert second_out_of_period_match.status_code == 400, second_out_of_period_match.text
    valid_match = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items/{second_items[0]['id']}/match",
        headers=auth_header(token),
        json={"matched_journal_entry_id": second_period_journal_id},
    )
    assert valid_match.status_code == 200, valid_match.text

    blocked_period_change = client.put(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}",
        headers=auth_header(token),
        json={"accounting_period_id": first_period_id, "note": "Should be blocked"},
    )
    assert blocked_period_change.status_code == 409, blocked_period_change.text
    assert blocked_period_change.json()["detail"] == (
        "Accounting period cannot be changed after reconciliation items are resolved"
    )
    summary_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/summary",
        headers=auth_header(token),
    )
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json() == {
        "total_items": 1,
        "unmatched_items": 0,
        "matched_items": 1,
        "ignored_items": 0,
    }


def test_grouped_reconciliation_supports_all_multi_source_relationships(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_specs = [
        ("N-to-N journal A", "70.00"),
        ("N-to-N journal B", "30.00"),
        ("One-to-N journal A", "60.00"),
        ("One-to-N journal B", "40.00"),
        ("N-to-one journal", "50.00"),
    ]
    journal_ids = [
        create_posted_journal(
            client,
            token,
            company_id,
            period_id,
            cash_account_id,
            revenue_account_id,
            description=description,
            amount=amount,
        )
        for description, amount in journal_specs
    ]
    bank_account_id = create_bank_account(
        client,
        token,
        company_id,
        ledger_account_id=cash_account_id,
    )
    csv_content = (
        b"date,description,debit,credit,reference\n"
        b"2026-07-02,N-to-N bank A,0.00,40.00,GROUP-A\n"
        b"2026-07-03,N-to-N bank B,0.00,60.00,GROUP-B\n"
        b"2026-07-04,One-to-N bank,0.00,100.00,GROUP-C\n"
        b"2026-07-05,N-to-one bank A,0.00,20.00,GROUP-D\n"
        b"2026-07-06,N-to-one bank B,0.00,30.00,GROUP-E\n"
    )
    upload_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("grouped.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert upload_response.status_code == 201, upload_response.text
    confirm_response = client.post(
        f"/api/companies/{company_id}/bank-imports/{upload_response.json()['id']}/confirm",
        headers=auth_header(token),
        json={"note": "Ready for grouped reconciliation"},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    session_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id},
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]
    items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    )
    assert items_response.status_code == 200, items_response.text
    item_ids = {item["bank_row"]["description"]: item["id"] for item in items_response.json()}

    group_payloads = [
        {
            "bank_allocations": [
                {"reconciliation_item_id": item_ids["N-to-N bank A"]},
                {"reconciliation_item_id": item_ids["N-to-N bank B"]},
            ],
            "journal_allocations": [
                {"journal_entry_id": journal_ids[0]},
                {"journal_entry_id": journal_ids[1]},
            ],
            "note": "Two bank rows to two journals",
        },
        {
            "bank_allocations": [{"reconciliation_item_id": item_ids["One-to-N bank"]}],
            "journal_allocations": [
                {"journal_entry_id": journal_ids[2]},
                {"journal_entry_id": journal_ids[3]},
            ],
            "note": "One bank row to two journals",
        },
        {
            "bank_allocations": [
                {"reconciliation_item_id": item_ids["N-to-one bank A"]},
                {"reconciliation_item_id": item_ids["N-to-one bank B"]},
            ],
            "journal_allocations": [{"journal_entry_id": journal_ids[4]}],
            "note": "Two bank rows to one journal",
        },
    ]
    created_groups = []
    for payload in group_payloads:
        group_response = client.post(
            f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups",
            headers=auth_header(token),
            json=payload,
        )
        assert group_response.status_code == 201, group_response.text
        created_groups.append(group_response.json())

    assert [
        (len(group["bank_allocations"]), len(group["journal_allocations"]))
        for group in created_groups
    ] == [(2, 2), (1, 2), (2, 1)]
    assert all(group["difference_amount"] == "0.00" for group in created_groups)
    summary_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/summary",
        headers=auth_header(token),
    )
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["matched_items"] == 5
    assert summary_response.json()["unmatched_items"] == 0

    duplicate_allocation = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups",
        headers=auth_header(token),
        json={
            "bank_allocations": [{"reconciliation_item_id": item_ids["One-to-N bank"]}],
            "journal_allocations": [{"journal_entry_id": journal_ids[4]}],
        },
    )
    assert duplicate_allocation.status_code == 409, duplicate_allocation.text

    delete_group_response = client.delete(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups/{created_groups[0]['id']}",
        headers=auth_header(token),
    )
    assert delete_group_response.status_code == 204, delete_group_response.text
    remaining_groups_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups",
        headers=auth_header(token),
    )
    assert remaining_groups_response.status_code == 200, remaining_groups_response.text
    assert len(remaining_groups_response.json()) == 2
    updated_items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    )
    updated_statuses = {
        item["bank_row"]["description"]: item["status"] for item in updated_items_response.json()
    }
    assert updated_statuses["N-to-N bank A"] == "unmatched"
    assert updated_statuses["N-to-N bank B"] == "unmatched"

    partial_group_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups",
        headers=auth_header(token),
        json={
            "bank_allocations": [
                {
                    "reconciliation_item_id": item_ids["N-to-N bank A"],
                    "allocated_amount": "30.00",
                }
            ],
            "journal_allocations": [
                {"journal_entry_id": journal_ids[0], "allocated_amount": "30.00"}
            ],
            "note": "First partial settlement",
        },
    )
    assert partial_group_response.status_code == 201, partial_group_response.text
    assert partial_group_response.json()["journal_allocations"][0]["ledger_account_id"] == str(
        cash_account_id
    )
    partially_allocated_items = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    ).json()
    assert (
        next(
            item
            for item in partially_allocated_items
            if item["bank_row"]["description"] == "N-to-N bank A"
        )["status"]
        == "unmatched"
    )

    ignore_partial_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items/{item_ids['N-to-N bank A']}/ignore",
        headers=auth_header(token),
        json={"reason": "Should require unmatching first"},
    )
    assert ignore_partial_response.status_code == 409, ignore_partial_response.text

    undocumented_tolerance_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups",
        headers=auth_header(token),
        json={
            "bank_allocations": [
                {
                    "reconciliation_item_id": item_ids["N-to-N bank A"],
                    "allocated_amount": "10.00",
                }
            ],
            "journal_allocations": [
                {"journal_entry_id": journal_ids[0], "allocated_amount": "9.00"}
            ],
            "tolerance_amount": "1.00",
        },
    )
    assert undocumented_tolerance_response.status_code == 400
    assert undocumented_tolerance_response.json()["detail"] == (
        "A note is required when accepting a tolerance difference"
    )

    overlapping_session_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id},
    )
    assert overlapping_session_response.status_code == 201, overlapping_session_response.text
    overlapping_session_id = overlapping_session_response.json()["id"]
    overlapping_items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{overlapping_session_id}/items",
        headers=auth_header(token),
    )
    assert overlapping_items_response.status_code == 200, overlapping_items_response.text
    assert overlapping_items_response.json() == []
    delete_overlapping_session = client.delete(
        f"/api/companies/{company_id}/reconciliation-sessions/{overlapping_session_id}",
        headers=auth_header(token),
    )
    assert delete_overlapping_session.status_code == 204, delete_overlapping_session.text

    final_partial_group_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups",
        headers=auth_header(token),
        json={
            "bank_allocations": [
                {
                    "reconciliation_item_id": item_ids["N-to-N bank A"],
                    "allocated_amount": "10.00",
                }
            ],
            "journal_allocations": [
                {"journal_entry_id": journal_ids[0], "allocated_amount": "10.00"}
            ],
            "note": "Final partial settlement",
        },
    )
    assert final_partial_group_response.status_code == 201, final_partial_group_response.text
    fully_allocated_items = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    ).json()
    fully_allocated_item = next(
        item for item in fully_allocated_items if item["bank_row"]["description"] == "N-to-N bank A"
    )
    assert fully_allocated_item["status"] == "matched"
    assert fully_allocated_item["matched_journal_entry_id"] is None


def test_grouped_reconciliation_supports_mixed_direction_net_settlements(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    fee_account_id = create_account(client, token, company_id, "6000", "Settlement fees", "expense")
    receipt_journal_id = create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id,
        revenue_account_id,
        description="Gross settlement receipts",
        amount="120.00",
    )
    fee_journal_id = create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        fee_account_id,
        cash_account_id,
        description="Settlement fee payment",
        amount="20.00",
    )
    bank_account_id = create_bank_account(
        client,
        token,
        company_id,
        ledger_account_id=cash_account_id,
    )
    upload_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={
            "file": (
                "net-settlement.csv",
                b"date,description,debit,credit,reference\n"
                b"2026-07-08,Net processor payout,0.00,100.00,NET-100\n",
                "text/csv",
            )
        },
        data={"bank_account_id": bank_account_id},
    )
    assert upload_response.status_code == 201, upload_response.text
    confirm_response = client.post(
        f"/api/companies/{company_id}/bank-imports/{upload_response.json()['id']}/confirm",
        headers=auth_header(token),
        json={"note": "Net settlement ready"},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    session_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id},
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]
    items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    )
    assert items_response.status_code == 200, items_response.text
    item_id = items_response.json()[0]["id"]

    group_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/match-groups",
        headers=auth_header(token),
        json={
            "bank_allocations": [{"reconciliation_item_id": item_id}],
            "journal_allocations": [
                {"journal_entry_id": receipt_journal_id},
                {"journal_entry_id": fee_journal_id},
            ],
            "note": "Gross receipts less settlement fees equal the net payout",
        },
    )
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()
    assert group["bank_total"] == "100.00"
    assert group["journal_total"] == "100.00"
    assert group["difference_amount"] == "0.00"
    assert {allocation["allocated_amount"] for allocation in group["journal_allocations"]} == {
        "-20.00",
        "120.00",
    }
    summary_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/summary",
        headers=auth_header(token),
    )
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["matched_items"] == 1
    assert summary_response.json()["unmatched_items"] == 0


def test_auto_reconciliation_matches_all_supported_cardinalities_and_leaves_uncertain_items(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")

    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id,
        revenue_account_id,
        entry_date="2026-07-02",
        description="One-to-one within tolerance",
        amount="100.99",
    )
    for description, amount in (("One-to-N A", "80.00"), ("One-to-N B", "123.00")):
        create_posted_journal(
            client,
            token,
            company_id,
            period_id,
            cash_account_id,
            revenue_account_id,
            entry_date="2026-07-10",
            description=description,
            amount=amount,
        )

    detailed_journal_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-20",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Detailed N-to-one journal",
            "lines": [
                {
                    "account_id": cash_account_id,
                    "debit_amount": "716.00",
                    "credit_amount": "0.00",
                },
                {
                    "account_id": revenue_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": "307.00",
                },
                {
                    "account_id": revenue_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": "409.00",
                },
            ],
        },
    )
    assert detailed_journal_response.status_code == 201, detailed_journal_response.text
    detailed_journal_id = detailed_journal_response.json()["id"]
    post_detailed_response = client.post(
        f"/api/companies/{company_id}/journals/{detailed_journal_id}/post",
        headers=auth_header(token),
    )
    assert post_detailed_response.status_code == 200, post_detailed_response.text
    aggregate_alternative_id = create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id,
        revenue_account_id,
        entry_date="2026-07-20",
        description="Aggregate N-to-one alternative",
        amount="716.00",
    )

    for description, amount in (("N-to-N A", "701.00"), ("N-to-N B", "433.00")):
        create_posted_journal(
            client,
            token,
            company_id,
            period_id,
            cash_account_id,
            revenue_account_id,
            entry_date="2026-08-01",
            description=description,
            amount=amount,
        )
    for description in ("Ambiguous journal A", "Ambiguous journal B"):
        create_posted_journal(
            client,
            token,
            company_id,
            period_id,
            cash_account_id,
            revenue_account_id,
            entry_date="2026-09-01",
            description=description,
            amount="555.00",
        )
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id,
        revenue_account_id,
        entry_date="2026-08-25",
        description="Outside date window",
        amount="881.00",
    )

    bank_account_id = create_bank_account(
        client,
        token,
        company_id,
        ledger_account_id=cash_account_id,
    )
    csv_content = (
        b"date,description,debit,credit,reference\n"
        b"2026-07-02,Auto 1-to-1,0.00,101.00,AUTO-11\n"
        b"2026-07-10,Auto 1-to-N,0.00,203.00,AUTO-1N\n"
        b"2026-07-20,Auto N-to-1 A,0.00,307.00,AUTO-N1A\n"
        b"2026-07-20,Auto N-to-1 B,0.00,409.00,AUTO-N1B\n"
        b"2026-08-01,Auto N-to-N A,0.00,521.00,AUTO-NNA\n"
        b"2026-08-01,Auto N-to-N B,0.00,613.00,AUTO-NNB\n"
        b"2026-09-01,Ambiguous statement,0.00,555.00,AUTO-AMB\n"
        b"2026-08-15,Outside date statement,0.00,881.00,AUTO-DATE\n"
        b"2026-09-10,No amount match,0.00,997.00,AUTO-NONE\n"
    )
    upload_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={"file": ("auto-reconcile.csv", csv_content, "text/csv")},
        data={"bank_account_id": bank_account_id},
    )
    assert upload_response.status_code == 201, upload_response.text
    confirm_response = client.post(
        f"/api/companies/{company_id}/bank-imports/{upload_response.json()['id']}/confirm",
        headers=auth_header(token),
        json={"note": "Ready for automatic matching"},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    session_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id},
    )
    assert session_response.status_code == 201, session_response.text
    session_id = session_response.json()["id"]

    auto_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/auto-reconcile",
        headers=auth_header(token),
        json={"amount_tolerance": "0.01", "date_window_days": 2, "max_group_size": 2},
    )
    assert auto_response.status_code == 200, auto_response.text
    result = auto_response.json()
    assert result["considered_statement_items"] == 9
    assert result["matched_statement_items"] == 6
    assert result["created_group_count"] == 4
    assert len(result["unmatched_statement_item_ids"]) == 3
    assert len(result["ambiguous_statement_item_ids"]) == 1
    assert sorted(
        (len(group["bank_allocations"]), len(group["journal_allocations"]))
        for group in result["groups"]
    ) == [(1, 1), (1, 2), (2, 1), (2, 2)]
    one_to_one_group = next(
        group
        for group in result["groups"]
        if len(group["bank_allocations"]) == len(group["journal_allocations"]) == 1
    )
    assert one_to_one_group["difference_amount"] == "0.01"
    detailed_group = next(
        group
        for group in result["groups"]
        if len(group["bank_allocations"]) == 2 and len(group["journal_allocations"]) == 1
    )
    assert detailed_group["journal_allocations"][0]["journal_entry_id"] == str(
        detailed_journal_id
    )
    assert detailed_group["journal_allocations"][0]["journal_entry_id"] != str(
        aggregate_alternative_id
    )

    items_after_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{session_id}/items",
        headers=auth_header(token),
    )
    assert items_after_response.status_code == 200, items_after_response.text
    statuses = {
        item["bank_row"]["description"]: item["status"]
        for item in items_after_response.json()
    }
    assert sum(status == "matched" for status in statuses.values()) == 6
    assert statuses["Ambiguous statement"] == "unmatched"
    assert statuses["Outside date statement"] == "unmatched"
    assert statuses["No amount match"] == "unmatched"


def test_document_listing_link_listing_and_invalid_link_target(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_id = create_posted_journal(
        client, token, company_id, period_id, cash_account_id, revenue_account_id
    )

    initial_documents = client.get(
        f"/api/companies/{company_id}/documents", headers=auth_header(token)
    )
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

    documents_after_upload = client.get(
        f"/api/companies/{company_id}/documents", headers=auth_header(token)
    )
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

    initial_bank_accounts = client.get(
        f"/api/companies/{company_id}/bank-accounts", headers=auth_header(token)
    )
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

    csv_content = (
        b"date,description,debit,credit,reference\n2026-07-01,Deposit,0.00,100.00,DEP001\n"
    )
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
    journal_id = create_posted_journal(
        client, token, company_id, period_id, cash_account_id, revenue_account_id
    )
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
    assert [session["id"] for session in reconciliation_sessions.json()] == [
        reconciliation_session_id
    ]

    items_response = client.get(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/items",
        headers=auth_header(token),
    )
    assert items_response.status_code == 200, items_response.text
    items_payload = items_response.json()
    assert items_payload[0]["bank_row"]["description"] == "Customer deposit"
    assert items_payload[1]["bank_row"]["description"] == "Unknown receipt"
    first_item_id = items_payload[0]["id"]
    second_item_id = items_payload[1]["id"]

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
