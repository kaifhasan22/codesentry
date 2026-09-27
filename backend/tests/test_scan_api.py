from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.api.routes import router
from app.auth import get_current_user
from app.db import Base, get_db
from app.models import Issue, Repo, Scan, User


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    user = User(id=1, email="owner@example.com", password_hash="test")
    other_user = User(id=2, email="other@example.com", password_hash="test")
    db.add_all([user, other_user])
    db.flush()

    repos = [
        Repo(owner_id=1, name="owner/old", source_url="https://github.com/owner/old"),
        Repo(owner_id=1, name="owner/new", source_url="https://github.com/owner/new"),
        Repo(owner_id=2, name="other/private", source_url="https://github.com/other/private"),
    ]
    db.add_all(repos)
    db.flush()
    scans = [
        Scan(repo_id=repos[0].id, status="completed", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        Scan(repo_id=repos[1].id, status="failed", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        Scan(repo_id=repos[2].id, status="completed", created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]
    db.add_all(scans)
    db.flush()
    db.add(
        Issue(
            scan_id=scans[0].id,
            fingerprint="f" * 64,
            category="security",
            severity="high",
            title="Unsafe call",
            message="Unsafe call found",
            file_path="sample.py",
        )
    )
    db.commit()
    db.close()

    test_app = FastAPI()
    test_app.include_router(router)

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    test_app.dependency_overrides[get_db] = override_db
    test_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)

    with TestClient(test_app) as client:
        yield client, TestingSession

    test_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_scan_history_is_user_scoped_and_reports_pagination_and_issue_count(api_client):
    client, _ = api_client

    response = client.get("/api/scans?limit=1&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["repo_url"] == "https://github.com/owner/new"
    assert response.headers["x-total-count"] == "2"

    next_page = client.get("/api/scans?limit=1&offset=1")
    assert next_page.json()["items"][0]["repo_url"] == "https://github.com/owner/old"
    assert next_page.json()["items"][0]["issue_count"] == 1


def test_scan_history_can_filter_status_and_reject_invalid_status(api_client):
    client, _ = api_client

    response = client.get("/api/scans?status=failed")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == "failed"

    invalid = client.get("/api/scans?status=unknown")
    assert invalid.status_code == 422


def test_scan_detail_includes_repository_url(api_client):
    client, _ = api_client

    response = client.get("/api/scans/1")

    assert response.status_code == 200
    assert response.json()["repo_url"] == "https://github.com/owner/old"


def test_enqueue_failure_marks_scan_failed_and_returns_retryable_error(api_client, monkeypatch):
    client, TestingSession = api_client

    def fail_enqueue(_scan_id):
        raise RuntimeError("broker details should not be exposed")

    monkeypatch.setattr(routes.run_scan, "delay", fail_enqueue)
    response = client.post(
        "/api/scans",
        json={"repo_url": "https://github.com/owner/new"},
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json()["detail"] == "Scan could not be queued. Please retry."

    with TestingSession() as db:
        failed_scan = (
            db.query(Scan)
            .filter(Scan.error_message == "Scan could not be queued. Please retry.")
            .one()
        )
        assert failed_scan.finished_at is not None
        assert failed_scan.error_message == "Scan could not be queued. Please retry."
