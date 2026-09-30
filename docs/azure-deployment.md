# Azure deployment preparation

Prepared 1 October 2026. **No Azure/Upstash resources have been created, no Azure login has been performed, and nothing has been deployed.** This guide describes a future deployment of the existing application, not a production certification. Existing release/security deployment gates still apply.

## Services and topology

- **Azure Static Web Apps:** built React/Vite files, separate from the API.
- **Azure Container Apps environment:** one API app with HTTPS ingress and one Celery worker app with **ingress disabled**, using the same backend image.
- **Azure Database for PostgreSQL Flexible Server:** durable users, repositories, scans and findings; PostgreSQL 17 matches local Compose if available in the selected region.
- **External Redis-compatible service, such as Upstash:** TCP/TLS Celery broker and configured result backend. Do not use the REST endpoint/REST SDK as the Celery connection.
- **Container registry:** ACR or another supported registry, plus the corresponding image-pull identity/credentials. Logs and budget alerts should be configured before public use.
- The existing custom domain is a later step. Start with assigned Azure HTTPS hostnames.

The local Compose file deliberately retains its own PostgreSQL/Redis URLs and loopback ports. It is not an Azure provisioning template. No deployment workflow or resource-creation script is added.

## Required environment variables

Set these directly on **both API and worker** Container Apps. Root `.env` values are not automatically uploaded to Azure. Secrets must use Container Apps secret references or an approved secret manager; never put them into image layers or the frontend build.

| Variable | API | Worker | Required production value |
| --- | --- | --- | --- |
| `ENVIRONMENT` | Required | Required | `production` |
| `DATABASE_URL` | Secret | Secret | Same PostgreSQL `postgresql+psycopg://` URL with verified TLS, database and credentials |
| `REDIS_URL` | Secret | Secret | Same native TCP `rediss://` URL and database index |
| `JWT_SECRET` | Secret | Secret | Same randomly generated value, at least 32 characters; stable across revisions |
| `CORS_ORIGINS` | Required | Required | Comma-separated explicit HTTPS frontend origins, no path or trailing slash; shared settings validate this even in the worker |

Additional settings:

| Variable | Where | Value / default |
| --- | --- | --- |
| `PORT` | API only | `8000`; match ingress targetPort and HTTP probe port |
| `WORKER_QUEUE` | Both | `celery`; if changed, set identically on both |
| `SCAN_ROOT` | Both | `/tmp/codesentry`; temporary files only |
| `ALLOWED_GITHUB_HOSTS` | Both | `github.com,www.github.com`; preserve existing host restrictions |
| `ANTHROPIC_API_KEY` | Worker secret, optional | Leave absent/blank for analyzer-only scans; no provider use is required |
| `ANTHROPIC_MODEL` | Worker, optional | An available provider model; current default has not had a verified successful live call |
| `ACCESS_TOKEN_MINUTES` | Both, optional | Existing default `60`; keep existing behavior |
| `MAX_ACTIVE_SCANS_PER_USER` | Both, optional | Existing default `2`; not a distributed global workload quota |
| `VITE_API_BASE_URL` | Frontend build only | Actual HTTPS API origin, e.g. `https://your-api.azurecontainerapps.io`; public, not a secret |

`VITE_API_URL` remains a supported alias. The new variable takes precedence. Vite consumes build-process environment or `frontend/.env.local`, **not the root backend `.env`**. SWA runtime application settings do not rewrite an already-built Vite bundle. Rebuild when the API origin changes.

Development keeps its localhost default. Production without an explicit API URL uses a relative URL rather than silently calling localhost; this target architecture has no same-origin API proxy, so the real HTTPS API origin **must** be supplied for a working Azure deployment. Do not publish a build made with the example's local API URL.

## Image, process commands and ports

Build/test locally; this command creates an image only and does not push/deploy:

```sh
docker build --platform linux/amd64 -t codesentry:azure-candidate ./backend
```

Use an amd64 image for the intended Container Apps Linux environment; a default Apple Silicon build may otherwise produce arm64. Publish an immutable image tag/digest later, after choosing the registry. Both apps use that same image. API startup is the image default:

