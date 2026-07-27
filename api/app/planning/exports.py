import csv
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.models.companies import Company
from app.planning.schemas import PlanningForecastRunRead, PlanningPlanDetailRead

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2B68A6")
PALE_BLUE = colors.HexColor("#EAF2F9")
PALE_GREY = colors.HexColor("#F4F6F8")
LINE = colors.HexColor("#CBD5E1")
TEXT = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748B")


def _money(value: Decimal) -> str:
    amount = Decimal(value)
    if amount == Decimal("0.00"):
        return "-"
    absolute = f"${abs(amount):,.2f}"
    return f"({absolute})" if amount < 0 else absolute


def build_plan_csv(detail: PlanningPlanDetailRead) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    plan = detail.plan
    writer.writerow(["Budget and forecast planning schedule"])
    writer.writerow(["Plan", plan.name])
    writer.writerow(["Type", plan.plan_type.value])
    writer.writerow(["Scenario", plan.scenario_label])
    writer.writerow(["Status", plan.status.value])
    writer.writerow(["Financial year", plan.financial_year_start, plan.financial_year_end])
    writer.writerow(["Currency", plan.currency_code])
    writer.writerow([])
    if detail.budget_items:
        writer.writerow(["Budget items"])
        writer.writerow(
            [
                "Item",
                "Account code",
                "Account name",
                "Amount per occurrence",
                "Frequency",
                "Starting month",
                "Ending month",
                "Note",
            ]
        )
        account_map = {account.id: account for account in detail.accounts}
        period_map = {period.id: period for period in detail.periods}
        for item in detail.budget_items:
            account = account_map[item.account_id]
            start = period_map[item.start_period_id]
            end = period_map[item.end_period_id] if item.end_period_id else detail.periods[-1]
            writer.writerow(
                [
                    item.name,
                    account.account_code,
                    account.account_name,
                    item.amount,
                    item.occurrence_frequency.value,
                    start.period_label,
                    start.period_label
                    if item.occurrence_frequency.value == "one_off"
                    else end.period_label,
                    item.note or "",
                ]
            )
        writer.writerow([])
    writer.writerow(
        ["Account code", "Account name", "Account type"]
        + [period.period_label for period in detail.periods]
        + ["Annual total"]
    )
    values = {(line.account_id, line.planning_period_id): line.amount for line in detail.lines}
    for account in detail.accounts:
        monthly = [values.get((account.id, period.id), "") for period in detail.periods]
        total = sum((Decimal(value) for value in monthly if value != ""), Decimal("0.00"))
        writer.writerow(
            [account.account_code, account.account_name, account.account_type] + monthly + [total]
        )
    writer.writerow([])
    writer.writerow(["Total income", detail.annual_budget_income])
    writer.writerow(["Total expenses", detail.annual_budget_expenses])
    writer.writerow(["Budget net profit", detail.annual_budget_net_profit])
    writer.writerow([])
    writer.writerow(
        [
            (
                "Internal planning support only. Budget and forecast values are estimates, "
                "do not modify the accounting ledger, and should be reviewed before operational "
                "or financial decisions are made."
            )
        ]
    )
    return output.getvalue().encode("utf-8-sig")


def build_forecast_csv(report: PlanningForecastRunRead) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Projected year-end profit and loss"])
    writer.writerow(["Plan", report.forecast_plan_name])
    writer.writerow(["Actual through", report.actual_through_date])
    writer.writerow(["Calculated at", report.ledger_calculated_at.isoformat()])
    writer.writerow(["Calculation version", report.calculation_version])
    writer.writerow([])
    writer.writerow(
        [
            "Account code",
            "Account name",
            "Account type",
            "Annual budget",
            "Actual YTD",
            "Forecast remaining",
            "Projected year-end",
            "Variance",
            "Variance %",
            "Direction",
        ]
    )
    for row in report.rows:
        writer.writerow(
            [
                row.account_code,
                row.account_name,
                row.account_type,
                row.annual_budget,
                row.actual_ytd,
                row.forecast_remaining,
                row.projected_year_end,
                row.variance_amount,
                row.variance_percentage if row.variance_percentage is not None else "",
                row.variance_direction,
            ]
        )
    writer.writerow([])
    writer.writerow(["Budget total income", report.budget_total_income])
    writer.writerow(["Budget total expenses", report.budget_total_expenses])
    writer.writerow(["Budget net profit", report.budget_net_profit])
    writer.writerow(["Projected total income", report.projected_total_income])
    writer.writerow(["Projected total expenses", report.projected_total_expenses])
    writer.writerow(["Projected gross profit", report.projected_gross_profit])
    writer.writerow(["Projected operating profit", report.projected_operating_profit])
    writer.writerow(["Projected net profit", report.projected_net_profit])
    writer.writerow(["Variance to budget", report.variance_to_budget])
    writer.writerow([])
    writer.writerow(["Warnings", report.warning_count])
    for warning in report.warnings:
        writer.writerow([warning.code, warning.message])
    return output.getvalue().encode("utf-8-sig")


