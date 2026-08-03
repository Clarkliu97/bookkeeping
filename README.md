# Bookkeeping Tax

Internal bookkeeping and tax support system for Australian companies.

This project helps an internal team maintain bookkeeping records, prepare BAS support numbers, generate company tax workpapers, and assemble review packs for manual entry into ATO website forms or paper forms. It is review-oriented support software, not an ATO lodgment platform and not a replacement for accountant review.

## What The Project Does

The implemented system currently supports:

- company setup with versioned bookkeeping and reporting configuration
- chart of accounts, tax codes, and reporting categories
- balanced journal entry drafting, single or atomic multi-entry posting, reversal, and audit history
- automatic period-end profit-and-loss rollover into retained earnings
- source document upload, journal evidence linking, and document download
- employment support records for workers, engagements, work rights, compensation, leave, reimbursements, and issued assets
- bank CSV import staging, duplicate detection, confirmation, and reconciliation workflows
- BAS period generation, BAS runs, adjustments, review notes, approvals, and exports
- monthly budget and forecast planning with posted-actual roll-forward, scenario comparison, controlled review states, and CSV/PDF outputs
- financial reporting including trial balance, profit and loss, balance sheet, cash flow, statement of changes in equity, and general ledger, with browser, CSV, and archive-ready PDF outputs
- fixed asset register maintenance, disposals, depreciation runs, and depreciation journal posting
- annual company tax workpaper packs with adjustments, notes, exceptions, approvals, and exports
- operational health, metrics, alerts, backup and restore guidance, and a browser diagnostics workbench
- AI-assisted journal drafting in single-document or multi-document mode, reusing stored evidence or accepting new uploads, with up to 50 PDFs or images grouped into one or more review-only journal recommendations

The project explicitly does not support:

- direct ATO lodgment
- tax-agent practice management
- payroll or STP lodgment
- bank scraping
- automatic finalization of tax returns without human review

## Product Principles

- Ledger first: reports and support packs are derived from accounting records, not raw bank data.
- Review before use: all BAS and tax outputs are support calculations only.
- Traceability: reported numbers should drill back to journals, lines, documents, imports, or adjustments.
- Auditability: workflow actions and important accounting changes should remain visible and explainable.
- No silent changes: approved or locked periods should not be altered invisibly.

## Functional Coverage

### Setup And Governance

- bootstrap the first admin user
- create companies and versioned company configurations
- manage company access permissions for prepare, review, approve, and administer roles
- maintain reporting categories, tax codes, and chart of accounts
- seed new companies from the supplied chart-of-accounts, tax-code, and reporting-category templates

### Ledger And Bookkeeping

- create draft journals
- post journals through the normal validation path
- select and post up to 500 reviewed draft journals together from a searchable, period-aware popup; the batch is all-or-nothing
- reverse journals
- lock periods with an automatic, balanced system journal that closes posted profit-and-loss balances into retained earnings
- unlock periods with an audited void of the prior rollover so corrections can be posted before relocking
- review journal detail including source type, lines, status, references, and audit-relevant metadata
- search and filter journal lists by text and status
- inspect a ledger explorer that can show both draft and posted lines for review

### Documents And Evidence

- upload supporting documents
- link documents to journals
- preview linked journal evidence inside Bookkeeping
- open full evidence views for images and PDFs without leaving the review workflow

### Employment Support

- maintain worker and engagement records without providing payroll or STP lodgment
- track work-rights reviews, evidence dates, restrictions, and upcoming review items
- maintain compensation-support settings, leave-liability snapshots, reimbursements, and issued assets
- review employment dashboard queues for onboarding, expiring work rights, missing evidence, and finalization work
- export headcount, work-rights, leave-liability-support, and contractor-review CSV reports

### Banking And Reconciliation

- maintain bank accounts and link each one to its asset or liability ledger account
- upload bank CSV files into staged import sessions
- review staged rows and duplicate protection
- confirm imports before reconciliation
- create reconciliation sessions, scope statement rows and posted-journal candidates to the selected accounting period, compare deterministic ranked matches, allocate partial or complete n-to-1, 1-to-n, and n-to-n match groups, unmatch groups, ignore items, delete open sessions when a restart is needed, and complete sessions