```sh
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

The Docker command uses `sh -c` with `exec`, so Uvicorn receives termination signals. No `--reload` or development server. Use one Uvicorn process/one API replica initially because startup performs existing additive schema initialization. Do not run concurrent initializers against an uninitialized database.

Worker command override, preserving the local command and 270/300-second task limits:

```sh
celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO --concurrency=2
```

For the student baseline below, use the same command with `--concurrency=1` to bound simultaneous worker memory/CPU usage. This changes concurrency only; analyzers, results and task limits remain unchanged. Do not override the time limits through CLI flags.

- API container port: `8000` by default, bind `0.0.0.0`; external HTTPS uses Azure ingress port 443.
- Worker: no web listener, HTTP ingress or exposed application port. Override the **command and arguments** with Celery; do not leave the default Uvicorn command running.
- PostgreSQL outbound: 5432. Upstash outbound: provider-specified native Redis port (commonly 6379), TLS enabled. Allow public GitHub HTTPS and optional AI-provider HTTPS outbound access.
- Ports in Docker `EXPOSE` are metadata; a nondefault `PORT` requires matching Azure ingress/probe configuration. Local Compose remains fixed at 8000 and does not forward root `.env` PORT overrides.

## Health checks and startup ordering

`GET /api/health` returns HTTP 200 with `{"status":"ok","service":"codesentry-api"}`. Use that path for API HTTP startup, liveness and readiness probes on the configured container port. Choose startup thresholds that permit PostgreSQL connection/schema initialization. Example initial choices: startup period 5 seconds/failure threshold 24; liveness/readiness period 10 seconds/timeout 3 seconds/failure threshold 3. These are proposed platform settings, not applied infrastructure.

The endpoint reports API liveness; it does **not** check database/broker/worker connectivity. Add external operational smoke checks; do not interpret green API probes as full-system health. The Celery-only app cannot use this HTTP endpoint. Observe worker startup logs and queue execution; broker-dependent remote-control checks are not a substitute for a validated worker probe. [Azure health probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes).

API startup currently creates missing tables/additive report/progress columns. For the future first deployment, prepare the database, start one API revision, wait for successful initialization, then start workers. For updates, drain scans and complete API initialization before new workers. This guide does not run/create/migrate any Azure database.

## PostgreSQL connection and TLS

The installed driver is **psycopg 3**, selected explicitly by SQLAlchemy:

```text
postgresql+psycopg://<user>:<url-encoded-password>@<server>.postgres.database.azure.com:5432/codesentry?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt
```

Percent-encode reserved characters in credentials. Use the Flexible Server username supplied for that server; do not blindly append the old Single Server `@servername` username convention. A bare `postgres://` or `postgresql://` can select an uninstalled driver; use the exact dialect above.

SQLAlchemy already passes URL query options to psycopg, so **no database code change is required**. The image now explicitly includes `ca-certificates`. Keep Azure secure transport enabled. `sslmode=require` encrypts but does not provide full server identity verification; the recommended URL uses `verify-full` plus a trusted CA bundle. Confirm that the image's trust bundle contains the current Azure root CAs; if an additional CA file is required, supply it through an approved mount/image and adjust `sslrootcert`. Never disable TLS or pin a leaf/intermediate certificate to bypass connection failures. [Azure TLS and CA guidance](https://learn.microsoft.com/en-us/azure/postgresql/security/security-tls-how-to-connect).

Choose a reachable network mode/firewall policy before deployment: private networking with matching Container Apps VNet/DNS, or narrowly scoped public access with stable allowed egress. Do not enable unrestricted database access to solve networking. Existing `pool_pre_ping` remains; size connections against API/worker process counts and the selected server tier. Backups, retention, restore verification and least-privilege/schema ownership must be decided before publication.

## Upstash Redis connection and TLS

```text
rediss://default:<url-encoded-token>@<native-redis-endpoint>:<port>/0
```

Use the actual provider username, token/password, endpoint and port; placeholders above are not credentials. No REST URL/token configuration is introduced. API and worker must share the same database index and `WORKER_QUEUE`; isolate this broker from unrelated applications.

