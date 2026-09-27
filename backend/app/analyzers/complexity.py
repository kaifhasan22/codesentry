from pathlib import Path

from radon.complexity import cc_visit

from app.analyzers.common import Finding, iter_python_files, safe_snippet


def analyze(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files(root):
        try:
            blocks = cc_visit(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for block in blocks:
            if block.complexity >= 15:
                findings.append(Finding(
                    category="complexity",
                    severity="high" if block.complexity >= 20 else "medium",
                    title=f"High cyclomatic complexity in {block.name}",
                    message=f"{block.name} has cyclomatic complexity {block.complexity}; splitting branches can reduce regression risk.",
                    file_path=str(path.relative_to(root)),
                    line=block.lineno,
                    snippet=safe_snippet(path, block.lineno),
                ))
    return findings
