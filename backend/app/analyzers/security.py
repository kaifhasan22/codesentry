from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path
import re

from app.analyzers.common import Finding, iter_python_files, safe_snippet, read_source, BoundedFindings

_CREDENTIAL_NAME = re.compile(r"(?:^|_)(?:api_key|password|passwd|client_secret|secret_key|access_token|auth_token|private_key)$", re.I)
_PLACEHOLDER = re.compile(r"example|dummy|changeme|placeholder|your[_ -]|test[_ -]|replace[_ -]|<[^>]+>|\$\{", re.I)


class _Bindings(ast.NodeVisitor):
    """Conservative lexical bindings; ambiguous/reassigned aliases are unknown."""

    def __init__(self):
        self.names: dict[str, str | None] = {}

    def bind(self, name, value=None):
        self.names[name] = value if name not in self.names else None

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bind(node.id)

    def visit_Import(self, node):
        for alias in node.names:
            self.bind(alias.asname or alias.name.split('.')[0], alias.name if alias.asname else alias.name.split('.')[0])

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.bind(alias.asname or alias.name, f"{node.module}.{alias.name}" if not node.level else None)

    def visit_FunctionDef(self, node):
        self.bind(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Lambda(self, node):
        pass

    visit_ListComp = visit_Lambda
    visit_SetComp = visit_Lambda
    visit_DictComp = visit_Lambda
    visit_GeneratorExp = visit_Lambda


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self, root: Path, path: Path, source: str):
        self.root, self.path, self.source = root, path, source
        self.scopes: list[dict[str, str | None]] = []
        self.scope_kinds: list[str] = []
        self.findings: list[Finding] = BoundedFindings()
        self.secrets: set[str] = set()

    def qualified(self, node):
        if isinstance(node, ast.Name):
            for index in range(len(self.scopes) - 1, -1, -1):
                # Class namespaces are not closures for their methods.
                if self.scope_kinds[index] == "class" and index != len(self.scopes) - 1:
                    continue
                scope = self.scopes[index]
                if node.id in scope:
                    return scope[node.id]
            return f"builtins.{node.id}" if node.id in {"eval", "exec"} else None
        if isinstance(node, ast.Attribute):
            parent = self.qualified(node.value)
            return f"{parent}.{node.attr}" if parent else None
        return None

    def scope(self, body, args=None, kind="function"):
        bindings = _Bindings()
        for node in body:
            bindings.visit(node)
        if args:
            for arg in args.posonlyargs + args.args + args.kwonlyargs:
                bindings.bind(arg.arg)
            for arg in (args.vararg, args.kwarg):
                if arg:
                    bindings.bind(arg.arg)
        self.scopes.append(bindings.names)
        self.scope_kinds.append(kind)
        for node in body:
            self.visit(node)
        self.scopes.pop()
        self.scope_kinds.pop()

    def visit_Module(self, node):
        self.scope(node.body, kind="module")

    def visit_FunctionDef(self, node):
        for value in node.decorator_list + node.args.defaults + [v for v in node.args.kw_defaults if v]:
            self.visit(value)
        self.scope(node.body, node.args)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        self.scope([node.body], node.args)

    def visit_ClassDef(self, node):
        for value in node.decorator_list + node.bases:
            self.visit(value)
        self.scope(node.body, kind="class")

    def visit_ListComp(self, node):
        # Comprehension targets shadow aliases locally, not in the outer scope.
        self.visit(node.generators[0].iter)
        bindings = _Bindings()
        for generator in node.generators:
            bindings.visit(generator.target)
        self.scopes.append(bindings.names)
        self.scope_kinds.append("comprehension")
        for index, generator in enumerate(node.generators):
            if index:
                self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.scopes.pop()
        self.scope_kinds.pop()

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def add(self, node, rule, severity, title, message, fix):
        self.findings.append(Finding(
            category="security", severity=severity, title=title, message=message,
            file_path=self.path.relative_to(self.root).as_posix(), line=node.lineno,
            snippet=safe_snippet(self.path, node.lineno, source=self.source),
            fix_suggestion=fix, rule_id=rule, column=node.col_offset,
        ))

    def visit_Call(self, node):
        name = self.qualified(node.func)
        if name in {"builtins.eval", "builtins.exec"} and node.args and not isinstance(node.args[0], ast.Constant):
            operation = name.split('.')[-1]
            self.add(node, f"security.{operation}", "high", f"Use of {operation}()",
                     f"AST analysis found {operation}() with a non-literal input. If that input is attacker-controlled, it can execute Python code; input trust is not established by this rule.",
                     "Replace dynamic execution with explicit operations or a dispatch table. For literal data, use json.loads or ast.literal_eval with input-size limits; do not pass untrusted text to eval/exec.")
        elif name in {"pickle.load", "pickle.loads", "_pickle.load", "_pickle.loads"}:
            local_round_trip = (
                name.endswith(".loads") and node.args and isinstance(node.args[0], ast.Call)
                and self.qualified(node.args[0].func) in {"pickle.dumps", "_pickle.dumps"}
            )
            # Serialization tests commonly decode bytes produced immediately
            # in-process. This is not an external serialized-input boundary.
            if not local_round_trip:
                self.add(node, "security.pickle", "high", "Potentially unsafe deserialization",
                         f"AST analysis resolved this call to {name}(). Pickle can execute code during deserialization. This is a risk if the input can be supplied or modified by an untrusted party; no exploit is proven here.",
                         "Use JSON plus schema validation for untrusted data. If pickle is required, accept only authenticated data from a trusted producer and prevent untrusted modification before loading.")
        elif name in {"yaml.load", "yaml.load_all", "yaml.unsafe_load", "yaml.unsafe_load_all"}:
            loader = next((k.value for k in node.keywords if k.arg == "Loader"), node.args[1] if len(node.args) > 1 else None)
            loader_name = self.qualified(loader)
            unsafe = "unsafe_load" in name or loader_name in {"yaml.Loader", "yaml.CLoader", "yaml.UnsafeLoader", "yaml.CUnsafeLoader"}
            if unsafe or loader_name not in {"yaml.SafeLoader", "yaml.CSafeLoader"}:
                self.add(node, "security.yaml", "high" if unsafe else "medium", "Review YAML deserialization loader",
                         f"AST analysis found {name}() with {'an unsafe loader' if unsafe else 'a loader not established as SafeLoader'}. Object construction depends on the loader and PyYAML version; untrusted input needs a restricted loader.",
                         "Use yaml.safe_load/safe_load_all or explicitly pass yaml.SafeLoader (CSafeLoader is also supported). Validate the resulting data structure before use.")
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.check_secret(node, node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.check_secret(node, [node.target], node.value)
        self.generic_visit(node)

    def check_secret(self, node, targets, value):
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            return
        literal = value.value
        if len(literal) < 12 or len(set(literal)) < 8 or _PLACEHOLDER.search(literal) or literal.startswith(("http://", "https://")):
            return
        names = [target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else "" for target in targets]
        if not any(_CREDENTIAL_NAME.search(name) for name in names):
            return
        fixture = any(part.lower() in {"test", "tests", "testing", "fixtures", "examples"} for part in self.path.relative_to(self.root).parts) or self.path.name.startswith("test_")
        self.secrets.add(literal)
        self.add(node, "security.hardcoded-credential", "low" if fixture else "high", "Potential hardcoded credential",
                 "AST analysis found a literal assigned to a credential-like name. It may be a placeholder; validity and exposure are not verified." + (" This is in test/example code, so severity is reduced pending verification." if fixture else " A real credential in source may be exposed to repository readers."),
                 "Confirm whether the value is a real credential. If real, revoke/rotate it and load the replacement from a secret store or environment variable. Use an unmistakable dummy value for fixtures.")


def analyze(root: Path, python_files: Sequence[Path] | None = None) -> list[Finding]:
    findings: list[Finding] = BoundedFindings()
    for path in python_files if python_files is not None else iter_python_files(root):
        try:
            source = read_source(path, root)
            tree = ast.parse(source)
        except (OSError, SyntaxError, ValueError):
            continue
        visitor = _SecurityVisitor(root, path, source)
        visitor.visit(tree)
        for finding in visitor.findings:
            for secret in visitor.secrets:
                finding.snippet = finding.snippet.replace(secret, "<redacted credential>")
        findings.extend(visitor.findings)
    return findings
