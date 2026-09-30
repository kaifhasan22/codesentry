# CodeSentry final security review — 2026-09-30

This is the security-pass snapshot (**91 tests**, SQLite E2E). The subsequent
[release-candidate pass](release-candidate-report.md) verified **93 backend / 7 frontend tests**,
actual PostgreSQL E2E/persistence, provider-unavailable fallback and worker loss.
It also tightened scan-ID/JWT-subject bounds to PostgreSQL's signed 32-bit INTEGER
range. Current local setup and configuration are in the [README](../README.md).

Scope: authentication, scan creation, Git preparation, source traversal, all four
analyzers, AI enrichment, persistence, history/detail/comparison responses, worker
failure recovery, configuration and frontend error rendering. Product features
and visual design are frozen. This is an application audit and regression pass,
not a penetration-test certification or a guarantee against all hostile input.
Existing unrelated working-tree changes were preserved. Nothing was committed or
pushed. Existing user API/worker containers were not replaced; activation requires
rebuilding/restarting them with the updated configuration.

## 1. Vulnerabilities/problems discovered

- **File disclosure through symlinks:** inventory followed Python file symlinks
  with `stat`, and analyzers subsequently read them. Source from outside the
  checkout could enter snippets and AI input. FIFOs could also block reads.
- **URL normalization before validation:** Pydantic `HttpUrl` could normalize a
  raw input before the repository validator saw it, including default ports or
  host encodings. The regex used an end anchor that could accept a final newline.
- **Git trusted the worker environment:** inherited environment/global Git
  configuration could enable credentials, proxies, filters, helpers or hooks.
  Preparation had a deadline but no explicit whole-checkout disk/entry budget.
- **Error disclosure:** raw clone stderr and arbitrary exception messages were
  stored as scan errors and returned to users. Standard validation errors could
  echo submitted input, including passwords. Historical errors remained exposed.
- **Authentication weaknesses:** shared development JWT defaults, expiration not
  required on decoded tokens, insufficient subject bounds, and malformed hashes
  capable of causing a server error. There was no local authentication throttle.
- **Resource and lifecycle gaps:** unlimited default history, no per-owner active
  scan limit, missing queued-job expiry, duplicate delivery/retry risks, and no
  cleanup when forced task termination bypassed the task's `finally` block.
  Read-triggered stale recovery also updated other owners' scans.
- **Unauthenticated WebSocket placeholder:** it held connections open without
  authentication, although it did not return actual scan data.
- **AI data hygiene:** credential redaction was confined mainly to security
  findings; overlapping complexity/style snippets could still contain literals.
- **Local exposure:** Compose published Redis, PostgreSQL and the API on all
  host interfaces. Environment variant files and private-key files were not
  comprehensively ignored.

## 2. Fixes implemented

### Repository and filesystem

Raw strings must fully match an ASCII GitHub HTTPS owner/repository URL before
normalization. Reject userinfo, explicit ports (including 443), percent encodings,
control characters, whitespace, query/fragment components, backslashes, unsupported
schemes, lookalike hosts, dot traversal and argument-like names. Accepted `www`
URLs and `.git` suffixes are canonicalized for cloning. Host configuration cannot
expand acceptance beyond `github.com` and `www.github.com`.

Git runs without a shell or inherited credentials/configuration. Its environment
has a fixed executable search path, private HOME, disabled prompting/system/global
Git configuration, HTTPS-only protocol access and disabled HTTP redirects. Hooks
are disabled; no submodules or LFS are fetched, and configured smudge filters are
not loaded. A separate checkout uses `core.symlinks=false`, so tracked symlinks
are ordinary link-text files, never filesystem links. Repositories are never
installed, imported, tested or executed by the scanner. These choices follow
Git's [configuration controls](https://git-scm.com/docs/git-config).

A trusted isolated Python supervisor preserves the **120-second total preparation
budget**, monitors **512 MiB / 50,000 checkout entries**, and kills the Git process
group on timeout/resource failure. It detects loss of its task parent and removes
the orphan checkout. A real-clone test found a temporary-file rename race in this
monitor; that was fixed and covered by a regression test. Monitoring is periodic,
not a filesystem quota: short-lived overshoot remains possible.

Inventory excludes symlinks and non-regular files. Source readers open each
component relative to the trusted root with `O_NOFOLLOW`, reject traversal,
check the opened inode, and perform bounded reads. Vulture now receives safely
read text and loads its trusted bundled whitelist once; full-repository context
is preserved. Fingerprint generation uses the same safe reader.

### Authentication, ownership and API

