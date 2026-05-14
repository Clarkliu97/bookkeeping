# Internal Bookkeeping and Tax Support System Implementation Plan

## Purpose

This document defines the implementation plan for an internal bookkeeping and tax form support system for Australian companies.

The system is intended to:

- maintain internal bookkeeping records
- support double-entry accounting
- import and reconcile bank transactions
- produce BAS support calculations
- produce company tax workpapers and review packs
- support manual entry into ATO website forms or paper forms

The system is not intended to:

- lodge with the ATO
- replace accountant review
- act as a public SaaS tax platform
- provide automated tax advice

All implementation choices in this plan stay within that boundary.

## Current Handoff Status

As of this handoff, the repository is beyond scaffold stage and already includes:

- implemented backend slices for auth, company setup, reference data, journals, accounting periods, documents, bank imports, reconciliation, BAS support, financial reports, fixed assets, tax workpapers, and operational health or alert surfaces
- the Compose web development service now runs Next.js with Webpack explicitly, avoiding Turbopack native-binding failures in the Docker Linux runtime when only SWC WASM bindings are available
- company creation now seeds an expanded Australian corporate reference-data pack generated from the provided chart-of-accounts, tax-code, and reporting-category templates
- a company-aware Next.js operator workspace at `/`, `/setup`, `/bookkeeping`, `/banking`, `/reports`, and `/year-end`, plus secondary `/operations` and `/workbench` routes for support and diagnostics
- shared operator workflow actions now show a blocking processing veil and use a duplicate-action guard, with the AI journal bundle analysis controls disabled while analysis is running
- an AI-assisted journal recommendation workflow in Bookkeeping that uploads invoice or receipt bundles, calls OpenAI through the backend, returns review-ready structured recommendations with extracted document transaction dates, and creates draft journals through the normal ledger validation path without silently falling back to the analysis date
- a compose-managed local runtime that applies Alembic migrations before API startup and passes through `OPENAI_API_KEY` for journal recommendation analysis when the host environment provides it
- a validated backend baseline from the latest implementation cycle: full backend `pytest` passed with 60 tests, including focused journal recommendation prompt-cache, compact reference-context, extracted transaction-date, and workflow mutation guard regressions
- a validated frontend baseline from the latest implementation cycle: Next production build passed and the Playwright operator suite passed with 5 tests

Recommended immediate next work:

- add browser-level coverage for AI journal recommendation analysis, rejection, and draft-journal acceptance
- continue hardening operator workflows that still rely on diagnostic surfaces for edge cases or have thin negative-path coverage
- add performance and reliability validation for import-heavy and report-heavy paths

## Executed Feature Plans

### 2026-05-15 Ubuntu Shell Counterparts For Operational Scripts

#### Scope

Add Ubuntu-friendly Bash counterparts for the tracked operational PowerShell scripts used for PostgreSQL backup and restore.

This work stays at the operations tooling layer. It does not change application logic, bookkeeping behavior, BAS support calculations, tax workpapers, or review workflows.

#### Problem

The repository included tracked operational scripts only in PowerShell format.

That left Ubuntu or other Bash-based environments without first-party script equivalents for the existing backup and restore procedures, even though the rest of the stack is Docker-based and cross-platform.

#### Implementation Approach

Add `infra/scripts/backup_postgres.sh` and `infra/scripts/restore_postgres.sh` as Bash counterparts to the existing PowerShell scripts.

Keep the same backup set shape of `database.sql`, optional `documents.zip`, and `metadata.json`, and keep the same Docker Compose service assumptions and environment-variable defaults for PostgreSQL connection details.

Update operational documentation so backup, restore, and restore-drill instructions point to both the PowerShell and Bash variants.

#### Validation

Validation for this executed plan should be:

1. parse both new shell scripts with `bash -n`
2. confirm the referenced documentation includes both `.ps1` and `.sh` script paths
3. confirm `clear_db.ps1` remains a local-only ignored helper rather than receiving a tracked shell counterpart

#### Execution Result

Completed on 2026-05-15.

Implemented by adding Bash backup and restore scripts under `infra/scripts/`, updating the operational documentation to show Windows and Ubuntu usage, and restoring `IMPLEMENTATION_PLAN.md` to the tracked documentation set so this execution record can be committed.

Followed up on 2026-05-15 by removing Bash-only constructs such as `pipefail` and `BASH_SOURCE` so the new `.sh` scripts also run correctly when invoked through Ubuntu `/bin/sh`, not only through `bash`.

Followed up again on 2026-05-15 by changing both restore scripts to drop and recreate the target database before importing `database.sql`, and by enabling fail-fast SQL restore behavior so restore runs stop on the first database error instead of streaming partial failures and incorrectly appearing successful.

### 2026-05-14 Git Hygiene Before First Publish

#### Scope

Tighten repository hygiene before the first GitHub push by normalizing line-ending behavior and excluding generated build metadata from the initial commit.

This work does not change application behavior. It only reduces noisy Windows line-ending warnings and keeps generated artifacts out of source control.

#### Problem

The repository had no `.gitattributes`, while the local Windows Git configuration uses `core.autocrlf=true`.

That caused noisy LF-to-CRLF warnings during `git add`.

The staged set also included generated files such as `api/bookkeeping_tax_api.egg-info/` and `web/tsconfig.tsbuildinfo`, which should not be committed as part of the source repository.

#### Implementation Approach

Add a root `.gitattributes` that defaults tracked text files to LF while preserving CRLF for Windows shell scripts.

Update `.gitignore` to exclude generated `.egg-info` directories and TypeScript incremental build metadata.

After that, remove the already staged generated artifacts from the index so the first commit contains only intended repository sources and documentation.

#### Validation

Validation for this executed plan should be:

1. confirm `.gitattributes` exists and is staged
2. confirm generated `.egg-info` and `*.tsbuildinfo` artifacts are no longer staged
3. confirm the repository remains ready for the first commit and push

#### Execution Result

Completed on 2026-05-14.

Implemented by adding `.gitattributes`, ignoring `.egg-info` and `*.tsbuildinfo`, and removing already staged generated files from the initial commit set.

### 2026-05-14 Proprietary License And README Screenshots

#### Scope

Prepare the repository for GitHub publication by adding a proprietary license and extending the root README with a short visual section that shows the implemented frontend workflows.

This work stays at the repository-documentation layer. It does not change runtime behavior, API behavior, bookkeeping logic, or workflow rules.

#### Problem

The repository did not yet include a standalone proprietary license file suitable for a GitHub-hosted private or view-only source distribution.

The root README also described the frontend routes in text only, without any visual examples of the operator experience.

In addition, the current `.gitignore` state had drifted so `IMPLEMENTATION_PLAN.md` was again being ignored, which is not desirable for repository handoff documentation.

#### Implementation Approach

Add a top-level `LICENSE` file with an explicit proprietary, all-rights-reserved license and a clear statement that publication of the repository does not grant open-source rights.

Generate real screenshots from the live local application using Playwright against the running development stack, save them under `assets/screenshots/`, and add a short `Screens/Workflows` section to the root README that references those image files.

Restore `IMPLEMENTATION_PLAN.md` visibility in `.gitignore` while preserving the agent customization ignore rules.

#### Validation

Validation for this executed plan should be:

1. confirm the screenshot files exist under `assets/screenshots/`
2. verify the generated images show the intended routes clearly enough for README use
3. confirm `LICENSE`, `README.md`, and `IMPLEMENTATION_PLAN.md` are not ignored by git
4. confirm the existing `.github/agents/` files remain ignored

#### Execution Result

Completed on 2026-05-14.

Implemented by adding a proprietary root license naming LISHE GROUP Pty. Ltd., capturing dashboard, bookkeeping, reports, and operations screenshots from the live local app, inserting a short README visuals section that references those assets, and restoring implementation-plan visibility in `.gitignore`.

### 2026-05-14 Repository README And Agent Ignore Cleanup

#### Scope

Refresh the repository-facing documentation before publishing the project to GitHub and tighten `.gitignore` so agent customization files stay out of source control.

This work does not change application behavior. It improves repository presentation, onboarding clarity, and Git hygiene.

#### Problem

The existing root README was useful as an internal handoff summary, but it did not serve well as a project overview for a broader GitHub audience.

It underexplained how the frontend is organized, how operators are expected to move through the routes, and which implemented workflows the system already supports.

The existing `.gitignore` also ignored `IMPLEMENTATION_PLAN.md`, which is a repository planning document rather than an agent-only file.

#### Implementation Approach

Rewrite the root README to:

1. explain the product boundary and non-goals clearly
2. summarize implemented functionality by domain
3. document how to use each main frontend route
4. provide clear local setup, runtime, and testing instructions
5. link the main supporting documents for planning and operations

Update `.gitignore` to ignore agent customization files generically, including `.agent.md`, `.instructions.md`, `.prompt.md`, `copilot-instructions.md`, `AGENTS.md`, and `SKILL.md`, while keeping repository documentation such as `IMPLEMENTATION_PLAN.md` commitable.

#### Validation

Validation for this executed plan should be:

1. inspect the resulting diff for `README.md`, `.gitignore`, and `IMPLEMENTATION_PLAN.md`
2. confirm the ignore rules no longer exclude the implementation plan while still covering the existing `.github/agents/` files

#### Execution Result

Completed on 2026-05-14.

Implemented by rewriting the root README around current product capabilities and route-by-route frontend usage, and by replacing the prior narrow agent ignore block with generic agent customization patterns while unignoring the implementation plan.

### 2026-05-13 Report Version Selection

#### Scope

Add explicit report-version selection to the operator reporting workflow so users can choose between:

1. a final review version based on posted journals only
2. a draft review version that also includes draft journals

This work stays within the existing internal-review boundary. It changes how report data is selected and presented for review, but it does not change posting rules, journal approval workflows, or any tax or lodgment boundary.

#### Problem

The Reports screen had no per-report control for draft-inclusive output.

At the backend level, trial balance, profit and loss, and balance sheet were effectively posted-only, while the shared general-ledger report path already included draft entries by default.

That mismatch made report behavior inconsistent and prevented operators from intentionally choosing draft-inclusive review output from each report panel.

#### Implementation Approach

Add an explicit `include_draft` query parameter to all report and report-export endpoints, with conservative default behavior that remains posted-only unless draft inclusion is requested.

Thread that parameter through the reports service so:

1. trial balance can include draft journals on request
2. profit and loss can include draft journals on request
3. balance sheet and current earnings can include draft journals on request
4. general ledger can switch between posted-only and draft-inclusive output on request

Add a `Version` select to each report panel in the Reports UI with review-oriented options for final versus draft output, and use the selected version for both on-screen generation and CSV export.

Preserve the existing Bookkeeping ledger-explorer behavior by explicitly requesting draft-inclusive general-ledger output there, since that surface is intended for draft review.

#### Validation

Validation for this executed plan was:

1. focused backend pytest coverage for default posted-only behavior and draft-inclusive report behavior in `tests/test_milestone_d.py`
2. file diagnostics on the touched backend and frontend files
3. `node node_modules/next/dist/bin/next build` from `web/`

#### Execution Result

Completed on 2026-05-13.

Implemented by:

1. adding `include_draft` handling to all report and export endpoints
2. updating the report service to select visible journal statuses explicitly per request
3. adding report-version selectors to all four report panels in the operator Reports screen
4. keeping the Bookkeeping ledger explorer explicitly draft-inclusive so its existing review purpose remains unchanged

### 2026-05-13 Next.js Dev Manifest Stability

#### Scope

Stabilize the Docker-based Next.js development runtime used for the internal operator workspace.

This work stays within the existing internal-use boundary. It does not change bookkeeping, tax-support calculations, journal behavior, or operator workflow logic. It only hardens the local development runtime so the review UI loads reliably.

#### Problem

The Docker Compose web service runs `next dev --webpack` against a Windows bind-mounted `web/` directory.

In that setup, Webpack's persistent cache under `.next/dev/cache/webpack` can fail rename operations on the bind mount, which leads to incomplete or corrupted React client-manifest output and runtime errors such as missing `ViewportBoundary`, `MetadataBoundary`, `OutletBoundary`, or client component modules.

#### Implementation Approach

Keep the existing Webpack-based dev server choice, but move the web service's `.next` directory onto a container-managed volume instead of the host bind mount.

This isolates transient Next.js build and cache artifacts from Windows filesystem rename semantics while preserving live source editing through the existing `./web:/app` bind mount.

#### Validation

Validation for this executed plan should be:

1. restart the `web` service through Docker Compose so it mounts a fresh `.next` volume
2. confirm the prior Webpack cache rename errors no longer appear in `docker compose logs web`
3. reload the Bookkeeping route and confirm the manifest/runtime error is gone

#### Execution Result

Completed on 2026-05-13.

Implemented by mounting a dedicated `web_next_data` volume at `/app/.next` for the Compose `web` service so Webpack dev cache and manifest output no longer rely on the Windows bind-mounted project directory.

### 2026-05-13 Journal Detail Evidence Preview

#### Scope

Add evidence thumbnails to the two journal-detail surfaces already used for review in Bookkeeping:

1. the inline detail card in the `Journals` panel
2. the dismissible journal popup in the `Ledger explorer`

This work stays within the existing internal-review boundary. It improves drill-through visibility of already linked source documents and does not change journal posting, document storage, document-linking rules, or any tax or lodgment behavior.

#### Objectives

1. Let operators see linked journal evidence directly from the journal detail view without leaving the review surface.
2. Show image thumbnails where browser preview is possible.
3. Let operators click a thumbnail or evidence card to open a full-document view.
4. Let operators dismiss the full-document view by clicking outside it, matching the existing click-away popup behavior already used in Bookkeeping.
5. Reuse the existing authenticated document download API instead of adding new backend endpoints.

#### Implementation Approach

##### Journal-detail evidence loading

Keep the existing selected-journal evidence flow intact, but add a local evidence cache in the Bookkeeping section keyed by `journal_id` so detail views can load evidence for:

- the currently selected journal
- the currently expanded journal row in the `Journals` panel
- the journal currently shown in the `Ledger explorer` popup

Use the existing `/api/companies/{company_id}/journals/{journal_id}/documents` endpoint for any detail view whose evidence is not already loaded.

##### Thumbnail and full-document preview

Use the existing authenticated blob fetch path already available through the frontend request helper and create object URLs locally in the Bookkeeping section.

Show actual thumbnail images for image evidence where browser rendering is possible.

For PDF or other file types, show a file-card style placeholder in the thumbnail grid while still allowing click-through to the full viewer where possible.

Render the full evidence view in a modal overlay above the existing journal surfaces:

- images display with a full-size image preview
- PDFs render client-side into page images so journal expansion and modal open do not trigger browser-native download behavior
- unsupported file types fall back to a download affordance with clear preview messaging

Dismiss the full viewer when:

- the user clicks outside the viewer card
- the user presses `Escape`

##### Styling

Extend the existing Bookkeeping review styling in `web/app/globals.css` rather than introducing a new visual language.

Keep the evidence gallery compact in the journal detail cards while ensuring the full-document viewer scales correctly on desktop and mobile.

#### Validation

Validation for this executed plan should be:

1. file diagnostics on the touched frontend files
2. `node node_modules/next/dist/bin/next build` from `web/`
3. live browser verification on a PDF-backed journal detail to confirm row-open and thumbnail-open actions stay inline while the explicit download control remains separate

