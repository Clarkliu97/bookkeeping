from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.audit.service import log_audit_event
from app.db.models.accounting import Account, AccountingPeriod, JournalEntry, JournalLine
from app.db.models.companies import CompanyConfigurationVersion
from app.db.models.enums import AccountType, EntityType, JournalSourceType, JournalStatus
from app.db.models.reference import ReportingCategory
from app.ledger.router import _next_entry_number

ZERO = Decimal("0.00")
PERIOD_ROLLOVER_REFERENCE_PREFIX = "PERIOD-ROLLOVER:"
RETAINED_EARNINGS_CATEGORY_CODE = "BS_EQ_RETAINED_EARNINGS"
PROFIT_AND_LOSS_ACCOUNT_TYPES = {
    AccountType.INCOME,
    AccountType.REVENUE,
    AccountType.OTHER_INCOME,
    AccountType.CONTRA_INCOME,
    AccountType.EXPENSE,
    AccountType.COST_OF_SALES,
    AccountType.OTHER_EXPENSE,
    AccountType.CONTRA_EXPENSE,
}


def period_rollover_reference(period_id: UUID) -> str:
    return f"{PERIOD_ROLLOVER_REFERENCE_PREFIX}{period_id}"


def period_rollover_journal_condition():
    reference = func.coalesce(JournalEntry.reference, "")
    return and_(
        JournalEntry.source_type == JournalSourceType.SYSTEM,
        reference.like(f"{PERIOD_ROLLOVER_REFERENCE_PREFIX}%"),
    )


def _active_rollover_journal(
    db: Session,
    *,
    company_id: UUID,
    period_id: UUID,
) -> JournalEntry | None:
    return db.scalar(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.accounting_period_id == period_id,
            JournalEntry.source_type == JournalSourceType.SYSTEM,
            JournalEntry.reference == period_rollover_reference(period_id),
            JournalEntry.status == JournalStatus.POSTED,
        )
        .order_by(JournalEntry.entry_number.desc())
        .limit(1)
    )


def _retained_earnings_category(db: Session, company_id: UUID) -> ReportingCategory | None:
    return db.scalar(
        select(ReportingCategory)
        .where(
            ReportingCategory.code == RETAINED_EARNINGS_CATEGORY_CODE,
            or_(ReportingCategory.company_id == company_id, ReportingCategory.company_id.is_(None)),
        )
        .order_by(case((ReportingCategory.company_id == company_id, 0), else_=1))
        .limit(1)
    )


def _find_or_create_retained_earnings_account(
    db: Session,
    *,
    company_id: UUID,
    actor_user_id: UUID,
) -> Account:
    rows = db.execute(
        select(Account, ReportingCategory.code)
        .outerjoin(ReportingCategory, ReportingCategory.id == Account.reporting_category_id)
        .where(
            Account.company_id == company_id,
            Account.account_type == AccountType.EQUITY,
            Account.is_active.is_(True),
        )
    ).all()
    for account, _ in rows:
        if account.account_code == "3110":
            return account
    for account, _ in rows:
        if account.name.strip().casefold() == "retained earnings":
            return account
    for account, category_code in rows:
        if (
            category_code == RETAINED_EARNINGS_CATEGORY_CODE
            and "retained earnings" in account.name.casefold()
        ):
            return account

    existing_codes = set(
        db.scalars(select(Account.account_code).where(Account.company_id == company_id)).all()
    )
    account_code = next(
        (
            code
            for code in ("3110", "RETAINED-EARNINGS", "SYSTEM-RETAINED-EARNINGS")
            if code not in existing_codes
        ),
        None,
    )
    suffix = 2
    while account_code is None:
        candidate = f"SYSTEM-RETAINED-EARNINGS-{suffix}"
        if candidate not in existing_codes:
            account_code = candidate
        suffix += 1
    category = _retained_earnings_category(db, company_id)
    account = Account(
        company_id=company_id,
        account_code=account_code,
        name="Retained Earnings",
        account_type=AccountType.EQUITY,
        reporting_category_id=category.id if category else None,
        default_tax_code_id=None,
        is_active=True,
        allow_manual_posting=False,
    )
    db.add(account)
    db.flush()
    log_audit_event(
        db,
        action="accounting_period.retained_earnings_account_created",
        summary="Created system Retained Earnings account",
        entity_type=EntityType.ACCOUNT.value,
        entity_id=account.id,
        actor_user_id=actor_user_id,
        company_id=company_id,
        metadata={"account_code": account.account_code},
    )
    return account