### BAS Support

- generate BAS periods
- create BAS runs from accounting data
- review BAS totals, warnings, detail counts, adjustments, and review notes
- submit and approve BAS support workflows
- export BAS support packs

### Financial Reporting

- trial balance with date filtering
- profit and loss with date filtering
- balance sheet with current earnings
- direct-method cash flow statement with major classes of gross receipts and payments, operating/investing/financing subtotals, exchange-rate effects, cash-account composition, and opening-to-closing reconciliation
- statement of changes in equity with profit or loss, owner contributions, distributions, other movements, and opening-to-closing equity reconciliation
- general ledger with account filtering and running balances
- browser review, CSV export, and professionally formatted PDF export for every report
- per-report version selection so operators can run a final review version from posted journals only or a draft review version that includes draft journals

### Budget And Forecast

- create separate monthly budgets and forecasts for a twelve-month financial year
- plan future income and expenditure against active profit-and-loss accounts without posting journals or changing financial reports
- create and manage one-off, monthly, quarterly, half-yearly, or annual budget items with an account, amount per occurrence, starting month, optional ending month, and note
- enter account-month values directly, clear an entire account line, spread an annual amount deterministically, copy prior-year posted actuals, apply a growth rate, or import a reviewed CSV
- combine posted actuals through a selected month-end with explicit future forecast values, then fall back to the linked budget and finally a warned zero
- calculate projected revenue, expenses, gross profit, operating profit, and year-end net profit or loss
- compare two to four baseline, upside, downside, or custom scenarios
- submit, review, approve, lock, archive, clone, and audit planning versions
- retain calculation runs and export plan detail or forecast results as CSV and archive-ready PDF

### Year-End Support

- fixed asset register maintenance
- asset disposal workflow
- straight-line and diminishing-value depreciation support
- depreciation-run generation, posting, and CSV export
- annual tax workpaper packs with manual adjustments, notes, exceptions, approvals, and PDF export
- financial-year locking as part of tax-workpaper approval workflows

### Operations And Diagnostics

- liveness and readiness endpoints
- Prometheus-style metrics
- recent alert feed
- structured request logging with correlation IDs
- browser operations dashboard
- browser workbench for direct API and workflow testing
- backup, restore, and restore-drill documentation under `infra/`

## Frontend Guide

The Next.js frontend is the main operator interface. It is organized around workflow routes rather than technical modules.

### Navigation And Appearance

- The authenticated shell uses a compact workspace header, company-aware sidebar, and a dashboard directory that links to every business workspace.
- Dense routes use focused, consistently sized workspace tabs. Switching tabs changes the visible task area without discarding the loaded company data or hiding the other available functions from navigation.
- Setup separates company details, users and access, configuration versions, and reference data. Selecting a user opens an explicit update workflow; clearing the selection switches to the separate create-user workflow.
- Bookkeeping separates periods, journals, AI drafting, ledger exploration, and document management.
- Banking separates bank accounts/imports, reconciliation, and BAS support.
- Budget & Forecast separates plan overview and governance, monthly budget building, actual-plus-forecast calculation, and scenario comparison.
- Employment separates dashboard/report queues from detailed worker records.
- Reports separates trial balance, profit and loss, balance sheet, cash flow, changes in equity, and general ledger.
- Year-end separates fixed assets/depreciation from tax workpapers.
- Use the `Dark`/`Light` control in the global header to change appearance. The selected mode is stored in the browser and applies to the operator routes, Operations, and the API workbench.
- The API workbench remains available from the global header and dashboard directory so advanced or diagnostic API actions stay reachable even when they are not part of a routine business workflow.

### First Use

1. Start the stack.
2. Open the frontend in the browser.
3. Bootstrap the first admin user if the system is empty.
4. Sign in.
5. Create or select a company.

### Dashboard: `/`

Use the dashboard as the operational summary for the selected company. It shows high-level counts such as open periods, draft journals, staged imports, BAS warnings, and tax packs, plus an attention queue across bookkeeping, banking, and year-end work.

