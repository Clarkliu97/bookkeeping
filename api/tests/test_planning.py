from conftest import auth_header, upsert_test_account

from tests.test_milestone_a import bootstrap_superuser, create_company, create_period


def create_plan(
    client, token: str, company_id: str, *, name: str, plan_type: str, baseline_id=None
):
    response = client.post(
        f"/api/companies/{company_id}/planning/plans",
        headers=auth_header(token),
        json={
            "name": name,
            "plan_type": plan_type,
            "scenario_type": "baseline",
            "scenario_label": "Baseline",
            "financial_year_start": "2026-07-01",
            "financial_year_end": "2027-06-30",
            "baseline_budget_plan_id": baseline_id,
            "actual_through_date": "2026-07-31" if plan_type == "forecast" else None,
            "assumption_summary": "Account-level monthly planning test",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def post_journal(
    client,
    token: str,
    company_id: str,
    period_id: str,
    *,
    description: str,
    debit_account_id: str,
    credit_account_id: str,
    amount: str,
):
    create_response = client.post(
        f"/api/companies/{company_id}/journals",
        headers=auth_header(token),
        json={
            "entry_date": "2026-07-15",
            "accounting_period_id": period_id,
            "source_type": "manual",
            "description": description,
            "lines": [
                {
                    "account_id": debit_account_id,
                    "debit_amount": amount,
                    "credit_amount": "0.00",
                },
                {
                    "account_id": credit_account_id,
                    "debit_amount": "0.00",
                    "credit_amount": amount,
                },
            ],
        },
    )
    assert create_response.status_code == 201, create_response.text
    post_response = client.post(
        f"/api/companies/{company_id}/journals/{create_response.json()['id']}/post",
        headers=auth_header(token),
    )
    assert post_response.status_code == 200, post_response.text


def test_budget_forecast_projects_year_end_profit_without_changing_ledger(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    period_id = create_period(client, token, company_id)
    cash_id = upsert_test_account(
        client,
        token,
        company_id,
        account_code="1000-PLAN",
        name="Planning Cash",
        account_type="asset",
    )
    revenue_id = upsert_test_account(
        client,
        token,
        company_id,
        account_code="4000-PLAN",
        name="Forecast Revenue",
        account_type="income",
    )
    expense_id = upsert_test_account(
        client,
        token,
        company_id,
        account_code="6000-PLAN",
        name="Forecast Operating Expense",
        account_type="expense",
    )

    budget = create_plan(
        client,
        token,
        company_id,
        name="FY2027 Baseline Budget",
        plan_type="budget",
    )
    detail_response = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}",
        headers=auth_header(token),
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert len(detail["periods"]) == 12
    assert detail["periods"][0]["start_date"] == "2026-07-01"
    assert detail["periods"][-1]["end_date"] == "2027-06-30"

    spread_revenue = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/spread",
        headers=auth_header(token),
        json={
            "revision": detail["plan"]["revision"],
            "account_id": revenue_id,
            "annual_amount": "120000.00",
            "note": "Monthly revenue target",
        },
    )
    assert spread_revenue.status_code == 200, spread_revenue.text
    revenue_detail = spread_revenue.json()
    spread_expense = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/spread",
        headers=auth_header(token),
        json={
            "revision": revenue_detail["plan"]["revision"],
            "account_id": expense_id,
            "annual_amount": "60000.00",
            "note": "Monthly expense envelope",
        },
    )
    assert spread_expense.status_code == 200, spread_expense.text
    budget_detail = spread_expense.json()
    assert budget_detail["annual_budget_income"] == "120000.00"
    assert budget_detail["annual_budget_expenses"] == "60000.00"
    assert budget_detail["annual_budget_net_profit"] == "60000.00"

    post_journal(
        client,
        token,
        company_id,
        period_id,
        description="July forecast revenue actual",
        debit_account_id=cash_id,
        credit_account_id=revenue_id,
        amount="15000.00",
    )
    post_journal(
        client,
        token,
        company_id,
        period_id,
        description="July forecast expense actual",
        debit_account_id=expense_id,
        credit_account_id=cash_id,
        amount="7000.00",
    )
    pnl_before = client.get(
        (
            f"/api/companies/{company_id}/reports/profit-and-loss"
            "?start_date=2026-07-01&end_date=2026-07-31"
        ),
        headers=auth_header(token),
    )
    assert pnl_before.status_code == 200, pnl_before.text
    assert pnl_before.json()["net_profit"] == "8000.00"

    clone_response = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/clone",
        headers=auth_header(token),
        json={
            "name": "FY2027 July Forecast",
            "plan_type": "forecast",
            "scenario_type": "baseline",
            "scenario_label": "July reforecast",
            "baseline_budget_plan_id": budget["id"],
            "actual_through_date": "2026-07-31",
        },
    )
    assert clone_response.status_code == 201, clone_response.text
    forecast = clone_response.json()

    calculate_response = client.post(
        f"/api/companies/{company_id}/planning/plans/{forecast['id']}/calculate",
        headers=auth_header(token),
        json={"actual_through_date": "2026-07-31", "persist": True},
    )
    assert calculate_response.status_code == 200, calculate_response.text
    calculation = calculate_response.json()
    assert calculation["actual_total_income"] == "15000.00"
    assert calculation["actual_total_expenses"] == "7000.00"
    assert calculation["forecast_total_income"] == "110000.00"
    assert calculation["forecast_total_expenses"] == "55000.00"
    assert calculation["projected_total_income"] == "125000.00"
    assert calculation["projected_total_expenses"] == "62000.00"
    assert calculation["projected_net_profit"] == "63000.00"
    assert calculation["budget_net_profit"] == "60000.00"
    assert calculation["variance_to_budget"] == "3000.00"
    assert calculation["id"] is not None

    saved_run = client.get(
        f"/api/companies/{company_id}/planning/forecast-runs/{calculation['id']}",
        headers=auth_header(token),
    )
    assert saved_run.status_code == 200, saved_run.text
    assert saved_run.json()["projected_net_profit"] == "63000.00"

    csv_export = client.get(
        f"/api/companies/{company_id}/planning/forecast-runs/{calculation['id']}/export/csv",
        headers=auth_header(token),
    )
    assert csv_export.status_code == 200, csv_export.text
    assert "Projected year-end profit and loss" in csv_export.text
    assert "Forecast Revenue" in csv_export.text

    pdf_export = client.get(
        f"/api/companies/{company_id}/planning/forecast-runs/{calculation['id']}/export/pdf",
        headers=auth_header(token),
    )
    assert pdf_export.status_code == 200, pdf_export.text
    assert pdf_export.content.startswith(b"%PDF")

    pnl_after = client.get(
        (
            f"/api/companies/{company_id}/reports/profit-and-loss"
            "?start_date=2026-07-01&end_date=2026-07-31"
        ),
        headers=auth_header(token),
    )
    assert pnl_after.status_code == 200, pnl_after.text
    assert pnl_after.json() == pnl_before.json()


