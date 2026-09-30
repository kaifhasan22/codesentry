from __future__ import annotations

import shutil
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.tasks.celery_app import celery_app
from celery.signals import task_failure
from billiard.exceptions import TimeLimitExceeded, WorkerLostError, SoftTimeLimitExceeded
from sqlalchemy import select, update

from app.ai.reasoner import review_findings
from app.db import SessionLocal
from app.models import Issue, Repo, Scan, ScanStage, ScanStatus
from app.services.analysis import health_score, run_static_analysis
from app.services.finding_identity import ANALYSIS_VERSION
from app.services.progress import (
    SCAN_HARD_TIME_LIMIT_SECONDS,
    SCAN_SOFT_TIME_LIMIT_SECONDS,
    estimate_ai_remaining,
    estimate_static_remaining,
)
from app.services.repository import (clone_github_repo, scan_workspace_id, cleanup_scan_workspace, git_environment,
    GIT_OPTIONS, RepositoryCloneError, RepositoryCloneTimeoutError, RepositoryResourceError)
from app.services import public_errors as errors
from app.config import get_settings

logger = logging.getLogger(__name__)


def _set_progress(
    db,
    scan: Scan,
    stage: ScanStage,
    estimate: tuple[int, int] | None = None,
) -> None:
    scan.stage = stage.value
    scan.estimated_min_seconds = estimate[0] if estimate else None
    scan.estimated_max_seconds = estimate[1] if estimate else None
    db.commit()


@task_failure.connect(weak=False)
def mark_scan_failed_after_worker_termination(
    sender=None,
    exception=None,
    args=None,
    **_kwargs,
) -> None:
    """Persist terminal status when Celery kills a task child before its finally block."""
    if getattr(sender, "name", None) != run_scan.name:
        return
    scan_id = next((value for value in (args or ()) if isinstance(value, int)), None)
    if scan_id is None or not isinstance(exception, (TimeLimitExceeded, WorkerLostError)):
        return

    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if not scan or scan.status in {ScanStatus.COMPLETED.value, ScanStatus.FAILED.value}:
            return
        scan.status = ScanStatus.FAILED.value
        scan.stage = ScanStage.FAILED.value
        scan.estimated_min_seconds = None
        scan.estimated_max_seconds = None
        if isinstance(exception, TimeLimitExceeded):
            scan.error_message = (
                "Scan exceeded the worker's hard processing limit and was stopped before results were saved. "
                "The analyzer workload needs to be reduced or split."
            )
        else:
            scan.error_message = "The scan worker stopped unexpectedly before results were saved."
        scan.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.error("Scan %s marked failed after Celery worker termination: %s", scan_id, exception)
    except Exception:
        db.rollback()
        logger.exception("Could not persist terminal status for scan %s after worker termination", scan_id)
    finally:
        db.close()
        cleanup_scan_workspace(scan_id)