def _period_profit_and_loss_balances(
    db: Session,
    *,
    period: AccountingPeriod,
) -> list[tuple[Account, Decimal]]:
    rows = db.execute(
        select(
            Account,
            (
                func.coalesce(func.sum(JournalLine.debit_amount), 0)
                - func.coalesce(func.sum(JournalLine.credit_amount), 0)
            ).label("raw_balance"),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(
            Account.company_id == period.company_id,
            Account.account_type.in_(PROFIT_AND_LOSS_ACCOUNT_TYPES),
            JournalEntry.accounting_period_id == period.id,
            JournalEntry.status == JournalStatus.POSTED,
            ~period_rollover_journal_condition(),
        )
        .group_by(Account.id)
        .order_by(Account.account_code.asc())
    ).all()
    return [
        (account, Decimal(raw_balance or ZERO))
        for account, raw_balance in rows
        if Decimal(raw_balance or ZERO) != ZERO
    ]


def draft_journal_count(db: Session, *, period: AccountingPeriod) -> int:
    return int(
        db.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.company_id == period.company_id,
                JournalEntry.accounting_period_id == period.id,
                JournalEntry.status == JournalStatus.DRAFT,
            )
        )
        or 0
    )


def create_period_earnings_rollover(
    db: Session,
    *,
    period: AccountingPeriod,
    actor_user_id: UUID,
) -> JournalEntry | None:
    remaining_drafts = draft_journal_count(db, period=period)
    if remaining_drafts:
        journal_label = "journal remains" if remaining_drafts == 1 else "journals remain"
        raise ValueError(
            f"Cannot lock {period.name}: {remaining_drafts} draft {journal_label}. "
            "Review and post or remove every draft journal before locking the period."
        )

    existing_rollover = _active_rollover_journal(
        db,
        company_id=period.company_id,
        period_id=period.id,
    )
    if existing_rollover is not None:
        return existing_rollover

    balances = _period_profit_and_loss_balances(db, period=period)
    if not balances:
        return None

    total_raw_balance = sum((raw_balance for _, raw_balance in balances), ZERO)
    retained_earnings_account = (
        _find_or_create_retained_earnings_account(
            db,
            company_id=period.company_id,
            actor_user_id=actor_user_id,
        )
        if total_raw_balance != ZERO
        else None
    )
    journal = JournalEntry(
        company_id=period.company_id,
        entry_number=_next_entry_number(db, period.company_id),
        entry_date=period.end_date,
        accounting_period_id=period.id,
        status=JournalStatus.POSTED,
        source_type=JournalSourceType.SYSTEM,
        description=f"Automatic profit and loss rollover for {period.name}",
        reference=period_rollover_reference(period.id),
        posted_at=datetime.now(timezone.utc),
        posted_by_user_id=actor_user_id,
        created_by_user_id=actor_user_id,
    )
    for account, raw_balance in balances:
        journal.lines.append(
            JournalLine(
                line_number=len(journal.lines) + 1,
                account_id=account.id,
                description=f"Close {account.account_code} {account.name}",
                debit_amount=-raw_balance if raw_balance < ZERO else ZERO,
                credit_amount=raw_balance if raw_balance > ZERO else ZERO,
            )
        )
    if retained_earnings_account is not None:
        journal.lines.append(
            JournalLine(
                line_number=len(journal.lines) + 1,
                account_id=retained_earnings_account.id,
                description=f"Transfer {period.name} result to retained earnings",
                debit_amount=total_raw_balance if total_raw_balance > ZERO else ZERO,
                credit_amount=-total_raw_balance if total_raw_balance < ZERO else ZERO,
            )
        )

    debit_total = sum((line.debit_amount for line in journal.lines), ZERO)
    credit_total = sum((line.credit_amount for line in journal.lines), ZERO)
    if len(journal.lines) < 2 or debit_total != credit_total:
        raise RuntimeError("Automatic period earnings rollover did not produce a balanced journal")

    db.add(journal)
    db.flush()
    log_audit_event(
        db,
        action="accounting_period.earnings_rolled_over",
        summary=f"Rolled {period.name} profit and loss into retained earnings",
        entity_type=EntityType.ACCOUNTING_PERIOD.value,
        entity_id=period.id,
        actor_user_id=actor_user_id,
        company_id=period.company_id,
        metadata={
            "journal_entry_id": str(journal.id),
            "journal_entry_number": journal.entry_number,
            "retained_earnings_account_id": (
                str(retained_earnings_account.id) if retained_earnings_account else None
            ),
            "net_profit": str(-total_raw_balance),
            "closed_account_count": len(balances),
        },
    )
    return journal


