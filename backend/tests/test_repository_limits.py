import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from test_scan_api import api_client
from app.models import Scan, Issue
from app.services import git_guard, repository, public_errors as errors
from app.tasks import scan as task

@pytest.mark.parametrize('code,reason', [(125, 'workspace_bytes'), (127, 'workspace_entries')])
def test_clone_guard_reason_and_cleanup(tmp_path, monkeypatch, code, reason):
    monkeypatch.setattr(repository, 'get_settings', lambda: SimpleNamespace(scan_root=str(tmp_path), allowed_github_host_set={'github.com'}))
    monkeypatch.setattr(repository.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=code))
    with pytest.raises(repository.RepositoryResourceError) as raised:
        repository.clone_github_repo('https://github.com/samugit83/redamon')
    assert raised.value.reason == reason
    assert not list(tmp_path.iterdir())

def test_resource_guard_exact_boundaries_and_git_data(tmp_path):
    git = tmp_path / '.git'
    git.mkdir()
    (git / 'pack').write_bytes(b'x' * 10)
    assert git_guard.resource_exit_code(tmp_path, 10, 2) == 0
    assert git_guard.resource_exit_code(tmp_path, 9, 2) == 125
    assert git_guard.resource_exit_code(tmp_path, 10, 1) == 127
    (tmp_path / 'source.py').write_bytes(b'x')
    assert git_guard.resource_exit_code(tmp_path, 10, 3) == 125

def test_supervisor_entry_rejection_exit(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    executable = bin_dir / 'git'
    executable.write_text(f'#!{sys.executable}\nimport time\ntime.sleep(30)\n')
    executable.chmod(0o700)
    root = tmp_path / 'workspace'
    root.mkdir()
    (root / 'one').touch()
    (root / 'two').touch()
    result = subprocess.run([sys.executable, '-I', str(Path(git_guard.__file__)), str(root), '10', '1000', '1', 'https://github.com/a/b'], env={'PATH': str(bin_dir)}, timeout=5)
    assert result.returncode == 127

@pytest.mark.parametrize('exception,message', [
    (repository.RepositoryResourceError('workspace_bytes'), errors.WORKSPACE_BYTES_ERROR),
    (repository.RepositoryResourceError('workspace_entries'), errors.WORKSPACE_ENTRIES_ERROR),
    (repository.RepositoryResourceError(), errors.RESOURCE_ERROR),
    (repository.RepositoryCloneTimeoutError(), errors.CLONE_TIMEOUT),
    (repository.RepositoryCloneError(), errors.CLONE_ERROR),
])
def test_expected_preparation_failure_is_normal_celery_result(api_client, monkeypatch, tmp_path, caplog, exception, message):
    client, sessions = api_client
    with sessions() as db:
        scan = Scan(repo_id=1)
        db.add(scan); db.commit(); sid = scan.id
    monkeypatch.setattr(task, 'SessionLocal', sessions)
    monkeypatch.setattr(repository, 'get_settings', lambda: SimpleNamespace(scan_root=str(tmp_path)))
    def fail(_):
        (tmp_path / f'scan-{sid}' / 'source').mkdir(parents=True)
        raise exception
    monkeypatch.setattr(task, 'clone_github_repo', fail)
    def should_not_run(*args, **kwargs):
        pytest.fail('analysis must not run after failed preparation')
    monkeypatch.setattr(task, 'run_static_analysis', should_not_run)
    with caplog.at_level(logging.INFO):
        result = task.run_scan.apply(args=(sid,), throw=True)
    assert result.successful()
    assert result.result == {'scan_id': sid, 'status': 'failed'}
    detail = client.get(f'/api/scans/{sid}').json()
    assert detail['status'] == detail['stage'] == 'failed'
    assert detail['error_message'] == message
    assert errors.public_scan_error(message) == message
    with sessions() as db:
        scan = db.get(Scan, sid)
        assert scan.finished_at is not None
        assert scan.estimated_min_seconds is scan.estimated_max_seconds is None
        assert not db.scalars(select(Issue).where(Issue.scan_id == sid)).all()
    assert not (tmp_path / f'scan-{sid}').exists()
    assert repository.scan_workspace_id.get() is None
    assert not any(record.exc_info or 'unexpected' in record.message for record in caplog.records)
    assert task.run_scan.run(sid)['status'] == 'failed'

def test_unknown_resource_reason_is_not_public():
    error = repository.RepositoryResourceError('SECRET /private/path')
    assert error.reason is None
    assert 'SECRET' not in str(error)

def test_analysis_resource_failure_is_normal_failed_scan(api_client, monkeypatch, tmp_path):
    client, sessions = api_client
    with sessions() as db:
        scan = Scan(repo_id=1)
        db.add(scan); db.commit(); sid = scan.id
    root = tmp_path / f'scan-{sid}' / 'source'
    root.mkdir(parents=True)
    monkeypatch.setattr(task, 'SessionLocal', sessions)
    monkeypatch.setattr(repository, 'get_settings', lambda: SimpleNamespace(scan_root=str(tmp_path)))
    monkeypatch.setattr(task, 'clone_github_repo', lambda _: root)
    def fail(*args, **kwargs):
        raise repository.RepositoryResourceError()
    monkeypatch.setattr(task, 'run_static_analysis', fail)
    assert task.run_scan.apply(args=(sid,), throw=True).result == {'scan_id': sid, 'status': 'failed'}
    assert client.get(f'/api/scans/{sid}').json()['error_message'] == errors.RESOURCE_ERROR
    assert not root.parent.exists()


def test_failure_persistence_error_still_raises(api_client, monkeypatch):
    _, sessions = api_client
    with sessions() as db:
        scan = Scan(repo_id=1)
        db.add(scan); db.commit(); sid = scan.id
    db = sessions()
    commit = db.commit
    count = 0
    def guarded_commit():
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('failure status could not be saved')
        commit()
    monkeypatch.setattr(db, 'commit', guarded_commit)
    monkeypatch.setattr(task, 'SessionLocal', lambda: db)
    def fail(_):
        raise repository.RepositoryResourceError('workspace_bytes')
    monkeypatch.setattr(task, 'clone_github_repo', fail)
    with pytest.raises(RuntimeError, match='failure status could not be saved'):
        task.run_scan.apply(args=(sid,), throw=True)
