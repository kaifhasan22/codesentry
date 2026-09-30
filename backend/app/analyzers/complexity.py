from collections.abc import Sequence
from pathlib import Path

from radon.complexity import add_inner_blocks, cc_visit
from radon.visitors import Function

from app.analyzers.common import Finding, iter_python_files, safe_snippet, read_source, BoundedFindings


def analyze(root: Path, python_files: Sequence[Path] | None = None) -> list[Finding]:
    findings: list[Finding] = BoundedFindings()
    for path in python_files if python_files is not None else iter_python_files(root):
        try:
            source = read_source(path, root)
            blocks = add_inner_blocks(cc_visit(source))
        except Exception:
            continue
        for block in blocks:
            # Class averages duplicate method findings and aren't callable
            # complexity. Include nested functions/closures explicitly instead.
            if isinstance(block, Function) and block.complexity >= 15:
                name = f"{block.classname}.{block.name}" if block.classname else block.name
                findings.append(Finding(
                    category="complexity",
                    severity="high" if block.complexity >= 20 else "medium",
                    title=f"High cyclomatic complexity in {name}",
                    message=f"Radon measures cyclomatic complexity {block.complexity} in {name} (review threshold: 15). Numerous independent paths make changes harder to test and increase regression risk.",
                    file_path=str(path.relative_to(root)),
                    line=block.lineno,
                    snippet=safe_snippet(path, block.lineno, source=source),
                    fix_suggestion="Add tests for the existing branches, then extract cohesive decisions into small named functions or use guard clauses. Preserve behavior and remeasure complexity after refactoring.",
                    rule_id="complexity.cyclomatic",
                    column=block.col_offset,
                    evidence={"cyclomatic_complexity": block.complexity},
                ))
    return findings
