from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db import Base, engine

settings = get_settings()
app = FastAPI(title="CodeSentry API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.websocket("/ws/scans/{scan_id}")
async def scan_progress_socket(websocket: WebSocket, scan_id: int) -> None:
    # Realtime Redis pub/sub is the next pass. Keep this endpoint explicit so the frontend
    # can be wired without changing the API shape later.
    await websocket.accept()
    try:
        await websocket.send_json({"scan_id": scan_id, "type": "connected"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
