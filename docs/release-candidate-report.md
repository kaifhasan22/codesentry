# CodeSentry release-candidate regression report — 2026-09-30

This report preserves the release verification record. Current setup and portfolio
presentation are in the [README](../README.md); implementation/configuration details
are in [architecture and technical decisions](architecture.md).

## Outcome and scope

**The tested local release candidate passes its functional regression gates and is ready for documentation. Public production deployment remains conditional on the prerequisites in section 6.** No unresolved functional defect was found in the exercised paths after the fixes below. This is not a load-test or security certification.

Testing used a separate release stack: the actual backend Dockerfile, FastAPI, **PostgreSQL 17**, **Redis 8**, a real Celery prefork worker with concurrency two, and the built React frontend served by Vite preview. Two disposable users exercised real registration, Argon2 login and signed JWT authorization. The user's regular service containers and data were not replaced. Existing working-tree changes were preserved; no features, UI redesign, commits or pushes were made.

[Recorded test evidence](release-candidate-verification.json) · [Desktop report screenshot](release-candidate-report.png) · [Mobile issue-details screenshot](release-candidate-mobile.png)

## 1. Automated test results

| Gate | Final result |
| --- | --- |
| Complete backend suite, rebuilt image, `python -m pytest -q` | **93 passed**, 2 existing deprecation warnings; 13.28 s |
| All frontend tests, `node --test tests/*.test.js` | **7 passed**, 0 failed |
| Frontend production build, `npm run build` | **Passed**, 1,432 modules; 5.61 s |
| Working-tree whitespace check, `git diff --check` | Passed |

The backend suite covers URL bypasses, real JWT expiry/ownership, body/auth limits, sanitized errors, Git environment isolation, supervisor timeout/parent loss, symlinks/FIFOs/traversal/file substitution, source limits, repository nonexecution, soft/hard failure hooks, duplicate tasks, queue failures, scoring/severity/deduplication, all analyzers, AI fallback/advisory boundaries, priorities/hotspots, structural fingerprints, comparison isolation and legacy migrations. Two new parameterized cases exercise PostgreSQL INTEGER scan-ID boundaries; the signed-JWT regression now also covers an out-of-range subject.

Frontend regressions exercise actual Axios 401 interceptors, safe error strings, GitHub URL alignment, composed search/severity/category/priority/file filtering, reset/hotspot behavior and comparison-state selection. Priority/file dropdowns previously removed from the UI remain removed; file filtering still works through hotspots/search.

