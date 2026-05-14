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


def create_company(client, token: str, *, self_approval_mode: str = "warn", period_lock_policy: str = "after_approval") -> str:
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
                "period_lock_policy": period_lock_policy,
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


def submit_and_approve_period(client, token: str, company_id: str, period_id: str) -> None:
    submit_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/submit",
        headers=auth_header(token),
        json={"note": "Period ready"},
    )
    assert submit_response.status_code == 200, submit_response.text
    approve_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/approve",
        headers=auth_header(token),
        json={"note": "Period approved"},
    )
    assert approve_response.status_code == 200, approve_response.text


def submit_period(client, token: str, company_id: str, period_id: str) -> None:
    submit_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/submit",
        headers=auth_header(token),
        json={"note": "Period ready"},
    )
    assert submit_response.status_code == 200, submit_response.text


def approve_period(client, token: str, company_id: str, period_id: str) -> None:
    approve_response = client.post(
        f"/api/companies/{company_id}/periods/{period_id}/approve",
        headers=auth_header(token),
        json={"note": "Period approved"},
    )
    assert approve_response.status_code == 200, approve_response.text


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
) -> None:
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
    assert response.status_code == 201, response.text


def create_tax_code(client, token: str, company_id: str, *, code: str, label: str) -> str:
    response = client.post(
        f"/api/companies/{company_id}/tax-codes",
        headers=auth_header(token),
        json={
            "code": code,
            "name": f"Tax {code}",
            "rate": "0.10",
            "is_gst_applicable": True,
            "bas_label": label,
            "input_output_type": "output_taxed",
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


def create_posted_sale_journal(
    client,
    token: str,
    company_id: str,
    period_id: str,
    *,
    cash_account_id: str,
    revenue_account_id: str,
    gst_payable_account_id: str,
    g1_tax_code_id: str,
    one_a_tax_code_id: str,
) -> str:
    response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-15",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": "Sale with GST",
            "lines": [
                {"account_id": cash_account_id, "debit_amount": "110.00", "credit_amount": "0.00"},
                {
                    "account_id": revenue_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": "100.00",
                    "tax_code_id": g1_tax_code_id,
                },
                {
                    "account_id": gst_payable_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": "10.00",
                    "tax_code_id": one_a_tax_code_id,
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


def generate_bas_run(client, token: str, company_id: str) -> tuple[str, str]:
    periods_response = client.post(
        f"/api/companies/{company_id}/bas/periods/generate",
        headers=auth_header(token),
        json={"start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert periods_response.status_code == 201, periods_response.text
    bas_period_id = periods_response.json()[0]["id"]
    run_response = client.post(
        f"/api/companies/{company_id}/bas/runs",
        headers=auth_header(token),
        json={"bas_period_id": bas_period_id},
    )
    assert run_response.status_code == 201, run_response.text
    return bas_period_id, run_response.json()["id"]


def test_bas_run_calculates_adjusts_approves_and_exports(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token, period_lock_policy="after_approval")
    period_id = create_period(client, token, company_id)
    submit_and_approve_period(client, token, company_id, period_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    gst_payable_account_id = create_account(client, token, company_id, "2200", "GST Payable", "liability")
    g1_tax_code_id = create_tax_code(client, token, company_id, code="SALE_G1", label="G1")
    one_a_tax_code_id = create_tax_code(client, token, company_id, code="GST_1A", label="1A")
    create_posted_sale_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id=cash_account_id,
        revenue_account_id=revenue_account_id,
        gst_payable_account_id=gst_payable_account_id,
        g1_tax_code_id=g1_tax_code_id,
        one_a_tax_code_id=one_a_tax_code_id,
    )

    _, bas_run_id = generate_bas_run(client, token, company_id)
    bas_run_response = client.get(f"/api/companies/{company_id}/bas/runs/{bas_run_id}", headers=auth_header(token))
    assert bas_run_response.status_code == 200, bas_run_response.text
    bas_run_payload = bas_run_response.json()
    label_totals = {item["label"]: item for item in bas_run_payload["line_results"]}
    assert label_totals["G1"]["system_amount"] == "100.00"
    assert label_totals["1A"]["system_amount"] == "10.00"
    assert bas_run_payload["warning_count"] == 1

    adjustment_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments",
        headers=auth_header(token),
        json={"label": "G1", "amount": "5.00", "note": "Fuel rounding adjustment"},
    )
    assert adjustment_response.status_code == 201, adjustment_response.text
    updated_totals = {item["label"]: item for item in adjustment_response.json()["line_results"]}
    assert updated_totals["G1"]["final_amount"] == "105.00"

    submit_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/submit",
        headers=auth_header(token),
        json={"note": "Ready for BAS review"},
    )
    assert submit_response.status_code == 200, submit_response.text
    approve_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/approve",
        headers=auth_header(token),
        json={"note": "Approved for manual BAS entry"},
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["status"] == "approved"

    period_list_response = client.get(f"/api/companies/{company_id}/periods", headers=auth_header(token))
    assert period_list_response.status_code == 200, period_list_response.text
    assert period_list_response.json()[0]["status"] == "locked"

    csv_export_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports/csv",
        headers=auth_header(token),
    )
    assert csv_export_response.status_code == 201, csv_export_response.text
    csv_document_id = csv_export_response.json()["document_id"]

    pdf_export_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports/pdf",
        headers=auth_header(token),
    )
    assert pdf_export_response.status_code == 201, pdf_export_response.text

    exports_response = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports",
        headers=auth_header(token),
    )
    assert exports_response.status_code == 200, exports_response.text
    assert len(exports_response.json()) == 2

    download_response = client.get(
        f"/api/companies/{company_id}/documents/{csv_document_id}/download",
        headers=auth_header(token),
    )
    assert download_response.status_code == 200, download_response.text
    assert b"BAS Label" in download_response.content


def test_bas_self_approval_policy_block_is_enforced(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token, self_approval_mode="block")
    period_id = create_period(client, token, company_id)
    reviewer_user_id = create_user(
        client,
        token,
        email="reviewer@example.com",
        full_name="Reviewer User",
        password="StrongPass123",
    )
    grant_company_access(
        client,
        token,
        company_id,
        reviewer_user_id,
        can_prepare=False,
        can_review=True,
        can_approve=True,
    )
    reviewer_token = login(client, "reviewer@example.com", "StrongPass123")
    submit_period(client, token, company_id, period_id)
    approve_period(client, reviewer_token, company_id, period_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    gst_payable_account_id = create_account(client, token, company_id, "2200", "GST Payable", "liability")
    g1_tax_code_id = create_tax_code(client, token, company_id, code="SALE_G1", label="G1")
    one_a_tax_code_id = create_tax_code(client, token, company_id, code="GST_1A", label="1A")
    create_posted_sale_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id=cash_account_id,
        revenue_account_id=revenue_account_id,
        gst_payable_account_id=gst_payable_account_id,
        g1_tax_code_id=g1_tax_code_id,
        one_a_tax_code_id=one_a_tax_code_id,
    )
    _, bas_run_id = generate_bas_run(client, token, company_id)

    submit_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/submit",
        headers=auth_header(token),
        json={"note": "Submitted by same user"},
    )
    assert submit_response.status_code == 200, submit_response.text
    approve_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/approve",
        headers=auth_header(token),
        json={"note": "Attempt same-user approval"},
    )
    assert approve_response.status_code == 400, approve_response.text
    assert "self-approval" in approve_response.json()["detail"].lower()


