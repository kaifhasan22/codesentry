"""Isolated real-source verification. Never run against a populated database.

Scans 1/2 use identical, unmodified Requests source. Scan 3 adds an explicitly
labeled synthetic test file; scan 4 removes it. No finding counts are fabricated.
No source repository code is executed and no git commits are created.
"""
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import hash_password
from app.config import get_settings
from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import Scan, User
from app.services.repository import clone_github_repo
from app.tasks import scan as task


def main():
    settings = get_settings()
    if not settings.database_url.startswith('sqlite:') or settings.anthropic_api_key:
        raise SystemExit('Use an isolated SQLite database with AI disabled.')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit('Refusing to reuse a populated database.')
        db.add(User(email='features@example.com', password_hash=hash_password('FeatureDemo123!')))
        db.commit()

    original = clone_github_repo('https://github.com/psf/requests')
    output = {'repository': 'https://github.com/psf/requests', 'method': 'Real analyzers and scan task, isolated SQLite, API authentication, AI disabled. One bounded clone reused to pin identical source.', 'runs': []}
    scenario = 'baseline'

    def prepare(_url):
        folder = Path(tempfile.mkdtemp(prefix='feature-check-', dir=settings.scan_root))
        root = folder / 'source'
        shutil.copytree(original, root)
        if scenario == 'controlled_add':
            (root / 'codesentry_comparison_fixture.py').write_text(
                '# Synthetic comparison verification only; not upstream Requests code.\n'
                'def codesentry_controlled_example_8d01(untrusted_controlled_input_8d01):\n'
                '    return eval(untrusted_controlled_input_8d01)\n'
            )
        return root

    try:
        with TestClient(app) as client, patch.object(task, 'clone_github_repo', prepare), patch.object(task.run_scan, 'delay', lambda _: None):
            login = client.post('/api/auth/login', data={'username': 'features@example.com', 'password': 'FeatureDemo123!'})
            login.raise_for_status()
            client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
            for scenario in ('baseline', 'same_commit', 'controlled_add', 'controlled_remove'):
                url = 'https://www.github.com/PSF/Requests.git' if scenario == 'same_commit' else output['repository']
                created = client.post('/api/scans', json={'repo_url': url})
                assert created.status_code == 202, created.text
                scan_id = created.json()['scan_id']
                task.run_scan.run(scan_id)
                if scenario == 'controlled_add':
                    # The fixture changes the checkout without creating a commit.
                    # Do not label this synthetic source as the upstream commit.
                    with SessionLocal() as db:
                        db.get(Scan, scan_id).source_commit = None
                        db.commit()
                detail = client.get(f'/api/scans/{scan_id}').json()
                comparison = client.get(f'/api/scans/{scan_id}/comparison').json()
                assert detail['status'] == 'completed'
                assert detail['top_issue_ids'] and detail['hotspots']
                assert all(i['priority_reasons'] for i in detail['issues'])
                output['runs'].append({'scenario': scenario, 'scan_id': scan_id, 'source_commit': detail['source_commit'],
                                       'score': detail['score'], 'findings': len(detail['issues']), 'comparison': comparison,
                                       'top_issue_ids': detail['top_issue_ids'], 'hotspot_count': len(detail['hotspots'])})
            first, same, added, removed = output['runs']
            assert same['source_commit'] == first['source_commit']
            assert not first['comparison']['available']
            assert same['comparison']['new_count'] == same['comparison']['resolved_count'] == 0
            assert same['comparison']['unchanged_count'] == first['findings']
            assert same['comparison']['score_delta'] == same['comparison']['total_delta'] == 0
            assert added['comparison']['new_count'] == 1 and added['comparison']['resolved_count'] == 0
            assert removed['comparison']['new_count'] == 0 and removed['comparison']['resolved_count'] == 1
            assert removed['findings'] == first['findings'] and removed['score'] == first['score']
        Path('/verification/results.json').write_text(json.dumps(output, indent=2) + '\n')
        print(json.dumps(output, indent=2))
    finally:
        shutil.rmtree(original.parent, ignore_errors=True)


if __name__ == '__main__':
    main()
