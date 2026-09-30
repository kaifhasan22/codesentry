from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
import os
import stat

from app.services.redaction import redact
from app.services.repository import RepositoryResourceError
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "virtualenv",
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", ".cache", "site-packages",
    "dist", "build", "target", "coverage", "htmlcov", "vendor", "vendors",
    "third_party", "third-party", "generated",
}
MAX_PYTHON_FILES = 5_000
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_SOURCE_BYTES = 100_000_000
MAX_DIRECTORIES = 20_000
SEVERITY_ORDER = {name: rank for rank, name in enumerate(("critical", "high", "medium", "low", "info"))}


class BoundedFindings(list):
    """Stop pathological finding growth before persistence and AI enrichment."""
    def append(self, finding):
        if len(self) >= 50_000:
            raise RepositoryResourceError()
        super().append(finding)

    def extend(self, findings):
        for finding in findings:
            self.append(finding)


@dataclass(slots=True)
class Finding:
    category: str
    severity: str
    title: str
    message: str
    file_path: str
    line: int | None = None
    snippet: str | None = None
    fix_suggestion: str | None = None
    rule_id: str | None = None
    column: int | None = None
    evidence: dict = field(default_factory=dict)
    comparison_key: str | None = None

    def __post_init__(self) -> None:
        self.severity = self.severity.strip().lower()
        if self.severity not in SEVERITY_ORDER:
            raise ValueError(f"Unknown finding severity: {self.severity}")
        path = Path(self.file_path)
        if path.is_absolute() or any(p in {"..", ".git"} for p in path.parts) or "\\" in self.file_path or any(ord(c) < 32 for c in self.file_path):
            raise ValueError("Finding path must be repository relative")
        self.file_path = path.as_posix()
        self.message = redact(self.message[:8000])
        self.snippet = redact((self.snippet or "")[:4000]) or None
        self.fix_suggestion = redact((self.fix_suggestion or "")[:4000]) or None
        self.title = self.title[:255]

    @property
    def fingerprint(self) -> str:
        # Rule identity is independent of wording and AI enrichment. Keep the
        # legacy identity for integrations that don't supply a rule identifier.
        raw = (
            f"{self.category}|{self.rule_id}|{self.file_path}|{self.line}|{self.column}"
            if self.rule_id else
            f"{self.category}|{self.title}|{self.file_path}|{self.line}|{self.message}"
        ).encode()
        return hashlib.sha256(raw).hexdigest()


def iter_python_files(root: Path):
    """Walk source files without descending into generated or vendored trees.

    Limits bound work on unusually large or adversarial repositories. Oversized
    repositories are partially scanned rather than making the worker unbounded.
    """
    if root.is_symlink():
        raise OSError("Symlink scan root is not allowed")
    file_count = 0
    total_bytes = 0
    directory_count = 0
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        directory_count += 1
        if directory_count > MAX_DIRECTORIES:
            logger.warning("Python source scan directory limit reached under %s", root)
            return
        directories[:] = sorted(
            name for name in directories
            if name not in IGNORED_DIRECTORIES and not (Path(current) / name).is_symlink()
        )
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = Path(current) / filename
            try:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or path.is_symlink():
                    continue
                size = info.st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                logger.debug("Skipping oversized Python file %s (%d bytes)", path, size)
                continue
            if file_count >= MAX_PYTHON_FILES or total_bytes + size > MAX_TOTAL_SOURCE_BYTES:
                logger.warning(
                    "Python source scan limit reached at %d files and %d bytes under %s",
                    file_count, total_bytes, root,
                )
                return
            file_count += 1
            total_bytes += size
            yield path


def read_source(path: Path, root: Path) -> str:
    """Open every component relative to a trusted root without following links.

    A bounded read and regular-file check also reject FIFOs/devices and files
    swapped between inventory and analysis. No repository code is imported.
    """
    relative = path.relative_to(root)
    if not relative.parts or any(p in {"..", ".git"} for p in relative.parts):
        raise OSError("Source path escapes scan root")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    directory = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                raise OSError("Source is not a bounded regular file")
            content = handle.read(MAX_FILE_BYTES + 1)
            if len(content) > MAX_FILE_BYTES:
                raise OSError("Source size limit exceeded")
            return content.decode("utf-8", errors="replace")
    finally:
        os.close(directory)


def safe_snippet(path: Path, line: int | None, radius: int = 2, *, source: str | None = None) -> str | None:
    if line is None:
        return None
    try:
        lines = (source if source is not None else read_source(path, path.parent)).splitlines()
        start = max(0, line - 1 - radius)
        end = min(len(lines), line + radius)
        return redact("\n".join(f"{i + 1:>4} | {lines[i][:500]}" for i in range(start, end)))
    except OSError:
        return None
