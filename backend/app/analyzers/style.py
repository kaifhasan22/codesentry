from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path

from app.analyzers.common import Finding, iter_python_files, safe_snippet, read_source, BoundedFindings


def analyze(root: Path, python_files: Sequence[Path] | None = None) -> list[Finding]:
    findings: list[Finding] = BoundedFindings()
    for path in python_files if python_files is not None else iter_python_files(root):
        try:
            source = read_source(path, root)
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue
        methods = {id(child) for parent in ast.walk(tree) if isinstance(parent, ast.ClassDef) for child in parent.body}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                positional_args = args.posonlyargs + args.args
                positional = len(positional_args)
                static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in node.decorator_list)
                if id(node) in methods and not static and positional_args:
                    positional -= 1  # implicit instance/class receiver
                if positional > 6:
                    findings.append(Finding(
                        category="style",
                        severity="low",
                        title=f"Long parameter list in {node.name}",
                        message=f"AST analysis found {positional} positional parameters in {node.name} (threshold: 6, excluding implicit receivers). Long positional interfaces make call sites easy to misread. Keyword-only options are not counted.",
                        file_path=str(path.relative_to(root)),
                        line=node.lineno,
                        snippet=safe_snippet(path, node.lineno, source=source),
                        fix_suggestion="Make optional settings keyword-only or group related values in a small configuration object. Update callers and tests; keep externally required callback/override signatures compatible.",
                        rule_id="style.positional-parameters",
                        column=node.col_offset,
                    ))
    return findings
