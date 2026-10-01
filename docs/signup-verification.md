# Signup release verification — 1 October 2026

## Implementation

The backend already exposed POST /api/auth/register with JSON email/password and a 201 bearer-token response. Login uses POST /api/auth/login with OAuth2 form data; the username is the account email. There is no separate username field.

The new /signup page reuses the existing auth design and is linked from Sign In. It validates email, a nonblank password of 8–128 characters, and matching confirmation, disables pending submission, and redirects to Sign In with a success message. Registration does not save the returned token. Successful login establishes the existing session and always redirects to home (/). An authenticated visit to /login also redirects home, preventing the previous return-to-login loop.

The backend normalizes email case and surrounding whitespace, preserves password contents, rejects blank passwords, and handles both duplicate lookup and uniqueness races with a generic 409 and rollback. Public validation handling strips submitted values. Frontend registration errors use fixed strings without database details. A distinguishable 409 is not full account-enumeration prevention.

## Verification results

All requested test and local end-to-end checks passed on the final tree:

| Check | Command/result |
| --- | --- |
| Native full backend suite | From backend: `/private/tmp/codesentry-signup-venv/bin/python -m pytest -q` — 102 passed, 2 existing FastAPI lifespan deprecation warnings, 9.36s |
| Compose stack | `docker compose -p codesentry-signup-check up -d --build` — API, worker, PostgreSQL, and Redis started successfully |
| Full backend suite in Linux container | `docker compose -p codesentry-signup-check exec -T api python -m pytest -q` — 102 passed, 2 existing warnings, 8.80s |
| Signup-specific backend coverage | Six tests included in both full runs: account creation/hash/login/protected access; duplicate case variants; invalid email; short/overlong/blank password; commit-race rollback |
| Auth/ownership/security regression | Existing full-suite tests cover real JWT ownership isolation, expired tokens, invalid credentials, password/body guards, auth throttling, and comparison authorization |
| Frontend tests | From frontend: `npm test` — 13 unit tests plus 10 component/routing tests passed |
| Frontend production build | From frontend: `npm run build` — passed, Vite 5.4.21, 1435 modules |
| Whitespace/diff check | `git diff --check` — passed |
| Repository inspection | `git status --short`, complete tracked diff and new-file review, ignored-file inspection, tracked-file credential/config checks |

The native suite's earlier Git-supervisor timing failures did not recur in the final native run; those tests were not modified. The Linux container suite also passed them.

Temporary native dependencies were installed with `python3 -m venv /private/tmp/codesentry-signup-venv` and `/private/tmp/codesentry-signup-venv/bin/pip install -r backend/requirements.txt 'cryptography<49'`. This compatible binary constraint was used only in the temporary Python 3.14 environment; repository requirements were not changed. Docker uses the normal requirements on Python 3.12.

## Browser end-to-end verification

Frontend started with `npm run dev -- --host 127.0.0.1`; browser used http://localhost:5173 to match development CORS. Backend services used an isolated Compose project with local-only published ports.

- Created a brand-new synthetic user through signup and reached Sign In with the success message.
- Signed in and reached home (/), signed out, tested incorrect credentials with the safe error, then signed back in and reached home again.
- Opened dashboard successfully.
- Started two real scans of https://github.com/psf/requests through API → PostgreSQL → Redis → Celery → Git → analyzers → report persistence.
- Observed scan #2 running with completed repository preparation, current static-analysis stage, remaining stages, and “Approximate completion window: under a minute”.
- Both scans completed with 25 findings and health score 68. Worker scan #1 elapsed 8.54s; report scan #2 duration 9.4s.
- Scan history listed both completed scans and their scores/finding counts.
- Second report compared against scan #1 at commit 611c6162cbc4: score/finding delta 0, 0 new, 0 resolved, 25 unchanged. Comparison filters displayed 0/25 and 25/25 as expected.
- Opened an issue detail drawer and verified message, priority, snippet, and suggested fix.
- Verified report refresh, history refresh, direct dashboard route and refresh, new-scan direct route and refresh, signup direct route and refresh, and logged-out dashboard redirect to Sign In.
- Tested mismatched password validation and uppercase duplicate signup; safe messages displayed and signup stayed on its page.
- No unexpected browser errors during valid flows. Expected invalid-login/duplicate requests return 401/409. React Router v7 migration notices are development warnings, not failures.

No AI API key was supplied to this isolated test stack. Static analysis, reports, and comparison completed normally; the detail drawer correctly displayed “AI explanation unavailable”. Paid AI enrichment was not tested.

## Dependency and repository review

Added patched Vitest 4.1.11, Testing Library, and jsdom for component tests. The test runner uses its own config; the production Vite version and product dependencies were preserved. `npm audit` reports the same pre-existing four advisories (3 moderate, 1 high) in Vite/esbuild and React Router. No new critical test-runner advisory remains. This audit was an additional check; it is not a zero-advisory release claim.

Ignored caches, dist, node_modules, and local databases are excluded. No real .env file, credentials, private key, generated build output, or deployment-private material is included. Existing public .env example files contain configuration placeholders only. The pre-existing frontend deployment docs/template were reviewed as public material; no server changes were made.

## Files in the reviewed change

- .gitignore (pre-existing public production example exception)
- backend/app/api/routes.py
- backend/app/schemas.py
- backend/tests/test_signup.py
- frontend/package.json
- frontend/package-lock.json
- frontend/src/App.jsx
- frontend/src/api/auth.js
- frontend/src/api/baseUrl.js (pre-existing production URL guard)
- frontend/src/api/client.js
- frontend/src/lib/signupValidation.js
- frontend/src/pages/Login.jsx
- frontend/src/pages/Signup.jsx
- frontend/tests/auth.component.test.jsx
- frontend/tests/componentSetup.js
- frontend/tests/signup.test.js
- frontend/tests/baseUrl.test.js (pre-existing URL guard tests)
- frontend/vite.config.js (pre-existing production URL guard)
- frontend/vitest.config.js
- frontend/.env.production.example (public placeholders)
- deploy/nginx/codesentry.conf.example (public template)
- docs/lightsail-frontend-deployment.md (pre-existing public deployment notes)
- docs/signup-verification.md

The authorized commit message is `feat: add user signup flow`. No Lightsail build, deployment, SSH action, or server configuration change is part of this verification.
