# RedAmon scan resource rejection — 1 October 2026

## Finding

The production traceback points to the original `repository.py:89`, which maps supervisor exit 125 to `RepositoryResourceError`. In the original supervisor that single code represented either workspace bytes > 536,870,912 (512 MiB) or filesystem entries > 50,000. It did not represent the 120-second clone timeout, the 270/300-second worker deadlines, analyzer limits, or an OOM signal. The supplied historical log alone cannot distinguish the two resource guards or recover the exact byte count/source commit at rejection.

A local reproduction of the public repository with the same clone commands and limits rejected **workspace bytes during checkout**, exit 125. At the measurement immediately following rejection:

- Workspace: **556,651,057 bytes**, **893 entries** (Git could grow between the guard check, measurement, and kill).
- Git data: **206,389,229 bytes**, including a **206,249,534-byte pack**.
- Checkout files already present: **350,261,828 bytes**; checkout was incomplete.
- Elapsed time: **110.99 seconds** on this local network/machine, rather than the production 19.45 seconds. Both are below the 120-second supervisor deadline.
- Temporary workspace was removed; no target repository code, hooks, submodules, or LFS smudge was executed.

Public metadata observed during investigation: default branch `master`, head commit `623beec5ae8bd8f027c237b376cb6e966cc17462`, commit timestamp `2026-10-01T07:29:38Z`, repository size metadata 357,850 KiB. The complete recursive tree had **4,168 entries** and **427,736,011 blob bytes**. Full checkout plus observed Git storage would need approximately **634,125,240 bytes**, above the cap. Metadata is corroboration; it is not the actual workspace measurement and should not replace enforcement. There is no production shell/config/commit inspection in this investigation, and the log's timezone/source commit is not supplied; historical identity cannot be proven.

Large files include `docs/assets/agent.gif` (42,153,225 bytes), `recon.gif` (39,986,532), `new_project.gif` (26,373,091), `recon-pipeline.gif` (25,758,086), `redamon-graph.gif` (20,164,821), and repeated CVE JSONL datasets under `recon/data` and `recon/main_recon_modules/data`. The safety guard measures all workspace regular files, including Git objects and non-Python assets, not just analyzer input. See the [public repository](https://github.com/samugit83/redamon).

## Change

- `backend/app/services/git_guard.py`: separate byte rejection (125) and entry rejection (127), retaining exact thresholds, polling, process-group termination and deadline behavior. Keep the boolean usage helper for existing callers/tests.
- `backend/app/services/repository.py`: translate codes into trusted resource reason identifiers; retain fail-closed workspace cleanup and subprocess isolation.
- `backend/app/services/public_errors.py`: allowlist fixed actionable messages naming 512 MiB of Git data plus checkout or 50,000 filesystem entries. Generic analysis-limit and legacy persisted messages remain supported.
- `backend/app/tasks/scan.py`: persist failed status, failed stage, finish time and cleared estimates, then return `{scan_id, status: failed}` for expected repository resource/clone/clone-timeout failures. Log a warning with the trusted reason without a traceback. Celery completes its processing normally while the product scan remains failed. Unexpected errors, soft worker deadlines and errors saving failure status still propagate.
- `backend/tests/test_repository_limits.py`: regression coverage for both supervisor codes and clone cleanup, exact byte/entry boundaries including Git data, actual entry-limit subprocess rejection, Celery eager failure-result handling and API messages, absence of analysis/findings after preparation failure, cleanup/context reset, no terminal-job rerun, analysis-resource rejection, and failure-persistence errors remaining exceptional.

Existing clone already uses `--depth 1 --single-branch --no-tags --no-checkout`, then bounded checkout. No new clone optimization is justified here: shallow cloning is already enabled, metadata size is not checkout size, and partial/sparse checkout could silently change scan coverage. No limits were increased and no exclusions were added. A smaller source-only repository is the actionable workaround; repeated scans of the unchanged full repository will still fail.

## Validation

- Full native backend suite: **114 passed**, two existing FastAPI startup deprecation warnings.
- Full frontend suite: **23 passed** (13 unit, 10 component/routing).
- Frontend production build: passed, Vite 5.4.21, 1,435 modules.
- Whitespace/diff check: passed.
- Live Celery broker/production environment and 270/300-second termination were not exercised in this task. Celery eager execution, actual supervisor entry rejection, existing supervisor timeout/parent-loss tests, and existing worker-limit configuration tests passed in the backend suite.

## Production recommendation

Keep the **120-second clone, 512 MiB workspace, 50,000-entry and 270/300-second worker limits**. The user confirmed that the shared 1 GB production Lightsail worker already runs with **`--concurrency=1`**. Leave that setting unchanged. Local Compose still uses its existing concurrency of 2; this release does not change either configuration. Concurrency of 1 does not make RedAmon fit the workspace cap or guarantee sufficient RAM for every accepted scan. The workspace cap is a disk-byte guard, not a memory quota. No production configuration was read or changed.

The initial investigation made no deployment, commit or push. The subsequent release gate below authorizes committing and pushing only after validation, without deployment.


## Final release gate

All checks passed on 1 October 2026:

| Check | Result |
| --- | --- |
| Complete native backend suite, Python 3.14 | 114 passed in 11.27s; 2 existing FastAPI lifespan deprecation warnings |
| Complete Linux backend suite through Docker/Compose, Python 3.12 | 114 passed in 11.62s; same 2 warnings |
| Frontend unit tests | 13 passed |
| Frontend component/routing tests | 10 passed |
| Frontend production build | Passed; Vite 5.4.21, 1,435 modules |
| Whitespace check | `git diff --check` passed |
| Secret/credential review | No real secrets found in tracked/proposed files; candidates were existing synthetic fixtures, local Compose demo credentials or documented placeholders |
| Complete change review | Only four backend implementation files, the new regression-test file and this report changed |

Docker validation built the current backend and used a disposable container via `docker compose -p codesentry-resource-gate run --build --rm --no-deps`, with a temporary SQLite database and an explicit synthetic test-only JWT secret. It exercised the complete suite, including both byte/entry limit rejection cases and Celery eager execution. It did not use a production database or server.

The resource regression tests verify failed scan/stage persistence, finish timestamp, cleared estimates, safe public messages, no findings or subsequent analysis after preparation failure, cleanup/context reset, no traceback records or unexpected Celery failures, and prevention of terminal-job reruns. Analysis resource failures also return normal failed scans; errors persisting failure status remain exceptional.

Review confirmed unchanged clone/worker deadlines (120/270/300 seconds), workspace cap (536,870,912 bytes), entry cap (50,000), raw URL validation, sanitized Git environment, transport restrictions, hooks/LFS/submodule safeguards, shallow clone arguments, process-group termination and workspace cleanup. Authentication, analyzer limits/coverage, scoring, progress/ETA calculations and frontend code were not changed. The intended failed-scan path still clears estimates.

`npm audit` reports the existing **4 advisories: 3 moderate and 1 high**, involving esbuild, react-router, react-router-dom and Vite; none critical. Dependencies and lockfiles were not changed. This was a frontend dependency audit, not a comprehensive backend vulnerability audit.

The user authorized commit message `fix: handle repository resource limit failures cleanly` and push to `origin/main` after the successful gate. No Lightsail deployment or production-server changes are part of this release.
