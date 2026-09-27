from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.db import Base, engine, get_db
from app.models import Issue, Repo, Scan, ScanStatus, User
from app.schemas import (
    RegisterRequest,
    ScanCreateRequest,
    ScanCreateResponse,
    ScanHistoryPage,
    ScanHistoryResponse,
    ScanResponse,
    TokenResponse,
)
from app.services.repository import validate_github_url
from app.tasks.scan import run_scan

router = APIRouter(prefix="/api")


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.email == form_data.username.lower())
    )

    if not user or not verify_password(
        form_data.password,
        user.password_hash,
    ):
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
        scan.error_message = "Scan could not be queued. Please retry."
        scan.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=scan.error_message,
            headers={"Retry-After": "5"},
        ) from exc
    return ScanCreateResponse(scan_id=scan.id, status=scan.status)

@router.get("/scans", response_model=ScanHistoryPage)
def list_scans(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=500),
    scan_status: ScanStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
            score=scan.score,
            error_message=scan.error_message,
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
def get_scan(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.scalar(select(Scan).join(Repo).where(Scan.id == scan_id, Repo.owner_id == user.id))
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanResponse.model_validate({
        "id": scan.id,
        "repo_url": scan.repo.source_url,
        "status": scan.status,
        "score": scan.score,
        "error_message": scan.error_message,
        "started_at": scan.started_at,
        "finished_at": scan.finished_at,
        "issues": scan.issues,
    })


@router.get("/health")
def health():
    return {"status": "ok", "service": "codesentry-api"}
