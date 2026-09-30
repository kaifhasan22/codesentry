install:
	python3 -m pip install -r backend/requirements.txt

# Native API/worker targets require shared exported settings and an absolute DB URL.
api:
	uvicorn app.main:app --reload --app-dir backend

worker:
	cd backend && celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO

test:
	cd backend && python3 -m pytest -q

up:
	docker compose up --build

up-d:
	docker compose up --build -d

logs:
	docker compose logs -f api worker
