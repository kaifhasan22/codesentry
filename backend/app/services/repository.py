from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status
from git import Repo as GitRepo

from app.config import get_settings

GITHUB_RE = re.compile(r"^https://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def validate_github_url(raw_url: str) -> tuple[str, str]:
    parsed = urlparse(raw_url)
    settings = get_settings()
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in settings.allowed_github_host_set:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only public GitHub HTTPS URLs are supported.")
    match = GITHUB_RE.match(raw_url)
    if not match:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Repository URL must look like https://github.com/owner/repo")
    return match.group(1), match.group(2)


def clone_github_repo(url: str) -> Path:
    validate_github_url(url)
    settings = get_settings()
    Path(settings.scan_root).mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="repo-", dir=settings.scan_root))
    target = root / "source"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        GitRepo.clone_from(url, target, depth=1, no_single_branch=True)
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return target


def extract_zip_safely(upload: UploadFile) -> Path:
    raise NotImplementedError("ZIP ingestion is the next implementation step; GitHub ingestion is the first vertical slice.")
