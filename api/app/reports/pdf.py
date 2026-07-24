from __future__ import annotations

import io
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from html import escape
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db.models.companies import Company
from app.schemas.common import (
    BalanceSheetReportRead,
    CashFlowLine,
    CashFlowReportRead,
    GeneralLedgerReportRead,
    ProfitAndLossReportRead,
    StatementOfChangesInEquityRead,
    TrialBalanceReportRead,
)

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2B68A6")
PALE_BLUE = colors.HexColor("#EAF2F9")
PALE_GREY = colors.HexColor("#F4F6F8")
MID_GREY = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")
TEXT = colors.HexColor("#172033")
DANGER = colors.HexColor("#9B2C2C")
PALE_DANGER = colors.HexColor("#FDECEC")
FONT_REGULAR = "ArchiveSans"
FONT_BOLD = "ArchiveSans-Bold"
REPORTLAB_FONT_DIRECTORY = Path(reportlab.__file__).resolve().parent / "fonts"

pdfmetrics.registerFont(
    TTFont(FONT_REGULAR, str(REPORTLAB_FONT_DIRECTORY / "Vera.ttf"))
)
pdfmetrics.registerFont(
    TTFont(FONT_BOLD, str(REPORTLAB_FONT_DIRECTORY / "VeraBd.ttf"))
)


def _money(value: Decimal) -> str:
    amount = Decimal(value)
    if amount == Decimal("0.00"):
        return "-"
    absolute = f"${abs(amount):,.2f}"
    return f"({absolute})" if amount < 0 else absolute


def _text(value: object) -> str:
    return escape("" if value is None else str(value))


def _styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ArchiveTitle",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=24,
            textColor=NAVY,
            spaceAfter=4,
        ),
        "company": ParagraphStyle(
            "ArchiveCompany",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=15,
            textColor=TEXT,
            spaceAfter=2,
        ),
        "period": ParagraphStyle(
            "ArchivePeriod",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=12,
            textColor=MID_GREY,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "ArchiveSection",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "ArchiveBody",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=11,
            textColor=TEXT,
        ),
        "small": ParagraphStyle(
            "ArchiveSmall",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=7,
            leading=9,
            textColor=MID_GREY,
        ),
        "table": ParagraphStyle(
            "ArchiveTable",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=9.5,
            textColor=TEXT,
        ),
        "table_right": ParagraphStyle(
            "ArchiveTableRight",
            parent=styles["Normal"],
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=9.5,
            alignment=TA_RIGHT,
            textColor=TEXT,
        ),
        "table_bold": ParagraphStyle(
            "ArchiveTableBold",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            textColor=TEXT,
        ),
        "table_bold_right": ParagraphStyle(
            "ArchiveTableBoldRight",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            alignment=TA_RIGHT,
            textColor=TEXT,
        ),
        "table_header": ParagraphStyle(
            "ArchiveTableHeader",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
        ),
        "table_header_right": ParagraphStyle(
            "ArchiveTableHeaderRight",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            alignment=TA_RIGHT,
            textColor=colors.white,
        ),
        "warning": ParagraphStyle(
            "ArchiveWarning",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8,
            leading=11,
            textColor=DANGER,
        ),
    }


def _paragraph(value: object, style) -> Paragraph:
    return Paragraph(_text(value), style)


