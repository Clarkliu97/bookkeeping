from tests.test_milestone_c import (
    approve_period,
    auth_header,
    bootstrap_superuser,
    create_company,
    create_posted_sale_journal,
    create_tax_code,
    create_user,
    generate_bas_run,
    grant_company_access,
    login,
    submit_period,
)
from tests.test_milestone_d import create_account, create_posted_journal
from tests.test_milestone_d_phase10 import create_fixed_asset


def create_year_period(client, token: str, company_id: str) -> str:
    response = client.post(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
        json={
            "name": "FY27",
            "period_type": "year",
            "start_date": "2026-07-01",
            "end_date": "2027-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def submit_and_approve_bas_run(client, token: str, company_id: str, bas_run_id: str) -> None:
    submit_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/submit",
        headers=auth_header(token),
        json={"note": "Ready for annual review"},
    )
    assert submit_response.status_code == 200, submit_response.text
    approve_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/approve",
        headers=auth_header(token),
        json={"note": "Approved for annual support pack"},
    )
    assert approve_response.status_code == 200, approve_response.text


def test_tax_workpaper_pack_generation_adjustments_and_pdf_export(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    year_period_id = create_year_period(client, token, company_id)
    submit_period(client, token, company_id, year_period_id)
    approve_period(client, token, company_id, year_period_id)

    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    expense_account_id = create_account(client, token, company_id, "5000", "Office Expense", "expense")
    gst_payable_account_id = create_account(client, token, company_id, "2200", "GST Payable", "liability")
    asset_account_id = create_account(client, token, company_id, "1500", "Plant Equipment", "asset")
    accumulated_account_id = create_account(
        client,
        token,
        company_id,
        "1590",
        "Accumulated Depreciation",
        "contra_asset",
    )
    depreciation_expense_account_id = create_account(
        client,
        token,
        company_id,
        "6100",
        "Depreciation Expense",
        "expense",
    )

    g1_tax_code_id = create_tax_code(client, token, company_id, code="SALE_G1", label="G1")
    one_a_tax_code_id = create_tax_code(client, token, company_id, code="GST_1A", label="1A")
    create_posted_sale_journal(
        client,
        token,
        company_id,
        year_period_id,
        cash_account_id=cash_account_id,
        revenue_account_id=revenue_account_id,
        gst_payable_account_id=gst_payable_account_id,
        g1_tax_code_id=g1_tax_code_id,
        one_a_tax_code_id=one_a_tax_code_id,
    )
    create_posted_journal(
        client,
        token,
        company_id,
        year_period_id,
        entry_date="2026-08-01",
        description="Office supplies",
        lines=[
            {"account_id": expense_account_id, "debit_amount": "30.00", "credit_amount": "0.00"},
            {"account_id": cash_account_id, "debit_amount": "0.00", "credit_amount": "30.00"},
        ],
    )
    create_fixed_asset(
        client,
        token,
        company_id,
        asset_payload={
            "asset_code": "FA-500",
            "name": "Fitout",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "1200.00",
            "salvage_value": "0.00",
            "useful_life_months": 24,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_account_id,
            "depreciation_expense_account_id": depreciation_expense_account_id,
        },
    )

    _, bas_run_id = generate_bas_run(client, token, company_id)
    submit_and_approve_bas_run(client, token, company_id, bas_run_id)

    pack_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs",
        headers=auth_header(token),
        json={"accounting_period_id": year_period_id, "note": "FY27 workpaper pack"},
    )
    assert pack_response.status_code == 201, pack_response.text
    pack_payload = pack_response.json()
    assert pack_payload["status"] == "draft"
    assert pack_payload["accounting_profit_schedule"]["net_profit"] == "70.00"
    assert pack_payload["total_adjustments"] == "0.00"
    assert pack_payload["taxable_income"] == "70.00"
    gst_totals = {line["label"]: line for line in pack_payload["gst_reconciliation_lines"]}
    assert gst_totals["G1"]["final_amount"] == "100.00"
    assert gst_totals["1A"]["final_amount"] == "10.00"
    assert pack_payload["fixed_asset_lines"][0]["asset_code"] == "FA-500"
    assert pack_payload["fixed_asset_lines"][0]["accumulated_depreciation"] == "600.00"
    assert pack_payload["fixed_asset_lines"][0]["carrying_amount"] == "600.00"

    adjustment_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/adjustments",
        headers=auth_header(token),
        json={"label": "NON_DEDUCTIBLE", "amount": "15.00", "note": "Entertainment adjustment"},
    )
    assert adjustment_response.status_code == 201, adjustment_response.text
    assert adjustment_response.json()["taxable_income"] == "85.00"

    review_note_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/notes",
        headers=auth_header(token),
        json={"note_type": "review", "message": "Reviewed profit support schedule"},
    )
    assert review_note_response.status_code == 201, review_note_response.text

    sign_off_note_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/notes",
        headers=auth_header(token),
        json={"note_type": "sign_off", "message": "Ready for accountant review"},
    )
    assert sign_off_note_response.status_code == 201, sign_off_note_response.text

    exception_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/exceptions",
        headers=auth_header(token),
        json={"severity": "warning", "message": "Check private-use apportionment"},
    )
    assert exception_response.status_code == 201, exception_response.text
    exception_id = exception_response.json()["id"]

    resolve_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/exceptions/{exception_id}/resolve",
        headers=auth_header(token),
        json={"note": "Confirmed no private use"},
    )
    assert resolve_response.status_code == 200, resolve_response.text
    assert resolve_response.json()["status"] == "resolved"

    submit_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/submit",
        headers=auth_header(token),
        json={"note": "Annual pack ready for review"},
    )
    assert submit_response.status_code == 200, submit_response.text
    approve_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/approve",
        headers=auth_header(token),
        json={"note": "Approved for accountant review"},
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["status"] == "approved"

    approval_actions_response = client.get(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/approval-actions",
        headers=auth_header(token),
    )
    assert approval_actions_response.status_code == 200, approval_actions_response.text
    assert [item["action_type"] for item in approval_actions_response.json()] == [
        "prepared",
        "submitted_for_review",
        "approved",
    ]

    period_list_response = client.get(f"/api/companies/{company_id}/periods", headers=auth_header(token))
    assert period_list_response.status_code == 200, period_list_response.text
    approved_year_period = next(period for period in period_list_response.json() if period["id"] == year_period_id)
    assert approved_year_period["status"] == "locked"

    export_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/exports/pdf",
        headers=auth_header(token),
    )
    assert export_response.status_code == 201, export_response.text
    document_id = export_response.json()["document_id"]

    exports_response = client.get(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_payload['id']}/exports",
        headers=auth_header(token),
    )
    assert exports_response.status_code == 200, exports_response.text
    assert len(exports_response.json()) == 1

    download_response = client.get(
        f"/api/companies/{company_id}/documents/{document_id}/download",
        headers=auth_header(token),
    )
    assert download_response.status_code == 200, download_response.text
    assert download_response.content.startswith(b"%PDF")


