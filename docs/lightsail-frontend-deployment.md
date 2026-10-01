# CodeSentry frontend on existing Lightsail

Prepared locally; not published. Repository: https://github.com/kaifhasan22/codesentry.
Reported backend docs: http://13.203.54.122/docs. This is HTTP, not a verified HTTPS API endpoint. Do not use `/docs` as an API base.

## Confirmed build

The frontend uses React 18, Vite 5, npm's committed package-lock.json, and BrowserRouter. Run `npm ci`, `npm test`, and `npm run build` inside `frontend`; upload the contents of `frontend/dist`, not the source folder. UI components and styles have not changed.

The preferred setup for review is to serve https://codesentry.tech and proxy its `/api/...` requests to the existing API on the same Lightsail machine. This avoids requiring a second hostname and keeps all browser requests HTTPS. The proxy's internal HTTP connection stays on loopback. Confirm Nginx runs on the host and that the live API actually listens on 127.0.0.1:8000 before applying this template.

Copy `frontend/.env.production.example` to ignored `frontend/.env.production` for that topology. The empty `VITE_API_BASE_URL` means same-origin requests. Ensure no stale `VITE_API_URL`, `.env.local`, or shell variable overrides this choice. The build now rejects explicit HTTP production API URLs. For a separately hosted frontend, set `VITE_API_BASE_URL` to a verified HTTPS API origin, without `/docs` or `/api`, and rebuild. There is no HTTPS API hostname confirmed yet.

## Remaining server steps (publication requires authorization)

1. Inspect current DNS, web-server virtual hosts, certificate paths, API port binding, and domain ownership. If the static IP really is 13.203.54.122, the proposed apex A record points there; confirm it is reserved as a Lightsail static IP. Remove or correct conflicting records, including stale IPv6, only after review. Do not change nameservers blindly.
2. Obtain a valid certificate for codesentry.tech through the existing server's certificate workflow; port 80 validation may require a temporary challenge configuration. Do not enable the TLS template before the certificate exists. Ensure 80/443 are available in both applicable firewalls.
3. Integrate `deploy/nginx/codesentry.conf.example` into the existing configuration. Set the actual release directory and certificate paths. Preserve current backend proxy settings and any deliberately exposed docs routes; the template does not expose `/docs`. Do not overwrite the working backend virtual host.
4. Upload `frontend/dist` to a new release directory and set `/var/www/codesentry/current` to that release after review. Keep the prior release for rollback. Run `nginx -t` before reloading. Build locally to avoid additional build memory load on the small server.
5. Set the live backend `CORS_ORIGINS=https://codesentry.tech` consistently for API and worker. Add www only if serving the app there. Existing backend middleware already allows GET/POST/OPTIONS, Authorization and Content-Type, with no cookie credentials. The same-origin proxy itself needs no browser CORS permission. Preserve the working JWT secret and other backend settings.
6. If supporting www, configure its DNS, certificate coverage, and HTTPS redirect to the apex, retaining paths and query strings. Otherwise use the apex exclusively.
7. Verify HTTPS `/api/health`, login, an authorized scan, progress and results from the public frontend. Refresh and directly open `/dashboard`, `/scans`, `/scans/new`, and `/scans/<valid-id>`; logged-out redirects are expected. Missing `/assets/...` should return 404; API errors must remain API responses rather than index.html. Check HTTP-to-HTTPS redirects and no browser mixed-content errors.

## Important server/repository difference

The earlier deployment conversation reports server-specific Postgres password changes and worker concurrency 1. The repository still has development database values and concurrency 2. Do not replace the server's docker-compose.yml with this checkout or run a blanket backend redeploy. This change prepares frontend deployment only.

## Verification limits

Local checks passed: all 10 frontend tests, the production build (1433 modules), and an intentional HTTP API build rejection. `git diff --check` passed. Nginx syntax and direct-route behavior on the target server remain unverified.

Dependency audit reports four affected packages (three moderate, one high), involving Vite/esbuild and React Router. The proposed deployment serves static build files through Nginx; do not expose the Vite development or preview server publicly. Review the router advisories and plan supported dependency upgrades before release; automatic forced fixes require major-version changes and were not applied. Audit details: https://github.com/advisories/GHSA-wrjc-x8rr-h8h6 and https://github.com/advisories/GHSA-fx2h-pf6j-xcff.

Local frontend tests and production build can establish build correctness. They cannot establish live DNS, certificate validity, live reverse-proxy behavior, or browser login/scan success. Those checks remain pending until hosting is configured and publication is authorized. No cloud resources, DNS records, or server files were changed by this task.

References: [Nginx try_files](https://nginx.org/en/docs/http/ngx_http_core_module.html#try_files), [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/).