#### Execution Result

Completed on 2026-05-13.

Implemented in the Bookkeeping frontend by adding:

1. evidence caching for expanded journal detail views
2. image thumbnails for linked journal evidence where browser preview is possible
3. PDF thumbnail and full-view rendering through `pdfjs-dist` instead of the browser's embedded PDF viewer path
4. click-through full-document preview with click-away and `Escape` dismissal
5. reuse of the existing authenticated document download endpoint instead of new API surface area

Follow-up fix completed on 2026-05-12 after live operator testing showed the browser-native PDF path could still trigger download prompts. The final implementation removed the iframe-based PDF preview, corrected modal PDF state handling, and was revalidated against `JE-000009` on the current source build where:

1. clicking the journal row did not trigger a browser download
2. clicking the PDF evidence thumb did not trigger a browser download
3. the PDF modal rendered three page images for `2025-06-08-Vodafone.pdf`
4. clicking outside the modal closed the full-view overlay as intended

### 2026-05-12 Bookkeeping Table Search and Filter

#### Scope

Add search and filter controls to the two high-traffic Bookkeeping review tables:

1. the `Journals` panel entry table
2. the `Ledger explorer` table

This work stays within the existing internal review boundary. It changes how already-loaded review data is navigated in the frontend and does not alter journal posting, ledger calculations, locking rules, or any tax or lodgment boundary.

#### Objectives

1. Let operators find journals by entry number, reference, source, date, description, or line-note text without scanning the entire list.
2. Let operators narrow visible journals by status when reviewing draft versus posted work.
3. Let operators search loaded ledger rows across account and journal text without reworking report generation.
4. Let operators filter loaded ledger rows by journal status while preserving the existing server-backed date and account filters.
5. Keep the implementation local to the Bookkeeping UI so the change remains low-risk and does not require API or schema changes.

#### Implementation Approach

##### Journals panel controls

Add task-local state in the Bookkeeping section for:

- a journal search query string
- a journal status filter value

Derive a filtered journals array with case-insensitive matching across review-relevant fields:

- `entry_number`
- `entry_date`
- `description`
- `reference`
- `source_type`
- line-note text from `journal.lines[].description`

Apply status filtering on top of the search result using the journal row status already available in the loaded data.

Keep the existing inline row-expansion behavior compatible with the filtered dataset by collapsing the expansion automatically when the expanded journal is no longer present in the filtered result.

##### Ledger explorer controls

Add task-local state in the Bookkeeping section for:

- a ledger search query string
- a ledger status filter value

Keep the existing server-backed date and account filters unchanged. After a ledger report is loaded, apply an in-memory search and status filter to the returned grouped report data.

Search matching should cover review-visible fields such as:

- account code
- account name
- entry number
- entry date
- journal status
- reference
- journal description
- line description

Preserve grouped account rendering while removing account groups that no longer have matching entries after filtering.

##### UX and layout

Add compact search and filter toolbars above each table using existing operator field styles so the new controls remain consistent with the rest of the Bookkeeping workspace.

Add filtered empty states for both tables so operators can distinguish between:

- no data loaded yet
- loaded data exists but no rows match the current search or filter

Add small filtered-result counts and clear actions so operators can quickly understand and reset the narrowed review set.

#### Validation

Validation for this executed plan was:

1. file diagnostics on touched frontend files
2. `node node_modules/next/dist/bin/next build` from `web/`

#### Execution Result

Completed on 2026-05-12.

Implemented in the Bookkeeping frontend by adding:

1. journal table search across entry metadata and line-note text
2. journal status filtering with filtered-result feedback and a reset action
3. ledger explorer search across loaded account and journal text
4. ledger status filtering layered on top of the existing date and account filters
5. filter-aware empty states and result counts for both tables

Validation completed with clean diagnostics on the touched files and a successful frontend build.

## Next-Agent Handoff Notes

This section is intended for Copilot, Codex, or any other coding agent resuming work after May 10, 2026.

Current system status:

- Backend implementation is broad and active across auth, admin, companies and access, expanded reference-data seeding, chart of accounts, accounting periods, journals, documents, bank imports, reconciliation, BAS, financial reports, fixed assets, tax workpapers, journal recommendations, audit logging, and operational health/metrics/alerts.
- Frontend implementation is a company-aware operator workspace split across `/`, `/setup`, `/bookkeeping`, `/banking`, `/reports`, `/year-end`, with `/operations` and `/workbench` still available for support and diagnostics.
- The Bookkeeping route contains a live AI document-to-journal workflow. Uploaded invoices or receipts create source documents, backend analysis calls OpenAI Responses, recommendations are stored as review-ready lines/proposals, and accepted recommendations create draft journals through the existing ledger validation path.
- AI journal prompt context is intentionally compact and cache-aware: stable company/reference context is sent before run-specific note/document data; account context uses `code`, `name`, `type`, `tax`, and `posting`; output still uses `lines[].account_code`.
- AI journal prompt now explicitly tells the model to determine whether GST applies even when no GST amount is visible and no related context is provided, and the backend now wires OpenAI Responses `web_search` for supported models when `API_JOURNAL_AI_WEB_SEARCH_ENABLED=true` so the model can actually verify suppliers, products, or services when needed.
- The Bookkeeping recommendation review UI now surfaces any returned search-verification sources as review-only citations so operators can inspect the provider's web references before accepting a draft.
- AI journal recommendations now allow more component-level journal lines for multi-document bundles and explicitly tell the model to separate materially distinct adjustments, settlement items, fees, credits, and other bundle components so GST can be assessed per component instead of once for the whole bundle.
- Focused recommendation coverage now includes a realistic three-document settlement-adjustment fixture that validates component-level separation across taxable, GST-control, GST-free, and no-tax lines before the accepted draft journal is created.
- Accepted AI draft journals now use the extracted transaction date from the document. If no transaction date is extracted, acceptance fails with a reviewable error instead of silently using the current date, and selected proposed accounts can now be accepted through the same prepare workflow instead of failing on an extra admin-only gate.
- OpenAI request compatibility is now model-aware for prompt caching: GPT-5.5 uses `prompt_cache_retention=24h` while other supported recommendation models continue using in-memory prompt caching.
- Structured-output recovery now retries once with explicit schema feedback and disables optional web-search tool calls on that retry so GPT-5.4 schema parsing remains stable under complex document bundles.
- Draft journal deletion now clears any linked AI recommendation accepted or target journal references and removes polymorphic journal evidence links before deleting the journal row, so accepted recommendation drafts can be removed without foreign-key failures.
- Operator actions use a shared processing veil and same-label duplicate-action guard. Do not replace this with per-button one-off state unless a workflow genuinely needs local handling.
- The Bookkeeping journal editor now exposes editable per-line notes (`journal line description`) in the line grid, and these values flow through create and update payloads so operators can add or revise line-level explanations during draft entry.
- The Bookkeeping journal editor now also allows operators to delete draft journal lines directly in the frontend, while keeping a minimum of two lines so the draft stays compatible with double-entry validation before save.
- The Bookkeeping journal editor layout is now split into clearer `Journal details` and `Journal lines` subpanels, with larger journal-only form controls and line-note text areas so draft entry and review are easier to read without squeezing the delete-line control into the line fields.
- The Journals workspace now lets the draft editor shrink correctly inside the panel by removing oversized grid minimums in the editor stack and collapsing the journals split to a single column earlier on narrower screens, avoiding panel overflow before the global mobile breakpoint.
- The Bookkeeping journal editor now exposes a `New journal` action while a draft is selected, clearing the current journal selection and resetting the editor to a fresh draft while carrying forward the active accounting period where possible.
- The Bookkeeping journals table now expands a selected journal inline to show its lines for quick review and collapses that inline preview when focus moves away from the table, while the ledger explorer adds a `Use all time` date-range shortcut across the earliest and latest journal dates and opens a dismissible journal-detail popup when a ledger row is clicked.
- The Bookkeeping Journals panel now includes client-side search and status filtering for the visible journal list, and the Ledger explorer now includes client-side search and status filtering layered on top of its existing server-backed date and account filters, with filtered result counts and empty states to keep review workflows fast without changing ledger calculations.
- API LAN-origin CORS support is now explicitly regression-covered for `192.168.x.x` operator access, including both simple and preflight requests, so browser-side `Failed to fetch` errors do not recur when the app is opened from the host machine's private IP.
- Journal entry numbering no longer uses `count(*)` to allocate the next `JE-` number. Draft creation paths, including accepted AI journal recommendations and fixed-asset depreciation journals, now advance from the highest existing journal number so deleted gaps do not cause duplicate-key failures that surface in the browser as `Failed to fetch` errors.
- Operator workflow flash messages now render in two places from the same shared message state: the existing top-of-page banner remains for persistent visibility, and floating toasts appear near the lower edge of the viewport with fade-in and fade-out animation, stack a small set of recent notifications, and can be dismissed manually so users working deep in long screens still get immediate request feedback without waiting for the timeout.
- The Playwright operator duplicate-action test now uses a non-null deferred route-release callback, avoiding a local TypeScript `never` call-site error while preserving the same request-blocking test behavior.
- The workspace now includes a dedicated custom agent at `.github/agents/bookkeeper.agent.md` for bookkeeping-heavy tasks. It is instructed to inspect repository and database context broadly enough to ground recommendations, prefer application-level mutations when possible, and only perform direct database repairs in a narrow, auditable, validated way.
- Docker Compose web development is pinned to Webpack mode because Turbopack native bindings were unavailable in the Linux container runtime and caused `:3000` connection failures.

Current validation baseline:

- `C:/Python314/python.exe -m pytest` from `api/`: 60 passed in the previous full-suite cycle (not re-run in this handoff pass).
- `docker compose run --rm api sh -lc "pip install --no-cache-dir '.[dev]' ; pytest tests/test_journal_recommendations.py"`: 22 passed after adding search-source extraction coverage, prepare-user proposal acceptance coverage, GPT-5.5 cache-retention compatibility coverage, retry-without-tools structured-output coverage, accepted-draft deletion-link cleanup coverage, and updated pricing assertions.
- `node node_modules/next/dist/bin/next build` from `web/`: passed.
- `node node_modules/playwright/cli.js test tests/e2e/operator.spec.ts --grep "analyzes a multi-document bundle" --reporter=line` from `web/` against a built app on `127.0.0.1:3100`: passed.

Environment cautions:

- `OPENAI_API_KEY` is read from the host environment and passed into the Compose-managed `api` service. Recreate the API container after changing the host variable.
- If local `npm run ...` commands fail with `next` or `playwright` not recognized, use the direct Node CLI commands above or reinstall `web` dependencies in the active Windows shell.
- The worktree appears fully untracked in this environment. Do not run cleanup, reset, or destructive git commands unless the user explicitly asks.
- Preserve the repository boundary: internal bookkeeping and tax support only; no ATO lodgment, no tax-agent product claims, no accountant replacement language.

Recommended next implementation targets:

1. Expand Playwright coverage around the AI journal recommendation path beyond the new multi-document analyze/accept journey, including rejection, missing transaction date error display, and duplicate-click protection on the Analyze bundle action.
2. Add a small UI affordance for manually setting or correcting the target transaction date when AI extraction fails, if the user wants that workflow. Keep it review-first and auditable.
3. Add reference-template administration screens for maintaining seeded chart of accounts, tax codes, and reporting categories.
4. Expand reconciliation UX toward suggested matches and optionally review-only suggested journals.
5. Decide whether the recommendation model picker should explicitly distinguish search-capable models in the operator UI instead of only reflecting that capability in the review output.

Suggested prompt for continuing with Copilot:

```text
You are continuing development in the Bookkeeping_Tax repository. Before making changes, read .github/agents/copilot-instructions.md.agent.md, README.md, and IMPLEMENTATION_PLAN.md. Preserve the scope: internal Australian bookkeeping and tax support only, no ATO lodgment, no tax-agent product behavior, and no accountant replacement claims.

Treat the current worktree as the project state even if git reports files as untracked. Do not reset, clean, or revert unrelated files. Docker Compose runs db/api/web; web is intentionally pinned to Next dev Webpack mode in docker-compose.yml. OPENAI_API_KEY is passed from the host environment into the api service.

Current baseline: backend pytest passed with 60 tests, journal recommendation focused tests passed with 21 tests, Next build passed, and Playwright operator suite passed with 5 tests using direct CLI commands documented in README.md. Continue from the requested task, update README.md and IMPLEMENTATION_PLAN.md when behavior changes, and add focused tests for financial, locking, AI recommendation, or workflow-guard behavior.
```

Suggested prompt for moving back to Codex:

```text
You are resuming work in the Bookkeeping_Tax repository after a temporary Copilot development period. First read .github/agents/copilot-instructions.md.agent.md, README.md, IMPLEMENTATION_PLAN.md, and inspect git status. Summarize the current repo state and any changes made since the last Codex handoff before editing.

Preserve all unrelated dirty worktree changes. Keep the product boundary to internal Australian bookkeeping and tax support only: no ATO lodgment, no tax-agent platform scope, no accountant replacement claims. Use the existing FastAPI/SQLAlchemy/PostgreSQL backend, Next.js operator workspace, Docker Compose runtime, expanded reference-data seeding, and AI journal recommendation architecture. Verify changes with the relevant backend pytest subset or full suite and the frontend build/Playwright checks where affected, then update README.md and IMPLEMENTATION_PLAN.md to match the implemented state.
```

## Confirmed Planning Decisions

The plan below assumes the following decisions are in force:

- Frontend: Next.js with TypeScript
- Backend: FastAPI with SQLAlchemy and Alembic
- Database: PostgreSQL
- Deployment target: single internal server or VPS
- User model: small internal team with roles
- Authentication: app-managed email and password
- File storage: local server filesystem for uploaded source documents
- Bank import scope for initial release: CSV only
- Ledger scope: account-only ledger with no cost centres, departments, or project tracking in v1
- Currency scope: AUD only
- Jurisdiction scope: Australia only
- Company scope: support multiple related companies in one internal system
- Approval workflow: maker/checker support is required, but the same user may act as both where allowed by configuration
- Export scope: accountant-facing PDF packs are required
- Admin tooling: lightweight backend-side internal admin UI is required
- BAS configuration: BAS frequency and reporting settings are entered per company at setup and can be modified later through controlled configuration changes

## Product Principles

These principles should guide every module and should be enforced in both design and implementation:

1. Ledger first.
   All reporting must derive from posted accounting records, not directly from raw bank imports.

2. Review before use.
   BAS and company tax outputs are internal support documents only.

3. Traceability.
   Every reported figure must be explainable from source records, journal lines, bank records, uploaded documents, or explicit adjustments.

4. Human control.
   The system may assist, but a person remains responsible for review and manual form entry.

5. Auditability.
   Sensitive actions must be logged and historically visible.

6. No silent changes.
   Reviewed, approved, and locked periods cannot change invisibly.

7. Configurability.
   BAS settings, GST codes, tax mappings, reporting periods, and review controls should be configurable where practical.

8. Conservative tax language.
   Use wording such as "ready for review" and avoid wording that implies lodgment or professional sign-off.

## Recommended Architecture

The recommended implementation is a modular monolith with a clear separation between web, API, and domain modules.

This is the right fit because:

- the repository is greenfield
- the product is internal rather than public SaaS
- correctness, auditability, and maintainability matter more than horizontal scale
- splitting into separate distributed services would add operational and development overhead without clear benefit