def build_forecast_pdf(
    company: Company,
    report: PlanningForecastRunRead,
    plan_detail: PlanningPlanDetailRead | None = None,
) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title="Budget and Forecast Projected Profit and Loss",
        author=company.legal_name,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "PlanningTitle",
        parent=styles["Title"],
        fontSize=19,
        leading=23,
        textColor=NAVY,
        spaceAfter=4,
    )
    heading = ParagraphStyle(
        "PlanningHeading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        textColor=NAVY,
        spaceBefore=9,
        spaceAfter=5,
    )
    body = ParagraphStyle(
        "PlanningBody",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        textColor=TEXT,
    )
    small = ParagraphStyle(
        "PlanningSmall",
        parent=body,
        fontSize=7,
        leading=9,
        textColor=MUTED,
    )
    right = ParagraphStyle("PlanningRight", parent=body, alignment=TA_RIGHT)
    story = [
        Paragraph("Budget &amp; Forecast — Projected Profit and Loss", title),
        Paragraph(company.legal_name, heading),
        Paragraph(
            (
                f"{report.forecast_plan_name} | Actual through {report.actual_through_date:%d %b %Y} | "
                f"Calculated {report.ledger_calculated_at:%d %b %Y %H:%M %Z}"
            ),
            small,
        ),
        Spacer(1, 4 * mm),
    ]
    summary_data = [
        ["Measure", "Budget", "Projected", "Variance"],
        [
            "Total income",
            _money(report.budget_total_income),
            _money(report.projected_total_income),
            _money(report.projected_total_income - report.budget_total_income),
        ],
        [
            "Total expenses",
            _money(report.budget_total_expenses),
            _money(report.projected_total_expenses),
            _money(report.projected_total_expenses - report.budget_total_expenses),
        ],
        [
            "Gross profit",
            _money(report.budget_gross_profit),
            _money(report.projected_gross_profit),
            _money(report.projected_gross_profit - report.budget_gross_profit),
        ],
        [
            "Operating profit",
            _money(report.budget_operating_profit),
            _money(report.projected_operating_profit),
            _money(report.projected_operating_profit - report.budget_operating_profit),
        ],
        [
            "Net profit / (loss)",
            _money(report.budget_net_profit),
            _money(report.projected_net_profit),
            _money(report.variance_to_budget),
        ],
    ]
    summary = Table(summary_data, colWidths=[75 * mm, 38 * mm, 38 * mm, 38 * mm])
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), PALE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary)
    if plan_detail and plan_detail.budget_items:
        story.append(Paragraph("Budget items", heading))
        account_map = {account.id: account for account in plan_detail.accounts}
        period_map = {period.id: period for period in plan_detail.periods}
        item_data = [["Item", "Account", "Amount", "Frequency", "Schedule"]]
        for item in plan_detail.budget_items:
            account = account_map[item.account_id]
            start = period_map[item.start_period_id]
            end = period_map[item.end_period_id] if item.end_period_id else plan_detail.periods[-1]
            schedule = (
                start.period_label
                if item.occurrence_frequency.value == "one_off"
                else f"{start.period_label} to {end.period_label}"
            )
            item_data.append(
                [
                    item.name,
                    f"{account.account_code} - {account.account_name}",
                    _money(item.amount),
                    item.occurrence_frequency.value.replace("_", " "),
                    schedule,
                ]
            )
        item_table = LongTable(
            item_data,
            repeatRows=1,
            colWidths=[58 * mm, 82 * mm, 28 * mm, 35 * mm, 42 * mm],
        )
        item_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREY]),
                    ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(item_table)
    story.append(Paragraph("Account detail", heading))
    detail_data = [
        [
            "Account",
            "Budget",
            "Actual YTD",
            "Forecast remaining",
            "Projected",
            "Variance",
            "Direction",
        ]
    ]
    for row in report.rows:
        if (
            row.annual_budget == Decimal("0.00")
            and row.actual_ytd == Decimal("0.00")
            and row.forecast_remaining == Decimal("0.00")
        ):
            continue
        detail_data.append(
            [
                Paragraph(f"{row.account_code} — {row.account_name}", body),
                Paragraph(_money(row.annual_budget), right),
                Paragraph(_money(row.actual_ytd), right),
                Paragraph(_money(row.forecast_remaining), right),
                Paragraph(_money(row.projected_year_end), right),
                Paragraph(_money(row.variance_amount), right),
                row.variance_direction.replace("_", " "),
            ]
        )
    detail = LongTable(
        detail_data,
        repeatRows=1,
        colWidths=[78 * mm, 31 * mm, 31 * mm, 35 * mm, 31 * mm, 31 * mm, 30 * mm],
    )
    detail.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GREY]),
                ("ALIGN", (1, 1), (5, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(detail)
    if report.warnings:
        story.append(Paragraph(f"Review warnings ({report.warning_count})", heading))
        for warning in report.warnings[:30]:
            story.append(Paragraph(f"• {warning.message}", small))
    story.extend(
        [
            Spacer(1, 4 * mm),
            Paragraph(
                (
                    "Internal planning support only. Budget and forecast values are estimates, "
                    "do not modify the accounting ledger, and should be reviewed before operational "
                    "or financial decisions are made."
                ),
                small,
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()
