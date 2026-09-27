from __future__ import annotations

import ast
from pathlib import Path
import re

from app.analyzers.common import Finding, iter_python_files, safe_snippet

SECRET_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{12,}['\"]"), "Potential hardcoded credential"),
]


def analyze(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "eval":
                findings.append(Finding(
                    category="security",
                    severity="high",
                    title="Use of eval()",
                    message="eval() turns a string into executable Python and can become code execution when input is attacker-controlled.",
                    file_path=str(path.relative_to(root)),
                    line=getattr(node, "lineno", None),
                    snippet=safe_snippet(path, getattr(node, "lineno", None)),
                ))

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "loads":
                chain = getattr(node.func.value, "id", None) or getattr(node.func.value, "attr", None)
                if chain in {"pickle", "yaml"}:
                    findings.append(Finding(
                        category="security",
                        severity="high",
                        title="Potentially unsafe deserialization",
                        message=f"{chain}.loads() deserves review because deserializing attacker-controlled data can execute or instantiate unsafe objects depending on the library and loader.",
                        file_path=str(path.relative_to(root)),
                        line=getattr(node, "lineno", None),
                        snippet=safe_snippet(path, getattr(node, "lineno", None)),
                    ))

        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, title in SECRET_PATTERNS:
                if pattern.search(line) and not any(x in line for x in ("example", "dummy", "changeme")):
                    findings.append(Finding(
                        category="security",
                        severity="critical",
                        title=title,
                        message="A credential-like value appears to be embedded directly in source code. Move secrets to environment/configuration and rotate exposed credentials.",
                        file_path=str(path.relative_to(root)),
                        line=lineno,
                        snippet=safe_snippet(path, lineno),
                    ))
    return findings