### Core Technical Shape

- Next.js application for internal user workflows and primary UI
- FastAPI application for business logic and internal APIs
- PostgreSQL as the system of record
- Filesystem-backed document storage with metadata in PostgreSQL
- Background jobs only where necessary for PDF generation, imports, or long-running pack generation
- Lightweight backend admin UI mounted from the API application for support and reference-data maintenance

### Suggested Repository Structure

```text
Bookkeeping_Tax/
  web/                    # Next.js frontend
  api/                    # FastAPI backend
    app/
      core/
      auth/
      admin/
      companies/
      chart_of_accounts/
      ledger/
      accounting_periods/
      tax/
      bank_imports/
      reconciliation/
      documents/
      bas/
      reports/
      fixed_assets/
      tax_workpapers/
      approvals/
      audit/
      exports/
    migrations/
  docs/
  infra/
  samples/
```

### Why FastAPI Still Fits with a Backend Admin UI

The backend admin requirement does not require changing to Django.

FastAPI can remain the main backend while exposing a limited internal admin surface for:

- user administration
- company configuration maintenance
- tax code and mapping management
- audit log inspection
- support operations
- import diagnostics

This admin surface should be intentionally narrower than the main product UI and reserved for support, configuration, and operational maintenance.

## Domain and Data Model Direction

The data model should reflect bookkeeping and reporting truth rather than just UI workflows.

### Core Shared Concepts

- `Company`
- `User`
- `Role`
- `UserCompanyAccess`
- `AuditEvent`
- `Document`
- `ApprovalAction`
- `ConfigurationChangeLog`

### Multi-Company Model

The system should support multiple related companies, but still remain an internal application.

Recommended model:

- one system-level user base
- explicit access mapping between users and companies
- company-specific accounting data and periods
- optional shared templates for chart of accounts, GST mappings, and report layouts
- strict scoping of all company data by `company_id`

This design allows a small internal finance team to manage related entities without turning the product into a public multi-tenant platform.

### Accounting and Ledger Model

Core accounting entities should include:

- `Account`
- `AccountType`
- `JournalEntry`
- `JournalLine`
- `PostingBatch`
- `TaxCode`
- `ReportingCategory`
- `AccountingPeriod`
- `PeriodLock`
- `ManualAdjustment`

Key rules:

- every posted journal entry must balance
- monetary values must use fixed precision decimal types
- posted entries should not be edited in place
- corrections should be made via reversal, replacement, or explicit adjustment entries
- any write affecting closed or locked periods must pass through controlled rules

### Configuration Model

Configuration should be company-specific and version-aware.

Important configuration objects:

- company registration and identifiers
- GST registration status
- BAS frequency
- BAS reporting basis
- financial year settings
- default reporting mappings
- approval policy settings
- period lock policy settings

Because BAS settings may change over time, configuration changes should be recorded with effective dates or effective periods where required. Historical reports must remain explainable under the settings in force at the time.

### Banking Model

Core banking entities:

- `BankAccount`
- `BankImportSession`
- `BankImportRow`
- `BankStatementPeriod`
- `BankMatchCandidate`
- `ReconciliationSession`
- `ReconciliationItem`

Raw bank import rows should be staged first, then reviewed, classified, and reconciled. They should not become ledger truth automatically.

### Document Model

Core document entities:

- `Document`
- `DocumentLink`
- `DocumentVersion`
- `DocumentChecksum`

Each document may attach to:

- bank import rows
- journal entries
- reconciliation items
- BAS adjustments
- review notes
- tax workpaper items

### BAS and Tax Support Model

Core BAS and tax support entities:

- `BASPeriod`
- `BASRun`
- `BASLineResult`
- `BASAdjustment`
- `BASReviewNote`
- `TaxWorkpaperPack`
- `TaxAdjustment`
- `FixedAsset`
- `DepreciationRun`
- `ExceptionItem`

These records must preserve how a number was calculated, what inputs were included or excluded, and who reviewed or approved the result.

## Security and Access Control

### Authentication

Initial authentication should use app-managed email and password.

Required capabilities:

- password hashing with a strong modern algorithm
- password reset flow
- login attempt controls
- session expiration
- admin-controlled user activation and deactivation

### Roles

Start with a small role model:

- `system_admin`
- `finance_admin`
- `bookkeeper`
- `reviewer`
- `read_only`

Roles should be scoped per company where appropriate.

### Maker/Checker Workflow

The system must support maker/checker workflows, but allow configuration that permits the same user to perform both actions when needed.

Recommended approach:

- every reviewable action records `prepared_by`
- every approval records `approved_by`
- policy determines whether self-approval is blocked, warned, or allowed
- actions display clearly in audit history and report metadata

This gives operational flexibility without losing visibility.

## Audit and Change-Control Requirements

The following actions must create audit events:

- user creation, activation, deactivation, and role changes
- company setup and configuration changes
- chart of accounts changes
- journal creation, posting, reversal, and adjustment
- document upload, replacement, and deletion requests
- bank import creation and confirmation
- reconciliation actions
- BAS calculations, adjustments, approvals, and locking
- financial year locks and unlocks
- workpaper pack generation and approval

Where practical, audit events should capture:

- actor
- timestamp
- company
- object type and object id
- action name
- summary of before and after state
- reason or note when required

## Reporting and Export Principles

### General Rule

All reports should be drillable or explainable from posted accounting data and adjustments.

### Required Report Classes

- trial balance
- profit and loss
- balance sheet
- general ledger detail
- GST and BAS support reports
- exception and review reports
- fixed asset and depreciation reports
- company tax workpaper packs

### Export Formats

Initial export targets:

- CSV for operational data movement
- spreadsheet exports for review and accountant handoff
- PDF review packs for accountant-facing output

PDF packs should include:

- report headings and period context
- company identification
- calculation support detail or appendices
- warnings and exceptions
- approval or review metadata
- required disclaimer language

Required disclaimer:

> Internal calculation support only. This report does not lodge anything with the ATO and should be reviewed before manual form entry or submission.

## Phase Plan

The delivery plan below is ordered to maximize correctness and reduce rework.

### Phase 0: Foundation and Project Setup

Objective:
Create the technical baseline and guardrails for all later accounting and tax-support work.

Scope:

- initialize the repository structure
- configure local development for `web`, `api`, and PostgreSQL
- add migration tooling and environment configuration
- establish API conventions, error handling, logging, and configuration loading
- set up frontend shell and backend application shell
- add CI basics for tests, linting, and migrations
- define money and decimal handling rules
- add initial admin UI framework on the backend side

Deliverables:

- running Next.js app
- running FastAPI app
- PostgreSQL migrations pipeline
- basic authentication skeleton
- initial internal admin entry point
- contribution and architecture docs

Exit criteria:

- developers can run the full stack locally
- schema migrations apply cleanly
- code quality checks and tests run in CI

Maintenance note:

- PostgreSQL-backed Alembic migrations must remain directly runnable against a fresh live database, including enum-backed schema creation. Local setup should apply `alembic upgrade head` before first API or frontend use.

### Phase 1: Identity, Companies, and Configuration

Objective:
Support multiple related companies and establish the configuration required to drive later bookkeeping and BAS behavior.

Scope:

- user model and authentication
- role model and company access mapping
- company creation and maintenance
- GST registration settings
- BAS frequency and reporting basis settings
- financial year setup
- approval policy settings including same-user maker/checker allowance rules
- audit trail for all configuration changes

Deliverables:

- company setup workflow in the main UI
- backend admin screens for user and company maintenance
- company configuration history view

Important design note:

BAS settings must be modifiable later, but the system must preserve what settings applied to previously prepared reports or locked periods. This should be implemented via configuration history, effective dates, or report snapshots.

Exit criteria:

- system can manage multiple companies with scoped access
- company configuration is editable and auditable
- approval rules are configurable

### Phase 2: Chart of Accounts and Ledger Core

Objective:
Deliver the first real accounting foundation.

Scope:

- account types and chart of accounts management
- company-level chart templates and imports if useful
- journal entry drafting and posting
- balanced journal validation
- manual journals and opening balances
- reversal and adjustment workflow
- ledger inquiry views
- audit events for all posting-related actions

Deliverables:

- chart of accounts screens
- journal entry screens
- ledger detail and trial balance views
- admin support views for posting diagnostics

Exit criteria:

- users can create and post valid journal entries
- invalid or unbalanced entries are blocked
- posted data is traceable and not silently mutable

### Phase 3: Accounting Periods, Review States, and Locking

Objective:
Prevent silent change and establish review control before complex tax outputs are introduced.

Scope:

- accounting period lifecycle
- draft, in-review, approved, and locked states
- maker/checker actions on period reviews
- lock protection rules for periods and financial years
- controlled unlock or adjustment process
- visible warnings for back-dated changes

Deliverables:

- period status dashboard
- review and approval actions
- lock history and audit views

Exit criteria:

- locked periods cannot be changed through normal workflows
- adjustment flows are explicit and auditable
- approval metadata is visible

### Phase 4: Source Documents and Traceability

Objective:
Support the evidence chain required for internal review and accountant review.

Scope:

- document upload and storage on local filesystem
- metadata and checksum storage in PostgreSQL
- linking documents to transactions, journals, and reviews
- document list and retrieval UI
- document permissions by company and role

Deliverables:

- upload and attach flows in the main UI
- backend admin views for document support and diagnostics

Exit criteria:

- important accounting records can be linked to supporting files
- document access is scoped and auditable

### Phase 5: Bank CSV Import and Staging

Objective:
Bring bank data into the system safely without treating it as accounting truth by default.

Scope:

- bank account setup
- CSV upload
- column mapping templates
- normalization and duplicate detection
- import preview
- staging of raw import rows
- import validation and error reporting

Deliverables:

- CSV import wizard
- import error and preview screens
- backend admin diagnostics for failed imports

Exit criteria:

- bank rows can be uploaded, previewed, and staged safely
- duplicate import risk is controlled
- bad input is handled clearly

### Phase 6: Classification and Reconciliation

Objective:
Turn staged bank data into reviewed accounting outcomes.

Scope:

- reconciliation sessions
- match imported rows to existing entries
- create suggested journals from bank rows where appropriate
- classify GST treatment and account destination
- unresolved and exception workflows
- reconciliation summaries and outstanding items lists

Deliverables:

- reconciliation workspace
- unresolved items queue
- exception reporting

Exit criteria:

- users can reconcile imported bank rows against ledger entries
- unresolved items are visible and cannot disappear silently
- resulting accounting records remain traceable to source bank rows

### Phase 7: BAS Support Calculations

Objective:
Produce reviewable BAS support numbers from reviewed accounting records.

Scope:

- BAS period generation based on company configuration
- BAS calculation engine using posted ledger data
- GST code and BAS label mapping
- adjustments, exclusions, and review notes
- warning rules for missing mappings or suspicious values
- calculation snapshots
- drill-down support to source transactions and journals

Deliverables:

- BAS preparation screen
- BAS review detail view
- BAS summary plus supporting transaction detail
- disclaimers and review-oriented wording

Important design note:

Because BAS frequency and reporting settings are company-configurable and changeable later, BAS runs must capture the configuration context used for that calculation. Later configuration changes must not silently alter historical BAS outputs.

Exit criteria:

- system produces BAS support figures with traceable detail
- calculation context is snapshot or version linked
- warnings and unmapped items are visible

### Phase 8: BAS Approval, Locking, and Export Packs

Objective:
Complete the end-to-end BAS support workflow through review and handoff.

Scope:

- maker/checker BAS approval flow
- period lock integration
- PDF BAS review pack generation
- spreadsheet and CSV exports
- cover pages, notes, and disclaimers
- audit capture for generated outputs

Deliverables:

- printable BAS review pack
- accountant-facing PDF support pack
- export history

Exit criteria:

- BAS support can be prepared, reviewed, approved, exported, and locked
- exported packs clearly state internal-use and manual-entry-only positioning

### Phase 9: Core Financial Reporting

Objective:
Provide reliable supporting reports beyond BAS.

Scope:

- profit and loss
- balance sheet
- trial balance
- account transaction detail
- GST reconciliation reports
- review exceptions dashboard

Deliverables:

- internal reporting screens
- exportable review reports

Exit criteria:

- financial statements reconcile to the posted ledger
- drill-through to supporting records is available where applicable

### Phase 10: Fixed Assets and Depreciation Support

Objective:
Add the minimum fixed asset capability needed for company tax workpapers.

Scope:

- fixed asset register
- acquisition and disposal tracking
- depreciation settings and runs
- posting depreciation journals
- asset support reporting

Deliverables:

- fixed asset maintenance screens
- depreciation run and review screens
- asset reports and export support

Exit criteria:

- assets and depreciation are trackable and explainable
- depreciation journals tie back to the ledger

### Phase 11: Company Tax Workpaper Support

Objective:
Produce internal annual workpapers to support company tax return preparation.

Scope:

- accounting profit support
- tax adjustment workpapers
- fixed asset and depreciation support schedules
- GST reconciliation support
- director or shareholder loan support if required by the business
- exception lists and review notes
- annual workpaper pack generation

Deliverables:

- workpaper preparation workspace
- exportable annual review pack
- PDF accountant-facing workpaper output

Exit criteria:

- workpaper pack is reviewable and traceable
- outputs remain clearly positioned as support only, not a lodged return

### Phase 12: Operational Hardening and Release Readiness

Objective:
Prepare the application for internal production use.

Scope:

- backup and restore procedures
- deployment scripts and environment hardening
- structured logging and monitoring
- file retention and storage limits
- audit log retention policy
- performance checks on larger datasets
- release checklist and rollback guidance

Deliverables:

- production deployment guide
- backup and recovery guide
- operational runbook

Exit criteria:

- system can be deployed and maintained reliably by the internal team
- recovery and operational procedures are documented

#### Frontend Work After Phase 12: Internal Operator Application

Objective:
Turn the Next.js application into the primary day-to-day interface for internal finance users so the system can be operated without falling back to Swagger for normal workflows.

Architecture direction:

- keep Next.js App Router as the primary internal UI
- use server-rendered pages for read-heavy landing and summary views where practical
- use client components for forms, uploads, workflow actions, and stateful review screens
- connect directly from the web application to the FastAPI server over HTTPS using `NEXT_PUBLIC_API_BASE_URL`
- avoid introducing a separate frontend BFF unless browser security, response aggregation, or caching needs prove that a direct API client is insufficient

Scope:

- authentication pages and protected route handling
- company selection and company-scoped navigation
- application shell, primary navigation, breadcrumbs, and role-aware menu structure
- CRUD and workflow pages for the implemented accounting modules
- file upload and download experience for evidence and exports
- operational pages for runtime health, metrics, alert review, and restore drill guidance
- shared form validation, loading states, error surfaces, and empty-state patterns
- frontend test coverage for critical user journeys

Frontend workstreams:

1. Application shell and session handling
   - login page
   - authenticated layout and route protection
   - token storage strategy suitable for the current backend auth model
   - logout flow and session-expiry handling

2. Company context and navigation
   - company switcher and current-company banner
   - dashboard landing page per company
   - navigation for bookkeeping, review, reporting, tax support, and operations

3. Master data and setup workflows
   - company setup and configuration history pages
   - user and company access admin screens where the frontend is expected to expose them
   - reporting category, tax code, and chart of accounts screens

