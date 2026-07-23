from datetime import date, timedelta
from io import BytesIO


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


def create_worker_with_engagement(client, token: str, company_id: str, code: str) -> tuple[str, str]:
    worker_response = client.post(
        f"/api/companies/{company_id}/employment/workers",
        headers=auth_header(token),
        json={
            "worker_code": code,
            "display_name": f"Worker {code}",
            "worker_kind": "individual",
            "is_active": True,
        },
    )
    assert worker_response.status_code == 201, worker_response.text
    worker_id = worker_response.json()["id"]

    engagement_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_id}/engagements",
        headers=auth_header(token),
        json={
            "engagement_type": "employee",
            "employment_basis": "permanent_full_time",
            "start_date": date.today().isoformat(),
            "role_name": f"Role {code}",
            "status": "active",
        },
    )
    assert engagement_response.status_code == 201, engagement_response.text
    return worker_id, engagement_response.json()["id"]


def test_employment_worker_detail_dashboard_and_reports(client):
    today = date.today()
    start_date = today.isoformat()
    reimbursement_date = (today + timedelta(days=17)).isoformat()
    review_due_date = (today + timedelta(days=7)).isoformat()
    visa_expiry_date = (today + timedelta(days=14)).isoformat()
    leave_snapshot_date = (today + timedelta(days=30)).isoformat()
    asset_due_back_date = (today + timedelta(days=365)).isoformat()

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)

    worker_response = client.post(
        f"/api/companies/{company_id}/employment/workers",
        headers=auth_header(token),
        json={
            "worker_code": "EMP-001",
            "display_name": "Ava Chen",
            "legal_name": "Ava Chen",
            "worker_kind": "individual",
            "primary_email": "ava@example.com",
            "primary_phone": "0400000000",
            "is_active": True,
            "note": "Payroll support worker",
        },
    )
    assert worker_response.status_code == 201, worker_response.text
    worker_id = worker_response.json()["id"]

    engagement_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_id}/engagements",
        headers=auth_header(token),
        json={
            "engagement_type": "employee",
            "employment_basis": "permanent_full_time",
            "start_date": start_date,
            "department": "Finance",
            "role_name": "Bookkeeper",
            "status": "active",
            "note": "Primary bookkeeping employee",
        },
    )
    assert engagement_response.status_code == 201, engagement_response.text
    engagement_id = engagement_response.json()["id"]

    work_rights_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_id}/work-rights",
        headers=auth_header(token),
        json={
            "engagement_id": engagement_id,
            "work_rights_basis": "student_visa",
            "review_status": "verified_with_restrictions",
            "visa_subclass": "500",
            "visa_label": "Student visa",
            "visa_expiry_date": visa_expiry_date,
            "next_review_due_at": review_due_date,
            "hours_restriction_summary": "Check work-hour limits during study periods",
        },
    )
    assert work_rights_response.status_code == 201, work_rights_response.text

    compensation_response = client.put(
        f"/api/companies/{company_id}/employment/engagements/{engagement_id}/compensation",
        headers=auth_header(token),
        json={
            "remuneration_basis": "salary",
            "expected_base_amount": "82000.00",
            "tax_profile": "resident",
            "superannuation_category": "standard",
            "workers_comp_category": "office",
            "payroll_tax_in_scope": True,
            "leave_profile": "full_time_employee",
            "reimbursement_allowed": True,
            "asset_issue_allowed": True,
            "tfn_declaration_received": True,
            "super_choice_received": True,
            "abn_provided": False,
            "gst_registered_known": False,
            "note": "Standard employee settings",
        },
    )
    assert compensation_response.status_code == 200, compensation_response.text

    leave_snapshot_response = client.post(
        f"/api/companies/{company_id}/employment/engagements/{engagement_id}/leave-snapshots",
        headers=auth_header(token),
        json={
            "snapshot_date": leave_snapshot_date,
            "annual_leave_hours": "38.00",
            "personal_leave_hours": "15.20",
            "long_service_leave_hours": "0.00",
            "leave_value_amount": "3100.00",
            "current_lsl_value_amount": "0.00",
            "non_current_lsl_value_amount": "0.00",
            "note": "Imported from payroll support workbook",
        },
    )
    assert leave_snapshot_response.status_code == 201, leave_snapshot_response.text

    reimbursement_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_id}/reimbursements",
        headers=auth_header(token),
        json={
            "engagement_id": engagement_id,
            "reimbursement_date": reimbursement_date,
            "description": "Parking reimbursement",
            "amount": "25.50",
            "status": "submitted",
            "note": "Awaiting payroll repayment",
        },
    )
    assert reimbursement_response.status_code == 201, reimbursement_response.text

    issued_asset_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_id}/issued-assets",
        headers=auth_header(token),
        json={
            "engagement_id": engagement_id,
            "asset_name": "Lenovo Laptop",
            "asset_type": "laptop",
            "serial_number": "LT-001",
            "assigned_on": start_date,
            "due_back_on": asset_due_back_date,
            "status": "issued",
            "note": "Primary issued device",
        },
    )
    assert issued_asset_response.status_code == 201, issued_asset_response.text

    upload_response = client.post(
        f"/api/companies/{company_id}/documents",
        headers=auth_header(token),
        files={"file": ("visa.pdf", BytesIO(b"visa evidence"), "application/pdf")},
    )
    assert upload_response.status_code == 201, upload_response.text
    document_id = upload_response.json()["id"]

    link_response = client.post(
        f"/api/companies/{company_id}/documents/{document_id}/links",
        headers=auth_header(token),
        json={
            "entity_type": "employment_worker",
            "entity_id": worker_id,
            "note": "Visa evidence",
        },
    )
    assert link_response.status_code == 201, link_response.text

    detail_response = client.get(
        f"/api/companies/{company_id}/employment/workers/{worker_id}",
        headers=auth_header(token),
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["display_name"] == "Ava Chen"
    assert len(detail["engagements"]) == 1
    assert len(detail["work_rights_records"]) == 1
    assert len(detail["compensation_profiles"]) == 1
    assert len(detail["leave_snapshots"]) == 1
    assert len(detail["reimbursements"]) == 1
    assert len(detail["issued_assets"]) == 1
    assert len(detail["linked_documents"]) == 1

    dashboard_response = client.get(
        f"/api/companies/{company_id}/employment/dashboard",
        headers=auth_header(token),
    )
    assert dashboard_response.status_code == 200, dashboard_response.text
    dashboard = dashboard_response.json()
    assert dashboard["total_workers"] == 1
    assert dashboard["active_engagements"] == 1
    assert dashboard["expiring_work_rights_count"] == 1
    assert dashboard["missing_document_count"] == 0

    headcount_report = client.get(
        f"/api/companies/{company_id}/employment/reports/headcount",
        headers=auth_header(token),
    )
    assert headcount_report.status_code == 200, headcount_report.text
    assert headcount_report.json()["rows"][0]["worker_name"] == "Ava Chen"

    leave_report_export = client.get(
        f"/api/companies/{company_id}/employment/reports/leave-liability-support/export",
        headers=auth_header(token),
    )
    assert leave_report_export.status_code == 200, leave_report_export.text
    assert "Ava Chen" in leave_report_export.text


def test_employment_contractor_review_report(client):
    start_date = date.today().isoformat()

    token = bootstrap_superuser(client)
    company_id = create_company(client, token)

    worker_response = client.post(
        f"/api/companies/{company_id}/employment/workers",
        headers=auth_header(token),
        json={
            "worker_code": "CTR-001",
            "display_name": "Northside Consulting Pty Ltd",
            "worker_kind": "entity",
            "is_active": True,
        },
    )
    assert worker_response.status_code == 201, worker_response.text
    worker_id = worker_response.json()["id"]

    engagement_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_id}/engagements",
        headers=auth_header(token),
        json={
            "engagement_type": "contractor_entity",
            "employment_basis": "project_fee",
            "start_date": start_date,
            "role_name": "Implementation partner",
            "status": "active",
            "note": "Review contractor classification annually",
        },
    )
    assert engagement_response.status_code == 201, engagement_response.text
    engagement_id = engagement_response.json()["id"]

    compensation_response = client.put(
        f"/api/companies/{company_id}/employment/engagements/{engagement_id}/compensation",
        headers=auth_header(token),
        json={
            "remuneration_basis": "contractor_fee",
            "expected_base_amount": "120000.00",
            "abn_provided": True,
            "gst_registered_known": True,
            "payroll_tax_in_scope": False,
            "note": "ABN and GST reviewed",
        },
    )
    assert compensation_response.status_code == 200, compensation_response.text

    report_response = client.get(
        f"/api/companies/{company_id}/employment/reports/contractor-review",
        headers=auth_header(token),
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert len(report["rows"]) == 1
    assert report["rows"][0]["worker_name"] == "Northside Consulting Pty Ltd"
    assert report["rows"][0]["abn_provided"] is True


def test_employment_worker_scoped_records_reject_another_workers_engagement(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    worker_a_id, engagement_a_id = create_worker_with_engagement(client, token, company_id, "EMP-A")
    worker_b_id, engagement_b_id = create_worker_with_engagement(client, token, company_id, "EMP-B")

    work_rights_payload = {
        "engagement_id": engagement_b_id,
        "work_rights_basis": "australian_citizen",
        "review_status": "verified",
    }
    work_rights_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_a_id}/work-rights",
        headers=auth_header(token),
        json=work_rights_payload,
    )
    assert work_rights_response.status_code == 400, work_rights_response.text
    assert work_rights_response.json()["detail"] == "Engagement does not belong to the selected worker"

    reimbursement_payload = {
        "engagement_id": engagement_b_id,
        "reimbursement_date": date.today().isoformat(),
        "description": "Invalid cross-worker reimbursement",
        "amount": "25.00",
        "status": "draft",
    }
    reimbursement_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_a_id}/reimbursements",
        headers=auth_header(token),
        json=reimbursement_payload,
    )
    assert reimbursement_response.status_code == 400, reimbursement_response.text

    issued_asset_payload = {
        "engagement_id": engagement_b_id,
        "asset_name": "Invalid cross-worker laptop",
        "assigned_on": date.today().isoformat(),
        "status": "issued",
    }
    issued_asset_response = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_a_id}/issued-assets",
        headers=auth_header(token),
        json=issued_asset_payload,
    )
    assert issued_asset_response.status_code == 400, issued_asset_response.text

    valid_work_rights = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_a_id}/work-rights",
        headers=auth_header(token),
        json={**work_rights_payload, "engagement_id": engagement_a_id},
    )
    assert valid_work_rights.status_code == 201, valid_work_rights.text
    update_work_rights = client.put(
        f"/api/companies/{company_id}/employment/work-rights/{valid_work_rights.json()['id']}",
        headers=auth_header(token),
        json=work_rights_payload,
    )
    assert update_work_rights.status_code == 400, update_work_rights.text

    valid_reimbursement = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_a_id}/reimbursements",
        headers=auth_header(token),
        json={**reimbursement_payload, "engagement_id": engagement_a_id},
    )
    assert valid_reimbursement.status_code == 201, valid_reimbursement.text
    update_reimbursement = client.put(
        f"/api/companies/{company_id}/employment/reimbursements/{valid_reimbursement.json()['id']}",
        headers=auth_header(token),
        json=reimbursement_payload,
    )
    assert update_reimbursement.status_code == 400, update_reimbursement.text

    valid_asset = client.post(
        f"/api/companies/{company_id}/employment/workers/{worker_a_id}/issued-assets",
        headers=auth_header(token),
        json={**issued_asset_payload, "engagement_id": engagement_a_id},
    )
    assert valid_asset.status_code == 201, valid_asset.text
    update_asset = client.put(
        f"/api/companies/{company_id}/employment/issued-assets/{valid_asset.json()['id']}",
        headers=auth_header(token),
        json=issued_asset_payload,
    )
    assert update_asset.status_code == 400, update_asset.text

    assert worker_b_id != worker_a_id


def test_employment_compensation_rejects_accounts_from_another_company(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    other_company_id = create_company(client, token)
    _, engagement_id = create_worker_with_engagement(client, token, company_id, "EMP-ACCOUNT")

    other_accounts_response = client.get(
        f"/api/companies/{other_company_id}/accounts",
        headers=auth_header(token),
    )
    assert other_accounts_response.status_code == 200, other_accounts_response.text
    other_account_id = other_accounts_response.json()[0]["id"]

    response = client.put(
        f"/api/companies/{company_id}/employment/engagements/{engagement_id}/compensation",
        headers=auth_header(token),
        json={
            "remuneration_basis": "salary",
            "expense_account_id": other_account_id,
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Expense account must belong to the selected company"
