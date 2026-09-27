from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app.analyzers import complexity, dead_code, security, style
from app.analyzers.common import Finding

ANALYZERS = [complexity.analyze, security.analyze, dead_code.analyze, style.analyze]


def run_static_analysis(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    with ThreadPoolExecutor(max_workers=len(ANALYZERS)) as executor:
        futures = {executor.submit(analyzer, root): analyzer.__module__ for analyzer in ANALYZERS}
        for future in as_completed(futures):
            try:
                findings.extend(future.result())
            except Exception:
                # One analyzer should never take down the complete report.
                continue
    seen: set[str] = set()
    unique: list[Finding] = []
    for finding in findings:
        if finding.fingerprint in seen:
            continue
        seen.add(finding.fingerprint)
        unique.append(finding)
    return sorted(unique, key=lambda x: (x.severity, x.file_path, x.line or 0))


def health_score(findings: list[Finding]) -> int:
    weights = {"critical": 18, "high": 10, "medium": 5, "low": 2, "info": 1}
    penalty = sum(weights.get(item.severity, 0) for item in findings)
    return max(0, min(100, 100 - penalty))
