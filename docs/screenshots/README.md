# CodeSentry portfolio screenshots

Captured from the real local application on **1 October 2026** (Asia/Kolkata), using the unchanged dark theme and a consistent **1440 × 900** desktop viewport. Files are native browser JPEG captures of page content, with browser chrome omitted. They are not generated mockups, retouched UI, or fixture reports.

## Gallery inventory

| File | Actual view |
| --- | --- |
| [landing.jpg](landing.jpg) | Public landing page and existing CodeSentry branding |
| [login.jpg](login.jpg) | Sign-in screen before entering demonstration credentials |
| [scan-history.jpg](scan-history.jpg) | Three genuine completed scans and their persisted counts/scores |
| [new-scan.jpg](new-scan.jpg) | Public Requests URL entered in the repository submission form |
| [scan-progress.jpg](scan-progress.jpg) | Actual Django static analysis with stages and an approximate completion window |
| [completed-report.jpg](completed-report.jpg) | Requests scan #15: score, severity counts, Top Issues and hotspots |
| [issue-detail.jpg](issue-detail.jpg) | Expanded detail from Requests scan #16: analyzer evidence, snippet, priority and fix |
| [hotspots-filtering.jpg](hotspots-filtering.jpg) | Requests scan #16: exact hotspot file + search + Medium + Complexity, yielding two findings |
| [scan-comparison.jpg](scan-comparison.jpg) | Requests scan #16 compared with #15, with genuinely unchanged findings |

## Scan provenance

The existing local setup was used: React/Vite, FastAPI, Redis, Celery and PostgreSQL. A separate local demonstration account kept personal credentials and unrelated users' reports out of the captures. All three scans were submitted through the actual frontend and completed through the normal worker pipeline. Repository source and findings were not altered for presentation.

| Public repository | Local scan IDs | Source commit | Completed result |
| --- | --- | --- | --- |
| `psf/requests` | #15, #16 | `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60` | 25 findings, score 68; 2 high / 7 medium / 16 low |
| `django/django` | #17 | `5a4511adb247a44a1cada11fe4763abba0a42663` | 420 findings, score 40 |

The comparison selected the preceding completed scan of the same repository/account: **0 new / 0 resolved / 25 unchanged**, score/total/all-severity deltas zero. This is fingerprint stability evidence, not a manufactured before/after improvement.

For the filtering capture, the user selected `src/requests/models.py` in File hotspots, searched `prepare`, and selected Medium severity and Complexity category. The two matches were `PreparedRequest.prepare_url` and `PreparedRequest.prepare_body`.

Optional AI credentials were not configured. The detail view accurately says **AI explanation unavailable** and retains the deterministic analyzer's practical fix. The progress estimate is a workload-based approximation, not a runtime guarantee.

Scan IDs and dates belong to this local capture session. Source changes, configuration and hardware can change future counts, scores and durations. Earlier engineering screenshots outside this directory remain dated verification evidence; these fresh captures are the portfolio gallery linked by the root README.

## Updating captures

Use real public-repository scans at the same desktop size/theme. Keep sensitive inputs and private source out of images. Replace files and captions together, check all repository-relative paths, and retain honest comparison results even when new/resolved counts are zero.
