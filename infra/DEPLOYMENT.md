# Deployment Shape

## Target Shape

Phase 12 assumes a conservative internal deployment model:

- single internal server or VPS
- Docker Compose orchestrating `db`, `api`, and `web`
- PostgreSQL as the system of record
- local persistent storage for uploaded documents and exported review packs

This stays aligned with the repository scope: internal use, traceable review workflows, and no public SaaS complexity.

## Container Roles

### `db`

- PostgreSQL 16
- persistent named volume for data files
- container health driven by `pg_isready`

### `api`

- FastAPI application
- structured JSON request logging
- readiness endpoint checks database and document storage
- mounted storage path for document assets

### `web`

- Next.js internal frontend
- depends on healthy API startup

## Deployment Steps

1. Create `.env` from `.env.example` with production credentials and paths.
2. Ensure document storage and backup directories are on persistent disk.
3. Start services with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d`.
4. Confirm `docker compose ps` shows healthy `db` and `api` services.
5. Verify `http://<host>:8000/health/ready` returns `200` before user traffic.

## Environment Recommendations

- set a strong `API_SECRET_KEY`
- restrict `API_ALLOWED_ORIGINS` to the internal frontend origin
- keep `API_BIND_ADDRESS` and `WEB_BIND_ADDRESS` on `127.0.0.1` unless another interface is intentionally required
- keep PostgreSQL and document storage on persistent disks
- direct backup output to a path outside ephemeral container filesystems