@celery_app.task(
    bind=True,
    ignore_result=True,
    acks_late=True,
    time_limit=SCAN_HARD_TIME_LIMIT_SECONDS,
    soft_time_limit=SCAN_SOFT_TIME_LIMIT_SECONDS,
)
def run_scan(self, scan_id: int) -> dict:
    db = SessionLocal()
    workdir: Path | None = None
    scan_started = perf_counter()
    workspace_token = scan_workspace_id.set(scan_id)
    claimed = False
    try:
        scan = db.get(Scan, scan_id)
        if not scan:
            return {"scan_id": scan_id, "status": "missing"}

        # Atomic claim: duplicate deliveries and expired queued jobs cannot run
        # twice, overwrite terminal states, or duplicate persisted findings.
        claimed = bool(db.execute(update(Scan).where(Scan.id == scan_id, Scan.status == "queued").values(
            status="running", stage="repository_preparation", started_at=datetime.now(timezone.utc),
            error_message=None, estimated_min_seconds=None, estimated_max_seconds=None)).rowcount)
        db.commit()
        if not claimed:
            return {"scan_id": scan_id, "status": scan.status}
        db.refresh(scan)

        repo = db.get(Repo, scan.repo_id)
        if not repo or not repo.source_url:
            raise ValueError("Repository source is missing")

        stage_started = perf_counter()
        workdir = clone_github_repo(repo.source_url)
        commit = subprocess.run(GIT_OPTIONS + ["-C", str(workdir), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, env=git_environment(workdir.parent))
        scan.source_commit = commit.stdout.strip() if commit.returncode == 0 else None
        scan.analysis_version = ANALYSIS_VERSION
        logger.info("Scan %s stage=clone elapsed=%.2fs", scan_id, perf_counter() - stage_started)
        _set_progress(db, scan, ScanStage.STATIC_ANALYSIS)

        ai_enabled = bool(get_settings().anthropic_api_key)

        def update_workload(file_count: int, source_bytes: int) -> None:
            estimate = estimate_static_remaining(file_count, source_bytes, ai_enabled)
            scan.estimated_min_seconds, scan.estimated_max_seconds = estimate
            db.commit()

        stage_started = perf_counter()
        findings = run_static_analysis(workdir, on_workload=update_workload)
        logger.info("Scan %s stage=static_analysis elapsed=%.2fs findings=%d", scan_id, perf_counter() - stage_started, len(findings))
        _set_progress(
            db,
            scan,
            ScanStage.AI_REVIEW,
            estimate_ai_remaining(len(findings), ai_enabled),
        )
        stage_started = perf_counter()
        ai_reviews = review_findings(findings)
        logger.info("Scan %s stage=ai_review elapsed=%.2fs reviews=%d", scan_id, perf_counter() - stage_started, len(ai_reviews))
        _set_progress(db, scan, ScanStage.FINALIZATION, (2, 10))
        scan.score = health_score(findings)
        scan.status = ScanStatus.COMPLETED.value
        scan.stage = ScanStage.COMPLETE.value
        scan.estimated_min_seconds = 0
        scan.estimated_max_seconds = 0
        scan.finished_at = datetime.now(timezone.utc)

        stage_started = perf_counter()
        for finding in findings:
            review = ai_reviews.get(finding.fingerprint)
            explanation = None
            fix = finding.fix_suggestion
            if review:
                assessment = "Possible false positive; verify context. " if review.is_false_positive else ""
                explanation = f"AI review (advisory): {assessment}{review.explanation}"
                fix = f"{fix or ''}\n\nAI suggestion (verify before applying): {review.fix_suggestion}".strip()
            db.add(Issue(
                scan_id=scan.id,
                fingerprint=finding.fingerprint,
                comparison_key=finding.comparison_key,
                analyzer_metadata={**finding.evidence, "rule_id": finding.rule_id},
                category=finding.category,
                severity=finding.severity,
                title=finding.title,
                message=finding.message,
                file_path=finding.file_path,
                line=finding.line,
                snippet=finding.snippet,
                ai_explanation=explanation,
                fix_suggestion=fix,
            ))
        db.commit()
        logger.info("Scan %s stage=persist elapsed=%.2fs issues=%d", scan_id, perf_counter() - stage_started, len(findings))
        logger.info("Scan %s completed elapsed=%.2fs", scan_id, perf_counter() - scan_started)
        return {"scan_id": scan.id, "status": scan.status, "issues": len(findings)}
    except Exception as exc:
        logger.exception("Scan %s failed after %.2fs", scan_id, perf_counter() - scan_started)
        db.rollback()
        scan = db.get(Scan, scan_id)
        if scan:
            scan.status = ScanStatus.FAILED.value
            scan.stage = ScanStage.FAILED.value
            scan.estimated_min_seconds = None
            scan.estimated_max_seconds = None
            scan.error_message = (
                errors.CLONE_TIMEOUT if isinstance(exc, RepositoryCloneTimeoutError) else
                errors.RESOURCE_ERROR if isinstance(exc, RepositoryResourceError) else
                errors.CLONE_ERROR if isinstance(exc, RepositoryCloneError) else
                errors.SOFT_TIMEOUT if isinstance(exc, (SoftTimeLimitExceeded, TimeoutError)) else errors.GENERIC_ERROR
            )
            scan.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
        if workdir:
            shutil.rmtree(workdir.parent, ignore_errors=True)
        if claimed:
            cleanup_scan_workspace(scan_id)
        scan_workspace_id.reset(workspace_token)
