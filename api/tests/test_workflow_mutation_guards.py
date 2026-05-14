from tests.test_milestone_b import create_bank_account, create_posted_journal
from tests.test_milestone_c import (
    approve_period,
    auth_header,
    bootstrap_superuser,
    create_account,
    create_company,
    create_period,
    create_posted_sale_journal,
    create_tax_code,
    generate_bas_run,
    submit_and_approve_period,
    submit_period,
)
from tests.test_milestone_d_phase10 import create_fixed_asset
from tests.test_milestone_d_phase11 import create_year_period


def submit_and_approve_bas_run(client, token: str, company_id: str, bas_run_id: str) -> None:
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


def test_bas_mutation_guards_cover_generated_warnings_and_export_documents(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    submit_and_approve_period(client, token, company_id, period_id)

    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    gst_payable_account_id = create_account(client, token, company_id, "2200", "GST Payable", "liability")
    untaxed_income_account_id = create_account(client, token, company_id, "4100", "Untaxed Income", "income")
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
    create_posted_journal(
        client,
        token,
        company_id,
        period_id,
        cash_account_id,
        untaxed_income_account_id,
    )

    bas_period_id, bas_run_id = generate_bas_run(client, token, company_id)

    adjustment_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments",
        headers=auth_header(token),
        json={"label": "G1", "amount": "5.00", "note": "Draft-only adjustment"},
    )
    assert adjustment_response.status_code == 201, adjustment_response.text
    adjustment_id = adjustment_response.json()["id"]

    review_notes_response = client.get(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes",
        headers=auth_header(token),
    )
    assert review_notes_response.status_code == 200, review_notes_response.text
    generated_note = next(note for note in review_notes_response.json() if note["created_by_user_id"] is None)

    update_generated_warning = client.put(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes/{generated_note['id']}",
        headers=auth_header(token),
        json={
            "severity": "warning",
            "message": "Should stay immutable",
            "related_label": None,
        },
    )
    assert update_generated_warning.status_code == 400, update_generated_warning.text
    assert update_generated_warning.json()["detail"] == "Generated BAS warnings cannot be edited"

    delete_generated_warning = client.delete(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/review-notes/{generated_note['id']}",
        headers=auth_header(token),
    )
    assert delete_generated_warning.status_code == 400, delete_generated_warning.text
    assert delete_generated_warning.json()["detail"] == "Generated BAS warnings cannot be removed"

    submit_and_approve_bas_run(client, token, company_id, bas_run_id)

    update_run_after_approval = client.put(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}",
        headers=auth_header(token),
        json={"bas_period_id": bas_period_id},
    )
    assert update_run_after_approval.status_code == 400, update_run_after_approval.text
    assert update_run_after_approval.json()["detail"] == "Only draft BAS runs can be changed"

    update_adjustment_after_approval = client.put(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/adjustments/{adjustment_id}",
        headers=auth_header(token),
        json={"label": "G1", "amount": "7.50", "note": "Should be blocked"},
    )
    assert update_adjustment_after_approval.status_code == 400, update_adjustment_after_approval.text
    assert update_adjustment_after_approval.json()["detail"] == "Approved BAS runs cannot be changed"

    export_response = client.post(
        f"/api/companies/{company_id}/bas/runs/{bas_run_id}/exports/csv",
        headers=auth_header(token),
    )
    assert export_response.status_code == 201, export_response.text
    export_document_id = export_response.json()["document_id"]

    delete_export_document = client.delete(
        f"/api/companies/{company_id}/documents/{export_document_id}",
        headers=auth_header(token),
    )
    assert delete_export_document.status_code == 400, delete_export_document.text
    assert delete_export_document.json()["detail"] == "Document is attached to a BAS export"