JWT validation requires `exp` and `sub`, pins HS256, bounds token and subject
sizes, and rejects nonexistent users. Production requires an explicit secret of
at least 32 characters; blank/known weak development secrets become random
process-local keys. Existing Argon2 password hashing remains. Login checks unknown
users against a dummy hash, rejects oversized passwords and malformed hashes, and
registration races return the existing conflict response. Expiration must be
explicitly required because the library's default is optional; see
[python-jose claim validation](https://github.com/mpdavis/python-jose/blob/master/jose/jwt.py).

Existing owner checks remain on history, detail and comparison. Stale recovery is
now owner-scoped. IDs are positive bounded integers. Default history is capped at
500 rows, retaining the existing page shape and total count. Request bodies are
capped at 64 KiB before parsing; authentication POSTs are limited to 20 per minute
per observed client IP per process. Forwarded IP headers are not blindly trusted.

Errors use fixed public messages; legacy stored errors are sanitized on read.
Validation omits input/exception details, and internal exceptions return a generic
500. The frontend safely handles structured validation responses without changing
its layout. The unused WebSocket placeholder rejects connections; authenticated
HTTP polling continues to provide progress.

### Worker, AI and configuration

A transactional claim accepts only queued scans. Terminal/duplicate deliveries do
not rerun or duplicate findings. Automatic timeout retries and lost-worker requeue
loops are disabled, following Celery's warning about
[worker-loss message loops](https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-reject-on-worker-lost).
Failures persist a terminal stage, clear estimates and record a safe reason.
Owner-scoped polling expires queued scans after 15 minutes and running scans after
330 seconds. Hard-failure hooks and the task cleanup remove scan-owned workspaces.
Per-owner active scans default to two; PostgreSQL locks the owner row before
counting submissions. Celery accepts JSON only, does not retain task results,
prefetches one task and recycles each worker child after 20 tasks.

Known credential literals/token formats/private-key blocks are redacted across
all finding snippets and API text, with additional AI-output redaction. AI receives
bounded JSON data, an explicit untrusted-content instruction, no tools and no
access to the environment. Unknown fingerprints, duplicates, low-confidence
reviews and echoed system-prompt lines are discarded. AI output remains advisory
text only; severity, priority, score, hotspot/comparison calculations and ownership
never use it. Redaction and prompt instructions are defenses, not perfect secret
recognition or proof against misleading generated prose.

CORS uses explicit configurable origins, GET/POST/OPTIONS and explicit request
headers; cookie credentials are disabled because the app uses bearer tokens.
Production origins must be HTTPS. Security-limit responses retain CORS headers.
Compose defaults bind published services to localhost. Ignore rules cover `.env`
variants, private keys and database files; the example configuration contains no
working credentials.

## 3. Defenses already present

- Argon2 hashing; signed JWTs; parameterized SQLAlchemy queries; existing owner
  checks for history, detail and comparison.
- Shallow single-branch cloning, no shell invocation, no repository execution.
- Source exclusions and limits: **5,000 Python files**, **1 MB per file**,
  **100 MB aggregate source**, **20,000 directories**. These remain unchanged.
- Celery **270-second soft / 300-second hard limits**, worker failure hooks,
  progress stages and ETA reporting. Global time limits were not raised.
- Four deterministic analyzers, stable comparison identities, deterministic
  scoring/priorities/hotspots and AI fallback. Finding growth is now additionally
  stopped at 50,000 per analyzer and 50,000 combined before report processing.
- AI: at most **24 findings**, **3 batches**, **15-second request timeout**,
  no SDK retries, bounded output and confidence/fingerprint validation.
- React renders finding and AI strings as text; no raw HTML execution sink was
  found in the frontend source.

## 4. Tests performed and results

- Complete backend suite: **91 passed**. Two existing FastAPI startup-event
  deprecation warnings remain.
- Frontend production build: **passed**, 1,431 modules.
- Security regressions cover raw URL bypasses, environment isolation, clone
  timeout/resource cleanup, actual supervisor timeout and parent-loss behavior,
  symlinks/traversal/FIFOs/file replacement/size growth, real signed JWT ownership
  and expiry, malformed hashes, body/auth limits, production configuration,
  legacy and internal-error sanitization, CORS, invalid IDs, queued/stale recovery,
  duplicate delivery, soft/hard failure cleanup, active-job limits and nonexecution
  of repository setup/conftest/sitecustomize files.
- Existing analyzer, score, prioritization, comparison and AI fallback tests all
  remain passing. One Vulture test was adapted from file scavenging to its safe
  text API while retaining its single-pass assertion.

Fresh end-to-end verification used separate API, Redis and a real Celery prefork
worker, an isolated SQLite database, actual registration/JWT authentication and a
fresh network clone. No mocked queue or task execution was used. AI was disabled.

| Result | Requests | Inaccessible repository |
| --- | --- | --- |
| Terminal status | completed | failed |
| HTTP submission-to-result time | 5.43 s | 1.17 s |
| Findings / score | 25 / 68 | no report |
| Severity counts | high 2; medium 7; low 16; critical/info 0 | — |
| Categories | complexity 9; dead code 11; style 4; security 1 | — |
| Cross-owner detail/comparison | 404 | 404 |
| Anonymous detail | 401 | 401 |
| Temporary checkout after completion | removed | removed |

Requests commit: `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`. Analyzer times:
complexity **1.18 s**, security **1.17 s**, dead code **1.57 s**, style **1.18 s**.
Parallel static-analysis wall time was **1.94 s**, clone **2.87 s**, persistence
**0.02 s**, worker processing **4.89 s** before cleanup. Polling can skip stages
that complete between polls; worker logs confirmed AI/finalization transitions.
The result matches the earlier 25-finding, score-68 analysis-quality checkpoint.

[Recorded verification data](security-verification.json). Temporary verification
containers were stopped after evidence collection. No real credentials are in the
report/artifacts, and no commits or pushes were made.

## 5. Remaining risks

- Hostile parser workloads, native Git vulnerabilities and resource exhaustion
  require operating-system isolation. Periodic disk monitoring is not a hard
  quota; source limits can produce partial coverage. Analyzer errors/skipped
  malformed files can reduce coverage. Static findings are not proof of safety.
- Python analyzer threads cannot be individually forcibly terminated; the Celery
  task deadline remains the final runtime bound. Whole-host/container failure can
  leave files until recovery/maintenance. Stale status recovery requires polling;
  a queued job can remain in the broker until a worker consumes and skips it.
- The application throttle is local to one API process and uses socket IPs. It
  cannot provide distributed abuse protection; behind a proxy it can group users
  together. Multiple accounts/IPs can exhaust aggregate queue/storage capacity.
- Bearer tokens still live in browser localStorage, so an XSS/browser-extension
  compromise can steal them. There is no token revocation, MFA or refresh rotation.
  Registration still discloses duplicate emails to preserve existing behavior.
- Unknown secret formats and prompt injection may affect advisory AI text. No
  live provider request was made in this pass. AI output is never executable or
  authoritative. Repository snippets sent to the configured provider require the
  deployment's data-retention/privacy policy.
- This security-pass evidence used SQLite. The subsequent release-candidate pass
  verified actual PostgreSQL E2E and restart persistence; PostgreSQL concurrency
  and production multi-worker behavior were not load-tested. Real 270/300-second Celery termination was not waited out;
  failure hooks/soft failures and actual subprocess timeout/orphan cleanup were
  tested separately.
- No comprehensive dependency CVE scan or external penetration test was performed.
  Dependency ranges remain broad, and the current image still runs as root.

## 6. Production-only recommendations/deferred work

1. Set `ENVIRONMENT=production`, a randomly generated `JWT_SECRET` of at least
   32 characters and explicit HTTPS `CORS_ORIGINS`. Use the same secret across API
   processes, keep it in a secret manager, and rotate any previously deployed
   shared/default key. Changing the signing key invalidates existing sessions.
2. Rebuild API and worker images, drain active scans, then update services. This
   pass adds no database columns; retain the previously documented report-column
   migration order (updated API before workers). Default history is now bounded,
   explicit `:443` URL inputs are rejected, and the unused WebSocket is closed.
3. Put HTTPS, trusted-host validation, security headers/CSP, connection/request
   deadlines, header/body limits and distributed rate limits at the reverse proxy.
   Configure the real-client-IP chain deliberately, never trust arbitrary headers.
4. Run each scan in a non-root isolated worker/container with read-only runtime,
   dedicated scratch filesystem and hard memory/CPU/PID/disk quotas. Drop Linux
   capabilities; apply seccomp/AppArmor. Restrict outbound network access to the
   intended GitHub/provider endpoints; source parsing itself needs no network.
5. Remove public database/broker access. Use private networks, Redis ACLs/TLS and
   database TLS/least-privilege credentials. Separate API, broker, scanner and AI
   privileges. Compose here is a local-development configuration.
6. Add distributed global/user quotas, queue admission control, disk retention,
   periodic orphan cleanup and stale-job reconciliation independent of polling.
   Add health monitoring and alerts for dead workers and repeated failures.
7. Pin/audit dependency and image versions, update Git/OS packages, generate an
   SBOM and run a vulnerability scanner in CI. Maintain regression tests and an
   independent security review before public multi-tenant deployment.
8. Consider HttpOnly secure sessions with CSRF protection, token revocation and
   MFA as a separately designed auth migration. Preserve current UI/API behavior
   until that migration is planned and tested.