4. Core accounting workflows
   - accounting period list, create, submit, approve, lock, and unlock views
   - journal list, create, post, reverse, and trial balance views
   - document upload, document list, document links, and download actions

5. Banking and reconciliation workflows
   - bank account setup screens
   - bank CSV upload and import review pages
   - import row list with duplicate visibility
   - reconciliation session list, detail, matching actions, ignore actions, and completion flow

6. Compliance and reporting workflows
   - BAS period and BAS run preparation screens
   - BAS adjustments, notes, approval timeline, and export actions
   - financial report parameter forms and result views for trial balance, profit and loss, balance sheet, and general ledger

7. Year-end support workflows
   - fixed asset register and asset detail pages
   - depreciation run generation, review, posting, and export flow
   - tax workpaper pack list, detail, adjustments, notes, exceptions, approval actions, and export flow

8. UX hardening and test coverage
   - shared table, filter, modal, and confirmation components
   - optimistic versus pessimistic update choices documented per workflow
   - accessibility review for forms, tables, and keyboard navigation
   - frontend integration tests for login, journal posting, BAS review, depreciation run posting, and tax workpaper approval

Deliverables:

- protected frontend application shell
- company-aware navigation and dashboard experience
- first-class web workflows for all implemented backend modules
- reusable typed API client layer in the frontend
- frontend testing baseline for critical finance journeys

Exit criteria:

- an internal user can perform normal bookkeeping, review, reporting, asset, and tax-support workflows from the web UI
- Swagger is no longer required for standard operations and is retained mainly for diagnostics and development
- major create, review, approve, upload, and export actions have matching frontend screens and validation states

#### Backend Work After Phase 12: Frontend Integration and API Readiness

Objective:
Prepare the FastAPI backend to support a production-grade internal web client with stable contracts, predictable error handling, and endpoints shaped for real user workflows rather than test-only access.

Architecture direction:

- retain FastAPI as the single business API surface
- keep domain modules in the modular monolith and avoid frontend-specific duplication of business rules
- expose contracts that are easy for a typed frontend client to consume
- stabilize response patterns before broad frontend rollout

Scope:

- browser-facing authentication and authorization behavior
- CORS and environment configuration for local and deployed frontend access
- consistent validation and business-error response shapes
- query support for list pages, dashboards, and drill-down workflows
- file upload and download compatibility from the browser
- API documentation and seed data support for frontend development
- contract and integration tests covering frontend-facing flows

Backend workstreams:

1. Authentication and browser-session compatibility
   - confirm the current bearer-token approach for the web client or replace it with a safer cookie-based session model if required
   - document token expiry and refresh expectations
   - ensure unauthorized and forbidden responses are consistent for frontend routing decisions

2. API contract stabilization
   - standardize error payloads for validation, permission, workflow, and not-found cases
   - ensure list endpoints have consistent sorting and predictable identifiers
   - review field names and nested response shapes for frontend usability

3. Dashboard and summary endpoints
   - add lightweight summary endpoints where the frontend would otherwise need to orchestrate many expensive calls
   - provide counts, statuses, and warning summaries for company dashboards, BAS work queues, reconciliation work queues, and tax workpaper queues

4. Query, filter, and pagination support
   - add pagination where list growth will become material
   - add filter parameters for dates, statuses, accounts, periods, and entity references
   - keep filtering rules aligned with internal review workflows and traceability needs

5. Frontend-friendly workflow actions
   - ensure every important workflow transition returns the updated entity shape needed to redraw the page immediately
   - add approval history and status summary surfaces where the frontend needs a timeline view
   - expose linked-document metadata in places where drill-through is required

6. File and export handling
   - validate browser upload constraints for documents and bank CSVs
   - keep export endpoints predictable for frontend download handling
   - ensure document and export downloads return stable filenames and content types

7. Contract documentation and seeded development support
   - keep OpenAPI accurate for every request and response shape
   - maintain example payloads and seeded data guidance for frontend development and QA
   - document environment settings required for web-to-API connectivity

8. Integration and contract test coverage
   - add backend tests that reflect real frontend sequences rather than isolated endpoint checks only
   - add contract checks for auth failures, locked-period actions, self-approval policy blocks, uploads, exports, and alert or health endpoints

Deliverables:

- frontend-ready API contract guidelines
- stable auth and error-handling behavior for browser clients
- summary and filtering endpoints needed by the web UI
- backend test coverage aligned to frontend user journeys

Exit criteria:

- the frontend can consume the backend without custom per-screen workarounds
- browser access, uploads, downloads, and workflow transitions behave consistently across modules
- the backend exposes enough summary and drill-down data for efficient frontend pages

## Milestone Plan

To keep delivery grounded, phases should be grouped into practical milestones.

### Milestone A: Foundation Ledger

Includes:

- Phase 0
- Phase 1
- Phase 2
- Phase 3

Outcome:

The team can manage users, companies, configuration, chart of accounts, journals, review states, and locked periods.

### Milestone B: Evidence and Banking

Includes:

- Phase 4
- Phase 5
- Phase 6

Outcome:

The team can import bank CSVs, stage them, reconcile them, and trace records to source documents.

### Milestone C: BAS Support

Includes:

- Phase 7
- Phase 8

Outcome:

The system can produce BAS support figures and accountant-facing review packs for manual ATO form entry.

### Milestone D: Year-End Support

Includes:

- Phase 9
- Phase 10
- Phase 11

Outcome:

The system supports financial reporting, fixed asset support, and company tax workpapers.

### Milestone E: Production Readiness

Includes:

- Phase 12

Outcome:

The system is operationally ready for sustained internal use.

#### Post-Milestone E Delivery Sequence: Frontend Work

The frontend rollout should proceed in the following order so each slice lands on a usable vertical workflow:

1. Auth, session handling, protected layout, and company selection
2. Company setup, configuration history, and chart of accounts screens
3. Accounting periods, journals, trial balance, and document flows
4. Bank accounts, bank imports, and reconciliation workflows
5. BAS review, approval, and export workflows
6. Financial reporting screens and export actions
7. Fixed asset register, depreciation runs, and export screens
8. Tax workpaper packs, notes, exceptions, approvals, and PDF export screens
9. Cross-cutting polish: search, tables, filters, accessibility, keyboard support, and frontend integration tests

Frontend completion outcome:

- the web application becomes the normal operating surface for internal users
- module coverage mirrors the backend capability already implemented through Milestone D and Phase 12 operations work

#### Post-Milestone E Delivery Sequence: Backend Work

The backend should support that rollout in the following order:

1. finalize browser auth approach, CORS rules, and unauthorized response behavior
2. standardize error payloads and workflow-state responses across modules
3. add summary endpoints for dashboards and work queues
4. add pagination and filtering for high-volume lists such as journals, imports, documents, and workpaper items
5. expand document-link, approval-history, and export metadata surfaces needed by the UI
6. add contract and sequence tests that mirror the new frontend workflows
7. maintain seeded example payloads and QA fixtures for sustained frontend development

Backend completion outcome:

- the FastAPI server behaves as a stable application backend for the internal web client rather than only as a development or Swagger surface
- frontend teams can build against predictable contracts without duplicating business logic or compensating for inconsistent endpoint behavior

## Testing Strategy

Testing must be built into every phase, especially for financial calculations and locking behavior.

### Unit Test Priorities

- balanced journal validation
- posting and reversal rules
- period lock enforcement
- BAS calculation logic
- GST mapping logic
- depreciation calculations
- report aggregation logic
- approval policy behavior including same-user maker/checker settings

### Integration Test Priorities

- authentication and access control
- company scoping
- journal posting end-to-end
- bank CSV import and duplicate detection
- reconciliation workflows
- BAS preparation and export
- PDF generation pipeline
- configuration change effect on future but not historical outputs

### End-to-End Test Priorities

- create company and configure BAS settings
- set up chart of accounts
- post journals
- upload documents
- import bank CSV
- reconcile and review
- generate BAS support pack
- approve and lock period

## Non-Functional Requirements

### Financial Correctness

- use decimal types everywhere for money and tax values
- define consistent rounding rules and document them
- prohibit float-based calculations in business logic

### Performance

- optimize for correctness first
- ensure large journal and bank datasets remain searchable and reportable
- use background processing for pack generation when necessary

### Reliability

- migrations must be reversible or safely forward-fixable
- backups must cover both database and document storage
- failed imports and exports must be recoverable and diagnosable

### Security

- strict company scoping on every data read and write
- hashed passwords only
- secure file access and storage paths
- clear separation between user UI and backend admin tooling

## Risks and Mitigations

### Risk: Configuration changes distort historical BAS outputs

Mitigation:

- version or snapshot configuration context per BAS run
- lock period outputs after approval
- show effective-date history clearly

### Risk: Users treat imported bank data as final accounting truth

Mitigation:

- force staging and review before ledger posting
- visually distinguish raw imports from posted accounting data

### Risk: Silent changes after approval

Mitigation:

- explicit lock states
- reversal and adjustment workflows only
- audit logging for unlocks and late changes

### Risk: Multi-company leakage

Mitigation:

- enforce company scoping in every query path
- test authorization boundaries thoroughly

### Risk: PDF generation becomes brittle or inconsistent

Mitigation:

- define standard report templates early
- treat PDF generation as a first-class export workflow with tests

## Recommended First Build Order

The first active development cycle should focus on the smallest slice that proves the architecture and accounting backbone.

### Sprint Sequence Recommendation

1. Scaffold `web`, `api`, PostgreSQL, migrations, auth skeleton, and backend admin shell.
2. Implement companies, user-company access, and company configuration history.
3. Implement chart of accounts and journal posting.
4. Implement accounting periods, review states, and lock controls.
5. Add trial balance and ledger inquiry views.

This sequence delivers the first meaningful milestone without prematurely jumping into BAS or bank imports before the ledger foundation is stable.

## Definition of Done

A feature should not be considered done unless it:

- stays within the internal-use boundary
- is traceable and reviewable
- does not imply automatic lodgment or tax-agent behavior
- handles errors clearly
- respects audit and lock rules
- includes appropriate automated tests
- uses conservative report wording
- fits the chosen stack without unnecessary architectural expansion

## Immediate Next Step Recommendation

The best next implementation step is to create the actual repository scaffold for:

- Next.js frontend
- FastAPI backend
- PostgreSQL integration
- Alembic migrations
- authentication foundation
- backend admin shell

That should be followed immediately by the `Company`, `UserCompanyAccess`, `CompanyConfiguration`, `Account`, `JournalEntry`, and `JournalLine` schema design.

## Implementation Status

The following planning outputs and scaffold artifacts now exist in the repository:

- root repository scaffold for `api`, `web`, `docs`, `infra`, and `samples`
- root Docker Compose file and shared environment template
- FastAPI app shell with settings loader, security helpers, database session wiring, and Milestone A core routers
- Next.js app shell with a Milestones A through D Phase 10 overview landing page
- initial core database schema draft in documentation, SQLAlchemy model form, and Alembic migration form for Milestones A through C
- phase backlog with epics and ticket candidates
- root repository README
- focused backend tests for Milestone A auth, company setup, journal posting, period locking, self-approval policy behavior, Milestone B documents, bank staging, reconciliation, Milestone C BAS calculation, approval, locking, and export behavior, Milestone D financial reporting and export behavior, Milestone D Phase 10 fixed asset depreciation behavior, Milestone D Phase 11 annual workpaper behavior, and Phase 12 operational health, metrics, and alert behavior

Milestone A backend implementation now includes:

- bootstrap authentication and login
- admin overview and user creation entry points
- company creation and configuration versioning
- company access assignment
- chart of accounts, reporting category, and tax code entry points
- accounting period lifecycle and maker/checker policy enforcement
- journal drafting, posting, reversal, and trial balance reporting

Milestone B backend implementation now includes:

- source document upload, checksum capture, document linking, and download
- bank account setup
- bank CSV upload and staging
- duplicate detection and staged row status tracking
- import confirmation before reconciliation
- reconciliation session creation, item matching, ignore actions, summary, and completion validation

Milestone C backend implementation now includes:

- BAS period generation driven by effective company configuration
- BAS run generation from posted journal lines using tax-code BAS label mapping
- BAS line results with manual adjustments and review notes
- BAS approval actions with self-approval policy enforcement
- accounting-period lock handling for `after_approval` and `after_export` BAS policies
- CSV and PDF BAS support exports stored as traceable documents

Milestone D Phase 9 backend implementation now includes:

- date-filtered trial balance reporting and CSV export endpoints
- profit and loss reporting from posted journals and account types
- balance sheet reporting with current earnings included in equity totals
- general ledger detail reporting with account filters and opening balances
- report route wiring under the company reporting module

Milestone D Phase 10 backend implementation now includes:

- fixed asset master data with acquisition, in-service, useful life, and account mapping fields
- fixed asset disposal workflow with auditable status history records
- depreciation run generation across accounting-period ranges
- straight-line and diminishing-value depreciation method support in the asset model
- posted depreciation journals using the standard ledger and `depreciation` source type
- CSV export for depreciation review support

Milestone D Phase 11 backend implementation now includes:

- annual tax workpaper pack generation tied to year accounting periods
- snapshot-based support schedules for accounting profit, GST reconciliation, and fixed assets
- manual tax adjustments with taxable income support totals
- annual review notes, sign-off notes, and exception tracking with resolution history
- maker and checker approval workflow with approval action history
- financial-year locking on pack approval
- document-backed PDF export for accountant review packs

Phase 12 operational baseline now includes:

- documented Docker Compose deployment shape for an internal single-server installation
- liveness and readiness endpoints with database and document-storage checks
- Prometheus-style metrics output for request, readiness, and alert counters
- degraded-readiness alert hooks with optional webhook delivery and cooldown control
- request-scoped structured JSON logging with request ID correlation
- Docker health checks for PostgreSQL and API readiness
- backup and restore scripts for PostgreSQL and document storage
- restore-drill procedure and log template for routine backup validation
- deployment and recovery documentation under `infra/`
- initial frontend operations workflow page for health, metrics, alert, and restore-drill visibility
- root-level `Vocab&Process.md` onboarding guide covering implemented frontend pages, operator tabs, accounting vocabulary, and end-to-end internal workflow explanations for engineers without accounting background

The next implementation step inside Phase 12 should extend observability and reliability with performance testing and then continue replacing static frontend surfaces with domain workflows.

Latest implementation update:

