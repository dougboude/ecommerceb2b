"""
SSE relay sidecar service.

Holds open EventSource connections per user and relays events
published by Django. Runs on TCP (not UDS) because browsers
connect directly via EventSource.

Start with:  uvicorn app:app --host 127.0.0.1 --port 8001
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("sse_service")
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SERVICE_TOKEN = os.environ.get("SSE_SERVICE_TOKEN", "dev-token-change-me")
STREAM_SECRET = os.environ.get("SSE_STREAM_SECRET", "dev-stream-secret")
TOKEN_TTL = int(os.environ.get("SSE_TOKEN_TTL", "86400"))  # 24h default
HEARTBEAT_INTERVAL = 20  # seconds
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("SSE_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Global state — one set of queues per user
# ---------------------------------------------------------------------------
user_connections: dict[int, set[asyncio.Queue]] = {}

app = FastAPI()

# ---------------------------------------------------------------------------
# CORS — browser on :8000 connects to SSE on :8001
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth middleware — X-Service-Token on all paths except /health and /stream
# ---------------------------------------------------------------------------
@app.middleware("http")
async def check_service_token(request: Request, call_next):
    path = request.url.path
    if path == "/health" or path.startswith("/stream/"):
        return await call_next(request)
    token = request.headers.get("x-service-token", "")
    if token != SERVICE_TOKEN:
        return JSONResponse(status_code=401, content={"error": "invalid token"})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Stream token verification (HMAC-signed query param)
# ---------------------------------------------------------------------------
def _verify_stream_token(user_id: int, token: str) -> bool:
    """Verify an HMAC-signed stream token. Format: timestamp:hmac_hex."""
    try:
        parts = token.split(":")
        if len(parts) != 2:
            return False
        timestamp_str, provided_hmac = parts
        timestamp = int(timestamp_str)
        if time.time() - timestamp > TOKEN_TTL:
            return False
        message = f"{user_id}:{timestamp_str}"
        expected = hmac.new(
            STREAM_SECRET.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, provided_hmac)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PublishRequest(BaseModel):
    user_id: int
    event_type: str
    data: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/publish")
async def publish(req: PublishRequest):
    """Django calls this after creating a message."""
    queues = user_connections.get(req.user_id, set())
    event = f"event: {req.event_type}\ndata: {json.dumps(req.data)}\n\n"
    dead = []
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        queues.discard(q)
    return {"ok": True, "delivered": len(queues) - len(dead)}


@app.get("/stream/{user_id}")
async def stream(user_id: int, token: str = Query(...)):
    """Browser connects here via EventSource."""
    if not _verify_stream_token(user_id, token):
        raise HTTPException(status_code=403, detail="invalid or expired token")

    queue: asyncio.Queue = asyncio.Queue(maxsize=64)

    if user_id not in user_connections:
        user_connections[user_id] = set()
    user_connections[user_id].add(queue)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_INTERVAL
                    )
                    yield event
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            user_connections.get(user_id, set()).discard(queue)
            if user_id in user_connections and not user_connections[user_id]:
                del user_connections[user_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "connected_users": len(user_connections),
        "total_connections": sum(len(q) for q in user_connections.values()),
    }