### Setup: `/setup`

Use Setup to establish the bookkeeping foundation for a company.

Typical tasks:

1. Create or edit the company record.
2. Open `Users & access` to create a new user, select an existing user for a distinct update workflow, and manage company permissions.
3. Review the active configuration version.
4. Add or adjust reporting categories.
5. Add or adjust tax codes.
6. Create or maintain accounts in the chart of accounts.
7. Review access rows for the users who can prepare, review, approve, or administer work.

This is the route to visit before operational work if a company is new or its accounting settings have changed.

### Bookkeeping: `/bookkeeping`

Use Bookkeeping for day-to-day ledger work.

Typical tasks:

1. Create accounting periods.
2. Draft journals manually.
3. Post a single reviewed draft, or use `Post multiple` to search, filter by accounting period, and select several drafts for one atomic posting action. Drafts in locked periods remain visible but cannot be selected until the period is unlocked.
4. Lock a completed period to close its posted profit-and-loss balances into retained earnings.
5. Search and filter journal lists.
6. Attach or review journal evidence.
7. Open the ledger explorer to inspect draft and posted journal lines.
8. Choose `Single document` when one item should produce one journal, or `Multiple documents` when an evidence bundle may contain several transactions. Selecting a second existing document, or combining an existing document with a new upload, automatically switches the frontend to multiple-document mode.
9. Search the existing-document library to reuse previously uploaded PDFs and images, such as a monthly bank statement. The checkbox list supports selecting several stored documents in a deliberate order; you can use stored evidence only, upload new files, or combine both.
10. Select up to 50 evidence documents in total. In multiple-document mode, stored documents retain their selection order and are numbered before new uploads; new files can be added in more than one selection and removed individually before analysis.
11. Review how the AI grouped the numbered evidence. Several documents can support one journal, and one source such as a monthly bank statement can support several journals, while unrelated transactions are returned as separate recommendations.
12. Review every recommended journal independently, including its evidence, date, reference, assumptions, GST handling, balanced lines, and any verification sources.
13. Accept the batch to create all recommended draft journals together, then review and post drafts individually or through the Journals tab's multi-entry posting popup.

### Period-End Earnings Rollover

Locking an accounting period first requires every journal assigned to it to be posted, reversed, voided, or removed; any remaining draft blocks the lock and the Periods workspace displays the blocking count. This prevents unreviewed balances from being silently omitted from equity. Once ready, the system checks the posted journals for non-zero income and expense balances. It reuses an active equity account with code `3110` or the name `Retained Earnings`; if neither exists, it creates a non-manual-posting `Retained Earnings` account and assigns the retained-earnings reporting category when available. It then posts a balanced `SYSTEM` journal on the period end date that closes each profit-and-loss account and transfers the net profit or loss to retained earnings. If the period has no posted profit-and-loss activity, no rollover journal is needed.

The rollover is idempotent while the period remains locked. Choosing `Lock` again safely checks an older locked period and backfills a missing rollover without duplicating one that is already posted. This is the upgrade path for periods locked before automatic rollover was introduced. Unlocking the period voids the active rollover and records the action in the audit trail; locking it again recalculates the balances and creates a new posted rollover. BAS approval policies and annual tax-workpaper approval use the same rollover behavior when they lock accounting periods automatically.

Profit-and-loss reports exclude these closing journals so the period's operating result remains visible. The trial balance and general ledger include them because they reflect the posted ledger. Balance-sheet `Current Earnings` begins at the later of the configured financial-year start and the day after the latest active rollover, preventing profit from appearing both in retained earnings and current earnings.

The statement of changes in equity also excludes system-generated rollover journals from its movement section because the same earnings are already presented as period profit or loss. It reconciles opening equity, the period result, contributions, distributions, and other direct equity movements to closing equity.