def test_bas_after_export_lock_policy_locks_on_export_not_approval(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token, period_lock_policy="after_export")
    period_id = create_period(client, token, company_id)
    submit_and_approve_period(client, token, company_id, period_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    gst_payable_account_id = create_account(client, token, company_id, "2200", "GST Payable", "liability")
    g1_tax_code_id = create_tax_code(client, token, company_id, code="SALE_G1", label="G1")
    one_a_tax_code_id = create_tax_code(client, token, company_id, code="GST_1A", label="1A")
    create_posted_sale_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id=cash_account_id,
        revenue_account_id=revenue_account_id,
        gst_payable_account_id=gst_payable_account_id,
        g1_tax_code_id=g1_tax_code_id,
        one_a_tax_code_id=one_a_tax_code_id,
    )
    _, bas_run_id = generate_bas_run(client, token, company_id)

    submit_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/submit",
        headers=auth_header(token),
        json={"note": "Ready for review"},
    )
    assert submit_response.status_code == 200, submit_response.text
    approve_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/approve",
        headers=auth_header(token),
        json={"note": "Approved before export"},
    )
    assert approve_response.status_code == 200, approve_response.text

    periods_after_approval = client.get(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
    )
    assert periods_after_approval.status_code == 200, periods_after_approval.text
    assert periods_after_approval.json()[0]["status"] == "approved"

    export_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports/csv",
        headers=auth_header(token),
    )
    assert export_response.status_code == 201, export_response.text

    periods_after_export = client.get(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
    )
    assert periods_after_export.status_code == 200, periods_after_export.text
    assert periods_after_export.json()[0]["status"] == "locked"