- the shared operator client has now been decomposed into a thin authenticated shell, a dedicated shared operator-state hook, reusable operator UI primitives, and route-scoped section components for dashboard, setup, bookkeeping, banking and BAS, reports, and year-end workflows so future UI changes can stay local to their owning route
- the browser suite now includes a fourth high-risk operator journey for year-end workpapers, covering year-period preparation, tax-pack creation, pack selection, submit and approve workflow transitions, and PDF export creation from the year-end route
- Docker Compose now includes a `test` profile with a dedicated Playwright `e2e` service plus a web health check, and GitHub Actions now runs that profile through `.github/workflows/playwright-e2e.yml` so browser validation can execute against the composed API and web services in CI rather than a host-only dev setup
- compose and API defaults now explicitly allow the internal `http://web:3000` browser origin used by the Playwright container so operator flows remain accessible when the suite runs inside Docker networking
- true backend update and delete endpoints are now implemented for the main user-created admin, company, reference, period, journal, document, bank import, reconciliation, BAS, fixed asset, depreciation run, and tax workpaper resources, with conservative draft and dependency guards where silent historical changes would be unsafe
- BAS run, depreciation run, and tax workpaper pack draft rebuild logic is now centralized in backend services so recalculated update paths follow the same calculation rules as initial generation
- the internal frontend workbench now uses module-specific update and delete cards instead of generic placeholder mutation tools, and captures additional resource IDs needed to drive those routes directly from the browser
- focused backend CRUD regression coverage now exists in `api/tests/test_crud_mutations.py`, and the workbench configuration builds successfully in the Next.js production build
- the frontend workbench now distributes mutation cards into their owning functional sections, hides them until prerequisite IDs and workflow states are satisfied, and clears stale context values after successful destructive actions so the browser UI tracks backend lifecycle rules more accurately
- broader backend contract coverage now exists in `api/tests/test_workflow_mutation_guards.py` for BAS warning immutability and export documents, confirmed bank import and completed reconciliation mutation guards, fixed-asset and depreciation-history mutation blocks, and tax workpaper dependent, resolved-exception, approved, and exported-document guard paths
- the root frontend surface is now a production-oriented operator workspace instead of a static status page, with authenticated company-aware sections for setup, bookkeeping, banking and BAS, reports, and year-end support backed by real forms, tables, workflow buttons, and file actions rather than generic API request cards
- the new operator workspace includes browser-driven login and bootstrap flows, session persistence, company selection, dashboard summaries, guided CRUD and workflow actions for the major implemented modules, and links that keep the diagnostic workbench and operations area available as secondary support surfaces
- the frontend navigation and styling were updated to support the new operator shell, and the Next.js production build now passes with the new workspace in place
- the operator workspace is now split across route-specific pages for dashboard, setup, bookkeeping, banking and BAS, reports, and year-end while keeping the shared authenticated shell and workflow state intact
- Playwright browser coverage now exists under `web/tests/e2e/operator.spec.ts` for the highest-risk operator journeys: UI sign-in and route navigation, bookkeeping period and journal posting, and BAS generation through approval and export creation; the suite runs through `npm run test:e2e` and boots an isolated frontend server on port `3100` for current-source validation
- the new browser suite exposed and the implementation now fixes a backend route-collision defect in the fixed-assets router where `/depreciation-runs` was being matched by the generic `/{asset_id}` path, plus local development CORS and compose defaults were widened so the managed e2e frontend origin can call the API cleanly
- LAN access is now supported without hardcoded localhost assumptions: the frontend derives API and Swagger targets from the current request hostname by default, safely ignores loopback-only overrides when opened from another machine, and the API now supports explicit origin regex configuration with private-network IP defaults so operator workflows can be opened from other PCs on the same internal network by IP while remaining conservative about allowed origins
- the Next.js development server now explicitly allows configured LAN dev origins through `allowedDevOrigins`, with the Compose-backed web service defaulting to the current host LAN IP so the operator shell, workbench request cards, login flow, and session actions can load their dev resources instead of failing on cross-origin dev-asset blocking when opened from another PC
- the active local runtime configuration has now been hardened for LAN use as well: `.env` no longer pins the frontend to a localhost-only API base URL, the allowed API origin list explicitly includes the current LAN frontend origin alongside localhost, and the recreated `api` and `web` containers were verified against the exact Setup-page accounts endpoint with successful `OPTIONS` and authenticated `GET` responses from `http://192.168.1.100:3000`
- a local-only PowerShell maintenance utility now exists at `infra/scripts/clear_postgres.local.ps1` to stop the API, drop and recreate the PostgreSQL database, and leave clear post-reset migration instructions, while `.gitignore` now excludes local operator scripts under `infra/scripts/*.local.ps1`
- the operator workspace now clears stale persisted auth state automatically on `401`, so after a database reset or any invalidated token the frontend falls back to the anonymous bootstrap/login view instead of remaining stuck in an authenticated shell backed by dead session and company IDs
- the bookkeeping journal editor now derives its effective `accounting_period_id` from the selected or first available accounting period and blocks submission with a clear frontend error when no periods exist yet, so journal creation no longer sends an empty UUID and surfaces the raw backend parsing error
- backend journal validation now enforces the same single-sided positive-amount rule as the database check constraint before insert or update, so invalid `0.00 / 0.00` or double-sided lines return a controlled `400` validation error instead of surfacing as an internal server error that the browser misreports as a CORS failure
- the bookkeeping journal editor now validates account selection, single-sided positive amounts, and balanced totals before submitting, so common draft mistakes are caught in the UI instead of round-tripping to the API
- the setup-page account form now constrains account type selection to the backend enum values, blocks empty account-code and account-name submissions before the request is sent, offers a direct reset path back to a fresh create form, and formats FastAPI validation responses into readable operator messages instead of showing raw JSON that can be mistaken for a transport or CORS defect
- reporting-category create and update requests now validate `category_type` through the backend request schema before the route runs, so invalid category types return a normal `422` response with LAN CORS headers instead of throwing an unhandled `500` that the browser reports as a missing `Access-Control-Allow-Origin`; the setup form source has also been aligned to valid enum-backed category-type options with local code and name checks before submission
- tax-code and account create and update requests now validate their enum-backed fields through the backend request schema before the route runs, and the chart-of-accounts backend now supports the richer operator-facing account taxonomy needed by Setup, including `revenue`, `cost_of_sales`, `other_income`, `other_expense`, and `non_posting` alongside legacy contra types required by existing report and fixed-asset flows
- non-posting accounts are now enforced as true non-manual-posting accounts instead of a cosmetic label only: the API rejects non-posting accounts that allow manual posting, journal validation blocks any account marked as not allowing manual posting, and focused regression coverage now exists for invalid tax-code/account enum values plus non-posting journal rejection
- the Setup route no longer treats reporting categories, tax codes, and accounts as three minimal list widgets inside one reference-data card: each now has its own dedicated management block with list views, formalized labels, row action menus for edit and delete, richer forms, and account-code range controls that lock the first two digits to the selected standard account-type band while preserving advanced legacy account types for compatibility
- the Bookkeeping route now includes a dedicated full-width ledger explorer directly beneath Journals so operators can inspect draft and posted journal lines without switching over to Reports; it reuses the existing general-ledger report API, supports date and account filters plus CSV export, groups lines by account with opening and closing balances, shows each line's journal status, highlights the currently selected journal, and automatically refreshes the visible ledger window after journal save, post, and reversal actions
- journal entries and supporting documents now have an explicit journal-owned evidence workflow on top of the existing optional `document_links` join table: the API exposes journal-side list, attach, and unlink routes for many-to-many document evidence, duplicate links to the same journal are blocked, focused CRUD regression coverage confirms the same document can support multiple journals, and the Bookkeeping journal card now shows a dedicated evidence panel where operators can attach uploaded files, upload-and-link fresh evidence, download attachments, and remove links without leaving the selected journal context
- a root-level PowerShell maintenance script now exists at `clear_db.ps1` so local testing can reset the PostgreSQL database, rerun Alembic migrations, and restart the API and web services with one command; `.gitignore` now excludes that exact script so the local destructive helper stays out of versioned source by default
- newly created companies now seed a broad default reference-data pack covering holding, investment, service, and sales-company workflows: company creation adds default reporting categories, GST/tax codes, and chart-of-accounts records with conservative mappings for cash, receivables, investments, loans, equity, revenue, direct costs, operating expenses, and passive income so operators start from a reviewable baseline instead of an empty setup
- reporting categories and tax codes now support the same active/inactive lifecycle already used by accounts, with persisted `is_active` flags, an Alembic migration for existing databases, focused backend regression coverage for seeding and disabling, and Setup-page controls that let operators disable records without deleting historical references
- operational selectors now hide inactive reference data by default while preserving already-selected inactive values for existing drafts: journal account and tax-code pickers plus fixed-asset account pickers use active-only option lists, while Setup still surfaces inactive records for administration and reactivation
- the create-company operator flow now reloads the new company workspace by the created company id instead of relying on asynchronously updated selected-company state, so newly seeded reference data appears immediately in the page after company creation rather than requiring a manual refresh or reselection
- the shared operator state now clears company-scoped tables, selections, and configuration drafts whenever auth is lost or the persisted selected company no longer exists, so a destructive database reset cannot leave stale configuration versions or other company data visible in the frontend after the next session load
- the bookkeeping workflow now includes an AI-assisted journal recommendation slice for invoice and receipt support documents: operators can upload one or more source files, pick an OpenAI ChatGPT-backed model, review structured line recommendations and warnings, and then accept the result into a draft journal for human review rather than automatic posting
- the backend now includes persisted journal recommendation runs, linked recommendation documents, recommended lines, and proposed reference-data additions plus conservative accept and reject flows; accepted runs reuse existing ledger validation, accounting-period lock rules, and journal evidence linking so the AI path does not bypass the normal accounting controls
- OpenAI integration is now environment-driven through `OPENAI_API_KEY` and related backend settings, with the first implementation exposing a model catalog for `gpt-5.5`, `gpt-5.4`, and `gpt-5.4-mini` plus estimated price-per-1000-call guidance derived from configured input and output token assumptions and surfaced to the operator UI before analysis starts
- the Bookkeeping route now includes a dedicated AI journal drafting panel that supports multi-file upload, optional operator notes, recommendation detail review, proposal acceptance, and draft-journal creation without leaving the existing bookkeeping workspace
- focused backend regression coverage now exists in `api/tests/test_journal_recommendations.py` for model-catalog exposure, recommendation analysis flow, draft-journal creation, evidence linking, and accepted reference-data proposals; those tests pass, and the Next.js production build also passes with the new bookkeeping UI in place
- the AI recommendation runtime now lazy-loads the OpenAI SDK during analysis instead of importing it at API startup, so a missing optional runtime dependency fails closed as a controlled `503` on the recommendation endpoint rather than breaking login and the rest of the operator workspace; live validation confirmed the API health endpoint, direct auth login, and the full Playwright operator suite all recovered once that path was isolated
- the OpenAI file-input adapter now sends PDF `input_file` payloads as `data:` URLs rather than raw base64 strings, matching the live Responses API shape accepted by the configured GPT-5.4 model family and preventing `invalid_request_error` failures during journal recommendation analysis
- the OpenAI structured-output schema for journal recommendation proposals now uses an explicit proposal-attributes object with `additionalProperties: false` instead of a free-form JSON dictionary, matching the Responses API schema validator and preventing live `invalid_json_schema` failures when GPT returns reference-data proposal attributes
- the OpenAI journal-analysis runtime now performs one conservative retry when the first model response fails local balance validation, feeding the model the invalid debit and credit totals and requiring a corrected balanced double-entry recommendation before the run can move to review
- the proposal structured-output schema now constrains `proposal_type` to the actual backend enum values (`account`, `tax_code`, `reporting_category`), preventing GPT output such as `reference_data` from reaching persistence and surfacing as a runtime enum-conversion failure
- the AI journal recommendation prompt is now versioned as `journal-document-v2` and instructs the model to separate visible GST on invoices or receipts into appropriate existing GST input-credit, GST collected, GST payable, or GST clearing accounts while preserving review-first behaviour and avoiding invented GST when the source document is unclear
- the AI journal recommendation model catalog now includes GPT-5, GPT-5 mini, and GPT-5 nano alongside the existing GPT-5.5, GPT-5.4, and GPT-5.4 mini options; GPT-5.2, GPT-5.1, and all GPT-4.1 variants have been removed from the selectable list, and displayed per-1,000-call estimates are calculated from the current 22,000 uncached text input token and 1,200 output token assumptions
- the OpenAI request builder now omits `temperature` for all journal recommendation models to avoid provider-side `unsupported_parameter` errors across the expanded GPT-5 and GPT-4.1 catalog; structured output validation and the local balance retry remain the determinism and quality controls
- the AI journal recommendation schema now caps free-text field lengths and the OpenAI request uses a higher `max_output_tokens` ceiling so smaller models such as GPT-5 mini and GPT-5 nano are less likely to return truncated structured JSON while still being instructed to keep summaries, explanations, warnings, and proposal rationales concise
- GPT-5, GPT-5 mini, and GPT-5 nano journal recommendation calls now explicitly request minimal reasoning effort so low-cost reasoning models preserve more output budget for the required structured JSON; raw provider responses and usage are also captured before structured-output validation failures so incomplete provider statuses and reasons are visible during diagnosis
- parse-time invalid JSON from `responses.parse(...)` now gets one corrective retry before the run fails; the retry tells the model to return exactly one schema object and not copy markdown, source-document transcripts, schemas, `reference_context`, or prompt instructions into the answer, which addresses smaller-model failures where prompt instruction text was appended to otherwise JSON-like output
- live GPT-5 nano probing against `2025-05-08-Officeworks.pdf` showed the small model inventing non-schema line fields, itemising receipt products, sometimes omitting the `proposals` field, and failing to include a balancing payment line; the prompt and schema now explicitly limit line/proposal counts, require aggregated one-sided lines, require a balancing payment/receivable/payable line, require `proposals` even when empty, and forbid non-schema fields such as `notes`, `debit_tax_amount`, or `credit_tax_amount`
- the migration hygiene test now checks only migrations that actually declare PostgreSQL `ENUM(...)` DDL, which keeps the `create_type=False` safeguard for enum-creating migrations while no longer failing on historical raw-SQL enum expansion migrations like `20260508_0006_expand_account_types.py`
- repository-wide backend validation is green again after aligning older test setup with the now-seeded default chart of accounts: the tests now reuse or normalize seeded account codes where appropriate instead of assuming an empty chart for every new company; full backend `pytest` currently passes with 55 tests
- the AI bundle-create path now aligns its enum storage with the live PostgreSQL schema: journal-recommendation status and proposal enums are bound by lowercase value instead of uppercase enum member name, and a follow-up migration adds uppercase `JOURNAL_RECOMMENDATION_RUN` labels to the shared document-link and entity enums so recommendation evidence linking no longer crashes the API and surface as a misleading browser CORS/fetch failure
- the compose-managed API runtime now applies Alembic migrations before boot and passes through `OPENAI_API_KEY` from the system environment, so newly added schema is present in the running container and the OpenAI-backed analysis step can see the host-provided key when one is configured
- the Setup route now exposes explicit configuration-version management controls instead of a save-only form: operators can select rows for update, start a fresh version with a dedicated reset action, and delete the latest editable version from either the selected-form action or the row actions menu while still respecting backend guards for historical versions
- the root `clear_db.ps1` reset helper now performs an explicit post-migration verification that both `companies` and `company_configuration_versions` are empty before it reports success, making the local reset workflow self-checking for the configuration-version data the frontend depends on
- the bank-import backend now auto-detects the four-column Commonwealth Bank export format with no header row and converts it into the system's internal `date / description / debit / credit` shape during upload, so operator CSV uploads no longer need manual pre-formatting before staging and reconciliation
- focused bank-import regression coverage now confirms both the original required-column validation path and the new Commonwealth Bank auto-conversion path in `api/tests/test_milestone_b.py`
- the development API compose service now runs `uvicorn` with `--reload` against the bind-mounted `/app` source tree, because otherwise backend fixes can remain invisible in the live operator workspace until the container is manually recreated even when tests are already green locally
- live validation confirmed the Commonwealth Bank CSV upload end to end after recreating the API service: the direct API request returned a staged import session and the browser Banking page showed `Uploaded bank import session.` with staged `commbank-live.csv` sessions visible in the import list
- the Banking operator panel now gives selected bank import sessions their own session-note editor instead of reusing the upload draft, so staged imports can be updated from the frontend without accidentally mutating the upload form state
- the Banking operator panel now exposes staged-only `Delete` and `Save note` actions for selected bank import sessions, matching the existing backend workflow guards while keeping confirmed sessions review-only in the frontend
- live browser validation on `/banking` confirmed both frontend actions end to end: a staged `bank-import-sample.csv` session note was updated to `Frontend updated staged note`, and the same staged session was then deleted successfully from the import list
- the live Example Pty Ltd dataset now includes a full ledger imported from `CSVData.csv`: 139 posted `bank_import` journals with stable `CSVDATA-L###` references, two covering accounting periods, a CommBank operating bank record, and the extra chart accounts needed to represent property deposits, rental income, utilities, communications, overseas software, rates, and director-loan activity
- the CSV-driven ledger import was loaded idempotently by checking existing `CSVDATA-L###` journal references before insert, and each journal line now carries `CSVData.csv:<line>` source references so the imported balances remain drillable back to the source statement rows
- focused live validation through the running API confirmed the imported ledger count and balance: `/journals` returned 139 posted entries and the trial balance for 2025-04-01 through 2026-05-31 showed account `1250 Operating Bank` at `36,994.67`, matching the final running balance in the supplied CSV data
- the Bookkeeping journals workspace now uses a journals-specific split layout and scroll shell so long journal lists stop at a fixed height and scroll internally instead of stretching the whole split row and distorting the journal editor panel on the right
- the live Example Pty Ltd dataset now also includes the separate `CSV CGA.csv` ledger: 28 posted `bank_import` journals with stable `CSVCGA-L###` references, a dedicated `CommBank CGA` banking record, and the extra chart accounts needed to track the CGA cash balance and TFN withholding-tax receivable without collapsing them into the operating bank account
- the CGA statement load was inserted idempotently by checking existing `CSVCGA-L###` references before insert, and focused validation confirmed account `1280 CommBank CGA Cash Reserve` at `180,191.40` and account `1580 TFN Withholding Tax Receivable` at `9,018.00`, matching the supplied statement totals