def void_period_earnings_rollover(
    db: Session,
    *,
    period: AccountingPeriod,
    actor_user_id: UUID,
) -> JournalEntry | None:
    rollover = _active_rollover_journal(
        db,
        company_id=period.company_id,
        period_id=period.id,
    )
    if rollover is None:
        return None

    rollover.status = JournalStatus.VOIDED
    db.flush()
    log_audit_event(
        db,
        action="accounting_period.earnings_rollover_voided",
        summary=f"Voided {period.name} retained earnings rollover before unlocking",
        entity_type=EntityType.ACCOUNTING_PERIOD.value,
        entity_id=period.id,
        actor_user_id=actor_user_id,
        company_id=period.company_id,
        metadata={"rollover_journal_entry_id": str(rollover.id)},
    )
    return rollover


def latest_active_rollover_date(
    db: Session,
    *,
    company_id: UUID,
    as_of_date: date,
) -> date | None:
    return db.scalar(
        select(JournalEntry.entry_date)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.source_type == JournalSourceType.SYSTEM,
            JournalEntry.reference.like(f"{PERIOD_ROLLOVER_REFERENCE_PREFIX}%"),
            JournalEntry.status == JournalStatus.POSTED,
            JournalEntry.entry_date <= as_of_date,
        )
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.entry_number.desc())
        .limit(1)
    )


def configured_financial_year_start(
    db: Session,
    *,
    company_id: UUID,
    as_of_date: date,
) -> date:
    configuration = db.scalar(
        select(CompanyConfigurationVersion)
        .where(
            CompanyConfigurationVersion.company_id == company_id,
            CompanyConfigurationVersion.effective_from <= as_of_date,
        )
        .order_by(
            CompanyConfigurationVersion.effective_from.desc(),
            CompanyConfigurationVersion.version_number.desc(),
        )
        .limit(1)
    )
    month = configuration.financial_year_start_month if configuration else 1
    day = configuration.financial_year_start_day if configuration else 1

    def start_for_year(year: int) -> date:
        return date(year, month, min(day, monthrange(year, month)[1]))

    candidate = start_for_year(as_of_date.year)
    return candidate if candidate <= as_of_date else start_for_year(as_of_date.year - 1)


def current_earnings_start_date(
    db: Session,
    *,
    company_id: UUID,
    as_of_date: date,
) -> date:
    financial_year_start = configured_financial_year_start(
        db,
        company_id=company_id,
        as_of_date=as_of_date,
    )
    latest_rollover = latest_active_rollover_date(
        db,
        company_id=company_id,
        as_of_date=as_of_date,
    )
    if latest_rollover is None:
        return financial_year_start
    return max(financial_year_start, latest_rollover + timedelta(days=1))