def test_bas_generation_review_note_listing_and_adjustment_only_label(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    submit_and_approve_period(client, token, company_id, period_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    gst_payable_account_id = create_account(client, token, company_id, "2200", "GST Payable", "liability")
    g1_tax_code_id = create_tax_code(client, token, company_id, code="SALE_G1", label="G1")
    one_a_tax_code_id = create_tax_code(client, token, company_id, code="GST_1A", label="1A")
    create_posted_sale_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id=cash_account_id,
        revenue_account_id=revenue_account_id,
        gst_payable_account_id=gst_payable_account_id,
        g1_tax_code_id=g1_tax_code_id,
        one_a_tax_code_id=one_a_tax_code_id,
    )

    initial_periods_response = client.get(
        f"/api/companies/{company_id}/bas/periods",
        headers=auth_header(token),
    )
    assert initial_periods_response.status_code == 200, initial_periods_response.text
    assert initial_periods_response.json() == []

    invalid_generation_response = client.post(
        f"/api/companies/{company_id}/bas/periods/generate",
        headers=auth_header(token),
        json={"start_date": "2026-09-30", "end_date": "2026-07-01"},
    )
    assert invalid_generation_response.status_code == 400, invalid_generation_response.text
    assert invalid_generation_response.json()["detail"] == "Invalid BAS generation range"

    first_generation = client.post(
        f"/api/companies/{company_id}/bas/periods/generate",
        headers=auth_header(token),
        json={"start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert first_generation.status_code == 201, first_generation.text
    bas_period_id = first_generation.json()[0]["id"]

    second_generation = client.post(
        f"/api/companies/{company_id}/bas/periods/generate",
        headers=auth_header(token),
        json={"start_date": "2026-07-01", "end_date": "2026-09-30"},
    )
    assert second_generation.status_code == 201, second_generation.text
    assert [period["id"] for period in second_generation.json()] == [bas_period_id]

    listed_periods = client.get(f"/api/companies/{company_id}/bas/periods", headers=auth_header(token))
    assert listed_periods.status_code == 200, listed_periods.text
    assert [period["id"] for period in listed_periods.json()] == [bas_period_id]

    run_response = client.post(
        f"/api/companies/{company_id}/bas/runs",
        headers=auth_header(token),
        json={"bas_period_id": bas_period_id},
    )
    assert run_response.status_code == 201, run_response.text
    bas_run_id = run_response.json()["id"]
    assert run_response.json()["warning_count"] == 1

    initial_adjustments = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments",
        headers=auth_header(token),
    )
    assert initial_adjustments.status_code == 200, initial_adjustments.text
    assert initial_adjustments.json() == []

    initial_review_notes = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes",
        headers=auth_header(token),
    )
    assert initial_review_notes.status_code == 200, initial_review_notes.text
    assert len(initial_review_notes.json()) == 1
    assert initial_review_notes.json()[0]["severity"] == "warning"

    added_review_note = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes",
        headers=auth_header(token),
        json={"severity": "info", "message": "Reviewed manually", "related_label": "G1"},
    )
    assert added_review_note.status_code == 201, added_review_note.text
    assert added_review_note.json()["related_label"] == "G1"

    review_notes_after_add = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes",
        headers=auth_header(token),
    )
    assert review_notes_after_add.status_code == 200, review_notes_after_add.text
    assert len(review_notes_after_add.json()) == 2

    adjustment_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments",
        headers=auth_header(token),
        json={"label": "W1", "amount": "20.00", "note": "PAYG instalment adjustment"},
    )
    assert adjustment_response.status_code == 201, adjustment_response.text
    line_results = {item["label"]: item for item in adjustment_response.json()["line_results"]}
    assert line_results["W1"]["system_amount"] == "0.00"
    assert line_results["W1"]["adjustment_amount"] == "20.00"
    assert line_results["W1"]["final_amount"] == "20.00"

    adjustments_after_add = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments",
        headers=auth_header(token),
    )
    assert adjustments_after_add.status_code == 200, adjustments_after_add.text
    assert len(adjustments_after_add.json()) == 1
    assert adjustments_after_add.json()[0]["label"] == "W1"

    run_detail_response = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}",
        headers=auth_header(token),
    )
    assert run_detail_response.status_code == 200, run_detail_response.text
    assert run_detail_response.json()["warning_count"] == 2


