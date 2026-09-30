from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from collections.abc import Callable
from collections import Counter
from pathlib import Path
from time import perf_counter

from app.analyzers import complexity, dead_code, security, style
from app.analyzers.common import Finding, SEVERITY_ORDER, iter_python_files
from app.services.finding_identity import assign_comparison_keys
from app.services.repository import RepositoryResourceError
from billiard.exceptions import SoftTimeLimitExceeded

ANALYZERS = [complexity.analyze, security.analyze, dead_code.analyze, style.analyze]
logger = logging.getLogger(__name__)


def run_static_analysis(
    root: Path,
    on_workload: Callable[[int, int], None] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    python_files = list(iter_python_files(root))
    source_bytes = sum(path.stat().st_size for path in python_files)
    logger.info("Source inventory found %d Python files (%d bytes)", len(python_files), source_bytes)
    if on_workload:
        on_workload(len(python_files), source_bytes)
    with ThreadPoolExecutor(max_workers=len(ANALYZERS)) as executor:
        futures = {
            executor.submit(_timed_analyzer, analyzer, root, python_files): analyzer.__module__
            for analyzer in ANALYZERS
        }
        for future in as_completed(futures):
            try:
                results = future.result()
                if len(findings) + len(results) > 50_000:
                    raise RepositoryResourceError()
                findings.extend(results)
            except (RepositoryResourceError, SoftTimeLimitExceeded):
                raise
            except Exception:
                # One analyzer should never take down the complete report.
                logger.exception("Analyzer %s failed", futures[future])
                continue
    unique = deduplicate_findings(findings)
    assign_comparison_keys(root, unique)
    return unique


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Stable order and highest-severity representative regardless of thread order."""
    unique: dict[str, Finding] = {}
    for finding in sorted(findings, key=lambda f: (
        SEVERITY_ORDER[f.severity], f.file_path, f.line or 0, f.column or 0,
        f.category, f.rule_id or "", f.title, f.message, f.fix_suggestion or "", f.snippet or "",
    )):
        unique.setdefault(finding.fingerprint, finding)
    return list(unique.values())


def _timed_analyzer(analyzer, root: Path, python_files: list[Path]) -> list[Finding]:
    started = perf_counter()
    result = analyzer(root, python_files)
    logger.info(
        "Analyzer %s completed in %.2fs with %d findings",
        analyzer.__module__, perf_counter() - started, len(result),
    )
    return result


# Nested severity thresholds ensure upgrading a finding can never improve its
# score, even when another bucket is saturated. Each (initial, maximum) penalty
# is incremental: single findings cost 1/2/5/10/18, respectively.
SCORE_POLICY = {"info": (1, 3), "low": (1, 7), "medium": (3, 15), "high": (5, 35), "critical": (8, 40)}


def health_score_breakdown(findings: list[Finding]) -> dict:
    counts = Counter(f.severity for f in deduplicate_findings(findings))
    threshold_counts = {
        threshold: sum(count for severity, count in counts.items() if SEVERITY_ORDER[severity] <= SEVERITY_ORDER[threshold])
        for threshold in SCORE_POLICY
    }
    penalties = {
        severity: cap * (1 - (1 - weight / cap) ** threshold_counts[severity])
        for severity, (weight, cap) in SCORE_POLICY.items()
    }
    score = max(0, min(100, 100 - int(sum(penalties.values()) + 0.5)))
    return {"version": "2", "score": score, "counts": dict(counts), "threshold_counts": threshold_counts, "penalties": penalties}


def health_score(findings: list[Finding]) -> int:
    """Deterministic score from unique analyzer findings; never AI judgments."""
    return health_score_breakdown(findings)["score"]
