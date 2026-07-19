"""FastAPI app — the web entry point (Sprint 8).

Topology A: runs on :8000, the TanStack frontend on its own port calls it cross-origin
(CORS enabled). Wraps the proven ragcore core; adds no business logic of its own.

Run:  uv run uvicorn web.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.routes import query as query_routes
from web.routes import upload as upload_routes

app = FastAPI(title="PDF RAG Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # prototype; tighten to the frontend origin for deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_routes.router)
app.include_router(query_routes.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