The cash flow statement follows the direct-method presentation encouraged by [AASB 107 Statement of Cash Flows](https://www.aasb.gov.au/admin/file/content105/c9/AASB107_08-15_COMPdec22_01-23.pdf). It aggregates ledger cash movements into major gross classes rather than listing individual journals: customer receipts, supplier and employee payments, tax payments/refunds, non-current asset and investment purchases/disposals, loans advanced/repaid, share capital, borrowings, lease principal, interest, dividends, and other material receipt/payment classes. Each line reports its source-transaction count, and the statement presents operating, investing, and financing subtotals, exchange-rate effects, opening and closing cash, the ledger reconciliation difference, and cash-account composition.

Accounts assigned to `BS_CA_CASH` are treated as cash and cash equivalents; asset accounts whose names include `cash` or `bank` are recognised as a compatibility fallback. Internal cash-to-cash transfers are omitted because their net movement is zero. For a consistent policy suitable for a non-financial entity, interest and dividends received are classified as investing cash flows, while interest paid, dividends/distributions paid, lease-liability principal payments, and borrowing movements are classified as financing cash flows. The dominant non-cash side of each journal determines its major gross class, so reporting-category and account-name quality still matters and professional review remains required.

The AI path is assistive only. It does not silently post entries. The backend requires every selected or uploaded evidence document to be assigned to at least one recommendation, validates each recommendation as independently balanced double-entry, and links only the assigned evidence to each accepted draft. Reusing a document does not create a duplicate upload; the existing company document is linked to the recommendation run and any accepted drafts that use it. Each document receives an authoritative source number for the run, and that same number is preserved in the recommendation review and accepted-journal evidence note, even when one stored document supports several entries. Batch acceptance is atomic: if any recommended journal cannot pass the normal account, tax-code, date, period, or balance controls, no journals from that batch are created.

When more than one evidence document is selected in multiple-document mode and the active company configuration uses the `accrual` reporting basis, the model receives an additional timing rule. If visible evidence shows a payment or bank-clearance date at least five calendar days after the invoice date, it should prefer an invoice-date recognition journal and a separate clearance-date journal when supportable. It must use visible dates, retain the relevant evidence on both entries, and avoid inventing or forcing the split when the documents are ambiguous.

### AI Model Choices And Cost Planning

The model selector is populated by the backend catalog. GPT-5.6 Sol, Terra, and Luna use explicit reasoning efforts of `high`, `medium`, and `low` respectively. OpenAI does not accept a `light` reasoning value, so Luna uses the supported low-effort setting. The configured effort and planning estimate are shown in the selector before analysis begins. See OpenAI's [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model) and [model catalog](https://developers.openai.com/api/docs/models) for the provider contract and current rates.

The estimates below use the current application baseline of 40,000 uncached input tokens and 3,500 total billed output tokens per moderate batch. Output includes any billed reasoning tokens. Rates and estimates are in USD and were reviewed against OpenAI's published model pricing on 2026-07-22.

| Model | Configured reasoning | Input / 1M | Output / 1M | Estimated / 1,000 calls |
| --- | --- | ---: | ---: | ---: |
| GPT-5.6 Sol | high | $5.00 | $30.00 | $305.00 |
| GPT-5.6 Terra | medium | $2.50 | $15.00 | $152.50 |
| GPT-5.6 Luna | low | $1.00 | $6.00 | $61.00 |
| GPT-5.5 | provider default | $5.00 | $30.00 | $305.00 |
| GPT-5.4 | provider default | $2.50 | $15.00 | $152.50 |
| GPT-5.4 mini | provider default | $0.75 | $4.50 | $45.75 |
| GPT-5 | minimal | $1.25 | $10.00 | $85.00 |
| GPT-5 mini | minimal | $0.25 | $2.00 | $17.00 |
| GPT-5 nano | minimal | $0.05 | $0.40 | $3.40 |

These are comparable planning baselines, not quotes. File count, extracted PDF text, image detail, number of journals, web-search calls, cache writes or hits, and actual reasoning-token use change the final charge. In particular, Sol at high reasoning can exceed the 3,500-output-token assumption on difficult batches. Provider usage is persisted so representative production runs can later replace the baseline with observed per-model averages.

### Employment: `/employment`

Use Employment for employment-support records that sit alongside bookkeeping but do not replace payroll, HR, migration, or legal systems.

Typical tasks:

1. Create workers and record one or more engagements.
2. Track engagement status, dates, role, department, and work location.
3. Record work-rights evidence, review status, restrictions, visa dates, and follow-up dates.
4. Maintain compensation-support settings and account references.
5. Capture leave-liability snapshots and reimbursement-support items.
6. Track issued assets and return status.
7. Review onboarding, work-rights, missing-document, and finalization queues.
8. Run or export headcount, work-rights, leave-liability-support, and contractor-review reports.

Worker-scoped records can only reference engagements belonging to that worker. Compensation account references must belong to the selected company.

### Banking: `/banking`

Use Banking for imported transaction workflows and BAS support.

Typical tasks:

1. Create bank accounts in the dedicated creation form and link each account to the asset or liability ledger account that records its cash or credit-card movement. The link is required for grouped reconciliation because the matcher compares the journal movement on that account rather than the journal's overall debit total.
2. Select an active bank account to update it, or delete it after confirming the warning. Deletion removes the account from new import and reconciliation workflows while retaining its historical banking records.
3. Upload a bank CSV file.
4. Review the staged import session.
5. Confirm the import when the rows look correct.
6. Create a reconciliation session. When an accounting period is selected, only statement rows dated within that period and posted journals assigned to that period are available in the matching window. A session without a period intentionally remains unrestricted.
7. To process the open statement queue conservatively, open the matching window, configure the amount tolerance, date window, and maximum sources per side, then select `Run auto reconcile`. It searches 1-to-1, 1-to-n, n-to-1, and n-to-n combinations using signed linked-ledger movement and transaction dates. Detailed journal-line amounts help choose between otherwise similar grouped candidates. Missing and equally ranked candidates remain unmatched rather than being guessed.
8. For a simple manual settlement, select one statement item and one posted journal. For batches, split settlements, or net settlements, use the checkboxes in the matching window to select one or many sources on each side, review the signed allocation totals, edit partial allocation amounts when needed, and create a grouped match.
9. A partial statement allocation remains open until its full signed amount is allocated. A group may contain both receipts and payments when reconciling a genuine net settlement, such as receipts less refunds or fees; the signed statement and ledger totals must still reconcile. The API prevents allocation against a source's direction, over-allocation, cross-currency groups, out-of-period sources, and reuse of one statement row in overlapping open sessions. A non-zero difference is accepted only within the entered tolerance and requires an explanatory note.
10. Review saved groups in the matching window and use `Unmatch` to reverse an incorrect group while the session is open. Manual and automatic group creation and unmatching are audited.
11. If an open session needs to be restarted, select `Delete session`, confirm the warning, and verify its linked bank rows have returned to staged status.
12. Complete the session when every statement item is fully allocated, matched, or intentionally ignored. Completed sessions are retained for audit history and cannot be edited or deleted.
13. Generate BAS periods.
14. Create a BAS run for a selected BAS period.
15. Review BAS lines, warnings, adjustments, and notes.
16. Submit, approve, and export BAS support outputs.

### Budget & Forecast: `/budget-forecast`

Use Budget & Forecast to plan future P&L performance without changing the accounting ledger.

Typical tasks:

1. Create a budget or forecast with a twelve-month financial-year range and scenario label.
2. For a draft plan, maintain its name, assumptions, preparer note, linked baseline budget, and actual-through cutoff in the separate management form.
3. Open `Budget builder` and add recurring or one-off budget items when the budget is driven by known income or expenses. Each item records its P&L account, amount per occurrence, frequency, starting month, optional ending month, and note. Overlapping items for the same account and month are added together.
4. Review the item-derived minimum shown under each protected grid value. The existing monthly grid remains editable above that minimum. Use the `Clear` button in an account row to blank all of its unprotected months in one action; months protected by budget items remain at their summed minimum. If an operator clears a protected value or enters less than the item total, the browser and API change it to the minimum and notify the operator. Select `Save planning values` to persist direct edits or a cleared line.
5. Enter any remaining monthly amounts directly against active income and expense accounts. Values are net of GST. Ordinary income and expenses are positive; contra accounts, refunds, or reductions are negative. Blank means unplanned, while zero is an explicit expectation when no budget-item floor applies.
6. Use the annual spread, prior-year actual copy, growth-rate, or CSV import tools when they are more efficient than direct entry. All of these paths enforce the same item-derived minimums. CSV imports require `account_code`, `period_start`, and `amount`; `note` is optional, and a successful preview is required before commit.
7. Open `Forecast`, choose the last completed fiscal month-end, and calculate a saved year-end run. Posted actual journals are used through the cutoff; rollover and draft journals are excluded.
8. Review income, expenses, gross profit, operating profit, net profit, budget variances, value sources, and warnings. A zero budget produces a blank percentage variance rather than a misleading percentage.
9. Compare two to four plans under `Scenarios`, or clone an approved plan into a new editable version or reforecast. Budget-to-budget cloning copies the item schedules; forecast versions retain monthly values without making the source budget items editable.
10. Submit the draft for review, record review, approve it, and optionally lock it. Approved and locked plans are immutable; use cloning to create the next revision.
11. Export plan detail or a saved forecast run as CSV or PDF for review and archiving.

Forecast values are resolved account by account and month by month in this order: posted actual for completed months, explicit forecast for future months, linked baseline budget, then zero with a warning. Planning records never create journal entries and do not affect trial balance, BAS, tax, reconciliation, or statutory financial reports.

### Reports: `/reports`

Use Reports for browser review and archive-ready financial outputs.

Available report panels:

- Trial balance
- Profit and loss
- Balance sheet
- Cash flow
- Changes in equity
- General ledger

Each panel supports running the report in the browser and exporting CSV or PDF. PDFs are designed for review packs and records retention: they include the legal company name, ABN/ACN when configured, reporting period, currency, version, generation timestamp, archive reference, repeating table headers, page numbers, and a final-review or draft-review notice. They are accounting support reports, not audited financial statements.

The `Version` selector lets the user choose:

- `Final review (posted only)` for conservative reporting based on posted journals only
- `Draft review (include draft entries)` when the operator wants a work-in-progress view that includes draft journals

### Year-End: `/year-end`

Use Year-end for fixed asset support and company tax workpapers.

Typical tasks:

1. Create or update fixed assets.
2. Dispose of assets when needed.
3. Create depreciation runs and post them.
4. Export depreciation review data.
5. Create a tax workpaper pack for the year period.
6. Add manual tax adjustments, notes, and exception items.
7. Submit and approve the pack.
8. Create the PDF export for accountant review.

### Operations: `/operations`

Use Operations for support and runtime visibility. It summarizes readiness, metrics, recent alerts, and restore-drill guidance. This route is for operational support, not bookkeeping data entry.

### Workbench: `/workbench`

Use Workbench as a browser-based diagnostics console for calling implemented API workflows directly. It is useful for QA, support checks, and endpoint verification without writing ad hoc scripts.

## Screens/Workflows

The screenshots below were captured from the live local development environment and show the current operator interface with sample company data.

### Dashboard Overview

The dashboard gives operators a quick company-level summary of queues, draft work, staged imports, BAS warning counts, and year-end workload.

![Dashboard overview](assets/screenshots/dashboard.png)

### Bookkeeping Workspace

Bookkeeping is the main day-to-day ledger screen for accounting periods, journal review, search and status filtering, evidence handling, and ledger inspection.

![Bookkeeping workspace](assets/screenshots/bookkeeping.png)

### Financial Reporting

The Reports route provides trial balance, profit and loss, balance sheet, cash flow, statement of changes in equity, and general ledger panels. Every panel supports browser review, CSV and archive-ready PDF export, and final-versus-draft selection.

![Financial reporting workspace](assets/screenshots/reports.png)

### Operations View

The Operations route exposes readiness, metrics, alerts, and recovery guidance for support and maintenance workflows.

![Operations dashboard](assets/screenshots/operations.png)

## Repository Layout

```text
.
├── .testing/               manual QA and test-support notes
├── api/                    FastAPI backend, business logic, migrations, tests
├── docs/                   backlog and schema documentation
├── infra/                  deployment, backup, restore, and recovery documents
├── storage/                local development document storage
├── web/                    Next.js frontend
├── docker-compose.yml      local multi-service runtime
├── chart_of_account_template.md
├── tax_codes.md
├── reporting_categories.md
└── README.md
```

## Architecture Summary

- frontend: Next.js 16, React 19, TypeScript
- backend: FastAPI, SQLAlchemy, Alembic
- database: PostgreSQL 16
- documents: local filesystem storage in development
- testing: pytest for backend, Playwright for browser workflows
- local orchestration: Docker Compose with `db`, `api`, `web`, and optional `e2e`

The development web service runs `next dev --webpack`. Compose keeps the web build cache, web dependencies, and E2E dependencies in dedicated named volumes so Linux container installs do not overwrite Windows host tooling through the repository bind mount.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 22+
- Python 3.12+

### Docker Compose Environment Setup

Copy `.env.example` to `.env` in the repository root. This root file is the Docker Compose environment file. Its default `API_DATABASE_URL` uses the Compose service hostname `db` and is not suitable for an API process launched directly on the host.

Important variables:

- `API_DATABASE_URL`: backend database connection string
- `API_SECRET_KEY`: JWT signing key
- `OPENAI_API_KEY`: required only for AI journal recommendation analysis
- `API_JOURNAL_AI_WEB_SEARCH_ENABLED`: enables optional web-search support for recommendation runs
- `API_JOURNAL_AI_MAX_FILE_COUNT`: maximum files in one recommendation run; defaults to `50` and cannot exceed `50`
- `API_JOURNAL_AI_MAX_FILE_SIZE_BYTES`: maximum size of each source file; defaults to `10485760` (10 MiB)
- `API_JOURNAL_AI_MAX_TOTAL_SIZE_BYTES`: maximum combined batch size; defaults to `104857600` (100 MiB)
- `API_JOURNAL_AI_REQUEST_TIMEOUT_SECONDS`: provider request timeout for a recommendation batch
- `API_ALLOWED_ORIGINS` and `API_ALLOWED_ORIGIN_REGEX`: CORS configuration
- `API_LOG_LEVEL` and `API_LOG_JSON`: backend logging behavior
- `API_METRICS_ENABLED`: enable the metrics endpoint
- `API_ALERT_WEBHOOK_URL`: optional degraded-readiness alert target
- `API_ALERT_WEBHOOK_TIMEOUT_SECONDS`: webhook delivery timeout
- `API_ALERT_MIN_INTERVAL_SECONDS`: minimum interval between alerts with the same code
- `NEXT_PUBLIC_API_BASE_URL`: leave blank when the browser should use the current hostname and `NEXT_PUBLIC_API_PORT`
- `NEXT_PUBLIC_API_PORT`: default API port used by the frontend
- `NEXT_ALLOWED_DEV_ORIGINS`: extra Next.js development origins as a comma-separated list or a short LAN range such as `192.168.1.100-253`

### Development Docker Compose

```bash
docker compose up -d --build
```

This command starts the normal development stack:

- `docker compose up` creates or recreates and starts the `db`, `api`, and `web` services in dependency order
- `-d` leaves the containers running in the background and returns control of the terminal
- `--build` rebuilds the development images before the containers start
- the optional `e2e` service is not started because it belongs to the `test` profile

The development targets use dedicated `:development` image tags. The API runs with autoreload and the web app runs `next dev --webpack` with bind-mounted source. Ordinary source edits are picked up by the development servers; use `--build` again after changing a Dockerfile, package lock, or installed dependency.

Expected local endpoints:

- frontend: `http://localhost:3000`
- backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

The API container runs Alembic migrations on startup before launching Uvicorn.

Inspect or follow the development services:

```bash
docker compose ps
docker compose logs -f api web
```

Build the development images without starting containers:

```bash
docker compose build
```

Stop and remove the development containers and network:

```bash
docker compose down
```

Running `docker compose up -d` without `--build` starts from the existing development images. Named volumes, including PostgreSQL data, are preserved by a normal `docker compose down`.

### Production Compose Override

For a long-lived server deployment, layer the production override on top of the base compose file:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The production override switches both services to dedicated `:production` image tags, removes the source bind mounts, runs the API without `--reload`, and runs the compiled frontend with `next start` instead of `next dev`. By default it binds ports `3000` and `8000` to `127.0.0.1`; set `WEB_BIND_ADDRESS` or `API_BIND_ADDRESS` in `.env` if the services must listen on another interface.

Inspect or follow the production services:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api web
```

Build the production images without starting containers:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
```

Stop and remove the production containers and network:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

Development and production use the same container names and published ports, so they cannot run simultaneously with the default configuration. Stop the active mode with its matching `down` command before starting the other mode. Do not add `-v` to `down` unless you intentionally want to delete named-volume data such as the PostgreSQL database.

The production file uses Docker Compose's `!override` YAML tag so inherited port and volume lists are replaced rather than appended. The repository's VS Code settings register this Compose tag with the YAML extension; it is not an application-specific value.

### LAN Access

The frontend can be reached from another device on the same LAN through the host machine IP, for example `http://192.168.x.x:3000`. By default, the frontend derives the API host from the current browser hostname, which makes LAN testing easier as long as the host firewall allows the published ports.

## Running Components Separately

### Backend

The API loads environment files in this order:

1. repository-root `.env`
2. `api/.env`, when present, as a local override
3. process environment variables, which have the highest priority

For a backend launched directly on the host, create `api/.env` with at least a host-reachable database URL. The document path below keeps standalone uploads in the repository-level `storage/` directory:

```dotenv
API_DATABASE_URL=postgresql+psycopg://bookkeeping:bookkeeping@localhost:5432/bookkeeping_tax
API_DOCUMENT_STORAGE_PATH=../storage/documents
```

Then install, migrate, and run the API:

```bash
cd api
pip install -e .[dev]
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Useful backend validation commands:

```bash
python -m pytest
python -m pytest tests/test_journal_recommendations.py
```

### Frontend

When running the frontend separately, put frontend overrides in `web/.env.local`; Next.js does not load the repository-root Compose file automatically. Defaults work when the browser and API are on the same host and the API uses port `8000`.

Example `web/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_API_PORT=8000
NEXT_ALLOWED_DEV_ORIGINS=192.168.1.100-253,web
```

```bash
cd web
npm install
npm run dev
```

Useful frontend validation commands:

```bash
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

On this Windows environment, direct `node` invocation may be more reliable than package-manager shims if `next` or `playwright` are not recognized:

```bash
node node_modules/next/dist/bin/next build
node node_modules/playwright/cli.js test --reporter=line
```

### Browser E2E In Compose

```bash
docker compose --profile test up --build e2e
```

## Operational Endpoints

- `/health/live`
- `/health/ready`
- `/health`
- `/metrics`
- `/alerts/recent`

These are surfaced both through the API and through the frontend operations dashboard.

## Key Documents

- [api/README.md](api/README.md)
- [docs/CORE_DATABASE_SCHEMA.md](docs/CORE_DATABASE_SCHEMA.md)
- [docs/PHASE_BACKLOG.md](docs/PHASE_BACKLOG.md)
- [infra/README.md](infra/README.md)
- [infra/BACKUP_AND_RESTORE.md](infra/BACKUP_AND_RESTORE.md)
- [infra/RESTORE_DRILL.md](infra/RESTORE_DRILL.md)

## Current Gaps And Follow-Up Areas

Current follow-up areas still visible in the project include:

- password reset and account recovery
- template-management UI for seeded reference data
- server-side reconciliation suggestions and journal auto-creation beyond the current client-side candidate ranking
- broader browser coverage for AI recommendation and evidence-heavy negative paths
- performance testing for import-heavy and report-heavy workflows

## Required Report Disclaimer

BAS and company tax support reports should display wording equivalent to:

> Internal calculation support only. This report does not lodge anything with the ATO and should be reviewed before manual form entry or submission.

## License

This repository is proprietary software of LISHE GROUP Pty. Ltd. and is distributed under the proprietary license in [LICENSE](LICENSE).
No open-source license is granted.
