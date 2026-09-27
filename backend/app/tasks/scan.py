from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from app.tasks.celery_app import celery_app
from sqlalchemy import select

from app.ai.reasoner import review_findings
from app.db import SessionLocal
from app.models import Issue, Repo, Scan, ScanStatus
from app.services.analysis import health_score, run_static_analysis
from app.services.repository import clone_github_repo


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    acks_late=True,
    time_limit=300,
    soft_time_limit=270,
)
def run_scan(self, scan_id: int) -> dict:
    db = SessionLocal()
    workdir: Path | None = None
    try:
        scan = db.get(Scan, scan_id)
        if not scan:
            return {"scan_id": scan_id, "status": "missing"}

        scan.status = ScanStatus.RUNNING.value
        scan.started_at = datetime.now(timezone.utc)
        db.commit()

        repo = db.get(Repo, scan.repo_id)
        if not repo or not repo.source_url:
            raise ValueError("Repository source is missing")

        workdir = clone_github_repo(repo.source_url)
        findings = run_static_analysis(workdir)
        ai_reviews = review_findings(findings)
        scored_findings = [replace(f, severity=ai_reviews[f.fingerprint].severity) if f.fingerprint in ai_reviews else f for f in findings]
        scan.score = health_score(scored_findings)
        scan.status = ScanStatus.COMPLETED.value
        scan.finished_at = datetime.now(timezone.utc)

        for finding in findings:
            db.add(Issue(
                scan_id=scan.id,
                fingerprint=finding.fingerprint,
                category=finding.category,
                severity=ai_reviews[finding.fingerprint].severity if finding.fingerprint in ai_reviews else finding.severity,
                title=finding.title,
                message=finding.message,
                file_path=finding.file_path,
                line=finding.line,
                snippet=finding.snippet,
                ai_explanation=ai_reviews.get(finding.fingerprint).explanation if finding.fingerprint in ai_reviews else None,
                fix_suggestion=ai_reviews.get(finding.fingerprint).fix_suggestion if finding.fingerprint in ai_reviews else None,
            ))
        db.commit()
        return {"scan_id": scan.id, "status": scan.status, "issues": len(findings)}
    except Exception as exc:
        db.rollback()
        scan = db.get(Scan, scan_id)
        if scan:
            scan.status = ScanStatus.FAILED.value
            scan.error_message = str(exc)[:2000]
            scan.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
        if workdir:
            shutil.rmtree(workdir.parent, ignore_errors=True)
