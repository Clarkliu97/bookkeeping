from decimal import Decimal

from app.db.models.fixed_assets import DepreciationRun, FixedAsset

from tests.test_milestone_d import (
    auth_header,
    bootstrap_superuser,
    create_account,
    create_company,
    create_period,
)


def create_fixed_asset(client, token: str, company_id: str, *, asset_payload: dict) -> str:
    response = client.post(
        f"/api/companies/{company_id}/fixed-assets",
        headers=auth_header(token),
        json=asset_payload,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_fixed_asset_register_detail_and_disposal(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    asset_account_id = create_account(client, token, company_id, "1500", "Plant Equipment", "asset")
    accumulated_account_id = create_account(
        client,
        token,
        company_id,
        "1590",
        "Accumulated Depreciation",
        "contra_asset",
    )
    expense_account_id = create_account(client, token, company_id, "6100", "Depreciation Expense", "expense")

    asset_id = create_fixed_asset(
        client,
        token,
        company_id,
        asset_payload={
            "asset_code": "FA-100",
            "name": "Laptop Fleet",
            "description": "Staff laptops",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "1200.00",
            "salvage_value": "0.00",
            "useful_life_months": 12,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_account_id,
            "depreciation_expense_account_id": expense_account_id,
            "acquisition_reference": "INV-001",
        },
    )

    register_response = client.get(
        f"/api/companies/{company_id}/fixed-assets",
        headers=auth_header(token),
        params={"as_of_date": "2026-07-31"},
    )
    assert register_response.status_code == 200, register_response.text
    register_payload = register_response.json()
    assert register_payload["as_of_date"] == "2026-07-31"
    assert len(register_payload["assets"]) == 1
    assert register_payload["assets"][0]["asset_code"] == "FA-100"
    assert register_payload["assets"][0]["accumulated_depreciation"] == "100.00"
    assert register_payload["assets"][0]["carrying_amount"] == "1100.00"

    detail_response = client.get(
        f"/api/companies/{company_id}/fixed-assets/{asset_id}",
        headers=auth_header(token),
        params={"as_of_date": "2026-07-31"},
    )
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert len(detail_payload["history"]) == 1
    assert detail_payload["history"][0]["to_status"] == "active"

    dispose_response = client.post(
        f"/api/companies/{company_id}/fixed-assets/{asset_id}/dispose",
        headers=auth_header(token),
        json={
            "disposal_date": "2026-10-15",
            "disposal_reference": "SALE-100",
            "disposal_note": "Disposed after hardware refresh",
            "disposal_proceeds": "150.00",
        },
    )
    assert dispose_response.status_code == 200, dispose_response.text
    disposed_payload = dispose_response.json()
    assert disposed_payload["status"] == "disposed"
    assert disposed_payload["disposal_date"] == "2026-10-15"
    assert len(disposed_payload["history"]) == 2
    assert disposed_payload["history"][-1]["to_status"] == "disposed"


def test_depreciation_run_generates_posts_and_exports(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    asset_account_id = create_account(client, token, company_id, "1500", "Plant Equipment", "asset")
    accumulated_account_id = create_account(
        client,
        token,
        company_id,
        "1590",
        "Accumulated Depreciation",
        "contra_asset",
    )
    expense_account_id = create_account(client, token, company_id, "6100", "Depreciation Expense", "expense")

    create_fixed_asset(
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
    create_fixed_asset(
        client,
        token,
        company_id,
        asset_payload={
            "asset_code": "FA-200",
            "name": "Warehouse Fitout",
            "acquisition_date": "2026-07-15",
            "in_service_date": "2026-07-15",
            "cost_amount": "2400.00",
            "salvage_value": "0.00",
            "useful_life_months": 24,
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
            "note": "July depreciation",
        },
    )
    assert run_response.status_code == 201, run_response.text
    run_payload = run_response.json()
    assert run_payload["status"] == "draft"
    assert run_payload["total_depreciation_amount"] == "154.84"
    line_amounts = {line["fixed_asset_id"]: line["depreciation_amount"] for line in run_payload["lines"]}
    assert sorted(line_amounts.values()) == ["100.00", "54.84"]

    post_response = client.post(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs/{run_payload['id']}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text
    posted_payload = post_response.json()
    assert posted_payload["status"] == "posted"
    assert posted_payload["journal_entry_id"] is not None

    journals_response = client.get(f"/api/companies/{company_id}/journals", headers=auth_header(token))
    assert journals_response.status_code == 200, journals_response.text
    depreciation_journal = next(journal for journal in journals_response.json() if journal["id"] == posted_payload["journal_entry_id"])
    assert depreciation_journal["source_type"] == "depreciation"
    assert depreciation_journal["status"] == "posted"
    assert sum(Decimal(line["debit_amount"]) for line in depreciation_journal["lines"]) == Decimal("154.84")
    assert sum(Decimal(line["credit_amount"]) for line in depreciation_journal["lines"]) == Decimal("154.84")

    export_response = client.get(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs/{run_payload['id']}/export",
        headers=auth_header(token),
    )
    assert export_response.status_code == 200, export_response.text
    assert export_response.headers["content-type"].startswith("text/csv")
    assert b"Asset Code,Asset Name,Run Amount" in export_response.content
    assert b"FA-100,Laptop Fleet,100.00" in export_response.content


def test_depreciation_run_requires_depreciable_assets_and_period_range(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    asset_account_id = create_account(client, token, company_id, "1500", "Plant Equipment", "asset")
    accumulated_account_id = create_account(
        client,
        token,
        company_id,
        "1590",
        "Accumulated Depreciation",
        "contra_asset",
    )
    expense_account_id = create_account(client, token, company_id, "6100", "Depreciation Expense", "expense")
    create_fixed_asset(
        client,
        token,
        company_id,
        asset_payload={
            "asset_code": "FA-300",
            "name": "Future asset",
            "acquisition_date": "2026-09-01",
            "in_service_date": "2026-09-01",
            "cost_amount": "600.00",
            "salvage_value": "0.00",
            "useful_life_months": 12,
            "depreciation_method": "straight_line",
            "asset_account_id": asset_account_id,
            "accumulated_depreciation_account_id": accumulated_account_id,
            "depreciation_expense_account_id": expense_account_id,
        },
    )

    invalid_range_response = client.post(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs",
        headers=auth_header(token),
        json={
            "accounting_period_id": period_id,
            "start_date": "2026-07-01",
            "end_date": "2026-10-01",
        },
    )
    assert invalid_range_response.status_code == 400, invalid_range_response.text
    assert invalid_range_response.json()["detail"] == "Depreciation run range must fall within the accounting period"

    no_assets_response = client.post(
        f"/api/companies/{company_id}/fixed-assets/depreciation-runs",
        headers=auth_header(token),
        json={
            "accounting_period_id": period_id,
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
        },
    )
    assert no_assets_response.status_code == 400, no_assets_response.text
    assert no_assets_response.json()["detail"] == "No depreciable assets found for the selected period"


def test_diminishing_value_asset_is_supported_in_depreciation_run(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    asset_account_id = create_account(client, token, company_id, "1500", "Plant Equipment", "asset")
    accumulated_account_id = create_account(
        client,
        token,
        company_id,
        "1590",
        "Accumulated Depreciation",
        "contra_asset",
    )
    expense_account_id = create_account(client, token, company_id, "6100", "Depreciation Expense", "expense")
    create_fixed_asset(
        client,
        token,
        company_id,
        asset_payload={
            "asset_code": "FA-400",
            "name": "Specialist equipment",
            "acquisition_date": "2026-07-01",
            "in_service_date": "2026-07-01",
            "cost_amount": "1000.00",
            "salvage_value": "0.00",
            "useful_life_months": 60,
            "depreciation_method": "diminishing_value",
            "diminishing_value_rate": "0.24",
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
        },
    )
    assert run_response.status_code == 201, run_response.text
    payload = run_response.json()
    assert payload["total_depreciation_amount"] == "20.00"
    assert len(payload["lines"]) == 1
    assert payload["lines"][0]["depreciation_amount"] == "20.00"