def test_bank_import_and_reconciliation_guards_apply_after_confirm_and_complete(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_account_id = create_account(client, token, company_id, "1000", "Cash", "asset")
    revenue_account_id = create_account(client, token, company_id, "4000", "Revenue", "income")
    journal_id = create_posted_journal(client, token, company_id, period_id, cash_account_id, revenue_account_id)
    bank_account_id = create_bank_account(client, token, company_id)

    upload_response = client.post(
        f"/api/companies/{company_id}/bank-imports/upload",
        headers=auth_header(token),
        files={
            "file": (
                "import.csv",
                b"date,description,debit,credit,reference\n2026-07-02,Customer deposit,0.00,100.00,DEP100\n",
                "text/csv",
            )
        },
        data={"bank_account_id": bank_account_id, "note": "Guard coverage import"},
    )
    assert upload_response.status_code == 201, upload_response.text
    import_session_id = upload_response.json()["id"]

    confirm_response = client.post(
        f"/api/companies/{company_id}/bank-imports/{import_session_id}/confirm",
        headers=auth_header(token),
        json={"note": "Confirmed for reconciliation"},
    )
    assert confirm_response.status_code == 200, confirm_response.text

    update_confirmed_import = client.put(
        f"/api/companies/{company_id}/bank-imports/{import_session_id}",
        headers=auth_header(token),
        json={"note": "Should be blocked"},
    )
    assert update_confirmed_import.status_code == 400, update_confirmed_import.text
    assert update_confirmed_import.json()["detail"] == "Only staged bank imports can be updated"

    delete_confirmed_import = client.delete(
        f"/api/companies/{company_id}/bank-imports/{import_session_id}",
        headers=auth_header(token),
    )
    assert delete_confirmed_import.status_code == 400, delete_confirmed_import.text
    assert delete_confirmed_import.json()["detail"] == "Only staged bank imports can be deleted"

    reconciliation_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions",
        headers=auth_header(token),
        json={"bank_account_id": bank_account_id, "accounting_period_id": period_id, "note": "Guard coverage"},
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
        json={"matched_journal_entry_id": journal_id, "note": "Matched for guard coverage"},
    )
    assert match_response.status_code == 200, match_response.text

    complete_response = client.post(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}/complete",
        headers=auth_header(token),
        json={"note": "Completed for guard coverage"},
    )
    assert complete_response.status_code == 200, complete_response.text

    update_completed_session = client.put(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}",
        headers=auth_header(token),
        json={"accounting_period_id": period_id, "note": "Should be blocked"},
    )
    assert update_completed_session.status_code == 400, update_completed_session.text
    assert update_completed_session.json()["detail"] == "Completed reconciliation sessions cannot be updated"

    delete_completed_session = client.delete(
        f"/api/companies/{company_id}/reconciliation-sessions/{reconciliation_session_id}",
        headers=auth_header(token),
    )
    assert delete_completed_session.status_code == 400, delete_completed_session.text
    assert delete_completed_session.json()["detail"] == "Completed reconciliation sessions cannot be deleted"


