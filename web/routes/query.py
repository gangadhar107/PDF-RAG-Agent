"""Query + summary routes.

POST /query          -> answer a question about a doc (rewrite→retrieve→rerank→answer).
GET  /summary/{id}   -> the document summary + its status.
GET  /status/{id}    -> current doc status (for polling if SSE missed).
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ragcore.db.engine import get_session
from ragcore.db.models import Document
from ragcore.query import QueryConfig, query, query_stream

router = APIRouter()


class Turn(BaseModel):
    role: str
    content: str


class QueryBody(BaseModel):
    doc_id: str
    question: str
    history: list[Turn] = []
    retrieval_mode: str = "hybrid"
    reranker: str = "identity"


class SourceOut(BaseModel):
    section: str | None
    page: int | None


class QueryOut(BaseModel):
    text: str
    sources: list[SourceOut]
    notFound: bool
    rewritten: str | None = None


@router.post("/query", response_model=QueryOut)
async def post_query(body: QueryBody) -> QueryOut:
    try:
        did = uuid.UUID(body.doc_id)
    except ValueError as e:
        raise HTTPException(400, "Invalid doc_id") from e

    result = query(
        did, body.question,
        QueryConfig(retrieval_mode=body.retrieval_mode, reranker=body.reranker),
        history=[t.model_dump() for t in body.history],
    )
    return QueryOut(
        text=result.answer,
        sources=[SourceOut(section=s.section, page=s.page) for s in result.sources],
        notFound=result.not_found,
        rewritten=result.rewritten_question,
    )


@router.post("/query/stream")
async def post_query_stream(body: QueryBody) -> StreamingResponse:
    try:
        did = uuid.UUID(body.doc_id)
    except ValueError as e:
        raise HTTPException(400, "Invalid doc_id") from e

    def event_generator():
        generator = query_stream(
            did, body.question,
            QueryConfig(retrieval_mode=body.retrieval_mode, reranker=body.reranker),
            history=[t.model_dump() for t in body.history],
        )
        for event in generator:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/summary/{doc_id}")
async def get_summary(doc_id: str) -> dict:
    with get_session() as s:
        doc = s.get(Document, uuid.UUID(doc_id))
        if doc is None:
            raise HTTPException(404, "Document not found")
        return {
            "doc_id": doc_id,
            "summary": doc.summary_text,
            "summary_status": doc.summary_status,
        }


@router.get("/status/{doc_id}")
async def get_status(doc_id: str) -> dict:
    with get_session() as s:
        doc = s.get(Document, uuid.UUID(doc_id))
        if doc is None:
            raise HTTPException(404, "Document not found")
        return {
            "doc_id": doc_id, "status": doc.status, "filename": doc.filename,
            "error_message": doc.error_message, "summary_status": doc.summary_status,
        }
