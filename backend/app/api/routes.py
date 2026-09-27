from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.db import Base, engine, get_db
from app.models import Repo, Scan, User
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    ScanCreateRequest,
    ScanCreateResponse,
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
    run_scan.delay(scan.id)
    return ScanCreateResponse(scan_id=scan.id, status=scan.status)


@router.get("/scans/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.scalar(select(Scan).join(Repo).where(Scan.id == scan_id, Repo.owner_id == user.id))
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanResponse.model_validate({
        "id": scan.id,
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
