import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text_repair import repair_windows_mojibake
from app.db.models.accounting import JournalEntry, JournalLine
from app.db.session import SessionLocal


def repair_transferred_accounting_text(db: Session) -> dict[str, int]:
    journal_entry_updates = 0
    journal_line_updates = 0

    journal_entries = list(db.scalars(select(JournalEntry).where(JournalEntry.description.contains("鈥"))).all())
    for journal in journal_entries:
        repaired_description = repair_windows_mojibake(journal.description)
        if repaired_description != journal.description:
            journal.description = repaired_description
            journal_entry_updates += 1

    journal_lines = list(db.scalars(select(JournalLine).where(JournalLine.description.contains("鈥"))).all())
    for line in journal_lines:
        repaired_description = repair_windows_mojibake(line.description)
        if repaired_description != line.description:
            line.description = repaired_description
            journal_line_updates += 1

    return {
        "journal_entries_updated": journal_entry_updates,
        "journal_lines_updated": journal_line_updates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair legacy Windows-transferred mojibake in accounting descriptions.")
    parser.add_argument("--apply", action="store_true", help="Persist repaired journal entry and journal line descriptions.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        summary = repair_transferred_accounting_text(session)
        total_updates = summary["journal_entries_updated"] + summary["journal_lines_updated"]
        if args.apply and total_updates:
            session.commit()
        else:
            session.rollback()

        mode = "applied" if args.apply else "dry-run"
        print(
            f"{mode}: journal_entries_updated={summary['journal_entries_updated']} "
            f"journal_lines_updated={summary['journal_lines_updated']}"
        )
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())