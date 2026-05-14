# Backup and Restore

## Scope

Operational backups must cover both:

- PostgreSQL data
- document storage under `storage/documents`

The accounting records and the source/export files must stay in sync to preserve traceability.

## Backup Workflow

Use either [infra/scripts/backup_postgres.ps1](scripts/backup_postgres.ps1) on Windows PowerShell or [infra/scripts/backup_postgres.sh](scripts/backup_postgres.sh) in Ubuntu or other Bash environments.

Examples from the repository root:

```powershell
pwsh ./infra/scripts/backup_postgres.ps1
```

```bash
sh ./infra/scripts/backup_postgres.sh
```

Outputs per run:

- timestamped folder under `BACKUP_OUTPUT_DIR` or `./backups`
- `database.sql` PostgreSQL dump
- `documents.zip` archive of document storage
- `metadata.json` summary of the backup set

## Restore Workflow

Use either [infra/scripts/restore_postgres.ps1](scripts/restore_postgres.ps1) on Windows PowerShell or [infra/scripts/restore_postgres.sh](scripts/restore_postgres.sh) in Ubuntu or other Bash environments with a selected backup directory.

Examples from the repository root:

```powershell
pwsh ./infra/scripts/restore_postgres.ps1 -BackupDir ./backups/<timestamp>
```

```bash
sh ./infra/scripts/restore_postgres.sh ./backups/<timestamp>
```

Restore steps performed by the script:

1. validate the backup set exists
2. drop and recreate the target PostgreSQL database
3. restore PostgreSQL from `database.sql`, stopping on the first SQL error
4. replace document storage with the archived files through a one-off Docker helper so bind-mounted storage can be rebuilt even when the host user cannot delete the directory directly
5. repair legacy Windows PowerShell mojibake in transferred journal descriptions when detected

## Safety Notes

- restore only from a backup set captured together
- the restore scripts are destructive for the target database and rebuild it before loading the backup
- prefer restoring while services are stopped or in maintenance mode
- verify `/health/ready` after restore
- spot-check a document download and a key report after recovery
- Windows PowerShell backups now use Docker file copy instead of a text pipeline so UTF-8 journal text is preserved in `database.sql`

## Restore Drill Cadence

- run a restore drill at least monthly
- record the backup set used, operator, timing, and pass/fail evidence
- use [infra/RESTORE_DRILL.md](RESTORE_DRILL.md) as the standard procedure
- capture the result in [infra/RESTORE_DRILL_LOG_TEMPLATE.md](RESTORE_DRILL_LOG_TEMPLATE.md) or an equivalent internal operations log
