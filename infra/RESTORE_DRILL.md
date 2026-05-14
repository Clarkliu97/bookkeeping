# Restore Drill Procedure

## Purpose

This procedure validates that backup sets can be restored with both database content and supporting document files intact.

The goal is operational confidence, not application feature testing.

## Cadence

- run monthly as the default operational cadence
- run after any substantial backup-script or storage-path change
- run after infrastructure migration affecting PostgreSQL volumes or document storage

## Inputs

- one recent backup set created by [infra/scripts/backup_postgres.ps1](scripts/backup_postgres.ps1)
- an operator with access to the internal deployment environment
- the current `.env` values for PostgreSQL and storage paths

## Preconditions

1. Choose a backup set that includes `database.sql`, `metadata.json`, and, where documents exist, `documents.zip`.
2. Confirm the target environment is either maintenance-only or isolated from normal user traffic.
3. Record the chosen backup folder and operator in the drill log.

## Drill Steps

1. Confirm the backup set contents match the expected files.
2. Stop or isolate normal user access.
3. Run [infra/scripts/restore_postgres.ps1](scripts/restore_postgres.ps1) against the chosen backup directory.
4. Start the application stack if it was stopped.
5. Verify `GET /health/ready` returns `200`.
6. Verify `GET /metrics` responds and still reports readiness status.
7. Open the operations dashboard in the web app and confirm readiness, request metrics, and alert state load successfully.
8. Spot-check one document-backed record and one export or report flow.
9. Record elapsed time, issues found, and corrective actions.

## Pass Criteria

- restore completed without manual database surgery
- readiness returned healthy after restore
- document storage remained accessible
- at least one traceability path from record to document was verified

## Failure Handling

- treat any missing document archive, unreadable SQL dump, or failed readiness check as a failed drill
- keep the environment in maintenance mode until the issue is understood
- open a follow-up operational ticket for any corrective action