def _table(
    headers: list[str],
    rows: list[list[object]],
    *,
    styles,
    column_widths: list[float] | None = None,
    right_columns: set[int] | None = None,
    total_rows: set[int] | None = None,
    compact: bool = False,
) -> LongTable:
    right_columns = right_columns or set()
    total_rows = total_rows or set()
    header = [
        _paragraph(
            label,
            styles["table_header_right"] if index in right_columns else styles["table_header"],
        )
        for index, label in enumerate(headers)
    ]
    body: list[list[Paragraph]] = []
    for row_index, row in enumerate(rows):
        is_total = row_index in total_rows
        rendered_row = []
        for column_index, value in enumerate(row):
            if is_total:
                style = (
                    styles["table_bold_right"]
                    if column_index in right_columns
                    else styles["table_bold"]
                )
            else:
                style = (
                    styles["table_right"]
                    if column_index in right_columns
                    else styles["table"]
                )
            rendered_row.append(_paragraph(value, style))
        body.append(rendered_row)
    table = LongTable(
        [header, *body],
        colWidths=column_widths,
        repeatRows=1,
        hAlign="LEFT",
    )
    commands: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2 if compact else 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 if compact else 4),
    ]
    for row_index in range(len(rows)):
        pdf_row_index = row_index + 1
        if row_index in total_rows:
            commands.append(("BACKGROUND", (0, pdf_row_index), (-1, pdf_row_index), PALE_BLUE))
            commands.append(("LINEABOVE", (0, pdf_row_index), (-1, pdf_row_index), 0.8, BLUE))
        elif row_index % 2 == 1:
            commands.append(("BACKGROUND", (0, pdf_row_index), (-1, pdf_row_index), PALE_GREY))
    table.setStyle(TableStyle(commands))
    return table


