"""Versioned comparison identities, separate from within-scan deduplication."""
import ast
from app.analyzers.common import read_source
from collections import Counter, defaultdict
import hashlib
import json

ANALYSIS_VERSION = "quality-v2-identity-v1"


def digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def assign_comparison_keys(root, findings):
    by_file = defaultdict(list)
    for finding in findings:
        by_file[finding.file_path].append(finding)
    for path, items in by_file.items():
        try:
            tree = ast.parse(read_source(root / path, root))
        except (OSError, SyntaxError, ValueError, RecursionError):
            continue  # Explicit legacy fallback, never invent unavailable context.
        locations = defaultdict(list)

        pending = [(tree, ())]
        while pending:
            node, scope = pending.pop()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = (*scope, node.name)
            if hasattr(node, "lineno"):
                locations[node.lineno].append((node, scope))
            pending.extend((child, scope) for child in reversed(list(ast.iter_child_nodes(node))))
        occurrences = Counter()
        for finding in sorted(items, key=lambda f: (f.line or 0, f.column or 0, f.rule_id or "")):
            if not finding.rule_id:
                continue
            candidates = locations.get(finding.line, [])
            if finding.category in {"complexity", "style"}:
                candidates = [(n, s) for n, s in candidates if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            elif finding.category == "security":
                kinds = (ast.Assign, ast.AnnAssign) if finding.rule_id == "security.hardcoded-credential" else (ast.Call,)
                candidates = [(n, s) for n, s in candidates if isinstance(n, kinds) and (finding.column is None or n.col_offset == finding.column)]
            if not candidates:
                continue
            node, scope = candidates[0]
            # A callable remains the same issue as its branches/metric change.
            # Calls/statements are structural AST data: whitespace/comments and
            # line shifts are absent, but changes to source semantics remain visible.
            try:
                anchor = "" if finding.category in {"complexity", "style"} or finding.rule_id.startswith("dead-code.import.") else ast.dump(node, include_attributes=False)
            except RecursionError:
                continue
            base = ("comparison-v1", path, finding.category, finding.rule_id, scope, anchor)
            base_hash = digest(base)
            occurrence = occurrences[base_hash]
            occurrences[base_hash] += 1
            finding.comparison_key = digest((base_hash, occurrence))


def legacy_comparison_key(issue):
    # Historical rows have no rule/AST data. Exclude message/severity/AI text;
    # retain location and normalized title instead of guessing a structural match.
    return digest((issue.category, issue.file_path, issue.line, " ".join(issue.title.split()).casefold()))
