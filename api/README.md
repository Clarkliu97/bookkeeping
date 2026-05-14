# API

FastAPI backend for the internal bookkeeping and tax support system.

The backend is organized as a modular monolith around accounting, compliance support, review, and audit domains.

## Operational Notes

- Liveness endpoint: `/health/live`
- Readiness endpoint: `/health/ready`
- Aggregate health endpoint: `/health`
- Metrics endpoint: `/metrics`
- Recent alerts endpoint: `/alerts/recent`
- Request-scoped logging includes `X-Request-ID` correlation values on responses and structured JSON output by default.

## Logging Configuration

- `API_LOG_LEVEL`: standard Python log level such as `DEBUG`, `INFO`, or `WARNING`
- `API_LOG_JSON`: `true` or `false` for JSON log formatting

## Metrics and Alert Hooks

- `API_METRICS_ENABLED`: enables the in-process Prometheus-style metrics endpoint
- `API_ALERT_WEBHOOK_URL`: optional webhook target for degraded-readiness alert delivery
- `API_ALERT_WEBHOOK_TIMEOUT_SECONDS`: timeout for webhook delivery attempts
- `API_ALERT_MIN_INTERVAL_SECONDS`: minimum interval before the same alert code is emitted again

## Backup and Restore

Operational backup and restore scripts for PostgreSQL data and document storage live under [infra/scripts/backup_postgres.ps1](../infra/scripts/backup_postgres.ps1) and [infra/scripts/restore_postgres.ps1](../infra/scripts/restore_postgres.ps1).

## Database Migrations

Before using the API against PostgreSQL, apply the Alembic migrations:

```bash
cd api
C:/ProgramData/miniconda3/envs/bookkeeping/python.exe -m alembic upgrade head
```

If this step is skipped, bootstrap and other API calls will fail because the database tables do not exist yet.
