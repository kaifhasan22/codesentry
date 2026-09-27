from __future__ import annotations

import ast
from pathlib import Path

from app.analyzers.common import Finding, iter_python_files, safe_snippet


def analyze(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                positional = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
                if positional > 6:
                    findings.append(Finding(
                        category="maintainability",
                        severity="medium",
                        title=f"Long parameter list in {node.name}",
                        message=f"{node.name} accepts {positional} parameters. Consider a smaller interface or an options object.",
                        file_path=str(path.relative_to(root)),
                        line=node.lineno,
                        snippet=safe_snippet(path, node.lineno),
                    ))
    return findings
