import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation


def parse_csv_date(raw_value: str) -> datetime.date:
    value = raw_value.strip()
    if not value:
        raise ValueError("date is required")
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date format: {value}")


def normalize_amount(raw_value: str) -> Decimal:
    value = (raw_value or "").strip()
    if not value:
        return Decimal("0.00")
    normalized = value.replace(",", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount: {raw_value}") from exc


def parse_bank_csv_rows(
    decoded: str,
    *,
    date_column: str,
    description_column: str,
    debit_column: str,
    credit_column: str,
    reference_column: str | None,
) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(decoded))
    if reader.fieldnames is None:
        raise ValueError("CSV headers are missing")

    required_columns = {date_column, description_column, debit_column, credit_column}
    if required_columns.issubset(set(reader.fieldnames)):
        return list(reader)

    commbank_rows = _parse_commonwealth_bank_rows(
        decoded,
        date_column=date_column,
        description_column=description_column,
        debit_column=debit_column,
        credit_column=credit_column,
        reference_column=reference_column,
    )
    if commbank_rows is not None:
        return commbank_rows

    raise ValueError("CSV is missing required columns")


def _parse_commonwealth_bank_rows(
    decoded: str,
    *,
    date_column: str,
    description_column: str,
    debit_column: str,
    credit_column: str,
    reference_column: str | None,
) -> list[dict[str, str]] | None:
    rows = list(csv.reader(io.StringIO(decoded)))
    parsed_rows: list[dict[str, str]] = []

    for raw_row in rows:
        row = [value.strip() for value in raw_row]
        if not any(row):
            continue
        if len(row) != 4:
            return None

        date_value, signed_amount_raw, description_value, _running_balance_raw = row
        if not description_value:
            return None

        try:
            parse_csv_date(date_value)
            signed_amount = normalize_amount(signed_amount_raw)
            normalize_amount(_running_balance_raw)
        except ValueError:
            return None

        debit_amount = abs(signed_amount) if signed_amount < 0 else Decimal("0.00")
        credit_amount = signed_amount if signed_amount > 0 else Decimal("0.00")
        parsed_row = {
            date_column: date_value,
            description_column: description_value,
            debit_column: f"{debit_amount:.2f}",
            credit_column: f"{credit_amount:.2f}",
        }
        if reference_column:
            parsed_row[reference_column] = ""
        parsed_rows.append(parsed_row)

    return parsed_rows if parsed_rows else None