Celery configures both broker and result backend from `REDIS_URL`. PostgreSQL remains authoritative for reports; `task_ignore_result=True` means normal scan return values are not stored in Redis. Queues, worker control/heartbeat traffic and transport bookkeeping still consume Redis operations/connections.

For `rediss://`, explicit certificate verification and hostname checks are now applied to both broker and result backend. This also handles provider URLs without a `ssl_cert_reqs` query parameter, which Celery's backend otherwise rejects. A URL parameter, if present, must specify `ssl_cert_reqs=required`; do not supply `none`/`optional`. Plain local `redis://` has unchanged behavior. [Celery TLS configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html#redis-backend-settings).

Upstash documents Celery support through its Redis interface, but an actual provider connection/plan has **not** been tested. Before choosing a plan, verify native Redis command compatibility, blocking queue operations, connection quotas, payload/command sizes, throughput, durability/consistency semantics and region latency. Free/low-cost quotas may be consumed by an idle worker's polling/control traffic, not only submitted scans. Keep an API and worker in a region near the database/broker; do not assume local Redis timings apply. [Upstash Celery integration](https://upstash.com/docs/redis/integrations/celery).

## Frontend build and Static Web Apps routes

From the repository root, with the actual API origin supplied to the build environment:

```sh
cd frontend
npm ci
VITE_API_BASE_URL=https://your-api.azurecontainerapps.io npm run build
```

Static Web Apps future build configuration: app location `frontend`, output location `dist`, API location empty. Serve `frontend/dist`; do not serve source files. Do not configure SWA integrated API authentication as a replacement for existing application JWTs.