def test_fixed_asset_and_depreciation_mutation_guards_apply_after_history_and_posting(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    asset_account_id = create_account(client, token, company_id, "1500", "Plant Equipment", "asset")
    accumulated_account_id = create_account(client, token, company_id, "1590", "Accumulated Depreciation", "contra_asset")
    expense_account_id = create_account(client, token, company_id, "6100", "Depreciation Expense", "expense")

    asset_id = create_fixed_asset(
        client,
        token,
        company_id,
        asset_payload={
            "asset_code": "FA-100",
            "name": "Laptop Fleet",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "1200.00",
            "salvage_value": "0.00",
            "useful_life_months": 12,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_account_id,
            "depreciation_expense_account_id": expense_account_id,
        },
    )

    run_response = client.post(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs",
        headers=auth_header(token),
        json={
            "accounting_period_id": period_id,
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "note": "Guard coverage run",
        },
    )
    assert run_response.status_code == 201, run_response.text
    run_id = run_response.json()["id"]

    update_asset_after_history = client.put(
        f"/api/companies/{company_id}/fixed-assets/{asset_id}",
        headers=auth_header(token),
        json={
            "asset_code": "FA-100",
            "name": "Should Be Blocked",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "1200.00",
            "salvage_value": "0.00",
            "useful_life_months": 12,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_account_id,
            "depreciation_expense_account_id": expense_account_id,
        },
    )
    assert update_asset_after_history.status_code == 400, update_asset_after_history.text
    assert update_asset_after_history.json()["detail"] == "Fixed assets with depreciation history cannot be updated"

    delete_asset_after_history = client.delete(
        f"/api/companies/{company_id}/fixed-assets/{asset_id}",
        headers=auth_header(token),
    )
    assert delete_asset_after_history.status_code == 400, delete_asset_after_history.text
    assert delete_asset_after_history.json()["detail"] == "Fixed assets with depreciation history cannot be deleted"

    post_response = client.post(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs/{run_id}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text

    update_posted_run = client.put(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs/{run_id}",
        headers=auth_header(token),
        json={
            "accounting_period_id": period_id,
            "start_date": "2026-07-01",
            "end_date": "2026-08-31",
            "note": "Should be blocked",
        },
    )
    assert update_posted_run.status_code == 400, update_posted_run.text
    assert update_posted_run.json()["detail"] == "Only draft depreciation runs can be updated"

    delete_posted_run = client.delete(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs/{run_id}",
        headers=auth_header(token),
    )
    assert delete_posted_run.status_code == 400, delete_posted_run.text
    assert delete_posted_run.json()["detail"] == "Only draft depreciation runs can be deleted"


def test_tax_workpaper_mutation_guards_cover_dependents_resolved_exceptions_and_export_documents(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    year_period_id = create_year_period(client, token, company_id)
    submit_period(client, token, company_id, year_period_id)
    approve_period(client, token, company_id, year_period_id)

    pack_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs",
        headers=auth_header(token),
        json={"accounting_period_id": year_period_id, "note": "Guard coverage pack"},
    )
    assert pack_response.status_code == 201, pack_response.text
    pack_id = pack_response.json()["id"]

    adjustment_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/adjustments",
        headers=auth_header(token),
        json={"label": "NON_DEDUCTIBLE", "amount": "15.00", "note": "Draft adjustment"},
    )
    assert adjustment_response.status_code == 201, adjustment_response.text
    adjustment_id = adjustment_response.json()["id"]

    note_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/notes",
        headers=auth_header(token),
        json={"note_type": "review", "message": "Draft review note"},
    )
    assert note_response.status_code == 201, note_response.text
    note_id = note_response.json()["id"]

    exception_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/exceptions",
        headers=auth_header(token),
        json={"severity": "warning", "message": "Draft exception"},
    )
    assert exception_response.status_code == 201, exception_response.text
    exception_id = exception_response.json()["id"]

    update_pack_with_dependents = client.put(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}",
        headers=auth_header(token),
        json={"accounting_period_id": year_period_id, "note": "Should be blocked"},
    )
    assert update_pack_with_dependents.status_code == 400, update_pack_with_dependents.text
    assert update_pack_with_dependents.json()["detail"] == "Tax workpaper packs with dependent records cannot be rebuilt"

    resolve_exception = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/exceptions/{exception_id}/resolve",
        headers=auth_header(token),
        json={"note": "Resolved for guard coverage"},
    )
    assert resolve_exception.status_code == 200, resolve_exception.text

    update_resolved_exception = client.put(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/exceptions/{exception_id}",
        headers=auth_header(token),
        json={"severity": "warning", "message": "Should stay resolved"},
    )
    assert update_resolved_exception.status_code == 400, update_resolved_exception.text
    assert update_resolved_exception.json()["detail"] == "Resolved exceptions cannot be edited"

    submit_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/submit",
        headers=auth_header(token),
        json={"note": "Ready for review"},
    )
    assert submit_response.status_code == 200, submit_response.text

    approve_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/approve",
        headers=auth_header(token),
        json={"note": "Approved for export"},
    )
    assert approve_response.status_code == 200, approve_response.text

    update_note_after_approval = client.put(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/notes/{note_id}",
        headers=auth_header(token),
        json={"note_type": "review", "message": "Should be blocked"},
    )
    assert update_note_after_approval.status_code == 400, update_note_after_approval.text
    assert update_note_after_approval.json()["detail"] == "Approved tax workpaper packs cannot be changed"

    delete_adjustment_after_approval = client.delete(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/adjustments/{adjustment_id}",
        headers=auth_header(token),
    )
    assert delete_adjustment_after_approval.status_code == 400, delete_adjustment_after_approval.text
    assert delete_adjustment_after_approval.json()["detail"] == "Approved tax workpaper packs cannot be changed"

    export_response = client.post(
        f"/api/companies/{company_id}/tax-workpapers/packs/{pack_id}/exports/pdf",
        headers=auth_header(token),
    )
    assert export_response.status_code == 201, export_response.text
    export_document_id = export_response.json()["document_id"]

    delete_export_document = client.delete(
        f"/api/companies/{company_id}/documents/{export_document_id}",
        headers=auth_header(token),
    )
    assert delete_export_document.status_code == 400, delete_export_document.text
    assert delete_export_document.json()["detail"] == "Document is attached to a tax workpaper export"