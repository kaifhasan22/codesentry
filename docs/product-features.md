# Report product features

This document retains the **2026-09-29 feature-phase evidence** and describes the
current compact report algorithms. Security hardening and the subsequent
[release-candidate pass](release-candidate-report.md) came later; the current
baseline is **93 backend / 7 frontend tests** with genuine PostgreSQL/Redis/Celery
E2E. Use the [README](../README.md) for current setup.

This phase adds prioritized findings, composed client-side filters, file
hotspots, and completed-scan comparison. It retains the existing visual system,
issue drawer, API routes/fields, scanner limits, progress/ETA behavior, analyzer
rules, and health-score formula. The original feature phase preceded security
hardening; current protections are documented in [the security report](security-hardening.md).
No commit or push was made.

## 1. Priority policy v1

Priority is a deterministic review order, not a second severity label. The
backend starts with analyzer severity and adds available evidence/context:

| Input | Points |
| --- | ---: |
| Critical / high / medium / low / info | 70 / 45 / 25 / 8 / 0 |
| Security category | +15 |
| Measured complexity 20–29 / at least 30 | +5 / +10 |
| Analyzer heuristic confidence 90–99% / 100% | +4 / +8 |
| Test, fixture, example, or documentation path | −8 |

Clamp to 0–100. P1 means at least 75 (first); P2 at least 50 (next); P3 at least
25 (planned); P4 below 25 (cleanup). For example, high severity without additional
evidence scores 45/P3; high security scores 60/P2. Two high-complexity findings can
have different scores because the measured complexity differs. No confidence
is inferred when the analyzer does not supply it. Vulture confidence remains a
heuristic, not a calibrated probability.

Top Issues selects five findings by descending priority score, then file, line,
and issue ID. The existing detail drawer shows the exact point contributions.
Historical findings use their recorded severity/category/context; missing
confidence/complexity evidence is not reconstructed from prose. Historical
severity provenance cannot be retroactively established. New scans retain the
authoritative analyzer severity and persist the supporting measurements.

The calculations never read AI explanation/fix fields or AI review responses.
The existing health-score policy is unchanged and independent of priority.

## 2. Search and filters

Search checks title, analyzer message, and file path, case-insensitively, after
trimming surrounding whitespace. Severity, category, and comparison-state controls compose with search using AND.
The priority and file dropdowns were removed in the compact UI update. Selecting
a hotspot still applies an exact file filter; Reset clears all filters. The table
supports priority, severity, and file sorting; opening an issue retains the
existing detail workflow. Priority is the initial table sort.

Filtering is client-side because the current reports already return the full
finding list and measured reports contain hundreds of findings. There is no new
server pagination or virtualized table; exceptionally large reports may need
those later. Search deliberately excludes AI prose.

## 3. File hotspots

For each exact repository-relative path, sum critical=16, high=8, medium=3;
multiply those contributions by 1.5 for security findings. Low findings add
0.25 each, capped at 2 per file; info adds 0.05 each, capped at 0.25. Thus no
number of low/info findings alone outranks a single medium finding. Ranking is
descending weighted concentration, then path. Counts and all five severity
counts remain visible even when minor contributions are capped.

The UI initially shows three files, with an option to show all in a bounded,
scrollable list. Top Issues also initially shows three compact entries. Choosing a file
resets other filters, selects that exact file, and moves focus to its findings.
The UI explains this reset before selection. Hotspots describe current findings;
resolved findings can be explored through comparison and the file filter.

## 4. Comparison and identity

### Selecting the baseline

`GET /api/scans/{id}/comparison` first authorizes the current scan using the
existing user dependency. Unknown/other-user scans return 404; a current scan
that is not completed returns 409.

Repository identity is the lowercased GitHub owner/repository pair, normalizing
`www`, a trailing slash, and `.git`. The existing database creates a separate
Repo row per scan; comparison therefore searches all matching Repo rows **owned
by the current user**, rather than assuming row IDs identify the same repository.
Unrelated owners/repositories and other users are excluded. New scan creation
behavior is unchanged. GitHub renames/transfers are not followed, and identity
does not use the GitHub repository numeric ID.

The baseline is the latest earlier scan in `(created_at, id)` submission order
that is currently completed. Failed, queued, running, current, and later scans
are excluded. This is submission order among completed scans, not completion
duration order. SQLite timestamp values are normalized numerically to handle
the different precision of server timestamps and bound Python datetimes;
PostgreSQL uses its native timestamp comparison.

### Fingerprint audit and structural matching

The existing within-scan `fingerprint` already excludes message wording for
built-in rules, but includes line/column. It is retained for deduplication and
health-score compatibility. New scans additionally persist a versioned
`comparison_key`, independent of line numbers, comments, whitespace, message,
title, severity, priority, and AI prose.

Structural identity consists of file, category, rule ID, enclosing class/function
names, a source anchor, and an occurrence number:

- Complexity/style identify the callable, so a changed complexity metric can
  remain the same finding while severity changes.
- Security calls/assignments use an AST representation without source positions.
- Dead-code imports use their rule/symbol and scope; other dead-code findings
  use source AST context.
- Repeated identical anchors are matched one-to-one using occurrence order.

AST work uses the existing bounded file inventory; unavailable/unparseable
context falls back rather than inventing evidence. No source code is executed.
File moves, symbol renames, and changed call/statement semantics can appear as
new/resolved findings. Repeated identical occurrences have no unique semantic
identity beyond their order.

When either report lacks structural keys, or analysis versions differ, both
reports use a conservative legacy fallback: category + file + line + normalized
title. Messages, severity, and AI text are still excluded. The API/UI explicitly
warn that line/title changes may create apparent changes. No historical keys or
analyzer measurements are guessed or backfilled.