def test_bas_export_requires_approval_and_approval_actions_are_listed(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    submit_and_approve_period(client, token, company_id, period_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    gst_payable_account_id = create_account(client, token, company_id, "2200", "GST Payable", "liability")
    g1_tax_code_id = create_tax_code(client, token, company_id, code="SALE_G1", label="G1")
    one_a_tax_code_id = create_tax_code(client, token, company_id, code="GST_1A", label="1A")
    create_posted_sale_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id=cash_account_id,
        revenue_account_id=revenue_account_id,
        gst_payable_account_id=gst_payable_account_id,
        g1_tax_code_id=g1_tax_code_id,
        one_a_tax_code_id=one_a_tax_code_id,
    )
    _, bas_run_id = generate_bas_run(client, token, company_id)

    initial_exports = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports",
        headers=auth_header(token),
    )
    assert initial_exports.status_code == 200, initial_exports.text
    assert initial_exports.json() == []

    blocked_export = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports/csv",
        headers=auth_header(token),
    )
    assert blocked_export.status_code == 400, blocked_export.text
    assert blocked_export.json()["detail"] == "BAS run must be approved before export"

    initial_actions = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/approval-actions",
        headers=auth_header(token),
    )
    assert initial_actions.status_code == 200, initial_actions.text
    assert [action["action_type"] for action in initial_actions.json()] == ["prepared"]

    submit_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/submit",
        headers=auth_header(token),
        json={"note": "Ready for review"},
    )
    assert submit_response.status_code == 200, submit_response.text

    approve_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/approve",
        headers=auth_header(token),
        json={"note": "Approved for export"},
    )
    assert approve_response.status_code == 200, approve_response.text

    actions_after_approval = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/approval-actions",
        headers=auth_header(token),
    )
    assert actions_after_approval.status_code == 200, actions_after_approval.text
    assert [action["action_type"] for action in actions_after_approval.json()] == [
        "prepared",
        "submitted_for_review",
        "approved",
    ]

    export_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports/csv",
        headers=auth_header(token),
    )
    assert export_response.status_code == 201, export_response.text

    exports_after_create = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports",
        headers=auth_header(token),
    )
    assert exports_after_create.status_code == 200, exports_after_create.text
    assert len(exports_after_create.json()) == 1
    assert exports_after_create.json()[0]["format"] == "csv"