def test_planning_lifecycle_stale_updates_and_account_validation(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    revenue_id = upsert_test_account(
        client,
        token,
        company_id,
        account_code="4100-PLAN",
        name="Lifecycle Revenue",
        account_type="revenue",
    )
    balance_sheet_id = upsert_test_account(
        client,
        token,
        company_id,
        account_code="1100-PLAN",
        name="Lifecycle Receivable",
        account_type="asset",
    )
    budget = create_plan(
        client,
        token,
        company_id,
        name="Lifecycle Budget",
        plan_type="budget",
    )
    detail = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}",
        headers=auth_header(token),
    ).json()
    first_period_id = detail["periods"][0]["id"]

    invalid_account = client.put(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/lines/bulk",
        headers=auth_header(token),
        json={
            "revision": detail["plan"]["revision"],
            "lines": [
                {
                    "planning_period_id": first_period_id,
                    "account_id": balance_sheet_id,
                    "amount": "100.00",
                }
            ],
        },
    )
    assert invalid_account.status_code == 400, invalid_account.text

    valid_update = client.put(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/lines/bulk",
        headers=auth_header(token),
        json={
            "revision": detail["plan"]["revision"],
            "lines": [
                {
                    "planning_period_id": first_period_id,
                    "account_id": revenue_id,
                    "amount": "1000.00",
                }
            ],
        },
    )
    assert valid_update.status_code == 200, valid_update.text
    updated = valid_update.json()

    stale_update = client.put(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/lines/bulk",
        headers=auth_header(token),
        json={
            "revision": detail["plan"]["revision"],
            "lines": [
                {
                    "planning_period_id": first_period_id,
                    "account_id": revenue_id,
                    "amount": "2000.00",
                }
            ],
        },
    )
    assert stale_update.status_code == 409, stale_update.text
    assert "current revision" in stale_update.json()["detail"]

    submit = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/submit",
        headers=auth_header(token),
        json={"note": "Ready for planning review"},
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "in_review"
    approve = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/approve",
        headers=auth_header(token),
        json={"note": "Approved baseline"},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
    assert approve.json()["is_primary"] is True

    immutable_update = client.put(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/lines/bulk",
        headers=auth_header(token),
        json={
            "revision": updated["plan"]["revision"],
            "lines": [
                {
                    "planning_period_id": first_period_id,
                    "account_id": revenue_id,
                    "amount": "2500.00",
                }
            ],
        },
    )
    assert immutable_update.status_code == 409, immutable_update.text
    assert "Only draft" in immutable_update.json()["detail"]


