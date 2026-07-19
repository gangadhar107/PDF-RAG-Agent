"""Upload + SSE progress routes.

POST /upload  -> validate file, create doc row, return doc_id, kick off background ingest.
GET  /events/{doc_id} -> SSE stream of pipeline stage events (§2.2).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ragcore.config import settings
from ragcore.db import repositories as repo
from ragcore.db.engine import get_session
from ragcore.sse.events import bus
from web.background import start_ingest

router = APIRouter()

_UPLOAD_DIR = settings.markdown_dir.parent / "uploads"


@router.post("/upload")
async def upload(file: UploadFile) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only .pdf files are supported.")

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with get_session() as s:
        doc_id = repo.create_document(s, filename=file.filename, status="validating").doc_id

    dest = _UPLOAD_DIR / f"{doc_id}.pdf"
    dest.write_bytes(await file.read())

    loop = asyncio.get_running_loop()
    start_ingest(dest, doc_id, loop)
    return {"doc_id": str(doc_id), "filename": file.filename}


@router.get("/events/{doc_id}")
async def events(doc_id: str) -> StreamingResponse:
    return StreamingResponse(
        bus.stream(doc_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
