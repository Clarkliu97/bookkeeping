# Operational Hardening

This directory contains deployment, backup, and recovery assets for the internal bookkeeping and tax support system.

## Deployment Shape

Recommended initial production shape:

- one internal VPS or server
- Docker Compose for `db`, `api`, and `web`
- persistent volume for PostgreSQL data
- persistent volume or mounted storage for document files
- reverse proxy or internal gateway in front of the web and API services where required by the environment

## Health Checks

- database health is provided by `pg_isready` in Docker Compose
- API liveness is served at `/health/live`
- API readiness is served at `/health/ready`
- readiness checks confirm database reachability and document storage availability

## Logging

- API runtime logs are JSON-formatted by default
- each request receives or echoes an `X-Request-ID`
- request logs include method, path, status code, and duration

## Backup and Restore Assets

- [infra/scripts/backup_postgres.ps1](scripts/backup_postgres.ps1) and [infra/scripts/backup_postgres.sh](scripts/backup_postgres.sh): create a timestamped PostgreSQL dump plus document archive
- [infra/scripts/restore_postgres.ps1](scripts/restore_postgres.ps1) and [infra/scripts/restore_postgres.sh](scripts/restore_postgres.sh): rebuild the target PostgreSQL database from a chosen backup directory and replace document storage
- [infra/RESTORE_DRILL.md](RESTORE_DRILL.md): recurring restore-drill procedure and evidence checklist
- [infra/RESTORE_DRILL_LOG_TEMPLATE.md](RESTORE_DRILL_LOG_TEMPLATE.md): run log template for scheduled restore drills

## Recovery Notes

- restore into a stopped or maintenance-mode environment where possible
- database restore should be paired with the matching document archive from the same backup set
- verify `/health/ready` after restore before returning the system to use