def test_planning_csv_growth_clone_comparison_and_plan_exports(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    revenue_id = upsert_test_account(
        client,
        token,
        company_id,
        account_code="4200-PLAN",
        name="Imported Planning Revenue",
        account_type="income",
    )
    budget = create_plan(
        client,
        token,
        company_id,
        name="CSV Baseline Budget",
        plan_type="budget",
    )
    detail = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}",
        headers=auth_header(token),
    ).json()

    invalid_csv = b"account_code,period_start,amount,note\nMISSING,2026-07-01,100.00,Invalid\n"
    invalid_preview = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/imports/preview",
        headers=auth_header(token),
        files={"file": ("invalid.csv", invalid_csv, "text/csv")},
    )
    assert invalid_preview.status_code == 200, invalid_preview.text
    assert invalid_preview.json()["valid_rows"] == 0
    assert invalid_preview.json()["errors"]

    csv_content = (
        b"account_code,period_start,amount,note\n"
        b"4200-PLAN,2026-07-01,100.01,July target\n"
        b"4200-PLAN,2026-08-01,200.00,August target\n"
    )
    preview = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/imports/preview",
        headers=auth_header(token),
        files={"file": ("planning.csv", csv_content, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["valid_rows"] == 2
    assert preview.json()["errors"] == []

    imported = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/imports/commit",
        headers=auth_header(token),
        data={"revision": str(detail["plan"]["revision"])},
        files={"file": ("planning.csv", csv_content, "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    imported_detail = imported.json()
    assert imported_detail["annual_budget_income"] == "300.01"
    assert {line["entry_method"] for line in imported_detail["lines"]} == {"csv_import"}

    grown = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/apply-growth",
        headers=auth_header(token),
        json={
            "revision": imported_detail["plan"]["revision"],
            "growth_percentage": "10.00",
            "account_ids": [revenue_id],
            "note": "Upside sensitivity",
        },
    )
    assert grown.status_code == 200, grown.text
    assert grown.json()["annual_budget_income"] == "330.01"

    clone = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/clone",
        headers=auth_header(token),
        json={
            "name": "CSV Upside Budget",
            "plan_type": "budget",
            "scenario_type": "upside",
            "scenario_label": "Upside",
        },
    )
    assert clone.status_code == 201, clone.text
    cloned_plan = clone.json()
    cloned_detail = client.get(
        f"/api/companies/{company_id}/planning/plans/{cloned_plan['id']}",
        headers=auth_header(token),
    ).json()
    cloned_growth = client.post(
        f"/api/companies/{company_id}/planning/plans/{cloned_plan['id']}/apply-growth",
        headers=auth_header(token),
        json={
            "revision": cloned_detail["plan"]["revision"],
            "growth_percentage": "10.00",
            "account_ids": [revenue_id],
        },
    )
    assert cloned_growth.status_code == 200, cloned_growth.text
    assert cloned_growth.json()["annual_budget_income"] == "363.01"

    comparison = client.post(
        f"/api/companies/{company_id}/planning/comparisons",
        headers=auth_header(token),
        json={"plan_ids": [budget["id"], cloned_plan["id"]]},
    )
    assert comparison.status_code == 200, comparison.text
    assert [item["projected_total_income"] for item in comparison.json()["items"]] == [
        "330.01",
        "363.01",
    ]

    plan_csv = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/export/csv",
        headers=auth_header(token),
    )
    assert plan_csv.status_code == 200, plan_csv.text
    assert "Imported Planning Revenue" in plan_csv.text
    plan_pdf = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/export/pdf",
        headers=auth_header(token),
    )
    assert plan_pdf.status_code == 200, plan_pdf.text
    assert plan_pdf.content.startswith(b"%PDF")


