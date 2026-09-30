"""Run the real scan task with isolated SQLite persistence and no paid AI calls.

Usage from backend: ANTHROPIC_API_KEY= python -m scripts.benchmark_analysis
The normal clone/file safeguards apply; this direct task run does not exercise
Celery's broker or hard-kill behavior. Repositories are never executed.
"""
from collections import Counter
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import logging
import platform
import subprocess
from time import perf_counter
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base
from app.models import Issue, Repo, Scan, User
from app.services import analysis
from app.tasks import scan as task


def benchmark(url):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        user = User(email="benchmark@example.invalid", password_hash="not-a-login")
        db.add(user)
        db.flush()
        repo = Repo(owner_id=user.id, name=url.rsplit('/', 1)[-1], source_url=url)
        db.add(repo)
        db.flush()
        scan = Scan(repo_id=repo.id, status="queued", stage="queued")
        db.add(scan)
        db.commit()
        scan_id = scan.id

    report = {"repository": url, "tested_at": datetime.now(timezone.utc).isoformat(),
              "ai": "disabled", "analyzers": {}, "stages": [], "python": platform.python_version(),
              "analyzer_versions": {name: version(name) for name in ("radon", "vulture")}}
    original_clone = task.clone_github_repo
    original_static = analysis.run_static_analysis
    original_progress = task._set_progress

    def clone(source_url):
        started = perf_counter()
        root = original_clone(source_url)
        report["clone_seconds"] = round(perf_counter() - started, 3)
        report["commit"] = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        return root

    def timed(analyzer, root, python_files):
        started = perf_counter()
        result = analyzer(root, python_files)
        report["analyzers"][analyzer.__module__.rsplit('.', 1)[-1]] = {
            "seconds": round(perf_counter() - started, 3), "findings": len(result),
        }
        return result

    def static(root, on_workload=None):
        def workload(count, size):
            report["python_files"], report["source_bytes"] = count, size
            if on_workload:
                on_workload(count, size)
        started = perf_counter()
        findings = original_static(root, on_workload=workload)
        report["static_seconds"] = round(perf_counter() - started, 3)
        report["score_breakdown"] = analysis.health_score_breakdown(findings)
        return findings

    def progress(db, scan, stage, estimate=None):
        report["stages"].append({"stage": stage.value, "estimate": estimate})
        original_progress(db, scan, stage, estimate)

    started = perf_counter()
    try:
        with patch.object(task, "SessionLocal", sessions), patch.object(task, "clone_github_repo", clone), \
             patch.object(task, "run_static_analysis", static), patch.object(task, "_set_progress", progress), \
             patch.object(analysis, "_timed_analyzer", timed):
            task.run_scan.run(scan_id)
        report["total_seconds"] = round(perf_counter() - started, 3)
        assert set(report["analyzers"]) == {analyzer.__module__.rsplit('.', 1)[-1] for analyzer in analysis.ANALYZERS}
        with sessions() as db:
            scan = db.get(Scan, scan_id)
            issues = list(db.scalars(select(Issue).where(Issue.scan_id == scan_id)))
            report.update(status=scan.status, stage=scan.stage, health_score=scan.score,
                          findings=len(issues), by_severity=dict(Counter(i.severity for i in issues)),
                          by_category=dict(Counter(i.category for i in issues)))
            report["incomplete_findings"] = sum(not all((i.category, i.severity, i.title, i.message,
                                                         i.file_path, i.line, i.snippet, i.fix_suggestion)) for i in issues)
            report["samples"] = [
                {key: getattr(issue, key) for key in ("category", "severity", "title", "message", "file_path", "line", "snippet", "fix_suggestion")}
                for category in sorted(report["by_category"])
                for issue in [next(i for i in issues if i.category == category)]
            ]
            assert scan.status == "completed" and scan.stage == "complete"
            assert report["incomplete_findings"] == 0
        return report
    finally:
        engine.dispose()


if __name__ == "__main__":
    if get_settings().anthropic_api_key:
        raise SystemExit("Unset ANTHROPIC_API_KEY for this deterministic benchmark.")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repositories", nargs="*", default=["https://github.com/psf/requests", "https://github.com/samugit83/redamon"])
    for url in parser.parse_args().repositories:
        print(json.dumps(benchmark(url), sort_keys=True), flush=True)
