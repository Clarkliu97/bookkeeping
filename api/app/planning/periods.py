import calendar
from datetime import date, timedelta


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def expected_financial_year_end(start_date: date) -> date:
    return add_months(start_date, 12) - timedelta(days=1)


def generate_fiscal_months(start_date: date, end_date: date) -> list[tuple[int, str, date, date]]:
    expected_end = expected_financial_year_end(start_date)
    if end_date != expected_end:
        raise ValueError(
            f"Financial year must contain twelve fiscal months and end on {expected_end.isoformat()}"
        )

    periods: list[tuple[int, str, date, date]] = []
    for index in range(12):
        period_start = add_months(start_date, index)
        period_end = add_months(start_date, index + 1) - timedelta(days=1)
        periods.append(
            (
                index + 1,
                period_start.strftime("%b %Y"),
                period_start,
                period_end,
            )
        )
    return periods
