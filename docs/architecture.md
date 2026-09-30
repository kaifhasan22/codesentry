# Architecture and technical decisions

CodeSentry is a Python-source review application. Its current local runtime is a React/Vite frontend and a Docker Compose backend containing FastAPI, PostgreSQL, Redis and Celery. The [root README](../README.md) provides the system diagram, setup and API overview. This document describes the implementation, not a proposed production architecture.

## Request and worker lifecycle

1. Registration stores an Argon2 password hash and returns an HS256 JWT. Login accepts OAuth2 form fields. Protected API dependencies require a bounded token, expiration and a positive subject within the database ID range; all scan/history/comparison queries are owner-scoped.
2. `POST /api/scans` validates the raw URL before normalizing it. It persists a Repo and queued Scan, then publishes only the scan ID to Redis. A PostgreSQL owner-row lock serializes the per-user active-scan check. The default allowance is two queued/running scans. Publication failure persists a terminal failure and returns 503.
3. Celery atomically changes `queued` to `running`; duplicate/terminal deliveries skip execution. One new Repo row is currently created per submission, so repository identity for comparison must span multiple rows.
4. A trusted Git supervisor prepares a shallow clone. Git has no inherited credentials/global configuration, disabled hooks/prompts/redirects and HTTPS-only transport. Submodules and LFS are not fetched. Repository code, setup hooks and tests are never executed.
5. Safe inventory selects `.py` files under exclusions and size/count limits. Source reads open each path component relative to the root without following symlinks, reject non-regular files and bound the read. The shared inventory goes to four concurrent analyzer threads; Vulture scans the whole eligible source set once.
6. Findings are deterministically deduplicated and assigned comparison keys. The task requests optional bounded AI advice, then finalization calculates the health score solely from analyzer findings and persists the original analyzer severity/fix plus explicitly labeled AI text.
7. The API returns recorded fields and derives priority/Top Issues/hotspots on read. It computes comparison when requested. Temporary checkouts are cleaned on success and failure.

### Status, stages and estimates

Lifecycle: `queued → running → completed`, with `failed` available after queueing, preparation, resource, analysis/task or persistence failures. Active stages are `repository_preparation`, `static_analysis`, `ai_review` and `finalization`; terminal stages are `complete` and `failed`.

The worker stores broad remaining-time ranges once workload is known. Estimates scale with Python file count/source bytes and capped AI batches. The frontend presents approximate windows, not a countdown or a completion guarantee. Queueing/preparation can have unknown estimates. New Scan polls every 2.5 seconds, scan detail every 4 seconds and active history every 5 seconds; short stages may not be visible between polls.

Soft failures propagate into persisted terminal status; parent-side failure hooks handle hard task termination/worker loss. Owner-scoped API reads expire running rows older than 330 seconds and queued rows older than 15 minutes. Estimates are cleared on failure. Recovery independent of polling and whole-host orphan cleanup remain operational work.

## Deterministic analysis and reporting

| Layer | Grounded inputs / behavior |
| --- | --- |
| Complexity | Radon callable cyclomatic complexity: ≥15 medium, ≥20 high; class aggregates omitted |
| Security | Custom AST rules for non-literal eval/exec, unsafe deserialization and credential-like literals; import aliases/shadowing and obvious benign cases reduce noise |
| Dead code | Vulture candidates with ≥90% heuristic confidence; re-exports and trusted whitelist source omitted; unreachable statements medium, other candidates low |
| Style | More than six positional parameters; excludes implicit receivers/keyword-only options; low severity |
| Deduplication | Category/rule/file/line/column fingerprint, independent of message formatting; highest severity with stable tie-breaking |
| Score | Health policy v2, nested severity thresholds and bounded diminishing penalties, based on unique analyzer findings |
| Priority | Policy v1: severity points plus security/complexity/confidence bonuses and test/example path adjustment; P1–P4 plus explicit reasons |
| Hotspots | Critical/high/medium weighted 16/8/3, ×1.5 for security; low/info contributions capped per file |

