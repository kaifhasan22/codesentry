from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from billiard.exceptions import TimeLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.api.routes import router
from app.auth import get_current_user
from app.db import Base, get_db
from app.models import Issue, Repo, Scan, User
from app.tasks import scan as scan_task


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
        Scan(repo_id=repos[0].id, status="completed", stage="complete", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        Scan(repo_id=repos[1].id, status="failed", stage="failed", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        Scan(repo_id=repos[2].id, status="completed", stage="complete", created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
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
    assert response.json()["stage"] == "complete"


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


def test_scan_create_includes_initial_progress_fields(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.setattr(routes.run_scan, "delay", lambda _scan_id: None)

    response = client.post(
        "/api/scans",
        json={"repo_url": "https://github.com/owner/new"},
    )

    assert response.status_code == 202
    assert response.json()["stage"] == "queued"
    assert response.json()["estimated_min_seconds"] is None
    assert response.json()["estimated_max_seconds"] is None


def test_hard_timeout_failure_hook_marks_scan_failed(api_client, monkeypatch):
    _, TestingSession = api_client
    with TestingSession() as db:
        scan = Scan(
            repo_id=1,
            status="running",
            stage="static_analysis",
            started_at=datetime.now(timezone.utc),
        )
        db.add(scan)
        db.commit()
        scan_id = scan.id

    monkeypatch.setattr(scan_task, "SessionLocal", TestingSession)
    scan_task.mark_scan_failed_after_worker_termination(
        sender=scan_task.run_scan,
        exception=TimeLimitExceeded(300),
        args=(scan_id,),
    )

    with TestingSession() as db:
        failed = db.get(Scan, scan_id)
        assert failed.status == "failed"
        assert failed.stage == "failed"
        assert "hard processing limit" in failed.error_message


def test_scan_detail_recovers_stale_running_scan(api_client):
    client, TestingSession = api_client
    with TestingSession() as db:
        scan = Scan(
            repo_id=1,
            status="running",
            stage="static_analysis",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=400),
        )
        db.add(scan)
        db.commit()
        scan_id = scan.id

    response = client.get(f"/api/scans/{scan_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["stage"] == "failed"
    assert "marked failed" in response.json()["error_message"]


@pytest.mark.parametrize("ai_enabled", [False, True])
def test_completed_scan_keeps_analyzer_severity_score_and_fix(api_client, monkeypatch, tmp_path, ai_enabled):
    from app.ai.reasoner import Review
    from app.analyzers.common import Finding
    from app.services.analysis import health_score

    client, TestingSession = api_client
    with TestingSession() as db:
        scan = Scan(repo_id=1, status="queued", stage="queued")
        db.add(scan)
        db.commit()
        scan_id = scan.id
    source = tmp_path / "checkout" / "source"
    source.mkdir(parents=True)
    finding = Finding(category="security", severity="high", title="Analyzer title", message="Analyzer evidence",
                      file_path="app.py", line=1, snippet="1 | eval(data)", fix_suggestion="Use a parser", rule_id="security.eval")
    review = Review(fingerprint=finding.fingerprint, severity="info", confidence=0.9, is_false_positive=True,
                    explanation="Input may be trusted", fix_suggestion="Check the input source")
    stages = []
    set_progress = scan_task._set_progress
    def record_progress(db, scan, stage, estimate=None):
        stages.append(stage.value)
        set_progress(db, scan, stage, estimate)
    monkeypatch.setattr(scan_task, "_set_progress", record_progress)
    monkeypatch.setattr(scan_task, "SessionLocal", TestingSession)
    monkeypatch.setattr(scan_task, "clone_github_repo", lambda _: source)
    monkeypatch.setattr(scan_task, "run_static_analysis", lambda *args, **kwargs: [finding])
    monkeypatch.setattr(scan_task, "review_findings", lambda _: {finding.fingerprint: review} if ai_enabled else {})

    assert scan_task.run_scan.run(scan_id)["status"] == "completed"
    result = client.get(f"/api/scans/{scan_id}").json()
    assert result["score"] == health_score([finding]) == 90
    assert result["stage"] == "complete" and result["estimated_max_seconds"] == 0
    assert stages == ["static_analysis", "ai_review", "finalization"]
    issue = result["issues"][0]
    assert issue["severity"] == "high" and issue["message"] == finding.message
    assert issue["fix_suggestion"].startswith("Use a parser")
    if ai_enabled:
        assert "advisory" in issue["ai_explanation"] and "Possible false positive" in issue["ai_explanation"]
        assert "AI suggestion" in issue["fix_suggestion"]
    else:
        assert issue["ai_explanation"] is None


def test_comparison_authorization_and_noncompleted_states(api_client):
    client, _ = api_client
    assert client.get('/api/scans/3/comparison').status_code == 404
    assert client.get('/api/scans/999/comparison').status_code == 404
    assert client.get('/api/scans/2/comparison').status_code == 409
    assert client.get('/api/scans/1/comparison').json()['available'] is False


def test_comparison_matches_canonical_repo_and_skips_unrelated_other_users_and_failed(api_client):
    client, sessions = api_client
    with sessions() as db:
        previous = db.get(Scan, 1)
        previous.score = 0
        variants = [
            Repo(owner_id=1, name='same', source_url='https://www.github.com/OWNER/OLD.git'),
            Repo(owner_id=2, name='same other user', source_url='https://github.com/owner/old'),
        ]
        db.add_all(variants)
        db.flush()
        for day, repo_id, status in [(4, 2, 'completed'), (5, variants[1].id, 'completed'), (6, 1, 'failed')]:
            db.add(Scan(repo_id=repo_id, status=status, created_at=datetime(2026, 1, day)))
        target = Scan(repo_id=variants[0].id, status='completed', score=10, created_at=datetime(2026, 1, 7))
        db.add(target)
        db.commit()
        target_id = target.id
    response = client.get(f'/api/scans/{target_id}/comparison')
    assert response.status_code == 200
    body = response.json()
    assert body['baseline_scan_id'] == 1
    assert body['score_delta'] == 10 and body['resolved_count'] == 1
    assert body['resolved_issues'][0]['file_path'] == 'sample.py'
    detail = client.get('/api/scans/1').json()
    assert detail['top_issue_ids'] == [detail['issues'][0]['id']]
    assert detail['issues'][0]['priority'] == 'p2'
    assert detail['hotspots'][0]['severity_counts']['high'] == 1


def test_comparison_uses_immediately_preceding_completed_scan_with_id_tiebreak(api_client):
    client, sessions = api_client
    with sessions() as db:
        first = Scan(repo_id=1, status='completed', score=20, created_at=datetime(2026, 2, 1))
        second = Scan(repo_id=1, status='completed', score=30, created_at=datetime(2026, 2, 1))
        third = Scan(repo_id=1, status='completed', score=40, created_at=datetime(2026, 2, 1))
        db.add_all([first, second, third])
        db.commit()
        second_id, third_id = second.id, third.id
    result = client.get(f'/api/scans/{third_id}/comparison').json()
    assert result['baseline_scan_id'] == second_id and result['score_delta'] == 10


def test_comparison_never_selects_itself_or_later_scan_with_server_timestamps(api_client):
    client, sessions = api_client
    with sessions() as db:
        repo = Repo(owner_id=1, name='natural/timestamps', source_url='https://github.com/natural/timestamps')
        db.add(repo)
        db.flush()
        scans = [Scan(repo_id=repo.id, status='completed', score=100) for _ in range(3)]
        db.add_all(scans)
        db.commit()
        ids = [s.id for s in scans]
    assert client.get(f'/api/scans/{ids[0]}/comparison').json()['available'] is False
    assert client.get(f'/api/scans/{ids[1]}/comparison').json()['baseline_scan_id'] == ids[0]
    assert client.get(f'/api/scans/{ids[2]}/comparison').json()['baseline_scan_id'] == ids[1]