def test_tax_workpaper_review_controls_enforce_approval_rules(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token, self_approval_mode="block")
    year_period_id = create_year_period(client, token, company_id)

    reviewer_user_id = create_user(
        client,
        token,
        email="tax-reviewer@example.com",
        full_name="Tax Reviewer",
        password="StrongPass123",
    )
    grant_company_access(
        client,
        token,
        company_id,
        reviewer_user_id,
        can_prepare=True,
        can_review=True,
        can_approve=True,
    )
    reviewer_token = login(client, "tax-reviewer@example.com", "StrongPass123")

    submit_period(client, token, company_id, year_period_id)
    approve_period(client, reviewer_token, company_id, year_period_id)

    pack_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs",
        headers=auth_header(token),
        json={"accounting_period_id": year_period_id},
    )
    assert pack_response.status_code == 201, pack_response.text
    pack_id = pack_response.json()["id"]

    export_before_approval = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/exports/pdf",
        headers=auth_header(token),
    )
    assert export_before_approval.status_code == 400, export_before_approval.text

    submit_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/submit",
        headers=auth_header(token),
        json={"note": "Prepared by admin"},
    )
    assert submit_response.status_code == 200, submit_response.text

    blocked_approval = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/approve",
        headers=auth_header(token),
        json={"note": "Self approval attempt"},
    )
    assert blocked_approval.status_code == 400, blocked_approval.text

    approved_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/approve",
        headers=auth_header(reviewer_token),
        json={"note": "Approved by reviewer"},
    )
    assert approved_response.status_code == 200, approved_response.text
    assert approved_response.json()["status"] == "approved"

    blocked_adjustment = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/adjustments",
        headers=auth_header(token),
        json={"label": "LATE_ADJ", "amount": "5.00", "note": "Should be blocked"},
    )
    assert blocked_adjustment.status_code == 400, blocked_adjustment.text


def test_tax_workpaper_pack_requires_year_period(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    quarter_period_response = client.post(
        f"/api/companies/{company_id}/periods",
        headers=auth_header(token),
        json={
            "name": "FY27-Q1",
            "period_type": "quarter",
            "start_date": "2026-07-01",
            "end_date": "2026-09-30",
        },
    )
    assert quarter_period_response.status_code == 201, quarter_period_response.text
    quarter_period_id = quarter_period_response.json()["id"]

    pack_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs",
        headers=auth_header(token),
        json={"accounting_period_id": quarter_period_id},
    )
    assert pack_response.status_code == 400, pack_response.text
    assert pack_response.json()["detail"] == "Tax workpaper packs require a year accounting period"