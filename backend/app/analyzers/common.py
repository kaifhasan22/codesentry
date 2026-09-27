from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Finding:
    category: str
    severity: str
    title: str
    message: str
    file_path: str
    line: int | None = None
    snippet: str | None = None

    @property
    def fingerprint(self) -> str:
        raw = f"{self.category}|{self.title}|{self.file_path}|{self.line}|{self.message}".encode()
        return hashlib.sha256(raw).hexdigest()


def iter_python_files(root: Path):
    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    for path in root.rglob("*.py"):
        if any(part in ignored for part in path.parts):
            continue
        yield path


def safe_snippet(path: Path, line: int | None, radius: int = 2) -> str | None:
    if line is None:
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, line - 1 - radius)
        end = min(len(lines), line + radius)
        return "\n".join(f"{i + 1:>4} | {lines[i]}" for i in range(start, end))
    except OSError:
        return None
