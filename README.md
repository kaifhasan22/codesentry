# CodeSentry

AI-augmented static analysis for Python repositories. The product goal is not to display every linter warning; it is to identify the small set of findings most likely to matter, explain why, and suggest concrete fixes.

## Current vertical slice

- FastAPI API
- JWT authentication
- PostgreSQL-ready SQLAlchemy models
- Celery + Redis job queue
- GitHub HTTPS URL validation with an allowlist
- Shallow Git clone for analysis
- AST-based security checks
- Radon complexity checks
- Vulture dead-code checks
- Custom maintainability check
- 0-100 deterministic health score
- Persisted scan + issue results
- Analyzer failure isolation
- Celery soft/hard time limits
- Optional Claude Sonnet 5 enrichment with structured output and graceful fallback
- Working React scan/auth dashboard with polling

The first version intentionally supports **Python repositories only**.

## Run locally

### With Docker

```bash
docker compose up --build
```

API: http://localhost:8000/docs

### Without Docker

Install Python dependencies from `backend/requirements.txt`, set `DATABASE_URL=sqlite:///./codesentry.db`, start Redis, then run:

```bash
uvicorn app.main:app --reload --app-dir backend
cd backend && celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO
```

## API flow

1. `POST /api/auth/register`
2. `POST /api/auth/login`
3. `POST /api/scans` with `{"repo_url":"https://github.com/owner/repo"}`
4. Poll `GET /api/scans/{id}` until `completed` or `failed`.

## Roadmap

1. Secure ZIP upload with traversal checks and file quotas
2. WebSocket scan progress backed by Redis pub/sub
3. Dependency auditing + richer Bandit/Pylint integrations
4. AST-based duplicate-code detection
5. File-tree/category breakdowns and a polished issue detail experience
6. PDF report + demo deployment

## Important MVP boundary

The system currently analyzes only Python source and intentionally does not execute repository code. Treat the current Git clone path as an MVP ingestion path, not a finished production sandbox: add clone timeouts, repository-size/file-count quotas, and container isolation before exposing it publicly.
