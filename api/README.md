# API

FastAPI backend for the internal bookkeeping and tax support system.

The backend is organized as a modular monolith around accounting, compliance support, review, and audit domains.

Employment support is included for worker and engagement records, work-rights reviews, compensation-support settings, leave snapshots, reimbursements, issued assets, and review exports. It does not calculate payroll or lodge STP reports.

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

`API_ALERT_COOLDOWN_SECONDS` remains accepted as a legacy alias for `API_ALERT_MIN_INTERVAL_SECONDS`. If both are set, `API_ALERT_MIN_INTERVAL_SECONDS` takes precedence.

## Environment Files

The API loads the repository-root `.env` first and `api/.env` second. Process environment variables override both files. Docker Compose injects the repository-root values directly into the container.

For a host-run API, use `api/.env` to override Docker-specific values, especially the database hostname and document path:

```dotenv
API_DATABASE_URL=postgresql+psycopg://bookkeeping:bookkeeping@localhost:5432/bookkeeping_tax
API_DOCUMENT_STORAGE_PATH=../storage/documents
```

## Accounting Period Rollover

`POST /companies/{company_id}/periods/{period_id}/lock` automatically closes the period's posted income and expense balances into retained earnings before marking the period locked. The service detects an active equity account with code `3110` or the name `Retained Earnings`. If one is not available, it creates a system-managed, non-manual-posting retained-earnings account and uses the standard retained-earnings reporting category when present.

The lock endpoint returns `400` while any draft journal remains assigned to the period, including when an older locked period is being rechecked. Draft entries must be reviewed and posted or removed; they are never silently included in a posted equity close. The close is a balanced, posted `SYSTEM` journal dated on the period end date and identified by `PERIOD-ROLLOVER:{period_id}`. Repeated calls are idempotent. Calling the lock endpoint for an already locked period rechecks it and backfills a missing rollover without adding another lock or duplicating an existing journal; this supports periods locked before the feature was introduced. Periods with no posted profit-and-loss activity do not need a close journal.

Unlocking a period voids its active rollover and records an audit event. Relocking recalculates the current posted balances and creates a new rollover version. BAS approval and tax-workpaper approval call the same service when their policy automatically locks accounting periods.

Financial reports handle the close deliberately: profit-and-loss reports exclude rollover journals, while the trial balance and general ledger include them. Balance-sheet current earnings start at the later of the configured financial-year start and the day after the latest active rollover, avoiding duplicate equity.

## Journal Posting

`POST /companies/{company_id}/journals/{journal_id}/post` posts one draft journal. `POST /companies/{company_id}/journals/bulk-post` accepts `{ "journal_ids": [...] }` with between 1 and 500 unique company journal IDs and returns the posted journals in the submitted order.

Both routes require prepare permission and apply the same controls: every journal must still be a draft, belong to an unlocked accounting period, contain at least two valid one-sided lines, balance exactly, and reference valid accounts that allow manual posting. Bulk posting validates the complete selection before changing any journal, uses one posting timestamp, records an audit event for every entry, and commits once. If any selected journal is missing or invalid, no journal in that batch is posted.

## AI Journal Drafting

The journal-recommendation API accepts PDF and supported image evidence in two explicit modes:

- `single`: exactly one evidence document and exactly one recommended journal
- `multiple`: from one to 50 evidence documents and from one to 50 recommended journals

The create request is multipart form data. It accepts optional repeated `existing_document_ids` fields for documents already stored under the company, optional repeated `files` fields for new uploads, plus `analysis_mode`, `model`, and optional operator context or target-period fields. At least one existing document or new file is required. Existing IDs must be unique and belong to the route company.

Evidence receives stable numbers: selected existing documents first in submitted order, then new files in upload order. Prompt metadata and the content marker immediately before each file carry both the authoritative run-scoped `document_number` and the persistent `document_id`; model output must reference the number through `source_document_numbers`. Existing documents are linked to the run without duplicating their stored content. The same source number is retained when evidence is shown on a recommendation or linked to an accepted draft, including when one stored document supports multiple journals. The structured result groups those numbers per recommended journal, so several documents can support the same economic transaction while unrelated transactions remain separate.

Document assignments are many-to-many. A source such as a monthly bank statement can be assigned to every journal containing a transaction evidenced by that statement. When a multiple-mode run contains more than one evidence document, an active `accrual` reporting basis also adds a conditional timing instruction: when visible clearance evidence is at least five calendar days after the invoice date, prefer separate invoice-recognition and liability-clearance journals when the evidence supports that treatment. Cash-basis and single-document runs do not receive this instruction.

Before a run becomes review-ready, the service verifies that every selected or uploaded document is assigned, recommendation and line numbers are sequential, every line is one-sided, and every recommended journal balances independently. Accepting a batch returns `{ "journals": [...] }`, creates all drafts in one transaction, and links each draft only to the documents assigned to it. Nothing is posted automatically.

Batch limits are configured with `API_JOURNAL_AI_MAX_FILE_COUNT` (maximum `50`), `API_JOURNAL_AI_MAX_FILE_SIZE_BYTES`, `API_JOURNAL_AI_MAX_TOTAL_SIZE_BYTES`, and `API_JOURNAL_AI_REQUEST_TIMEOUT_SECONDS`. `API_JOURNAL_AI_WEB_SEARCH_ENABLED` controls optional review-only verification for supported models. Larger batches use more provider input and output tokens, so the model list endpoint exposes the active limits and a batch-oriented planning estimate to the frontend.

The catalog includes `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`. Requests use `high`, `medium`, and `low` reasoning effort respectively; `low` is the supported API equivalent used for the requested light-effort Luna profile. All three accept image input, structured output, Responses API requests, and optional web search. GPT-5.6 requests retain the deterministic prompt cache key but omit the legacy `prompt_cache_retention` field so the provider can continue using implicit caching without receiving a deprecated parameter. OpenAI's [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) is the source of truth for these request settings.

The displayed estimates use 40,000 uncached input tokens and 3,500 total billed output tokens, including reasoning tokens. At the current standard token rates, this produces $305.00 per 1,000 calls for Sol, $152.50 for Terra, and $61.00 for Luna. The endpoint applies the same formula to every catalog model for an apples-to-apples baseline; actual usage can be higher or lower depending on documents, reasoning, tools, and cache behavior.

Provider-facing monetary fields use JSON Schema `number` values and are parsed into Python `Decimal` values locally. This avoids Pydantic's default decimal-string regex, whose lookaround syntax is not accepted by OpenAI Structured Outputs, while preserving exact decimal accounting checks after parsing.

## Backup and Restore

Operational backup and restore scripts for PostgreSQL data and document storage live under [infra/scripts/backup_postgres.ps1](../infra/scripts/backup_postgres.ps1), [infra/scripts/backup_postgres.sh](../infra/scripts/backup_postgres.sh), [infra/scripts/restore_postgres.ps1](../infra/scripts/restore_postgres.ps1), and [infra/scripts/restore_postgres.sh](../infra/scripts/restore_postgres.sh).

## Database Migrations

Before using the API against PostgreSQL, apply the Alembic migrations:

```bash
cd api
python -m alembic upgrade head
```

If this step is skipped, bootstrap and other API calls will fail because the database tables do not exist yet.

## Validation

```bash
python -m alembic check
python -m ruff check .
python -m pytest
```

The GitHub Actions validation job enforces Ruff and pytest, together with frontend lint, type checking, build, and browser tests, for pushes to `main` and pull requests. Run the Alembic drift check against a migrated PostgreSQL database before merging model or migration changes.