Score counts findings at each threshold or higher. Each contributes `c × (1 − (1 − w/c)^n)` with incremental `(w,c)` of info `(1,3)`, low `(1,7)`, medium `(3,15)`, high `(5,35)`, critical `(8,40)`. Round the summed penalty half-up, subtract from 100 and clamp. No findings yields 100; low-only findings cannot lower the score below 90. This is a review heuristic, not a probability of vulnerability or reliability. Historical scores are not silently recalculated.

Priority starts at critical/high/medium/low/info = 70/45/25/8/0, adds security +15, measured complexity ≥20 +5 or ≥30 +10, confidence ≥90 +4 or 100 +8, and subtracts 8 for test/example/documentation paths. Clamp to 0–100; thresholds 75/50/25 determine P1/P2/P3, otherwise P4. Top Issues returns five deterministic IDs; the compact UI initially displays three. Exact formulas and evidence caveats are in [analysis quality](analysis-quality.md) and [report features](product-features.md).

Bandit, Pylint and GitPython are declared Python dependencies, but the active pipeline uses custom AST security/style checks and subprocess Git. Their presence does not imply those tools' complete rule sets run. Dependency pruning is deferred during the freeze.

## AI boundary and fallback

The reasoner uses Anthropic structured output and bounded JSON containing only selected findings/context. Default selection is severity-first, not the separate report priority score: up to 24 findings, eight per batch, at most three requests, 15 seconds/request, no SDK retries and bounded output tokens/text.

Repository text is untrusted data. The model has no tools or environment access and receives explicit system instructions to explain supplied findings. Response validation accepts only supplied fingerprints, unique reviews and confidence ≥0.7; invalid/provider/client failures retain analyzer results. Secret-redaction heuristics cover input/output and recognized source literals, but cannot establish perfect secrecy or prompt-injection resistance.

AI text can append an advisory explanation, possible-false-positive opinion and suggested fix. It cannot add/remove deterministic findings, overwrite persisted analyzer severity, calculate score/priority/hotspots, choose comparison state or authorize access. Missing `ANTHROPIC_API_KEY` disables enrichment. Successful live-provider operation and model availability still require the owner's validation.

## Comparison identities

Within-scan fingerprints serve deduplication. Cross-scan `comparison_key` uses file/category/rule, enclosing class/function scope, a position-free AST anchor and occurrence order. Complexity/style key the callable; security and many dead-code rules use statement semantics. This tolerates line shifts, whitespace/comments and message/severity/AI wording changes. Moves, renames or changed semantics can legitimately appear new/resolved.

Repository identity is lowercased GitHub owner/name, normalizing `www`, optional `.git` and trailing slash. For the authorized owner, select the latest earlier completed scan ordered by `(created_at, id)` submission order. Other repositories/users and failed/active/later scans are excluded. GitHub numeric repository IDs, renames/transfers and explicit branch history are not modeled.

