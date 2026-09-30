from collections import Counter, defaultdict

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from app.models import Repo, Scan, ScanStatus
from app.services.finding_identity import legacy_comparison_key
from app.services.reporting import SEVERITIES, issue_payload
from app.services.repository import validate_github_url


def repository_key(url):
    if not url:
        return None
    try:
        owner, name = validate_github_url(url.rstrip('/'))
    except HTTPException:
        return None
    return f"github.com/{owner.lower()}/{name.lower()}"


def previous_completed_scan(db, scan, user_id):
    key = repository_key(scan.repo.source_url)
    if not key or scan.repo.owner_id != user_id:
        return None
    # Existing installations have one Repo row per scan. Canonical identity must
    # work across those rows, always within this user's repository collection.
    repo_ids = [repo.id for repo in db.scalars(select(Repo).where(Repo.owner_id == user_id)) if repository_key(repo.source_url) == key]
    # SQLite's CURRENT_TIMESTAMP omits fractional seconds while bound Python
    # datetimes include them. Numeric timestamp comparison avoids treating a
    # scan as older than itself (or accepting a later ID in the same second).
    sqlite = db.get_bind().dialect.name == "sqlite"
    created = func.julianday(Scan.created_at) if sqlite else Scan.created_at
    current_created = func.julianday(scan.created_at) if sqlite else scan.created_at
    return db.scalar(select(Scan).where(
        Scan.id != scan.id, Scan.repo_id.in_(repo_ids), Scan.status == ScanStatus.COMPLETED.value,
        or_(created < current_created, and_(created == current_created, Scan.id < scan.id)),
    ).order_by(created.desc(), Scan.id.desc()).limit(1))


def compare_scans(current, baseline):
    if baseline is None:
        return {"available": False, "reason": "No previous completed scan of this repository is available."}
    structural = all(i.comparison_key for i in [*current.issues, *baseline.issues]) and bool(current.analysis_version and current.analysis_version == baseline.analysis_version)
    key = (lambda i: i.comparison_key) if structural else legacy_comparison_key
    before, after = defaultdict(list), defaultdict(list)
    for issue in sorted(baseline.issues, key=lambda i: i.id):
        before[key(issue)].append(issue)
    for issue in sorted(current.issues, key=lambda i: i.id):
        after[key(issue)].append(issue)
    new, resolved, unchanged = [], [], []
    for identity in sorted(before.keys() | after.keys()):
        shared = min(len(before[identity]), len(after[identity]))
        unchanged.extend(i.id for i in after[identity][:shared])
        new.extend(i.id for i in after[identity][shared:])
        resolved.extend(issue_payload(i) for i in before[identity][shared:])
    old_counts, new_counts = Counter(i.severity for i in baseline.issues), Counter(i.severity for i in current.issues)
    warnings = []
    if not structural:
        warnings.append("Historical report: matching uses file, line, category, and title. Line moves or title changes can appear new/resolved; message edits do not.")
    if not current.analysis_version or current.analysis_version != baseline.analysis_version:
        warnings.append("Analysis versions differ or are unknown; score and finding changes may reflect rule changes as well as source changes.")
    return {
        "available": True, "baseline_scan_id": baseline.id,
        "baseline_commit": baseline.source_commit, "current_commit": current.source_commit,
        "identity_mode": "structural-v1" if structural else "legacy-location", "warnings": warnings,
        "score_delta": current.score - baseline.score if current.score is not None and baseline.score is not None else None,
        "total_delta": len(current.issues) - len(baseline.issues),
        "severity_delta": {s: new_counts[s] - old_counts[s] for s in SEVERITIES},
        "new_issue_ids": sorted(new), "unchanged_issue_ids": sorted(unchanged),
        "resolved_issues": sorted(resolved, key=lambda i: (i["file_path"], i["line"] or 0, i["id"])),
        "new_count": len(new), "resolved_count": len(resolved), "unchanged_count": len(unchanged),
    }