def _metadata_table(
    company: Company,
    *,
    version_label: str,
    generated_at: datetime,
    styles,
) -> Table:
    identifier = (
        f"ABN {company.abn}"
        if company.abn
        else f"ACN {company.acn}"
        if company.acn
        else "Company identifier not recorded"
    )
    rows = [
        [
            _paragraph("Entity", styles["small"]),
            _paragraph(company.legal_name, styles["body"]),
            _paragraph("Identifier", styles["small"]),
            _paragraph(identifier, styles["body"]),
        ],
        [
            _paragraph("Currency", styles["small"]),
            _paragraph(company.base_currency, styles["body"]),
            _paragraph("Report version", styles["small"]),
            _paragraph(version_label, styles["body"]),
        ],
        [
            _paragraph("Generated", styles["small"]),
            _paragraph(generated_at.strftime("%Y-%m-%d %H:%M UTC"), styles["body"]),
            _paragraph("Archive reference", styles["small"]),
            _paragraph(str(company.id), styles["body"]),
        ],
    ]
    table = Table(rows, colWidths=[24 * mm, 62 * mm, 28 * mm, 56 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_GREY),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _page_callback(
    *,
    company: Company,
    title: str,
    generated_at: datetime,
) -> Callable:
    def draw_page(pdf_canvas, document) -> None:
        pdf_canvas.saveState()
        width, _ = document.pagesize
        pdf_canvas.setStrokeColor(LINE)
        pdf_canvas.setLineWidth(0.4)
        pdf_canvas.line(document.leftMargin, 13 * mm, width - document.rightMargin, 13 * mm)
        pdf_canvas.setFont(FONT_REGULAR, 7)
        pdf_canvas.setFillColor(MID_GREY)
        pdf_canvas.drawString(
            document.leftMargin,
            8.5 * mm,
            f"{company.legal_name} | {title}",
        )
        pdf_canvas.drawRightString(
            width - document.rightMargin,
            8.5 * mm,
            f"Generated {generated_at:%Y-%m-%d %H:%M UTC} | Page {document.page}",
        )
        pdf_canvas.restoreState()

    return draw_page


def _build_document(
    *,
    company: Company,
    title: str,
    period_label: str,
    include_draft: bool,
    story_builder: Callable[[dict], list],
    pagesize=A4,
) -> bytes:
    generated_at = datetime.now(UTC)
    version_label = (
        "Draft review - posted and draft journals"
        if include_draft
        else "Final review - posted journals only"
    )
    styles = _styles()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"{company.legal_name} - {title}",
        author=company.legal_name,
        subject=f"{title}; {period_label}; {version_label}",
        creator="Bookkeeping Tax",
    )
    story: list = [
        Paragraph(_text(title), styles["title"]),
        Paragraph(_text(company.legal_name), styles["company"]),
        Paragraph(_text(period_label), styles["period"]),
        _metadata_table(
            company,
            version_label=version_label,
            generated_at=generated_at,
            styles=styles,
        ),
        Spacer(1, 7 * mm),
    ]
    if include_draft:
        warning = Table(
            [[Paragraph("DRAFT REVIEW: Includes unposted journal entries and is not a final ledger report.", styles["warning"])]],
            colWidths=[document.width],
        )
        warning.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE_DANGER),
                    ("BOX", (0, 0), (-1, -1), 0.6, DANGER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([warning, Spacer(1, 5 * mm)])
    story.extend(story_builder(styles))
    story.extend(
        [
            Spacer(1, 7 * mm),
            Paragraph(
                "Prepared from the bookkeeping ledger for review and archival support. "
                "This report is not an audited financial statement and remains subject to professional review.",
                styles["small"],
            ),
        ]
    )
    callback = _page_callback(company=company, title=title, generated_at=generated_at)
    document.build(story, onFirstPage=callback, onLaterPages=callback)
    return buffer.getvalue()


def build_trial_balance_pdf(
    company: Company,
    report: TrialBalanceReportRead,
    *,
    include_draft: bool,
) -> bytes:
    period_label = (
        f"{report.start_date or 'Beginning'} to {report.end_date or 'Latest'}"
    )

    def story(styles):
        rows = [
            [
                row.account_code,
                row.account_name,
                _money(row.debit_total),
                _money(row.credit_total),
                _money(row.balance),
            ]
            for row in report.rows
        ]
        rows.append(
            [
                "",
                "Totals",
                _money(sum((row.debit_total for row in report.rows), Decimal("0.00"))),
                _money(sum((row.credit_total for row in report.rows), Decimal("0.00"))),
                _money(sum((row.balance for row in report.rows), Decimal("0.00"))),
            ]
        )
        return [
            Paragraph("Account balances", styles["section"]),
            _table(
                ["Code", "Account", "Debit", "Credit", "Balance"],
                rows,
                styles=styles,
                column_widths=[22 * mm, 70 * mm, 26 * mm, 26 * mm, 26 * mm],
                right_columns={2, 3, 4},
                total_rows={len(rows) - 1},
            ),
        ]

    return _build_document(
        company=company,
        title="Trial Balance",
        period_label=period_label,
        include_draft=include_draft,
        story_builder=story,
    )


def build_profit_and_loss_pdf(
    company: Company,
    report: ProfitAndLossReportRead,
    *,
    include_draft: bool,
) -> bytes:
    def story(styles):
        elements: list = []
        for label, lines, total_label, total in (
            ("Income", report.income_lines, "Total income", report.total_income),
            ("Expenses", report.expense_lines, "Total expenses", report.total_expenses),
        ):
            rows = [
                [line.account_code, line.account_name, _money(line.amount)]
                for line in lines
            ]
            rows.append(["", total_label, _money(total)])
            elements.extend(
                [
                    Paragraph(label, styles["section"]),
                    _table(
                        ["Code", "Account", "Amount"],
                        rows,
                        styles=styles,
                        column_widths=[25 * mm, 115 * mm, 30 * mm],
                        right_columns={2},
                        total_rows={len(rows) - 1},
                    ),
                ]
            )
        result = Table(
            [
                [
                    Paragraph("Net profit / (loss)", styles["table_bold"]),
                    Paragraph(_money(report.net_profit), styles["table_bold_right"]),
                ]
            ],
            colWidths=[140 * mm, 30 * mm],
        )
        result.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                    ("BOX", (0, 0), (-1, -1), 0.8, BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        elements.extend([Spacer(1, 5 * mm), result])
        return elements

    return _build_document(
        company=company,
        title="Statement of Profit or Loss",
        period_label=f"For the period {report.start_date} to {report.end_date}",
        include_draft=include_draft,
        story_builder=story,
    )


def build_balance_sheet_pdf(
    company: Company,
    report: BalanceSheetReportRead,
    *,
    include_draft: bool,
) -> bytes:
    def story(styles):
        elements: list = []
        sections = (
            ("Assets", report.asset_lines, "Total assets", report.total_assets),
            (
                "Liabilities",
                report.liability_lines,
                "Total liabilities",
                report.total_liabilities,
            ),
            (
                "Equity",
                [*report.equity_lines, report.current_earnings],
                "Total equity",
                report.total_equity,
            ),
        )
        for label, lines, total_label, total in sections:
            rows = [
                [line.account_code, line.account_name, _money(line.amount)]
                for line in lines
            ]
            rows.append(["", total_label, _money(total)])
            elements.extend(
                [
                    Paragraph(label, styles["section"]),
                    _table(
                        ["Code", "Account", "Amount"],
                        rows,
                        styles=styles,
                        column_widths=[25 * mm, 115 * mm, 30 * mm],
                        right_columns={2},
                        total_rows={len(rows) - 1},
                    ),
                ]
            )
        reconciliation = report.total_assets - report.total_liabilities_and_equity
        rows = [
            [
                "Total liabilities and equity",
                _money(report.total_liabilities_and_equity),
            ],
            ["Balance check", _money(reconciliation)],
        ]
        elements.extend(
            [
                Paragraph("Statement reconciliation", styles["section"]),
                _table(
                    ["Measure", "Amount"],
                    rows,
                    styles=styles,
                    column_widths=[140 * mm, 30 * mm],
                    right_columns={1},
                    total_rows={0, 1},
                ),
            ]
        )
        return elements

    return _build_document(
        company=company,
        title="Statement of Financial Position",
        period_label=f"As at {report.as_of_date}",
        include_draft=include_draft,
        story_builder=story,
    )


def _cash_flow_rows(lines: list[CashFlowLine]) -> list[list[object]]:
    return [
        [
            line.label,
            _money(line.amount),
        ]
        for line in lines
    ]


def build_cash_flow_pdf(
    company: Company,
    report: CashFlowReportRead,
    *,
    include_draft: bool,
) -> bytes:
    def story(styles):
        elements: list = [
            Paragraph(
                f"<b>Presentation method:</b> {_text(report.method.title())}. "
                f"{_text(report.classification_policy)}",
                styles["body"],
            )
        ]
        for label, lines, total_label, total in (
            (
                "Operating activities",
                report.operating_lines,
                "Net cash from operating activities",
                report.total_operating,
            ),
            (
                "Investing activities",
                report.investing_lines,
                "Net cash from investing activities",
                report.total_investing,
            ),
            (
                "Financing activities",
                report.financing_lines,
                "Net cash from financing activities",
                report.total_financing,
            ),
        ):
            rows = _cash_flow_rows(lines)
            if not rows:
                rows.append(["No cash flows in this activity", "-"])
            rows.append([total_label, _money(total)])
            elements.extend(
                [
                    Paragraph(label, styles["section"]),
                    _table(
                        ["Cash flow", "Amount"],
                        rows,
                        styles=styles,
                        column_widths=[145 * mm, 25 * mm],
                        right_columns={1},
                        total_rows={len(rows) - 1},
                        compact=True,
                    ),
                ]
            )
        reconciliation_rows = [
            ["Net increase/(decrease) in cash and cash equivalents", _money(report.net_cash_change)],
            [
                "Effect of exchange rate changes on cash and cash equivalents",
                _money(report.effect_of_exchange_rate_changes),
            ],
            ["Cash and cash equivalents at beginning of period", _money(report.opening_cash)],
            ["Calculated closing cash", _money(report.calculated_closing_cash)],
            ["Cash and cash equivalents at end of period", _money(report.closing_cash)],
            ["Reconciliation difference", _money(report.reconciliation_difference)],
        ]
        cash_account_rows = [
            [
                account.account_code,
                account.account_name,
                _money(account.opening_balance),
                _money(account.closing_balance),
            ]
            for account in report.cash_accounts
        ]
        elements.extend(
            [
                Paragraph("Reconciliation of cash and cash equivalents", styles["section"]),
                _table(
                    ["Measure", "Amount"],
                    reconciliation_rows,
                    styles=styles,
                    column_widths=[140 * mm, 30 * mm],
                    right_columns={1},
                    total_rows={3, 4, 5},
                    compact=True,
                ),
                KeepTogether(
                    [
                        Paragraph("Cash and cash equivalents", styles["section"]),
                        _table(
                            ["Code", "Account", "Opening balance", "Closing balance"],
                            cash_account_rows or [["", "No cash accounts identified", "-", "-"]],
                            styles=styles,
                            column_widths=[25 * mm, 85 * mm, 30 * mm, 30 * mm],
                            right_columns={2, 3},
                            compact=True,
                        ),
                    ]
                ),
            ]
        )
        return elements

    return _build_document(
        company=company,
        title="Statement of Cash Flows",
        period_label=f"For the period {report.start_date} to {report.end_date}",
        include_draft=include_draft,
        story_builder=story,
    )


def build_statement_of_changes_in_equity_pdf(
    company: Company,
    report: StatementOfChangesInEquityRead,
    *,
    include_draft: bool,
) -> bytes:
    def story(styles):
        movement_rows = [
            ["Opening equity", "", _money(report.opening_equity)],
            ["Profit or loss", "", _money(report.profit_or_loss)],
            *[
                [
                    line.movement_type.replace("_", " ").title(),
                    f"{line.account_code} {line.account_name}",
                    _money(line.amount),
                ]
                for line in report.movement_lines
            ],
            ["Total changes in equity", "", _money(report.total_changes)],
            ["Calculated closing equity", "", _money(report.calculated_closing_equity)],
            ["Ledger closing equity", "", _money(report.closing_equity)],
            ["Reconciliation difference", "", _money(report.reconciliation_difference)],
        ]
        return [
            Paragraph("Equity movements", styles["section"]),
            _table(
                ["Movement", "Account", "Amount"],
                movement_rows,
                styles=styles,
                column_widths=[58 * mm, 82 * mm, 30 * mm],
                right_columns={2},
                total_rows={
                    len(movement_rows) - 4,
                    len(movement_rows) - 3,
                    len(movement_rows) - 2,
                    len(movement_rows) - 1,
                },
            ),
            Paragraph("Opening equity composition", styles["section"]),
            _table(
                ["Code", "Account", "Amount"],
                [
                    [line.account_code, line.account_name, _money(line.amount)]
                    for line in report.opening_equity_lines
                ],
                styles=styles,
                column_widths=[36 * mm, 104 * mm, 30 * mm],
                right_columns={2},
            ),
        ]

    return _build_document(
        company=company,
        title="Statement of Changes in Equity",
        period_label=f"For the period {report.start_date} to {report.end_date}",
        include_draft=include_draft,
        story_builder=story,
    )


def build_general_ledger_pdf(
    company: Company,
    report: GeneralLedgerReportRead,
    *,
    include_draft: bool,
) -> bytes:
    def story(styles):
        elements: list = []
        if not report.accounts:
            return [Paragraph("No ledger entries matched the selected filters.", styles["body"])]
        for account in report.accounts:
            account_heading = KeepTogether(
                [
                    Paragraph(
                        f"{_text(account.account_code)} - {_text(account.account_name)}",
                        styles["section"],
                    ),
                    Paragraph(
                        f"Opening balance {_money(account.opening_balance)} | "
                        f"Closing balance {_money(account.closing_balance)}",
                        styles["small"],
                    ),
                    Spacer(1, 2 * mm),
                ]
            )
            rows = [
                [
                    entry.entry_date.isoformat(),
                    entry.entry_number,
                    entry.journal_status,
                    entry.journal_description,
                    entry.reference or "",
                    _money(entry.debit_amount),
                    _money(entry.credit_amount),
                    _money(entry.running_balance),
                ]
                for entry in account.entries
            ]
            elements.extend(
                [
                    account_heading,
                    _table(
                        [
                            "Date",
                            "Entry",
                            "Status",
                            "Description",
                            "Reference",
                            "Debit",
                            "Credit",
                            "Running balance",
                        ],
                        rows,
                        styles=styles,
                        column_widths=[
                            23 * mm,
                            24 * mm,
                            19 * mm,
                            70 * mm,
                            35 * mm,
                            27 * mm,
                            27 * mm,
                            32 * mm,
                        ],
                        right_columns={5, 6, 7},
                    ),
                    Spacer(1, 5 * mm),
                ]
            )
        return elements

    return _build_document(
        company=company,
        title="General Ledger",
        period_label=f"For the period {report.start_date} to {report.end_date}",
        include_draft=include_draft,
        story_builder=story,
        pagesize=landscape(A4),
    )
