from fastapi import FastAPI, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.services.http_security import RequestGuards
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.routes import router
from app.config import get_settings
from app.db import Base, engine
from app.services.report_migration import ensure_report_columns

settings = get_settings()
app = FastAPI(title="CodeSentry API", version="0.1.0")
app.add_middleware(RequestGuards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
)
app.include_router(router)

@app.exception_handler(RequestValidationError)
async def validation_error(_request, exc):
    # Pydantic includes the submitted password/token in its default `input` field.
    return JSONResponse(status_code=422, content={"detail": [{"loc": e["loc"], "type": e["type"], "msg": "Invalid request value"} for e in exc.errors()]})

@app.exception_handler(Exception)
async def application_error(_request, _exc):
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred. Please retry."})


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_report_columns(engine)
    # Keep existing installations compatible without requiring a separate migration tool.
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("scans")}
        additions = {
            "stage": "VARCHAR(32) NOT NULL DEFAULT 'queued'",
            "estimated_min_seconds": "INTEGER",
            "estimated_max_seconds": "INTEGER",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE scans ADD COLUMN {name} {definition}"))
        connection.execute(text(
            "UPDATE scans SET stage = CASE status "
            "WHEN 'completed' THEN 'complete' WHEN 'failed' THEN 'failed' "
            "WHEN 'running' THEN 'static_analysis' ELSE 'queued' END "
            "WHERE stage = 'queued' AND status != 'queued'"
        ))


@app.websocket("/ws/scans/{scan_id}")
async def scan_progress_socket(websocket: WebSocket, scan_id: int) -> None:
    # This unused placeholder had no authentication or connection bounds.
    # Progress remains available through the authenticated polling API.
    await websocket.close(code=1008)