## Appended Plan: Production Frontend UI and UX Delivery

### Why this plan is needed now

The current web application already includes a company-aware operator workspace, an operations dashboard, and a browser workbench for direct request execution.

That is enough for real internal workflows across the main implemented domains, but follow-up work is still needed to harden the UI architecture, deepen workflow coverage, and keep diagnostic surfaces secondary for routine operations.

The next frontend stage must:

- replace request-card API driving with task-oriented internal workflows
- expose bookkeeping, review, reconciliation, BAS, reporting, fixed asset, and tax-support work in business terms rather than endpoint terms
- remain conservative, auditable, and internal-use-only
- be production-ready in delivery shape, authentication behavior, error handling, accessibility, and monitoring

This plan assumes the backend remains FastAPI and the frontend remains Next.js App Router, and that the browser client continues to operate inside the internal-use scope defined for this repository.

### Production frontend objective

Deliver a production-grade internal operator application where normal users can complete routine work from guided screens, forms, queues, tables, review panels, and export actions without needing Swagger or the testing workbench for standard operations.

### Explicit non-goals for this frontend plan

This frontend plan should not introduce or imply:

- automatic ATO lodgment
- tax-agent portal behavior
- public SaaS tenancy or self-service onboarding
- mobile app scope
- AI-first or autonomous categorisation or advice workflows that bypass human review
- replacing maker and checker review responsibilities with automation

### Product and UX principles for the production frontend

1. Task-first, not endpoint-first.
   Users should think in terms of companies, periods, journals, imports, BAS runs, depreciation runs, and tax packs rather than `POST`, `PUT`, and `DELETE` cards.

2. Review-oriented language.
   UI text must continue to use internal and conservative wording such as `ready for review`, `awaiting approval`, `export support pack`, and `manual form entry support`.

3. Traceability on every important screen.
   Each workflow screen should expose source records, related documents, approval actions, warnings, and export history where relevant.

4. Safe mutation patterns.
   Destructive and workflow-changing actions must use confirmations, status guards, and visible consequences. The UI must never make a reviewed or locked state feel casually editable.

5. One clear primary action per screen.
   The interface should reduce ambiguity: list pages should guide users into the next valid step instead of presenting a generic action matrix.

6. Internal speed over decorative complexity.
   The UI should feel intentional and professional, but productivity, clarity, and correctness matter more than visual novelty.

7. Accessibility and operational resilience are production requirements.
   Keyboard access, form labeling, focus handling, loading states, empty states, retry states, and degraded-backend states must be treated as required behavior.

### Target production frontend architecture

The production web application should move from a thin page set to a structured internal app with these layers:

1. Shell and navigation layer
   - authenticated app frame
   - top navigation and company switcher
   - section navigation by domain workflow
   - global session and status banner area

2. Domain route layer
   - route groups for setup, bookkeeping, compliance, reports, year-end support, and operations
   - summary pages for each major workflow area
   - entity detail pages for drill-down and review actions

3. Shared data and mutation layer
   - typed API client wrappers
   - consistent fetch, error, retry, and auth handling
   - mutation helpers for create, update, delete, submit, approve, lock, export, and upload actions

4. Shared presentation layer
   - tables, filters, status pills, detail panels, timeline components, upload controls, review note blocks, confirmation dialogs, and export controls

5. Feature-level workflow layer
   - forms, list pages, queue pages, review pages, and action drawers specific to each business module

The workbench should remain available for diagnostics and QA, but it should be clearly secondary once production workflows exist.

### Proposed production information architecture

The frontend should be reorganized into the following internal sections:

1. Dashboard
   - company summary
   - open work queues
   - readiness and alert summary
   - period and workflow attention items

2. Company setup
   - company profile
   - BAS and approval configuration history
   - user access management
   - reporting categories, tax codes, and chart of accounts

3. Bookkeeping
   - accounting periods
   - journals
   - trial balance and ledger drill-down
   - source documents

4. Banking
   - bank accounts
   - CSV imports
   - staged import review
   - reconciliation sessions and unresolved items

5. BAS support
   - BAS periods
   - BAS runs
   - adjustments and notes
   - approval history
   - export pack history

6. Financial reports
   - trial balance
   - profit and loss
   - balance sheet
   - general ledger

7. Year-end support
   - fixed assets
   - depreciation runs
   - tax workpaper packs
   - annual review notes and exceptions

8. Operations
   - health and readiness
   - alert feed
   - metrics summary
   - backup and restore guidance

### Proposed route map

The frontend should move toward a route model similar to the following:

```text
/
/login
/select-company
/dashboard

/setup/company
/setup/configurations
/setup/users
/setup/access
/setup/reporting-categories
/setup/tax-codes
/setup/accounts

/bookkeeping/periods
/bookkeeping/periods/[periodId]
/bookkeeping/journals
/bookkeeping/journals/new
/bookkeeping/journals/[journalId]
/bookkeeping/documents
/bookkeeping/documents/[documentId]

/banking/accounts
/banking/imports
/banking/imports/[sessionId]
/banking/reconciliation
/banking/reconciliation/[sessionId]

/bas/periods
/bas/runs
/bas/runs/[runId]

/reports/trial-balance
/reports/profit-and-loss
/reports/balance-sheet
/reports/general-ledger

/year-end/fixed-assets
/year-end/fixed-assets/[assetId]
/year-end/depreciation-runs
/year-end/depreciation-runs/[runId]
/year-end/tax-workpapers
/year-end/tax-workpapers/[packId]

/operations
/workbench
```

The final route structure may differ, but the application should clearly separate setup, operational bookkeeping, compliance workflows, and operational support.

### UX system and design language plan

The production frontend should move to a coherent internal design system rather than per-page styling.

#### Visual direction

- professional internal finance product rather than developer console
- clear typographic hierarchy for dashboards, data tables, forms, and review panels
- neutral, high-contrast palette with deliberate status colors for draft, review, approved, locked, warning, and error states
- strong spacing and panel rhythm for dense information screens
- restrained motion for transitions, drawers, confirmation states, and progressive disclosure

#### Shared UI primitives to build first

- authenticated app shell
- page header with breadcrumbs and primary action slot
- status pill system
- summary stat cards
- filter bar
- data table with empty, loading, and error states
- side panel or drawer for row detail
- sectioned form layout
- confirmation dialog
- timeline or approval history component
- warning and exception banner component
- document attachment list
- export action bar

#### Required interaction patterns

- replace freeform request editing with validated forms
- hide unavailable actions when lifecycle rules block them
- show why an action is unavailable where helpful
- use inline validation for field-level issues and top-level error banners for business-rule failures
- use review checklists or summary panels before approval and export steps
- keep downloads and exports user-driven and explicit

### Frontend feature plan by domain

#### Stage 1: Application shell, session, and navigation

Objective:
Establish the production app frame and remove reliance on a bare public overview page.

Scope:

- login screen and session restoration
- authenticated root layout
- company selector and company-scoped navigation
- role-aware navigation visibility
- global environment banner for internal or production context
- consistent top-level links to dashboard, workflows, reports, and operations

Deliverables:

- protected app shell
- session-expiry handling
- no requirement to manually paste tokens for standard use

Exit criteria:

- a normal user reaches a dashboard after login
- company context is visible and changeable
- workbench access becomes optional rather than required

#### Stage 2: Setup and reference data workflows

Objective:
Replace setup-related request cards with guided administration screens.

Scope:

- company profile page
- configuration history page with effective-from visibility
- user list and user detail screens
- company access matrix or list
- reporting categories screen
- tax codes screen
- chart of accounts screen

UX requirements:

- inline search and filtering for reference lists
- modals or side panels for light edits
- audit visibility or change-history links where available
- clear soft-delete and deactivation language

Exit criteria:

- reference-data maintenance is possible without opening Swagger or the workbench

#### Stage 3: Bookkeeping workflows

Objective:
Turn the ledger and period features into operator-grade workflows.

Scope:

- accounting period list and detail screens
- period submit, approve, lock, and unlock actions
- journal list with status, period, and source filters
- journal draft form with balanced-line editing UX
- journal detail view with posting and reversal actions
- trial balance screen with parameter inputs and drill-down links
- document upload and document-link management screens

UX requirements:

- line-entry table UX for journals
- running debit or credit balance indicators
- period status warnings before posting into restricted periods
- document attachment visibility from the journal detail surface

Exit criteria:

- daily bookkeeping and review work can happen in the app without endpoint-level tooling

#### Stage 4: Banking and reconciliation workflows

Objective:
Replace upload-and-mutate request cards with a real staged import and reconciliation workspace.

Scope:

- bank account maintenance pages
- CSV upload wizard with validation feedback
- import session detail page with row counts, duplicate counts, and status summary
- row review table with filters for duplicate, unresolved, and matched states
- reconciliation session list and detail view
- reconciliation item actions for match and ignore
- completion workflow with unresolved-item blocking explanation

UX requirements:

- upload progress and validation reporting
- side-by-side comparison for bank row and candidate journal match
- clear unresolved counts and completion readiness indicators
- visible link back to source import session

Exit criteria:

- a user can upload, inspect, confirm, reconcile, and complete a bank workflow from the app alone

#### Stage 5: BAS support workflows

Objective:
Present BAS support as a review and approval workspace rather than a list of API calls.

Scope:

- BAS period list and generation flow
- BAS run list with status filters
- BAS run detail workspace with label totals, adjustments, warnings, and manual notes
- submit and approve actions with policy feedback
- export controls and export history
- document download access for export outputs

UX requirements:

- label summary at top with drill-down sections below
- warning panel separated from manual review notes
- clear distinction between system totals and manual adjustments
- pre-export checklist and conservative disclaimer display

Exit criteria:

- BAS preparation, review, approval, and export are fully app-driven and understandable without Swagger knowledge

#### Stage 6: Financial report workflows

Objective:
Make standard reports easy to run and review with filters, summaries, and downloads.

Scope:

- report parameter panels
- report result tables and summary cards
- account and period drill-down links
- CSV export buttons with stable filenames and visible filter context

UX requirements:

- saved or sticky filter state per report page where practical
- empty-state guidance when report filters produce no rows
- export buttons grouped with report metadata and date range

Exit criteria:

- users can run and export supported reports without manual URL or query editing

#### Stage 7: Fixed assets and depreciation workflows

Objective:
Replace asset mutation cards with real asset register and depreciation workflows.

Scope:

- fixed asset register page with as-of-date support
- asset detail page with history, depreciation totals, and disposal state
- create and update asset flows with account selection
- depreciation run list and detail pages
- depreciation run generation, review, posting, and export actions

UX requirements:

- clear display of active versus disposed assets
- history timeline or status history section on asset detail
- depreciation run detail view showing totals and line items before posting
- explicit warnings when asset updates are blocked by depreciation history

Exit criteria:

- fixed asset maintenance and depreciation workflow become normal UI actions rather than diagnostic operations

#### Stage 8: Tax workpaper workflows

Objective:
Turn annual workpaper support into a structured review workspace.

Scope:

- tax workpaper pack list and detail pages
- schedules for accounting profit, GST reconciliation, and fixed assets
- adjustment, note, and exception management
- submit, approve, and export actions
- approval history and export history display

UX requirements:

- pack detail should read like a workpaper workspace, not a raw JSON object
- exception severity and resolution state should be visually obvious
- approved and exported states should visibly disable edits
- export screen or panel should reinforce review-only disclaimer language

Exit criteria:

- annual review support can be prepared, checked, approved, and exported entirely through the application UI

#### Stage 9: Operations and support workflows

Objective:
Keep the current operations surface, but integrate it into the authenticated internal application as a real support area.

Scope:

- preserve readiness, metrics, and alerts pages
- add support links to restore-drill procedures and deployment docs where appropriate
- add runtime connection-state messaging for frontend and backend outages

Exit criteria:

- operations remain available in production without exposing them as the main landing experience for normal users

### Frontend data, auth, and integration plan

The current workbench directly issues browser fetch requests from request cards. Production workflows need a more structured integration model.

#### Data access plan

- introduce typed API wrappers per domain rather than per-page ad hoc fetches
- centralize base URL resolution and auth header or cookie handling
- standardize parsing of validation errors, workflow errors, and not-found responses
- normalize download helpers for CSV, PDF, and document files

#### Auth and session plan

- remove manual token entry from standard user flows
- implement login form and persistent authenticated session behavior appropriate to the backend’s final auth model
- add logout and session-expiry redirect behavior
- ensure role and company-scoped permissions are reflected in the UI without assuming frontend-only security

#### Mutation plan

- create domain-specific mutation helpers for create, update, delete, submit, approve, reverse, confirm, complete, post, resolve, and export actions
- standardize success messaging, error banners, confirmation steps, and revalidation or refresh behavior
- prefer pessimistic updates for financial workflows where correctness and backend truth are more important than perceived instant response

#### Form plan

- use structured, schema-driven validation where practical
- create reusable field types for decimals, dates, enums, account selectors, tax code selectors, and document attachments
- preserve server-side validation as the final authority

### Backend support work required for a production frontend

The frontend can only become a proper operator application if backend contracts are shaped for it.

Required backend support items:

