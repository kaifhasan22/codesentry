# Analysis quality and deterministic scoring

Current rules and score policy are described below; benchmark/test results are a
**2026-09-29 historical snapshot**. The later [release-candidate report](release-candidate-report.md)
records **93 backend / 7 frontend tests**, genuine PostgreSQL/Redis/Celery E2E and
worker-loss/provider-unavailable verification. Setup is in the [README](../README.md).

## Finding contract

Every built-in rule supplies an analyzer-grounded message, category, severity,
title, repository-relative file path, source line/context snippet where available,
and practical fix. The existing Issue API fields carry these values. No database or
frontend redesign is required. Snippet lines are bounded to 500 characters.

Internal rule IDs plus source location identify duplicates independently of
wording. Separate rules and separate call columns remain separate findings.
Deduplication retains the highest analyzer severity and has a stable tie-break,
so thread completion order cannot change the report. Unknown severities are
rejected; case and surrounding whitespace are normalized.

| Analyzer | Evidence and noise reduction |
| --- | --- |
| Complexity | Radon callable complexity at least 15 (medium), at least 20 (high). Includes methods and nested functions; excludes class aggregate scores that duplicate method evidence. |
| Security | AST calls with conservative import-alias and lexical-shadow handling. Flags non-literal eval/exec, pickle load/loads, and YAML loaders not established as safe. Omits immediate in-process pickle dumps/loads round trips, while retaining warnings when the bytes are modified or supplied separately. Messages explicitly distinguish possible risk from proven exploitability. |
| Credentials | Literal assignments to specific credential-like names, rather than raw regex matches in comments/docstrings. Excludes obvious placeholders, repeated-character values, and URLs. Test/example literals receive lower severity; detected values are redacted across finding snippets, with additional API/AI text redaction. No claim that a literal is a valid credential. |
| Dead code | One Vulture pass over the whole eligible repository remains intact. Reports heuristic confidence at least 90; omits external whitelist files, package import re-exports, and explicit same-name import aliases. Multiline imports point to the imported name. Unreachable statements are medium; other candidates low. Removal suggestions require checking dynamic/external consumers. |
| Style | More than six positional parameters is low severity. Excludes implicit method/class receivers and keyword-only options; retains static-method arguments. Suggestions preserve required external signatures. |

The dead-code confidence threshold intentionally trades recall for fewer public
API/framework false positives. It does not reduce the inventory scanned. Vulture
confidence values are heuristics, not measured probabilities. The style rule is
an interface warning, not a complete formatting or PEP 8 audit.

## AI enrichment

AI cannot add findings, remove analyzer findings, overwrite severity, or affect
the health score. It can append an explicitly labeled advisory explanation and
fix alongside the original analyzer suggestion. Possible false positives remain
visible and are labeled as requiring verification.

Only fingerprints supplied in the current batch are accepted. Duplicate,
unknown, low-confidence (below 0.7), blank, and invalid reviews are ignored or
fall back to the analyzer report. Prompt data is JSON, with explicit instructions
to treat repository contents as untrusted data. This reduces instruction
confusion but cannot guarantee that generated advice is correct.

Missing credentials, SDK initialization failure, request failure, or malformed
structured output retain deterministic reports and fixes. Celery soft-limit
exceptions propagate. The existing default maximum of 24 reviewed findings,
eight per batch, 15-second request timeout, and no retries is preserved. A
three-request ceiling also applies when a smaller batch size is requested.
Findings are prioritized critical → high → medium → low → info.

## Health score version 2

The score depends only on unique deterministic findings. For each severity
threshold, count findings at that severity **or higher**:

| Threshold | Initial incremental penalty `w` | Maximum incremental penalty `c` |
| --- | ---: | ---: |
| Info or higher | 1 | 3 |
| Low or higher | 1 | 7 |
| Medium or higher | 3 | 15 |
| High or higher | 5 | 35 |
| Critical | 8 | 40 |

For count `n`, that threshold contributes `c × (1 − (1 − w/c)^n)`.
Sum these contributions, round the total penalty half-up to an integer, subtract
from 100, and clamp to 0–100. `health_score_breakdown` returns the policy version,
raw counts, threshold counts, individual penalties, and score for inspection.

Examples:

- No findings: 100.
- One info/low/medium/high/critical finding: 99/98/95/90/82.
- Even thousands of unique low findings: no lower than 90.
- Findings no higher than medium: no lower than 75.
- Findings no higher than high: no lower than 40; critical findings can push lower.
- Repeated copies of the same finding do not multiply the penalty.
- Adding a finding or raising severity can never improve the score.

Nested thresholds avoid a subtle flaw of independent saturated buckets: moving
a finding into a more severe but already saturated bucket could otherwise raise
the score. The policy is an explainable prioritization heuristic, not a measured
probability of security or production reliability. Compare reports using the
same rule/policy version. Previously saved scans are not recalculated; run a new
scan to obtain the new findings and score. New rule-based fingerprints also
differ from fingerprints in older reports.

## Safeguards and scope