### Results

Comparison matches multisets rather than collapsing repeated findings. It
returns new/current IDs, unchanged/current IDs, and resolved findings from the
baseline, plus total/severity deltas and `current score − previous score`.
Score zero is valid; a missing score yields a null delta. Unchanged means identity
matched, not that every field remained equal. Resolved means no longer detected,
not proof that code was fixed. Rule changes, scan limits, and skipped files may
also affect results. Unknown/different analysis versions are disclosed.

Resolved detail drawers explicitly identify the earlier scan. Comparison buttons
filter to new, resolved, or unchanged findings; the existing drawer works for all
three. Navigation discards stale fetch results from a previously viewed scan.

## API and database implications

Existing endpoints and fields remain. Scan detail adds `source_commit`,
`priority_version`, `top_issue_ids`, and `hotspots`. Each returned issue adds
`priority`, `priority_score`, and `priority_reasons`. Comparison is a new endpoint;
it does not change scan creation or history response shapes.

API startup performs four nullable, additive column migrations:

| Table | Column | SQL type |
| --- | --- | --- |
| scans | analysis_version | VARCHAR(64) |
| scans | source_commit | VARCHAR(64) |
| issues | comparison_key | VARCHAR(64) |
| issues | analyzer_metadata | JSON |

Migration requires ALTER TABLE rights and is idempotent for sequential startups.
It preserves existing records, fingerprints, scores, and issue details. No data
backfill or new uniqueness constraint is introduced. As with the existing startup
migration approach, run one API instance through migration before starting the
updated workers. Coordinate this with active jobs; the verification run did not
replace the user's running API/worker containers. PostgreSQL and SQLite accept
the additive column definitions; the migration regression test used SQLite.

New source commits are recorded from the prepared Git checkout. New finding
metadata contains the analyzer rule ID plus actual complexity/confidence where
available. A new scan is required for structural identity and measured-priority
bonuses; old reports continue to work with the documented fallback.

## Verification — 2026-09-29

- Complete backend suite: **69 passed**, including priority/evidence separation,
  hotspot caps, fingerprint stability, repeated-identity matching, zero/missing
  scores, version/legacy behavior, repository/user isolation, natural server
  timestamps, additive migrations, and existing scanner/AI/progress safeguards.
- Frontend filter tests: **3 passed** with Node's built-in runner.
- Frontend production build: **passed**, 1,431 modules; JavaScript 262.10 kB
  (86.18 kB gzip). One backend warning concerns the pre-existing Starlette 422
  constant alias; it does not affect the assertions.
- Actual browser verification against an isolated API/database: Top Issues opened
  the original drawer with point explanations; a hotspot selected five findings
  in `src/requests/models.py`; search `prepare` + medium + complexity + P3 + that
  file + unchanged returned two findings. P1 then returned zero; reset returned
  all 25. New/resolved controls and prior-scan details were also exercised.

### Real successive scans, then a separate controlled change

Requests commit: `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`. A bounded clone was
reused to ensure the same source for both unmodified scans. The real scan task,
analyzers, persistence, authenticated API, and report calculations ran each time.
AI was disabled. Jobs were invoked directly rather than delivered through Redis.

| Scenario | Findings | Score | New | Resolved | Unchanged | Score delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unmodified baseline | 25 | 68 | — | — | — | — |
| Same unmodified commit again | 25 | 68 | **0** | **0** | **25** | **0** |
| Add a labeled synthetic test file locally | 26 | 64 | 1 | 0 | 25 | −4 |
| Remove that synthetic file | 25 | 68 | 0 | 1 | 25 | +4 |

The synthetic file contains a single dynamic `eval` example, is explicitly
marked as verification code, and was never added to the user's project or the
upstream repository. The modified scan's commit field was cleared to avoid
misrepresenting the local variant as an unmodified upstream commit. No source
commits were created and no reported finding totals were altered. The first
identical pair's genuine zero-new/zero-resolved result is retained.

The reusable harness is `backend/scripts/verify_product_features.py`. It refuses
a populated database and requires isolated SQLite with AI disabled. For Docker,
use a disposable container, mount the trusted `backend/scripts` at `/app/scripts`
(the Dockerfile does not copy scripts), mount a fresh temporary directory at
`/verification`, set `SCAN_ROOT=/verification/scans` and
`DATABASE_URL=sqlite:////verification/features.db`, and run
`python -m scripts.verify_product_features` with the updated backend source.
The harness writes `results.json` there for inspection.

[Recorded API verification results](product-feature-verification.json)

## Compact report update — 2026-09-30

Removed the priority/file dropdowns, tightened summary spacing, and added
Expand/Restore to the issue drawer. Opening the drawer locks background scrolling
and keyboard focus; closing it restores the prior page position and focus.
Verified in the browser: hotspot/reset, show more/less, 460px to 1040px expansion,
independent drawer scrolling, unchanged background position, and Escape close.
The frontend production build passed. Backend behavior is unchanged.

## Remaining limitations

Priority and hotspot weights are transparent heuristics, not calibrated risk
probabilities. Historical severity provenance and missing analyzer metadata
cannot be reconstructed. Comparison is URL-based and conservative for legacy
reports, file moves, symbol changes, repeated occurrences, or changed analysis
versions. It does not yet include file coverage equivalence or Git diff mapping.
Filtering loads the full report into the browser. Existing scan/clone limits can
still truncate coverage or fail preparation, and live AI and a full Celery
delivery/kill cycle were not exercised by this dated product-feature verification.
The later release-candidate pass tested real Redis/Celery/PostgreSQL execution,
provider-unavailable fallback and actual worker-child termination; successful live
AI and a real 300-second deadline remain unverified.