1. Authentication hardening for browser sessions
   - finalize bearer versus cookie strategy for production use
   - ensure CSRF, token expiry, and logout semantics are appropriate to the chosen model

2. Dashboard and queue endpoints
   - company dashboard summaries
   - counts for draft, review, approved, locked, unmatched, warning, and exception states

3. Lookup endpoints for selectors
   - accounts, tax codes, reporting categories, periods, bank accounts, and users should be easy to load for forms

4. Stable list filtering and pagination
   - journals, documents, import rows, reconciliation sessions, BAS runs, depreciation runs, and tax packs will need filtering and pagination as data grows

5. Frontend-friendly detail responses
   - detail pages should not require a large number of separate network calls to render basic context

6. Consistent error payloads
   - blocked workflow actions should return stable business-rule messages suitable for UI display

7. File handling consistency
   - stable filenames, media types, and content disposition for document and export downloads

### Production deployment plan for the frontend

The current frontend already builds, but production rollout requires more than a successful `next build`.

#### Runtime and environment plan

- define production environment variables for API base URL, environment labeling, and any auth-related settings
- decide whether the frontend is served behind the same origin as the API or through an internal reverse proxy
- prefer a same-origin or controlled reverse-proxy setup where practical to reduce browser auth and CORS complexity

#### Build and release plan

- keep a repeatable production build path for the Next.js app
- define container or service runtime for the frontend within the existing deployment model
- add deployment documentation for frontend environment configuration and smoke checks

#### Production checks before release

- login flow
- company switcher
- key CRUD workflows for setup and bookkeeping
- upload and download flows
- BAS prepare, approve, and export path
- depreciation run generate, post, and export path
- tax workpaper approve and export path
- operations page availability

### Testing and quality gates for production frontend delivery

The frontend should not be considered production-ready until it has workflow-level coverage.

#### Required automated coverage

- route rendering and auth guard coverage
- API client unit coverage for error parsing and download handling
- integration tests for critical mutation forms and review flows
- end-to-end tests for the highest-risk business journeys

#### Minimum end-to-end journey set

1. login and company selection
2. create and post a journal
3. upload and link a document
4. upload and confirm a bank CSV import
5. complete a reconciliation session
6. generate, review, approve, and export a BAS run
7. create and post a depreciation run
8. create, approve, and export a tax workpaper pack

#### Manual QA expectations before production rollout

- keyboard navigation on core forms and tables
- responsive behavior for laptop-sized internal screens
- clear error display during backend downtime or partial degradation
- correct disabling or hiding of blocked actions for reviewed, approved, posted, completed, or locked states

### Rollout sequencing plan

The production frontend should be delivered in controlled waves rather than replacing everything at once.

#### Wave 1: foundation

- login
- authenticated shell
- dashboard
- company setup and reference-data management

#### Wave 2: bookkeeping core

- periods
- journals
- documents
- trial balance drill-down

#### Wave 3: banking workflows

- bank accounts
- import sessions
- reconciliation workspace

#### Wave 4: BAS and reporting

- BAS periods and BAS runs
- financial report pages
- export history visibility

#### Wave 5: year-end support

- fixed assets
- depreciation runs
- tax workpaper packs

#### Wave 6: production hardening

- end-to-end coverage
- support tooling polish
- environment hardening and final operator documentation

The workbench should remain available during rollout, but each completed wave should remove the need to use it for that domain’s normal workflow.

### Definition of done for the production frontend

This frontend effort is not complete until all of the following are true:

1. Standard users no longer need to manually call APIs for normal workflows.
2. Core workflows are exposed through guided UI screens with proper validation and status handling.
3. Approval, export, posting, and deletion actions are represented with conservative, review-safe UX.
4. Important records remain traceable to source documents, workflow history, and related entities.
5. Authentication, error handling, uploads, downloads, and degraded-backend states behave reliably in production.
6. Accessibility, testing, and release documentation reach production-ready quality.
7. Swagger and the workbench become support and diagnostic tools rather than the standard operating interface.

### Recommended next implementation step after this plan update

Continue from the existing authenticated operator workspace by hardening route-level workflow modules, shared data and mutation helpers, and browser coverage, starting with gaps where operators still fall back to diagnostics or lack end-to-end validation.

## Appended Plan: AI-Assisted Document-to-Journal Drafting

### Why this plan is needed now

The repository already supports:

- document upload and download
- many-to-many document linking to journal entries
- draft journal creation and posting
- company-specific reference data for accounts, tax codes, and reporting categories

What it does not yet support is a review-safe workflow that starts from uploaded invoices or receipts, asks a multimodal LLM for a recommended journal draft, and lets the operator review that recommendation before creating a journal.

This plan defines that workflow while preserving the repository boundary:

- internal support only
- no automatic lodgment
- no automatic tax advice finalisation
- no silent posting into the ledger

### Objective

Add an internal workflow that allows an operator to:

1. upload one or more invoice or receipt files that relate to the same transaction or journal entry
2. optionally add descriptive free-text context explaining the transaction
3. send those files plus a structured engineered prompt to a server-side multimodal LLM provider integration
4. include company-specific reference data in that prompt so the model can prefer existing accounts, tax codes, and reporting categories where appropriate
5. receive a structured recommendation for a draft journal entry plus any proposed new reference data needed to formalize the draft
6. review, edit, approve, and then create a draft journal entry with all uploaded files attached as evidence

The system should create a recommended draft. It should not automatically post the journal entry and it should not silently create new reference data.

### Explicit non-goals for the first version

The first version should not:

- auto-post journals after model output
- auto-approve or auto-lock anything
- auto-create reference data without explicit user approval
- replace accountant or reviewer judgment on GST, BAS, or tax treatment
- provide free-form natural-language financial advice as a primary output
- depend on a single vendor-specific API shape throughout the domain model

### Product principles for this feature

1. Human review remains mandatory.
   The LLM output is a recommendation only and must be presented as such.

2. Existing reference data should be preferred.
   The model should only propose new accounts, tax codes, or reporting categories when the existing company data is not sufficient.

3. Multiple files must be supported as one transaction bundle.
   The user must be able to upload several files that collectively support the same journal recommendation.

4. Traceability must remain strong.
   The recommendation must retain links to every uploaded file, the prompt version, the provider used, the optional user note, and the normalized model output.

5. No silent mutation.
   The feature may create a draft recommendation record, but any resulting journal entry or new reference data must be explicitly confirmed by the user.

6. Conservative wording is required.
   Use terms such as `recommended draft`, `suggested account`, `proposed tax code`, and `needs review`.

### Proposed operator workflow

#### Step 1: Start a recommendation session

From the Bookkeeping route, the operator should be able to start a new `document-to-journal` recommendation session.

The start form should capture:

- one or more uploaded files
- optional free-text context from the user
- optional target accounting period
- optional indicator that the recommendation should be attached to an existing draft journal instead of creating a new one later

#### Step 2: Store documents first

All uploaded files should be stored through the existing document storage pipeline before any model call happens.

This preserves:

- checksum tracking
- document lifecycle consistency
- later evidence linking
- retry capability without re-uploading files

#### Step 3: Build the prompt package

The backend should construct a versioned prompt package containing:

- company identity and internal-use context
- company GST and BAS configuration relevant to classification
- active chart of accounts with compact structured metadata
- active tax codes with BAS labels and GST treatment metadata
- active reporting categories
- any selected accounting period context
- file metadata and document attachments for the multimodal provider
- optional extracted text where available
- the operator’s optional descriptive note
- a strict JSON response schema for the recommendation

#### Step 4: Call the multimodal provider

The backend should call a provider adapter that supports multimodal prompts, such as ChatGPT, Gemini, or another configured provider.

The provider should return structured data only, not narrative prose as the primary contract.

#### Step 5: Normalize and validate the result

The backend should convert the raw model response into an internal normalized recommendation model.

That normalized result should include:

- extracted transaction date
- extracted vendor or counterparty name
- extracted document totals and currency
- recommended journal description and reference
- recommended debit and credit lines
- recommended use of existing account ids or account codes
- recommended use of existing tax code ids or tax code codes
- recommended use of existing reporting categories where relevant
- proposed new reference data when no existing option is suitable
- confidence signals or warning flags
- ambiguity notes where the model could not determine a safe answer

The backend must then validate that the proposed journal is balanced and that any referenced existing entities actually belong to the company.

#### Step 6: Present the recommendation to the user

The frontend should show a review screen that separates:

- uploaded files
- optional user note
- extracted document facts
- recommended journal lines
- proposed reference data additions
- model warnings and uncertainty

The user should be able to:

- edit the journal fields before saving
- map a proposed new reference item to an existing one instead
- reject individual proposed reference items
- accept selected proposed reference items for explicit creation
- create a draft journal from the reviewed recommendation

#### Step 7: Create a draft journal and attach evidence

When the operator confirms the recommendation, the backend should:

- create a draft journal entry only
- attach all uploaded files to that journal as evidence
- optionally create explicitly approved reference data first if the user chose to accept it
- record audit events for the recommendation outcome and any created records

Posting the journal should remain a separate existing workflow step.

### Proposed backend architecture

This feature should be implemented as a dedicated domain module rather than scattered across the existing document and ledger routers.

Recommended module shape:

```text
api/app/document_journal_ai/
  router.py
  service.py
  prompts.py
  providers/
    base.py
    openai_adapter.py
    gemini_adapter.py
  schemas.py
  normalization.py
  reference_context.py
```

#### Responsibilities by layer

`router.py`

- create recommendation sessions
- upload or reference documents for the session
- trigger analysis
- fetch recommendation results
- accept reviewed recommendations into draft journals

`service.py`

- orchestration logic
- document-to-prompt packaging
- provider invocation
- normalization and validation
- creation of draft journals and approved reference data

`prompts.py`

- engineered system prompts
- prompt templates and version identifiers
- output schema instructions

`providers/*`

- server-side vendor abstractions
- request and response translation
- retry, timeout, and error handling

`reference_context.py`

- compact serialization of accounts, tax codes, reporting categories, and configuration into prompt-ready structures

`normalization.py`

- convert model output into repository-owned typed structures
- reject malformed or incomplete model responses

### Proposed data model additions

The feature needs its own durable run and recommendation records. Reuse the existing `documents` table for file storage, but add dedicated analysis entities.

Recommended additions:

- `DocumentJournalRecommendationRun`
- `DocumentJournalRecommendationDocument`
- `DocumentJournalRecommendationResult`
- `DocumentJournalRecommendationLine`
- `DocumentJournalReferenceProposal`

#### Suggested run entity fields

`DocumentJournalRecommendationRun`

- company_id
- created_by_user_id
- status such as `draft`, `analyzing`, `review_ready`, `accepted`, `rejected`, `failed`
- optional target accounting_period_id
- optional existing journal_entry_id if augmenting a draft
- user_context_note
- prompt_version
- provider_name
- provider_model
- started_at
- completed_at
- failure_reason
- accepted_journal_entry_id

`DocumentJournalRecommendationDocument`

- recommendation_run_id
- document_id
- display_order

`DocumentJournalRecommendationResult`

- recommendation_run_id
- raw_provider_response_json
- normalized_summary_json
- confidence_summary
- warning_text

`DocumentJournalRecommendationLine`

- recommendation_run_id
- line_number
- suggested_account_id nullable
- suggested_account_code nullable
- suggested_tax_code_id nullable
- suggested_reporting_category_id nullable
- debit_amount
- credit_amount
- explanation

`DocumentJournalReferenceProposal`

- recommendation_run_id
- proposal_type such as `account`, `tax_code`, `reporting_category`
- suggested_code
- suggested_name
- suggested_attributes_json
- rationale
- status such as `proposed`, `accepted`, `rejected`, `created`

The first version should keep proposals limited to the current reference-data surface already used in this repository:

- accounts
- tax codes
- reporting categories

### Reference-data strategy for the prompt

The user specifically wants existing reference data attached to the prompt and shared with the model. That should be done carefully so prompts stay useful and deterministic.

#### Prompt context should include

- active accounts with:
  - id
  - account_code
  - name
  - account_type
  - default_tax_code_code where present
  - allow_manual_posting
- active tax codes with:
  - id
  - code
  - name
  - rate
  - bas_label
  - input_output_type
- active reporting categories with:
  - id
  - code
  - name
  - category_type
- company GST registration and reporting basis

#### Prompt packing rules

To avoid token bloat and ambiguous output:

- use compact structured lists rather than narrative descriptions
- keep stable ids and codes in the prompt so the model can point to existing reference data deterministically
- prefer including all active tax codes and reporting categories because they are usually limited in count
- include all active accounts if the size remains manageable; if the chart grows materially later, add retrieval or ranking so the prompt includes the most relevant candidate accounts plus a fallback compact master list

#### Model instruction rule

The prompt should explicitly instruct the model:

- first try to use an existing reference item by id or code
- only propose a new reference item if no current option is suitable
- explain why the new item is needed
- never invent ids for existing records

### Prompt-engineering plan

The repository should treat prompt design as versioned application logic, not ad hoc string concatenation.

#### Prompt structure

Recommended sections:

1. System role and product boundary
   - internal bookkeeping support only
   - no lodgment claims
   - no final tax advice claims

2. Model task definition
   - analyze one transaction bundle that may include multiple supporting files
   - recommend a draft journal entry and any needed reference-data proposals

3. Company context
   - company name
   - GST status
   - BAS basis if relevant

4. Reference data context
   - active accounts
   - active tax codes
   - active reporting categories

5. User note
   - optional operator description of the transaction

6. Output contract
   - strict JSON object
   - no markdown
   - no natural-language paragraphs outside required fields

7. Guardrails
   - if uncertain, mark uncertainty explicitly
   - do not claim a posting is final
   - do not omit balancing requirements

#### Prompt output schema should require

- recommendation status
- summary
- extracted facts
- journal header recommendation
- journal line recommendations
- existing reference ids or codes used
- proposed new references
- warnings
- confidence notes

#### Prompt lifecycle requirements

- version every prompt template
- log prompt version on every run
- keep representative fixtures for regression tests
- separate vendor-specific payload formatting from vendor-neutral prompt content

### Provider abstraction plan

The repository should not bind the domain logic directly to one provider SDK.

#### Recommended provider contract

A provider interface should accept:

- prompt text or structured prompt parts
- attached document handles or bytes
- allowed mime types
- output schema definition

It should return:

- raw provider response
- normalized JSON payload
- provider metadata such as model name and token usage when available

#### Configuration requirements

Backend settings should support:

- provider enable or disable flags
- default provider selection
- API keys or credentials via environment variables only
- model name per provider
- request timeout
- maximum file count and maximum file size per run
- maximum page or image conversion limits

This keeps the feature safe for internal deployment and vendor swapping.

### File and multimodal handling plan

The model call must work with multiple uploaded files tied to one recommendation run.

#### First-version supported file classes

- PDF invoices and receipts
- image files such as PNG, JPG, JPEG, WEBP where supported by the provider

#### Normalization behavior

- store the original file in existing document storage
- preserve original media type and checksum
- if a provider needs a different representation, create transient converted payloads rather than replacing the stored original
- where useful, extract text from PDFs locally as supplementary context, but keep the original file available to the multimodal model

#### Multi-file rule

The prompt should clearly state that all attached documents relate to one transaction bundle and should be analyzed together, not as unrelated entries.

### Frontend workflow plan

