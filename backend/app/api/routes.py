from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Path as PathParam, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, update, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password, DUMMY_HASH
from app.config import get_settings
from app.services.public_errors import public_scan_error, STALE_ERROR, QUEUE_EXPIRED
from app.services.repository import cleanup_scan_workspace
from app.db import Base, engine, get_db
from app.models import Issue, Repo, Scan, ScanStatus, User
from app.services.progress import SCAN_HARD_TIME_LIMIT_SECONDS, SCAN_STALE_AFTER_SECONDS
from app.schemas import (
    RegisterRequest,
    ScanCreateRequest,
    ScanCreateResponse,
    ScanHistoryPage,
    ScanHistoryResponse,
    ScanResponse,
    ScanComparison,
    TokenResponse,
)
from app.services.repository import validate_github_url
from app.services.reporting import issue_payload, report_insights
from app.services.comparison import compare_scans, previous_completed_scan
from app.tasks.scan import run_scan

router = APIRouter(prefix="/api")


def _mark_stale_scans_failed(db: Session, user_id: int) -> None:
    """Recover rows left running if Celery killed a worker before its failure hook ran."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=SCAN_STALE_AFTER_SECONDS)
    rows = list(db.scalars(select(Scan).join(Repo).where(
        Repo.owner_id == user_id,
        or_(and_(Scan.status == "running", Scan.started_at < cutoff),
            and_(Scan.status == "queued", Scan.created_at < now - timedelta(minutes=15))),
    )))
    for scan in rows:
        old_status = scan.status
        changed = db.execute(update(Scan).where(Scan.id == scan.id, Scan.status == old_status).values(
            status="failed", stage="failed", estimated_min_seconds=None, estimated_max_seconds=None,
            error_message=STALE_ERROR if old_status == "running" else QUEUE_EXPIRED, finished_at=now)).rowcount
        if changed and old_status == "running":
            cleanup_scan_workspace(scan.id)
    if rows:
        db.commit()



@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Unable to create account with these details")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to create account with these details") from None
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.email == form_data.username.strip().lower())
    )

    valid = verify_password(form_data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    return TokenResponse(
        access_token=create_access_token(user.id)
    )


@router.post("/scans", response_model=ScanCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_scan(
    payload: ScanCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    url = str(payload.repo_url).rstrip("/")
    owner, name = validate_github_url(url)
    _mark_stale_scans_failed(db, user.id)
    # Serialize per-owner submissions on PostgreSQL before counting active jobs.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    active = db.scalar(select(func.count(Scan.id)).join(Repo).where(Repo.owner_id == user.id, Scan.status.in_(["queued", "running"]))) or 0
    if active >= get_settings().max_active_scans_per_user:
        raise HTTPException(status_code=429, detail="You already have scans in progress. Wait for one to finish.", headers={"Retry-After": "30"})
    repo = Repo(owner_id=user.id, name=f"{owner}/{name}", source_url=url)
    db.add(repo)
    db.flush()
    scan = Scan(repo_id=repo.id)
    db.add(scan)
    db.commit()
    db.refresh(scan)
    try:
        run_scan.delay(scan.id)
    except Exception as exc:
        scan.status = ScanStatus.FAILED.value
        scan.stage = "failed"
        scan.error_message = "Scan could not be queued. Please retry."
        scan.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=scan.error_message,
            headers={"Retry-After": "5"},
        ) from exc
    return ScanCreateResponse(
        scan_id=scan.id,
        status=scan.status,
        stage=scan.stage,
        estimated_min_seconds=scan.estimated_min_seconds,
        estimated_max_seconds=scan.estimated_max_seconds,
    )

@router.get("/scans", response_model=ScanHistoryPage)
def list_scans(
    response: Response,
    offset: int = Query(default=0, ge=0, le=1_000_000),
    limit: int | None = Query(default=500, ge=1, le=500),
    scan_status: ScanStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _mark_stale_scans_failed(db, user.id)
    filters = [Repo.owner_id == user.id]
    if scan_status is not None:
        filters.append(Scan.status == scan_status.value)

    total = db.scalar(
        select(func.count(Scan.id)).join(Repo, Scan.repo_id == Repo.id).where(*filters)
    ) or 0
    rows = db.execute(
        select(
            Scan,
            Repo.source_url,
            func.count(Issue.id).label("issue_count"),
        )
        .join(Repo, Scan.repo_id == Repo.id)
        .outerjoin(Issue, Issue.scan_id == Scan.id)
        .where(*filters)
        .group_by(Scan.id, Repo.source_url)
        .order_by(Scan.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        ScanHistoryResponse(
            id=scan.id,
            repo_url=source_url,
            status=scan.status,
            stage=scan.stage,
            estimated_min_seconds=scan.estimated_min_seconds,
            estimated_max_seconds=scan.estimated_max_seconds,
            score=scan.score,
            error_message=public_scan_error(scan.error_message),
            created_at=scan.created_at,
            started_at=scan.started_at,
            finished_at=scan.finished_at,
            issue_count=issue_count,
        )
        for scan, source_url, issue_count in rows
    ]
    response.headers["X-Total-Count"] = str(total)
    return ScanHistoryPage(items=items, total=total, limit=limit, offset=offset)

@router.get("/scans/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int = PathParam(gt=0, le=2**31 - 1), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _mark_stale_scans_failed(db, user.id)
    scan = db.scalar(select(Scan).join(Repo).where(Scan.id == scan_id, Repo.owner_id == user.id))
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanResponse.model_validate({
        "id": scan.id,
        "repo_url": scan.repo.source_url,
        "status": scan.status,
        "stage": scan.stage,
        "estimated_min_seconds": scan.estimated_min_seconds,
        "estimated_max_seconds": scan.estimated_max_seconds,
        "score": scan.score,
        "error_message": public_scan_error(scan.error_message),
        "started_at": scan.started_at,
        "finished_at": scan.finished_at,
        "issues": [issue_payload(i) for i in scan.issues],
        "source_commit": scan.source_commit,
        **report_insights(scan.issues),
    })


@router.get("/health")
def health():
    return {"status": "ok", "service": "codesentry-api"}


@router.get("/scans/{scan_id}/comparison", response_model=ScanComparison)
def get_scan_comparison(scan_id: int = PathParam(gt=0, le=2**31 - 1), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.scalar(select(Scan).join(Repo).where(Scan.id == scan_id, Repo.owner_id == user.id))
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != ScanStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Comparison is available after this scan completes.")
    return compare_scans(scan, previous_completed_scan(db, scan, user.id))
