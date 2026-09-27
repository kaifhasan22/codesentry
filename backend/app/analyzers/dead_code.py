from __future__ import annotations

from pathlib import Path

import vulture

from app.analyzers.common import Finding, iter_python_files, safe_snippet


def analyze(repo_path: Path) -> list[Finding]:
    """Find likely unused Python code using Vulture's public API."""

    findings: list[Finding] = []

    py_files = list(iter_python_files(repo_path))

    if not py_files:
        return findings

    vulture_finder = vulture.Vulture()

    for py_file in py_files:
        try:
            vulture_finder.scavenge([str(py_file)])
        except Exception:
            # A single malformed Python file shouldn't kill the entire scan.
            continue

    for item in vulture_finder.get_unused_code():
        try:
            relative_path = Path(item.filename).relative_to(repo_path)
        except ValueError:
            relative_path = Path(item.filename)

        line = item.first_lineno

        findings.append(
            Finding(
                category="maintainability",
                severity="low",
                title=f"Potentially unused {item.typ}: {item.name}",
                message=f"Vulture identified {item.typ} '{item.name}' as potentially unused code.",
                file_path=str(relative_path),
                line=line,
                snippet=safe_snippet(Path(item.filename), line),
            )
        )

    return findings