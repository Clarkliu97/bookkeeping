# Backup and Restore

## Scope

Operational backups must cover both:

- PostgreSQL data
- document storage under `storage/documents`

The accounting records and the source/export files must stay in sync to preserve traceability.

## Backup Workflow

Use [infra/scripts/backup_postgres.ps1](scripts/backup_postgres.ps1) from the repository root.

Outputs per run:

- timestamped folder under `BACKUP_OUTPUT_DIR` or `./backups`
- `database.sql` PostgreSQL dump
- `documents.zip` archive of document storage
- `metadata.json` summary of the backup set

## Restore Workflow

Use [infra/scripts/restore_postgres.ps1](scripts/restore_postgres.ps1) from the repository root with a selected backup directory.

Restore steps performed by the script:

1. validate the backup set exists
2. restore PostgreSQL from `database.sql`
3. replace document storage with the archived files

## Safety Notes

- restore only from a backup set captured together
- prefer restoring while services are stopped or in maintenance mode
- verify `/health/ready` after restore
- spot-check a document download and a key report after recovery

## Restore Drill Cadence

- run a restore drill at least monthly
- record the backup set used, operator, timing, and pass/fail evidence
- use [infra/RESTORE_DRILL.md](RESTORE_DRILL.md) as the standard procedure
- capture the result in [infra/RESTORE_DRILL_LOG_TEMPLATE.md](RESTORE_DRILL_LOG_TEMPLATE.md) or an equivalent internal operations log