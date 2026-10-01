from __future__ import annotations

from contextvars import ContextVar
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile
from app.config import get_settings

CLONE_TIMEOUT_SECONDS = 120
MAX_REPOSITORY_BYTES = 512 * 1024 * 1024
MAX_REPOSITORY_ENTRIES = 50_000
scan_workspace_id = ContextVar("scan_workspace_id", default=None)

class RepositoryCloneTimeoutError(RuntimeError):
    pass

class RepositoryResourceError(RuntimeError):
    def __init__(self, reason: str | None = None):
        # Only trusted guard identifiers; never expose Git stderr or repo content.
        self.reason = reason if reason in {"workspace_bytes", "workspace_entries"} else None
        super().__init__(self.reason or "repository_resource_limit")

class RepositoryCloneError(RuntimeError):
    pass

# Match the raw string before any URL parser can normalize ports, whitespace,
# encoded hostnames, backslashes or dot segments. A configured host cannot widen this.
GITHUB_RE = re.compile(r"https://(github\.com|www\.github\.com)/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9_.-]{1,100})/?", re.ASCII)

def validate_github_url(raw_url: str) -> tuple[str, str]:
    match = GITHUB_RE.fullmatch(raw_url) if isinstance(raw_url, str) and len(raw_url) <= 200 else None
    if not match or match[1] not in get_settings().allowed_github_host_set:
        raise HTTPException(status_code=422, detail="Repository URL must be a public GitHub HTTPS URL: https://github.com/owner/repo")
    owner, name = match[2], match[3]
    name = name[:-4] if name.endswith(".git") else name
    if owner.endswith('-') or '--' in owner or name in {'', '.', '..'} or name.startswith('-'):
        raise HTTPException(status_code=422, detail="Invalid GitHub owner or repository name.")
    return owner, name

def git_environment(home: Path) -> dict[str, str]:
    # No inherited credentials, proxies, Git overrides, SSH agents or API secrets.
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home),
            "XDG_CONFIG_HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false", "GIT_ALLOW_PROTOCOL": "https",
            "GIT_LFS_SKIP_SMUDGE": "1", "LANG": "C.UTF-8"}

GIT_OPTIONS = ["git", "-c", "core.hooksPath=/dev/null", "-c", "credential.helper=",
               "-c", "http.followRedirects=false", "-c", "protocol.allow=never",
               "-c", "protocol.https.allow=always", "-c", "core.symlinks=false"]

def cleanup_scan_workspace(scan_id: int) -> None:
    if type(scan_id) is not int or scan_id <= 0:
        return
    root = Path(get_settings().scan_root) / f"scan-{scan_id}"
    if root.is_symlink():
        root.unlink(missing_ok=True)
    else:
        shutil.rmtree(root, ignore_errors=True)

def clone_github_repo(url: str) -> Path:
    owner, name = validate_github_url(url)
    canonical = f"https://github.com/{owner}/{name}.git"
    settings = get_settings()
    parent = Path(settings.scan_root)
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    scan_id = scan_workspace_id.get()
    if scan_id is None:
        root = Path(tempfile.mkdtemp(prefix="repo-", dir=parent))
    else:
        root = parent / f"scan-{scan_id}"
        root.mkdir(mode=0o700)  # Fail closed instead of reusing an existing checkout.
    target = root / "source"
    try:
        # The supervisor enforces time/disk limits, kills the entire Git process
        # group, and cleans this workspace if the Celery task child disappears.
        result = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("git_guard.py")), str(root),
             str(CLONE_TIMEOUT_SECONDS), str(MAX_REPOSITORY_BYTES), str(MAX_REPOSITORY_ENTRIES),
             canonical], env=git_environment(root), timeout=CLONE_TIMEOUT_SECONDS + 5,
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if result.returncode == 124:
            raise RepositoryCloneTimeoutError()
        if result.returncode == 125:
            raise RepositoryResourceError("workspace_bytes")
        if result.returncode == 127:
            raise RepositoryResourceError("workspace_entries")
        if result.returncode:
            raise RepositoryCloneError()
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise RepositoryCloneTimeoutError() from exc
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return target

def extract_zip_safely(upload: UploadFile) -> Path:
    raise NotImplementedError("ZIP ingestion is not supported.")