Match identities as multisets, preserving repeated occurrences. Return new/current and unchanged/current IDs plus resolved baseline issue details. Score delta is current minus baseline; zero is valid, missing score produces null. “Unchanged” means identity matched; “resolved” means no longer detected, which may also reflect rule/coverage changes. Old/differently versioned reports use category/file/line/normalized-title fallback with warnings. [Detailed matching limitations](product-features.md#4-comparison-and-identity).

## Resource envelope

| Boundary | Current limit |
| --- | --- |
| Git preparation | 120 seconds total |
| Checkout | 512 MiB, 50,000 entries; periodically monitored |
| Python source | 5,000 files; 1,000,000 bytes/file; 100,000,000 bytes total |
| Directory traversal | 20,000 directories |
| Finding growth | 50,000 per analyzer and 50,000 combined before report processing |
| Celery task | 270-second soft / 300-second hard deadline |
| AI | 24 findings, 3 batches, 15-second requests, no retries |
| API requests | 64 KiB bodies; 20 auth POSTs/minute/socket IP/API process |
| History | Default/max page 500; offset up to 1,000,000 |

Source inventory limits can yield partial coverage; checkout/finding/time limits can fail the scan. Analyzer exceptions are logged and isolated except resource/soft-limit failures. Threads cannot be individually forcibly stopped; Celery is the final task bound. Two prefork worker processes each start up to four analyzer threads, so production CPU/memory sizing must consider their combined workload. Prefetch is one, results are ignored, only JSON is accepted, worker children recycle after 20 tasks, and lost-worker automatic requeue loops are disabled.

## Persistence and migrations

`User → Repo → Scan → Issue` records live in PostgreSQL under Compose; source checkouts are temporary and not the persistent report store. Named `postgres_data` retains the database; shared `scan_work` makes task workspaces available to API recovery and the worker. Redis transports work IDs; application reads always use the database.

Startup creates missing tables and adds missing report/progress columns. Report additions are `scans.analysis_version/source_commit` and `issues.comparison_key/analyzer_metadata`; progress additions are stage and estimate fields. Existing reports/scores/fingerprints are preserved without inferred evidence backfill. Scan/user ID validation matches current PostgreSQL INTEGER columns. Release-candidate fixes added no new columns.

For an existing installation: back up data, drain active work, build/start one updated API, allow startup migrations to finish, then start updated workers. ALTER TABLE rights are required. Sequential idempotence is tested; concurrent schema migration is not a supported release procedure. The [release report](release-candidate-report.md) verifies actual PostgreSQL restart persistence and comparisons.

## Configuration and local runtime

The root `.env` is read by Compose for interpolation. Native Python settings read `.env` from their process working directory. These are different configuration paths.

| Setting | Behavior in the committed Compose file |
| --- | --- |
| `JWT_SECRET` | Forwarded to API and worker; set a shared random value ≥32 characters |
| `ENVIRONMENT` | Forwarded; defaults to development; production rejects weak secrets and HTTP CORS |
| `CORS_ORIGINS` | Forwarded; defaults to `http://localhost:5173`; explicit origins only |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Forwarded; key blank disables AI; verify model availability before enabling |
| `DATABASE_URL` / `REDIS_URL` | Hard-coded to the Compose PostgreSQL/Redis services; root `.env` values do not replace them |
| `SCAN_ROOT` | Default `/tmp/codesentry`, mounted in both services; custom root `.env` values are not forwarded |
| `ALLOWED_GITHUB_HOSTS` | Hard-coded to GitHub/www; cannot expand the raw validator to arbitrary hosts |
| `ACCESS_TOKEN_MINUTES` | Code default 60; not forwarded by the current Compose file |
| `MAX_ACTIVE_SCANS_PER_USER` | Code default 2; not forwarded by current Compose |
| `WORKER_QUEUE` | Code default `celery`; not forwarded by current Compose |
| `VITE_API_URL` | Frontend-only: ignored `frontend/.env.local`, default `http://localhost:8000`; public build-time value |

For native development, API and worker must share exported configuration and an absolute database URL; starting the legacy Makefile API/worker targets from different working directories with relative SQLite/default `.env` settings can point at different databases. The documented Compose path avoids that ambiguity. Native Python/filesystem safeguards require a Unix-like environment; the Docker path supplies it on supported hosts.

Vite is separate from Compose. The README binds the dev server explicitly to loopback; the repository's Vite default otherwise uses `host: true`. Compose publishes its services only on loopback. Use the exact configured frontend origin for CORS. The generated production frontend requires an intended `VITE_API_URL` at build time and hosting with SPA fallback for `/dashboard`, `/scans` and report URLs; no hosting configuration or deployed URL is included.

## Verification harnesses

`backend/scripts/benchmark_analysis.py` uses fresh public clones and isolated SQLite, with real analyzers/persistence and AI disabled. `verify_product_features.py` refuses a populated SQLite database and checks comparison/filter behavior including a labeled local source variation. They invoke tasks directly and do not prove broker delivery or real Celery deadlines.

The backend image copies `app/` and `tests/`, not `scripts/`. Run these harnesses from `backend` with local Python 3.12/dependencies installed, as documented in the dated [analysis report](analysis-quality.md#verification-and-reproducible-benchmark), or explicitly mount the trusted scripts into a disposable test image/container. Do not point harnesses at the application database or an active scan workspace.

Latest full-system evidence: [93 backend / 7 frontend tests and PostgreSQL E2E](release-candidate-report.md). Remaining public-deployment work is detailed in the [security report](security-hardening.md#6-production-only-recommendationsdeferred-work).