def test_budget_items_build_monthly_floors_and_clamp_direct_edits(client):
    token = bootstrap_superuser(client)
    company_id = create_company(client, token)
    revenue_id = upsert_test_account(
        client,
        token,
        company_id,
        account_code="4300-PLAN",
        name="Budget Item Revenue",
        account_type="income",
    )
    budget = create_plan(
        client,
        token,
        company_id,
        name="Budget Item Plan",
        plan_type="budget",
    )
    detail = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}",
        headers=auth_header(token),
    ).json()
    periods = detail["periods"]

    create_item = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/budget-items",
        headers=auth_header(token),
        json={
            "revision": detail["plan"]["revision"],
            "name": "Monthly subscription revenue",
            "account_id": revenue_id,
            "amount": "100.00",
            "occurrence_frequency": "monthly",
            "start_period_id": periods[0]["id"],
            "end_period_id": periods[2]["id"],
            "note": "Committed subscriptions",
        },
    )
    assert create_item.status_code == 201, create_item.text
    item_detail = create_item.json()
    assert len(item_detail["budget_items"]) == 1
    assert len(item_detail["budget_item_floors"]) == 3
    assert len(item_detail["floor_adjustments"]) == 3
    assert item_detail["annual_budget_income"] == "300.00"
    item_id = item_detail["budget_items"][0]["id"]

    clamped = client.put(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/lines/bulk",
        headers=auth_header(token),
        json={
            "revision": item_detail["plan"]["revision"],
            "lines": [
                {
                    "planning_period_id": periods[0]["id"],
                    "account_id": revenue_id,
                    "amount": "50.00",
                },
                {
                    "planning_period_id": periods[1]["id"],
                    "account_id": revenue_id,
                    "amount": None,
                },
                {
                    "planning_period_id": periods[3]["id"],
                    "account_id": revenue_id,
                    "amount": "25.00",
                },
            ],
        },
    )
    assert clamped.status_code == 200, clamped.text
    clamped_detail = clamped.json()
    assert len(clamped_detail["floor_adjustments"]) == 2
    amounts = {
        (line["account_id"], line["planning_period_id"]): line["amount"]
        for line in clamped_detail["lines"]
    }
    assert amounts[(revenue_id, periods[0]["id"])] == "100.00"
    assert amounts[(revenue_id, periods[1]["id"])] == "100.00"
    assert amounts[(revenue_id, periods[3]["id"])] == "25.00"

    update_item = client.put(
        (f"/api/companies/{company_id}/planning/plans/{budget['id']}/budget-items/{item_id}"),
        headers=auth_header(token),
        json={
            "revision": clamped_detail["plan"]["revision"],
            "name": "Quarterly subscription revenue",
            "account_id": revenue_id,
            "amount": "150.00",
            "occurrence_frequency": "quarterly",
            "start_period_id": periods[0]["id"],
            "end_period_id": periods[-1]["id"],
            "note": "Quarterly committed subscriptions",
        },
    )
    assert update_item.status_code == 200, update_item.text
    updated_detail = update_item.json()
    assert len(updated_detail["budget_item_floors"]) == 4
    assert {floor["planning_period_id"] for floor in updated_detail["budget_item_floors"]} == {
        periods[index]["id"] for index in (0, 3, 6, 9)
    }
    assert updated_detail["annual_budget_income"] == "800.00"

    item_csv = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/export/csv",
        headers=auth_header(token),
    )
    assert item_csv.status_code == 200, item_csv.text
    assert "Budget items" in item_csv.text
    assert "Quarterly subscription revenue" in item_csv.text
    item_pdf = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/export/pdf",
        headers=auth_header(token),
    )
    assert item_pdf.status_code == 200, item_pdf.text
    assert item_pdf.content.startswith(b"%PDF")

    clone = client.post(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/clone",
        headers=auth_header(token),
        json={
            "name": "Budget Item Plan v2",
            "plan_type": "budget",
            "scenario_type": "baseline",
            "scenario_label": "Baseline v2",
        },
    )
    assert clone.status_code == 201, clone.text
    clone_detail = client.get(
        f"/api/companies/{company_id}/planning/plans/{clone.json()['id']}",
        headers=auth_header(token),
    )
    assert clone_detail.status_code == 200, clone_detail.text
    assert len(clone_detail.json()["budget_items"]) == 1
    assert len(clone_detail.json()["budget_item_floors"]) == 4

    delete_item = client.delete(
        (
            f"/api/companies/{company_id}/planning/plans/{budget['id']}"
            f"/budget-items/{item_id}?revision={updated_detail['plan']['revision']}"
        ),
        headers=auth_header(token),
    )
    assert delete_item.status_code == 204, delete_item.text
    after_delete = client.get(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}",
        headers=auth_header(token),
    ).json()
    assert after_delete["budget_items"] == []
    assert after_delete["budget_item_floors"] == []

    reduced = client.put(
        f"/api/companies/{company_id}/planning/plans/{budget['id']}/lines/bulk",
        headers=auth_header(token),
        json={
            "revision": after_delete["plan"]["revision"],
            "lines": [
                {
                    "planning_period_id": periods[0]["id"],
                    "account_id": revenue_id,
                    "amount": "50.00",
                }
            ],
        },
    )
    assert reduced.status_code == 200, reduced.text
    assert reduced.json()["floor_adjustments"] == []
    reduced_amounts = {
        (line["account_id"], line["planning_period_id"]): line["amount"]
        for line in reduced.json()["lines"]
    }
    assert reduced_amounts[(revenue_id, periods[0]["id"])] == "50.00"

    forecast = create_plan(
        client,
        token,
        company_id,
        name="Budget Item Forecast",
        plan_type="forecast",
        baseline_id=budget["id"],
    )
    forecast_detail = client.get(
        f"/api/companies/{company_id}/planning/plans/{forecast['id']}",
        headers=auth_header(token),
    ).json()
    invalid_forecast_item = client.post(
        f"/api/companies/{company_id}/planning/plans/{forecast['id']}/budget-items",
        headers=auth_header(token),
        json={
            "revision": forecast_detail["plan"]["revision"],
            "name": "Not allowed on forecast",
            "account_id": revenue_id,
            "amount": "100.00",
            "occurrence_frequency": "monthly",
            "start_period_id": forecast_detail["periods"][0]["id"],
        },
    )
    assert invalid_forecast_item.status_code == 400, invalid_forecast_item.text