The clone timeout (120 seconds), Celery soft/hard limits (270/300 seconds), stale
scan recovery, stage names, ETA fields, directory exclusions, and source limits
(5,000 files, 1 MB/file, 100 MB total, 20,000 directories) are unchanged. Analyzer
failures remain isolated. Source is parsed, never executed. Later security hardening also enforces checkout
512 MiB/50,000-entry limits, symlink-safe reads and bounded finding growth; see
[the current resource envelope](architecture.md#resource-envelope).

These lightweight rules do not perform complete data-flow, dependency,
cross-language, or interprocedural analysis. Dynamic imports, computed aliases,
reflection, unusual scoping/rebinding, and newer syntax can limit coverage.
Malformed/unsupported files and sources beyond the existing caps may be skipped;
the existing API does not yet expose full coverage diagnostics. No finding or a
high score is therefore a clean security bill. Secret detection/redaction is
heuristic, not comprehensive data-loss prevention.

## Verification and reproducible benchmark

The backend suite covers analyzer evidence, false-positive fixtures, severity
normalization, stable deduplication, score saturation/monotonicity, AI failure and
validation paths, persisted API reports with/without AI, existing progress/ETA,
source exclusions, and terminal timeout handling. The frontend production build
validates compatibility with its existing report fields.

From `backend`, with dependencies installed:

```sh
python -m pytest -q -p no:cacheprovider tests
ANTHROPIC_API_KEY= python -m scripts.benchmark_analysis
```

The benchmark clones public Requests and Redamon using the production clone
function, calls the real scan task with an isolated SQLite database, executes all
four analyzers concurrently, persists every finding, and checks report
completeness and terminal stage. It prints JSON with commit IDs, runtime
versions, workload, per-analyzer wall times, counts, score breakdowns, and one
representative finding per category. Temporary checkouts are cleaned by the
normal task. Live AI is disabled; fallback is separately tested with simulated
provider failures. Direct task invocation does not test delivery through Redis
or a real Celery hard kill. Concurrent analyzer times overlap and must not be
added together. Hardware, worker contention, and clone/network speed affect ETA.

Pass repository URLs as arguments to benchmark a different set, for example:

```sh
ANTHROPIC_API_KEY= python -m scripts.benchmark_analysis https://github.com/django/django
```

## Results — 2026-09-29

Measured in the local Docker Python 3.12.14 runtime with Radon 6.0.1 and Vulture
2.16. These are single-run wall times, not performance guarantees. Full scan time
includes cloning, all analyzers, SQLite persistence, and checkout cleanup. AI was
disabled. All report fields were present for every saved finding.

| Measurement | Requests | Django |
| --- | ---: | ---: |
| Commit | `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60` | `9332b163a67eabe5bdbf8066b1c5da394be9aa9c` |
| Eligible Python files | 37 | 2,932 |
| Source bytes | 407,127 | 19,413,839 |
| Clone | 1.96 s | 7.67 s |
| Static analysis wall time | 2.54 s | 132.19 s |
| Full scan | 4.64 s | 140.68 s |
| Findings | 25 | 419 |
| Health score | **68/100** | **40/100** |
| Critical | 0 | 0 |
| High | 2 | 147 |
| Medium | 7 | 98 |
| Low | 16 | 174 |
| Info | 0 | 0 |

| Analyzer/category | Requests: seconds / findings | Django: seconds / findings |
| --- | ---: | ---: |
| Complexity | 1.61 / 9 | 89.25 / 204 |
| Security | 1.77 / 1 | 89.87 / 42 |
| Dead code | 2.52 / 11 | 131.93 / 95 |
| Style | 1.74 / 4 | 89.22 / 78 |

Reviewing Requests samples led to removal of seven immediate pickle round-trip
warnings. The remaining security result is a review candidate, not proof of a
vulnerability. Django contains an intentionally invalid Python test fixture
(`tests/test_runner_apps/tagged/tests_syntax_error.py`); it was skipped. Trusted
deserialization, public compatibility exports, and intentionally unreachable
test code can still require human dismissal after checking context.

Redamon was also exercised during the audit. An earlier successful run at commit
`dbef36cb2441284595ce033de6308ea1249480a3` scanned 1,077 files and completed in
205.11 seconds (108.20-second clone, 96.29-second analysis), with 696 findings and
score 40 under the final scoring formula. That run preceded the final
round-trip/re-export filtering and report-wording refinements; it is not the
final-rule benchmark. Its latest download attempt exceeded the existing
120-second clone limit and the task failed before analysis. Network-heavy
repositories can therefore still time out during preparation; no timeout was
increased or bypassed in the clone function.

Validation: **56 backend tests passed**, frontend production build passed
(1,430 modules; JS bundle 254.58 kB, gzip 84.18 kB), and `git diff --check` passed.
No live AI provider call or end-to-end Celery worker kill was exercised. The
existing frontend source, API schemas, progress/ETA system, and scanner limits
were not changed in this analysis-quality pass. No commit or push was made.

Machine-readable measurements and penalty breakdowns are saved in
[analysis-benchmarks-2026-09-29.json](analysis-benchmarks-2026-09-29.json).

The running API/worker containers were not replaced during testing. Rebuild
them with `docker compose up -d --build api worker` to activate the source
changes, then create a new scan; historical reports retain their saved scores.