The feature should live primarily in the Bookkeeping area because its output is a journal draft.

#### Recommended UI entry points

- `Bookkeeping > Journals` action such as `Create draft from invoice or receipt`
- optional reuse path from the document list to `Analyze as journal draft`

#### Recommended frontend flow

1. Open new recommendation drawer or page
2. Upload one or more files
3. Enter optional descriptive text note
4. Optionally choose accounting period
5. Submit for analysis
6. Show `analyzing` state and provider failure handling
7. Render structured review page when ready
8. Allow edits, mapping changes, and explicit acceptance of any proposed new reference data
9. Save reviewed result as a draft journal and attach all files as evidence

#### UI requirements

- multi-file upload control
- note textarea for operator context
- visible list of attached files
- review-safe labels such as `model recommendation` and `needs review`
- clear distinction between existing matched reference data and proposed new reference data
- explicit `Create draft journal` action
- no `Post journal` action on the recommendation screen itself

### API surface plan

Recommended new routes under a dedicated prefix such as:

```text
/api/companies/{company_id}/journal-recommendations
/api/companies/{company_id}/journal-recommendations/{run_id}
/api/companies/{company_id}/journal-recommendations/{run_id}/analyze
/api/companies/{company_id}/journal-recommendations/{run_id}/documents
/api/companies/{company_id}/journal-recommendations/{run_id}/accept
/api/companies/{company_id}/journal-recommendations/{run_id}/reject
```

The `accept` endpoint should create only a draft journal plus evidence links and any explicitly approved reference-data additions.

### Reference-data creation policy

The user asked for the model to decide whether to use existing reference data or recommend adding another reference item.

That should be implemented as a proposal workflow, not direct creation.

#### First-version policy

- the model may propose new accounts, tax codes, or reporting categories
- the backend stores those proposals as recommendations only
- the frontend lets the operator accept or reject each proposal
- accepted proposals should be created through controlled backend logic that reuses current validation rules and audit logging

This keeps the feature aligned with the repository’s auditability and no-silent-change rules.

### Audit and traceability plan

The following actions should create audit events:

- recommendation run created
- analysis request sent
- analysis completed
- analysis failed
- recommendation accepted into draft journal
- recommendation rejected
- proposed reference data accepted and created

Audit metadata should include where practical:

- provider name and model
- prompt version
- attached document ids
- created journal id
- accepted proposal ids
- operator note presence

The system should retain enough history to explain how a draft was suggested, without requiring the operator to trust an opaque model result.

### Security and privacy plan

This feature sends potentially sensitive accounting documents to an external model provider, so it requires explicit guardrails.

Required controls:

- provider calls must happen server-side only
- credentials must never be exposed to the browser
- provider use must be configurable and disableable by environment
- document sharing should be limited to files explicitly uploaded for the run
- prompt context should be restricted to the active company’s relevant reference data only
- logs must avoid dumping raw document contents or full prompts into plain request logs by default
- raw provider payload retention should be configurable, with conservative defaults

If later business rules require stricter data residency or vendor limitations, the provider abstraction should allow narrowing to approved providers without changing the domain workflow.

### Validation and fallback behavior

The system should not fail open.

#### Backend validation requirements

- reject unsupported file types
- reject too many files or too-large files
- reject malformed provider output
- reject unbalanced recommended journals
- reject references to nonexistent company data

#### Fallback UX requirements

- if the provider call fails, keep the uploaded files and run record so the user can retry
- if the model returns an incomplete recommendation, show partial extracted facts plus explicit warnings instead of silently fabricating the missing pieces
- if no safe recommendation can be made, allow the user to keep the uploaded files and continue with manual journal entry

### Testing strategy for this feature

#### Unit tests

- prompt context packing
- prompt version selection
- normalization of provider output into internal structures
- validation of balanced suggested journals
- reference-data proposal parsing and acceptance rules

#### Integration tests

- recommendation run creation with multiple files
- provider adapter stub returning a valid structured recommendation
- provider adapter stub returning malformed output
- accept flow creating a draft journal and linking all documents
- accept flow with approved new account proposal creation
- rejection flow preserving documents but not creating a journal

#### Frontend tests

- multi-file upload and note entry
- analyzing state and retry state
- review screen rendering of suggested lines and warnings
- accept flow creating a draft journal
- evidence visibility on the created draft journal

### Delivery sequence recommendation

#### Stage 1: Backend foundation

- add recommendation-run data model and migrations
- add provider abstraction and prompt module skeleton
- add stub provider for local development and tests

#### Stage 2: Analysis orchestration

- build prompt context serialization from existing accounts, tax codes, reporting categories, and company configuration
- implement provider call and normalization pipeline
- expose create, analyze, fetch, accept, and reject routes

#### Stage 3: Frontend review workflow

- add Bookkeeping entry point for document-to-journal recommendation
- add multi-file upload and user note UI
- add analyzing and result screens

#### Stage 4: Draft journal acceptance

- create reviewed draft journal from recommendation
- link all uploaded documents to the draft journal
- keep posting as a separate existing action

#### Stage 5: Reference-data proposal workflow

- allow explicit acceptance or rejection of proposed accounts, tax codes, and reporting categories
- ensure proposal acceptance uses normal backend validation and audit rules

#### Stage 6: Hardening

- add audit coverage
- add failure and retry handling
- add provider configuration docs
- add regression coverage for prompt versions and structured output parsing

### Definition of done for this feature

This feature is not complete until all of the following are true:

1. A user can upload multiple invoice or receipt files for one recommendation run.
2. A user can add optional descriptive text that is included in the model prompt.
3. The backend sends a versioned engineered prompt plus company reference data to a server-side multimodal provider adapter.
4. The model output is normalized into a structured recommendation rather than free-form prose.
5. Existing company reference data can be selected by the recommendation, and proposed new reference data is surfaced as explicit proposals rather than silently created.
6. A reviewed recommendation can create only a draft journal, not a posted journal.
7. All uploaded files are linked to the resulting journal as evidence.
8. Audit events, provider metadata, and prompt versioning are retained for traceability.
9. Failure states, malformed output, and unsupported files are handled clearly.
10. The entire workflow remains inside the repository’s internal-use, review-first, and no-automatic-lodgment boundary.

### Recommended first implementation step after this plan update

Start with a backend-only vertical slice:

- add recommendation-run tables and migrations
- implement a provider-agnostic prompt and normalization contract
- wire a stubbed multimodal provider that returns strict JSON
- expose create, analyze, fetch, and accept endpoints

That slice should create a reviewed draft journal and attach uploaded documents before any real external LLM provider is introduced.

---

# AI Journal Drafting Cost Reduction Plan

## Scope

This plan covers the next cost-reduction pass for the AI document-to-journal workflow.

Chosen measures for this stage:

1. Use OpenAI prompt caching properly.
2. Remove low-value fields from account context.

The goal is to lower effective input-token cost without weakening the system boundary:

- internal Australian bookkeeping support only
- review-ready draft journal recommendations only
- no ATO lodgment
- no automatic posting
- no accountant replacement claims

## Current State

The AI journal drafting flow is implemented in `api/app/journal_recommendations/service.py`.

The active OpenAI request path is:

1. `analyze_run(...)`
2. `_analyze_with_openai(...)`
3. `_build_reference_context(...)`
4. `_build_cached_reference_prefix(...)`
5. `_build_recommendation_request_suffix(...)`
6. `client.responses.parse(...)`

The expanded company reference-data pack now includes:

- 676 chart-of-account rows
- 35 tax-code rows
- 82 reporting-category rows

The current pricing estimate assumes approximately:

- 22,000 uncached text input tokens per recommendation run after compacting account context
- 1,200 output tokens per recommendation run

The main cost driver remains the repeated reference context, especially the full account list, but repeated runs for unchanged company reference data now pass a deterministic prompt cache key.

## OpenAI Prompt Caching Plan

### Objective

Maximize cache hits for repeated prompt prefixes by making the large, stable part of the prompt identical across journal recommendation runs for the same company reference-data version.

OpenAI prompt caching works best when long repeated content appears at the beginning of the prompt and variable content appears later. The implementation should therefore separate:

- stable prefix: system instructions, output contract, company configuration, active reference data
- variable suffix: operator note, selected accounting period, document metadata, attached file contents

### Implementation Steps

1. Split prompt construction into explicit stable and variable parts.

   Proposed functions:

   ```python
   def _build_cached_reference_prefix(...)
   def _build_recommendation_request_suffix(...)
   def _build_prompt_cache_key(...)
   ```

   The current `_build_user_text(...)` can then combine:

   ```text
   stable_reference_prefix + variable_request_suffix
   ```

2. Put stable content first in the request input.

   Preferred shape:

   ```python
   content_items = [
       {"type": "input_text", "text": stable_reference_prefix},
       {"type": "input_text", "text": variable_request_suffix},
       ...document_content_items,
   ]
   ```

   This keeps the large repeated reference-data section at the front of the prompt.

3. Add a deterministic prompt cache key.

   Proposed key shape:

   ```text
   jr:{company_prompt_hash}:{reference_context_hash_prefix}
   ```

   The key must stay within OpenAI's 64-character `prompt_cache_key` limit. The `company_prompt_hash` should be derived from the company id and prompt version, and the `reference_context_hash` should be based on the exact stable prefix text or the normalized reference-context JSON. If accounts, tax codes, reporting categories, company configuration, or prompt version change, the key changes.

4. Pass prompt-cache options to `client.responses.parse(...)`.

   Proposed request parameters, subject to SDK support:

   ```python
   prompt_cache_key=cache_key
   ```

   Optional follow-up:

   ```python
   prompt_cache_retention="24h"
   ```

   The first implementation should prefer safe in-memory caching unless the selected model supports extended retention and the project accepts the data-retention tradeoff.

5. Preserve auditability without storing sensitive prompt text in plain logs.

   Store or expose only:

   - prompt version
   - reference-context hash
   - provider model
   - usage metrics returned by OpenAI
   - cached token counts where available

6. Capture cache effectiveness from response usage.

   Extend existing provider usage persistence to preserve:

   - input token count
   - cached input token count if present
   - output token count
   - total token count

   This allows the UI estimate to be checked against actual usage after several runs.

### Acceptance Criteria

- The large repeated reference context appears before run-specific note and document data.
- OpenAI requests include a deterministic cache key when supported.
- Prompt cache behavior does not change recommendation semantics.
- Provider usage JSON keeps cached-token details when returned.
- A regression test verifies that identical company reference data produces the same cache key and changed reference data produces a different cache key.

## Remove Low-Value Account Context Fields

### Objective

Reduce input tokens sent for each account row while preserving the fields the model needs to choose appropriate existing accounts.

### Current Account Context

Current account prompt entries include:

```json
{
  "account_code": "...",
  "name": "...",
  "account_type": "...",
  "default_tax_code_id": "...",
  "allow_manual_posting": true
}
```

The low-value field is:

- `default_tax_code_id`

Reason:

- It is a UUID.
- The model is instructed to use tax-code codes, not IDs.
- UUIDs consume tokens and do not help accounting classification.
- They are not stable across companies.

### Target Account Context

Replace `default_tax_code_id` with a compact code field:

```json
{
  "code": "1021",
  "name": "Main Business Transaction Account",
  "type": "asset",
  "tax": "NO_TAX",
  "posting": true
}
```

Recommended field changes:

- `account_code` -> `code`
- `account_type` -> `type`
- `default_tax_code_id` -> `tax`
- `allow_manual_posting` -> `posting`

Keep `name`, because account names are essential for model selection.

Do not remove `posting`. The model should avoid non-posting/header accounts.

### Implementation Steps

1. Update `_build_reference_context(...)`.

   Join or map each account's `default_tax_code_id` to the corresponding `TaxCode.code`.

   Output compact account objects:

   ```python
   {
       "code": account.account_code,
       "name": account.name,
       "type": str(account.account_type),
       "tax": tax_code_by_id.get(account.default_tax_code_id),
       "posting": account.allow_manual_posting,
   }
   ```

2. Update prompt instructions.

   Replace references to `account_code` in the account context with the new compact field name, while preserving the model output contract:

   - context field: `accounts[].code`
   - response field: `lines[].account_code`

   This keeps backend persistence stable.

3. Keep output schema unchanged.

   The model should still return:

   ```json
   "account_code": "..."
   ```

   This avoids database and UI churn.

4. Recalculate token and cost estimates after slimming.

   Run the same compact prompt-size smoke check used for the previous estimate and update:

   - `PRICE_ESTIMATE_INPUT_TOKENS`
   - `PRICE_ESTIMATE_NOTE`
   - model estimate regression expectations

### Acceptance Criteria

- Prompt account context no longer contains account UUIDs or tax-code UUIDs.
- Prompt account context contains default tax-code codes where available.
- Model output schema remains unchanged.
- Existing recommendation persistence still resolves returned account codes against company accounts.
- Cost estimate is recalculated after implementation.

## Testing Plan

Backend focused tests:

- prompt reference context includes compact account fields
- prompt reference context excludes `default_tax_code_id`
- default tax-code IDs are converted to tax-code codes
- prompt cache key is stable for unchanged reference data
- prompt cache key changes when account data changes
- journal recommendation analysis still accepts valid provider output

Operational smoke checks:

- Create a fresh company and confirm expanded reference data is seeded.
- Trigger AI journal recommendation analysis.
- Confirm request succeeds with the existing OpenAI Responses integration.
- Inspect persisted provider usage JSON for cached-token fields when returned.

## Risks and Constraints

- Prompt caching is best-effort and depends on exact prefix matching.
- Any change to reference data, prompt version, or prefix formatting can reduce cache hits.
- Extended prompt-cache retention may have data-retention implications and should not be enabled without explicit review.
- PDF and image inputs may still dominate cost for large documents because file inputs can add extracted text and page/image tokens.
- Removing too much context may increase proposal rates or reduce account-selection quality, so this stage removes UUID-like low-value fields only.

## Expected Outcome

This stage should reduce effective cost in two ways:

1. Cached repeated input tokens should become cheaper on repeated runs for the same company reference-data pack.
2. The uncached prompt should shrink by removing UUID-like account context and using shorter field names.

The implementation should preserve the current review-first behavior and should not add automatic posting, lodgment, or tax-advice behavior.

## Implementation Status

Completed in the backend journal recommendation service:

- stable company, configuration, and reference-data content is now built by `_build_cached_reference_prefix(...)` and sent before the run-specific request suffix and file inputs
- OpenAI Responses calls now include a deterministic short `prompt_cache_key` within OpenAI's 64-character limit, `prompt_cache_retention="in_memory"`, and metadata with the full reference-context hash
- account context is now compact (`code`, `name`, `type`, `tax`, `posting`) and no longer sends account or tax-code UUIDs in the prompt
- the model output schema remains unchanged, so returned `lines[].account_code` values still resolve through the existing ledger validation and draft-journal creation path
- the displayed text-token estimate has been recalculated from the compact expanded reference payload to approximately 22,000 uncached input tokens plus 1,200 output tokens per call

Validation added:

- compact account context regression coverage
- stable and changed prompt-cache-key regression coverage
- prompt-cache-key length regression coverage for OpenAI's 64-character limit
- OpenAI request construction coverage for stable prefix ordering, cache options, metadata, and one unbalanced-result retry
- focused journal recommendation accept/proposal/runtime-failure regression coverage against the expanded seeded chart

