from __future__ import annotations

from collections.abc import Sequence
import ast
import logging
from pathlib import Path

import vulture

from app.analyzers.common import Finding, iter_python_files, safe_snippet, read_source, BoundedFindings

logger = logging.getLogger(__name__)


def analyze(repo_path: Path, python_files: Sequence[Path] | None = None) -> list[Finding]:
    """Find likely unused Python code using Vulture's public API."""

    findings: list[Finding] = BoundedFindings()

    py_files = list(python_files) if python_files is not None else list(iter_python_files(repo_path))

    if not py_files:
        return findings

    vulture_finder = vulture.Vulture()
    for path in py_files:
        try:
            vulture_finder.scan(read_source(path, repo_path), filename=path)
        except (OSError, ValueError, RecursionError):
            continue
    vulture_finder.scavenge([])

    # 60% candidates include public APIs, framework hooks, and dynamic lookups.
    # Report only Vulture's high-confidence evidence, with uncertainty explicit.
    source_cache = {}
    import_locations = {}
    for item in vulture_finder.get_unused_code(min_confidence=90):
        try:
            relative_path = Path(item.filename).relative_to(repo_path)
        except ValueError:
            continue  # Vulture's bundled whitelist is not repository source.

        if item.typ == "import" and relative_path.name == "__init__.py":
            continue  # Common package re-export; absence of local use isn't dead code.

        line = item.first_lineno
        path = Path(item.filename)
        if path not in source_cache:
            try:
                source_cache[path] = read_source(path, repo_path)
                tree = ast.parse(source_cache[path])
                import_locations[path] = {
                    (node.lineno, alias.asname or alias.name.split('.')[0]):
                    (alias.lineno, alias.asname == alias.name)
                    for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names
                }
            except (OSError, SyntaxError, ValueError):
                source_cache[path] = ""
                import_locations[path] = {}
        if item.typ == "import":
            line, explicit_reexport = import_locations[path].get((line, item.name), (line, False))
            if explicit_reexport:
                continue

        findings.append(
            Finding(
                category="dead_code",
                severity="medium" if item.typ == "unreachable_code" else "low",
                title="Unreachable branch or statement" if item.typ == "unreachable_code" else f"Potentially unused {item.typ}: {item.name}",
                message=f"Vulture reports: {item.message} ({item.confidence}% heuristic confidence). " + ("The highlighted branch or statement is statically unreachable; surrounding statements may still run." if item.typ == "unreachable_code" else "No use was found in the scanned source; dynamic use or use outside this repository may not be visible."),
                file_path=str(relative_path),
                line=line,
                snippet=safe_snippet(path, line, source=source_cache[path]),
                fix_suggestion=("Check whether the preceding return/raise or condition is intentional. Remove unreachable statements, or correct the control flow and add a regression test." if item.typ == "unreachable_code" else "Check dynamic consumers and public exports before removing this code. Remove an unused import only if its side effects are unnecessary; preserve required callback signatures and explicitly mark intentionally unused arguments."),
                rule_id=f"dead-code.{item.typ}.{item.name}",
                evidence={"confidence": item.confidence},
            )
        )

    return findings