`frontend/public/staticwebapp.config.json` is copied by Vite to `dist/staticwebapp.config.json`. Its navigation fallback serves `/index.html` for direct React routes such as `/login`, `/dashboard`, `/scans`, `/scans/new` and `/scans/123`. Missing assets and `/api/*` are excluded so they do not return misleading HTML. Validate route refresh on the actual SWA host later; no SWA resource is created here. [SWA routing configuration](https://learn.microsoft.com/en-us/azure/static-web-apps/configuration).

## CORS and custom domain later

Existing API CORS already reads comma-separated `CORS_ORIGINS` and rejects wildcard/malformed origins and non-HTTPS production origins. No middleware/security behavior is changed. Set the exact assigned SWA origin first, then add the verified custom frontend HTTPS origin later, for example:

```text
CORS_ORIGINS=https://your-site.azurestaticapps.net,https://www.your-domain.example
```

No trailing slash, path, wildcard or API URL in this list. API/worker shared settings must receive the same valid production value. Configure DNS and platform-managed TLS later after domain ownership is confirmed. If adding a custom API domain, update the frontend build's API origin and rebuild; authorize only frontend origins in CORS. Preview environments need explicitly approved origins; do not globally allow `*.azurestaticapps.net`.

## Replicas, temporary storage and student budget

Recommended initial topology: **API min=1/max=1, worker min=1/max=1**, one active revision each. This is an operational recommendation for the existing app, not a high-availability setup. The worker has no HTTP trigger and no Redis scaler has been implemented; min=0 can strand queued tasks. API min=1 avoids cold-start/schema initialization surprises. Scaling/revisions must be tested before increasing replicas because throttling is process-local and resource admission is not a global quota.

Starting resource proposals (capacity testing is still required): API 0.25 vCPU/0.5 GiB; worker concurrency 1 with **2 vCPU/4 GiB** for representative larger repository scans. A budget-limited 1 vCPU/2 GiB worker can be evaluated for small demo workloads, but do not promise large scans will complete within the existing 270/300-second limits on that tier. Do not raise limits to compensate for undersizing.

Use worker `terminationGracePeriodSeconds=330` so a normal Celery warm shutdown can finish a bounded scan and cleanup. Drain queues/active tasks before revisions or manual stops. Abrupt platform termination can still fail active scans; existing persisted status/stale recovery remain, and scans are not guaranteed to resume. [Container Apps revision template](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/container-apps/get?view=rest-resource-manager-containerapps-2025-07-01).

Repository clones and subprocess artifacts are temporary under `SCAN_ROOT`; database reports persist remotely. Container Apps disks are ephemeral and separate between API/worker replicas. Normal worker/supervisor cleanup operates locally; API stale cleanup cannot reach another replica's workspace. A destroyed replica loses its temporary files; a long-lived worker interrupted during cleanup may leave files until its lifecycle/cleanup runs. Do not depend on the local Compose shared volume, SQLite, or Azure Files for durable reports. Existing caps stay unchanged. Account for checkout space, Python subprocesses and concurrency within actual ephemeral disk/memory limits. [Container Apps storage](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts).

For Azure for Students, prefer SWA Free, Container Apps Consumption, a small eligible Burstable PostgreSQL server and a nearby Redis plan whose quotas fit Celery. Confirm student benefits, regional availability and service eligibility in the subscription **before** provisioning; do not assume these services are indefinitely free. Cap replicas, limit log retention/ingestion, set budget alerts and leave optional AI disabled until budgeted. Constant worker/broker activity and PostgreSQL/storage/registry/logs can incur charges even when no user scans. Manually stop demo infrastructure only after draining work; account for database auto-start/storage charges. [Azure for Students](https://azure.microsoft.com/en-in/free/students/) · [Container Apps billing](https://learn.microsoft.com/en-us/azure/container-apps/billing).

## Future deployment order — do not execute yet

1. Confirm region, subscription/student quotas, spend limit, registry and domain ownership; decide networking and credentials/secret management.
2. Build/test the amd64 image, scan dependencies and choose an immutable tag. Publish only when deployment is authorized.
3. Prepare PostgreSQL, database/user, TLS/firewall/DNS and backups; prepare a compatible Redis service/plan. Verify connections from the intended environment.
4. Configure the Container Apps environment/secrets; start one API revision with explicit environment and ingress/probes. Let existing initialization complete, then verify health/auth/database persistence.
5. Start one Celery worker revision from the same image, no ingress, matching URLs/queue, graceful shutdown settings. Run a real scan through Redis/PostgreSQL and verify failure/cleanup behavior.
6. Build frontend with the real HTTPS API origin, configure SWA and explicit API CORS for its assigned origin; publish only with authorization. Verify direct-route refresh, login, report polling and comparison.
7. Configure custom DNS/TLS later; explicitly update frontend API origin/CORS as needed and repeat smoke checks.

Public deployment additionally needs the existing security/production gates in [the release report](release-candidate-report.md#6-documentationdeployment-readiness-and-blockers); this compatibility pass does not waive them.

## Verification boundary

Local checks cover backend/frontend suites, production build, SWA-config copying, Redis TLS parameter construction, PostgreSQL URL/TLS option pass-through, configurable API port and Compose API/worker execution. Real Azure ingress, SWA fallback, Azure CA/firewall access, Upstash quotas/TLS connectivity, platform shutdown and student-tier workload capacity remain **unverified until an authorized deployment**. No Azure migration/resource operation is performed by these checks.

### Local verification results — 1 October 2026

| Check | Result |
| --- | --- |
| Rebuilt API/worker image | Passed; inspected `linux/amd64` |
| `docker compose run --rm --no-deps api pytest -q` | **96 passed**, 2 existing FastAPI startup-event deprecation warnings |
| `npm test` | **9 passed**, 0 failures |
| Standard `npm run build` | Passed, 1,433 modules |
| Build with placeholder HTTPS `VITE_API_BASE_URL` | Passed; explicit origin present in generated bundle |
| SWA routing file | Copied unchanged into `dist/staticwebapp.config.json` |
| Nondefault API listener | `PORT=8088`; HTTP 200 health on local mapped port 18888; Uvicorn is PID 1 |
| CA trust bundle | Current image contains DigiCert Global Root G2 and Microsoft RSA Root Certificate Authority 2017 |
| Compose end-to-end public Requests scan | #18 completed; **25 findings**, score **68**; persistent history and workspace cleanup verified |
| Worker limits | Soft **270 s**, hard **300 s**, unchanged |
| `git diff --check` | Passed |

Three backend tests and two frontend tests were added solely for deployment configuration compatibility. The disposable port-check container was removed. No real cloud endpoint/credential was used in connection-construction or frontend build checks. Existing application security/deployment limitations remain documented above.