At the time of this regression pass, bare `pytest` lacked the application import path. A subsequent test-environment fix added `backend/pytest.ini` to the image, so `docker compose run --rm api pytest -q` now works without manual environment flags. The frontend suite is now exposed through `npm test`. See the [current test commands](../README.md#tests-and-production-build). The results above retain the original regression-pass commands.

## 2. E2E scenarios and results

### Authentication and validation

- Registration: **201**; duplicate email: **409**; correct login: **200**; incorrect credentials: **401**. The browser now shows one useful incorrect-credentials message.
- Anonymous/invalid-token history, detail and comparison: **401**. A genuinely signed expired JWT was also rejected by the API, and expired/invalid client-token fixtures redirected the browser to sign-in.
- Logout removed client authentication; direct access to a protected results URL redirected to sign-in.
- Two actual users saw only their own history. Other-owner detail/comparison requests returned **404**, including a direct browser access attempt.
- Unsupported schemes, explicit ports, lookalike hosts, userinfo, encoded traversal and dot traversal returned **422**. Negative pagination, invalid status and invalid IDs returned sanitized validation responses without submitted input. Full malicious-URL coverage also passed in the automated suite.
- Final PostgreSQL verification: scan ID `2147483648` returns **422** on detail/comparison; maximum valid INTEGER ID `2147483647` safely returns **404** when absent. An out-of-range signed JWT subject returns **401**.

### Genuine repository scans and infrastructure

The first Requests scan was submitted through the browser while the worker was stopped. It visibly queued, then ran through Redis/Celery/PostgreSQL to completed results and automatic frontend navigation. Later, after all fixes and removal of test hooks, a second browser-origin scan verified the normal worker again.

| Repository / scenario | Result | Findings | Health score |
| --- | --- | --- | --- |
| `psf/requests`, genuine frontend scans #1 and #15 | Completed | 25 | 68 |
| `psf/requests`, unchanged repeated scans #2/#3/#7/#9 | Completed | 25 | 68 |
| `pallets/itsdangerous`, separately scanned by both users | Completed | 4 | 94 |
| Nonexistent `psf/codesentry-rc-nonexistent-39f2d6b9` | Failed with safe repository-access message | 0 | No score |
| Unreachable AI provider, dummy credential, scan #7 | Completed; analyzer findings/fixes retained | 25 | 68 |
| Deliberately terminated Celery task child, scan #12 | Queued → running → failed; safe worker-loss message | 0 | No score |
| Broker stopped during browser submission, scan #14 | Safe queue error; persisted terminal failed state | 0 | No score |

Requests commit: `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`. Findings were **2 high / 7 medium / 16 low**, with **9 complexity / 11 dead-code / 4 style / 1 security**. Every actual Requests finding had title, message, file, line, snippet and actionable fix. AI was not used for score, severity, priorities, hotspots or comparison.

Final normal-worker scan #15 timings: clone **2.76 s**; complexity **1.50 s**; security **1.53 s**; style **1.61 s**; dead code **2.27 s**; parallel static-analysis stage **2.68 s**; disabled AI **0.00 s**; persistence **0.04 s**; total worker processing **5.82 s**. Individual analyzer times overlap. The frontend displays about 5.5 s between database start/finish timestamps; worker timing also includes surrounding task bookkeeping.

PostgreSQL and API were restarted: existing history rows, repository metadata, issue counts and original reports persisted. Two duplicate Redis task deliveries for a completed scan did not rerun analysis or duplicate findings. Two queued scans for one owner were accepted, a third returned **429**, and another user's scan was accepted independently. This tests admission behavior, not a sustained concurrency/load benchmark.

All inspected scan workspaces were removed after normal completion, clone failure and actual worker termination. A labeled abandoned-row fixture verified owner-scoped stale-running recovery, expired-queue recovery, cleared estimates and cleanup. API and broker outages were restored; browser history retry succeeded. PostgreSQL/Redis were healthy and API/worker running before cleanup.

### Comparison and reporting

- Successive unchanged upstream scans selected the immediately preceding completed scan of the same repository/owner: **0 new / 0 resolved / 25 unchanged**, score/total/all-severity deltas zero. The final scan selected #9, skipping failed later scans.
- Unrelated repositories had no comparison baseline. Another user's scans were inaccessible and never used as a baseline.
- Separately labeled controlled-source test: a trusted test hook added `codesentry_rc_fixture.py` to an actual temporary Requests clone; source was analyzed, never executed. Scan #8 produced **1 new / 0 resolved / 25 unchanged**, score **68 → 64**, total **+1**, high **+1**. A fresh unmodified clone (#9) produced **0 new / 1 resolved / 25 unchanged**, score **64 → 68**, total **−1**, high **−1**. No findings, scores or classifications were fabricated. The altered scan's commit metadata was cleared because its temporary checkout differed from upstream. The hook was removed before the final normal-worker scan.
- Browser new/resolved buttons selected the correct finding. Resolved details retained their previous-scan provenance, location, message, snippet and fix.
- Top Issues opened the existing drawer with deterministic priority reasons. Hotspot selection filtered to `src/requests/models.py` (five findings). Hotspot + search `prepare` + medium + complexity yielded two results; unchanged + medium + complexity yielded seven, then search `prepare` yielded two. Empty combinations showed “No matching findings”; reset restored 25.

### Progress, history and refresh

Actual API monitoring observed queued, repository preparation, static analysis, AI review, finalization and completed stages. Scan #7 exposed workload-based ranges (static **2–64 s**, AI **11–55 s**), then completed with zero remaining estimates. Very short stages may finish between frontend polls.

Browser rendering fixtures, clearly separated from analyzed repositories, verified the results/history ETA wording (“Approximate completion window: about 1 minute to about 3 minutes”), stage markers after direct refresh, and an old completed report dated 2010 with **score 0** shown as `0 / 100` and history score `0`, not missing data. The fixtures were not used as genuine analyzer-quality evidence. Failed real scans remained failed after refresh and showed safe explanations.

## 3. Defects discovered and fixes

Only these release-pass changes were made to application behavior:

1. **Incorrect login treated as session expiry:** the global 401 interceptor cleared auth and triggered expiry messaging for the login endpoint. `frontend/src/api/client.js` now treats login failure separately and displays a clear bad-credentials message; protected-endpoint 401 behavior remains. Two focused frontend tests cover interceptor and safe-message behavior. Optional access to Vite's environment object permits the same client module to run in Node regression tests.
2. **Frontend/backend GitHub URL mismatch:** `ScanForm.jsx` rejected valid `www.github.com` URLs and accepted unsupported HTTP. A small `frontend/src/lib/githubUrl.js` helper now mirrors the backend's raw HTTPS owner/repository contract. Two tests cover accepted URLs and bypass rejection. Layout and styling were unchanged.
3. **PostgreSQL ID overflow:** detail/comparison and JWT subjects permitted 64-bit values although current database IDs use PostgreSQL INTEGER. Bounds in `backend/app/api/routes.py` and `backend/app/auth.py` now match signed 32-bit IDs. Regression tests cover both endpoints and signed subjects; actual PostgreSQL verifies 422/401 instead of 500.

No database migration or schema change is needed for these fixes. Existing report/progress migration behavior remains covered. Earlier product/security changes visible in the working tree are not new changes from this pass.

## 4. Frontend/build results

Direct navigation and refresh passed for `/`, `/login`, `/dashboard`, `/scans/new`, `/scans` and completed report URLs. The dashboard showed the latest repository, score 68, 25 findings and two high-severity findings. Loading states, empty account/history, empty filters, failed scans, missing/other-owner resources, API connection errors and retry were exercised.

Responsive report testing used **375×812**, **768×1024** and **1440×900**. Document widths matched the viewport; the mobile findings table scrolled within its own container. Major pages also had no document overflow at 375 px. Details opened, expanded/restored, closed and locked background scrolling; at mobile width the drawer remained within the viewport. The final production report had no captured console errors or warnings.

Final production build: JS **264.38 kB** (**87.00 kB gzip**); CSS **30.39 kB** (**6.95 kB gzip**). No large-chunk warning. The test API URL was removed by rebuilding with normal configuration; the temporary auth test page was erased. Test login was cleared, browser viewport restored, preview and isolated containers stopped, and disposable stack data/secrets cleaned up.

## 5. Remaining warnings/known limitations

- Two existing FastAPI startup-event deprecation warnings; no refactor was made during the freeze.
- Backend unit/API fixtures primarily use SQLite. This pass additionally exercised actual PostgreSQL persistence, ID boundaries, owner checks, queue admission and comparisons, but not sustained concurrent database submissions or production load.
- No successful request to a real AI provider was made. Disabled AI, SDK/response failures and an actual unreachable-provider worker run passed; valid-provider enrichment quality/credentials/model availability still need deployment-specific verification.
- The real 270/300-second Celery deadline was not waited out. Automated soft/hard-limit failure tests, actual child termination, actual Git-supervisor deadlines/parent loss and stale recovery passed. This does not guarantee every hostile workload completes; bounded scans can intentionally fail, and excluded/oversized/malformed files can reduce coverage.
- Status recovery for abandoned rows requires API polling. Whole-container/host failure still needs periodic orphan reconciliation/cleanup outside the request path. Health currently reports API liveness, not database/broker/worker readiness.
- Frontend history renders the bounded backend page (up to 500 rows); it has no pagination UI. Old rows remain available through API pagination/direct detail URLs. Registration was tested through the API; the frozen frontend has no registration form.
- Browser coverage used the in-app browser, not a cross-browser/device lab. Dependency CVE/SBOM review, external penetration testing and production load testing were not performed.
- Existing security-review limitations remain: worker image runs as root, localStorage bearer tokens, process-local auth throttling, no distributed global admission quotas, and periodic disk monitoring rather than a hard quota. See [security report](security-hardening.md).

## 6. Documentation/deployment readiness and blockers

**Documentation:** ready to document the tested behavior, limits, failure messages, estimates and deployment instructions. No unresolved blocker was found for documentation or the tested local functional release candidate.

**Public production deployment: not approved by this regression pass. Explicit remaining gates:**

1. Build/activate the final API and worker images in the intended environment; the user's regular services were not upgraded. Preserve the established additive migration order and take a database backup. Configure the production frontend API URL and SPA fallback for direct routes.
2. Supply a shared strong production JWT secret, production environment setting, explicit HTTPS CORS origins, HTTPS/reverse-proxy limits and private authenticated database/broker networking. Do not deploy development secrets or localhost/default URL assumptions.
3. Complete the worker-isolation gate from the security report: non-root execution, restricted privileges/network access and hard CPU/memory/PID/scratch-disk limits appropriate for untrusted repositories. Add periodic orphan/stale-job reconciliation and dependency-aware monitoring.
4. Establish distributed rate/admission limits and capacity/retention policy, then validate expected concurrent and large-repository workloads in staging. This pass cannot establish capacity from a few successful scans.
5. Audit/pin dependencies and image versions for known vulnerabilities; validate the intended production database configuration and backup/restore process. If AI is enabled, verify the configured provider/model and data-handling policy with an approved real-provider smoke test.

These are production release gates/deferred operational work, not features added in this pass. Nothing was committed or pushed.
