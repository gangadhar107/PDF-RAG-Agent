"""Repository layer — DB reads/writes for documents & chunks.

Keeps SQL/ORM out of the pipeline code. The hybrid RRF retrieval query is added here
in Sprint 4; Sprint 2 only needs document create + chunk bulk-insert + helpers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ragcore.db.models import Chunk, Document
from ragcore.ingest.chunk import ChunkData


# --- documents --------------------------------------------------------------
def create_document(session: Session, filename: str, status: str = "validating") -> Document:
    doc = Document(filename=filename, status=status)
    session.add(doc)
    session.flush()  # populate doc_id
    return doc


def get_document(session: Session, doc_id: uuid.UUID) -> Document | None:
    return session.get(Document, doc_id)


def set_status(session: Session, doc_id: uuid.UUID, status: str,
               error_message: str | None = None) -> None:
    doc = session.get(Document, doc_id)
    if doc:
        doc.status = status
        if error_message is not None:
            doc.error_message = error_message


def set_document_meta(session: Session, doc_id: uuid.UUID, *,
                      page_count: int | None = None, markdown_path: str | None = None,
                      company: str | None = None, fiscal_period: str | None = None) -> None:
    doc = session.get(Document, doc_id)
    if not doc:
        return
    if page_count is not None:
        doc.page_count = page_count
    if markdown_path is not None:
        doc.markdown_path = markdown_path
    if company is not None:
        doc.company = company
    if fiscal_period is not None:
        doc.fiscal_period = fiscal_period


def delete_document(session: Session, doc_id: uuid.UUID) -> None:
    """Hard-delete (chunks cascade). Used by the reupload cleanup path."""
    session.execute(delete(Document).where(Document.doc_id == doc_id))


# --- summary ----------------------------------------------------------------
def set_summary(session: Session, doc_id: uuid.UUID, *, text: str | None = None,
                status: str, model: str | None = None) -> None:
    doc = session.get(Document, doc_id)
    if not doc:
        return
    doc.summary_status = status
    if text is not None:
        doc.summary_text = text
    if model is not None:
        doc.summary_model = model
    if status == "completed":
        doc.summary_generated_at = datetime.now(timezone.utc)


# --- chunks -----------------------------------------------------------------
def insert_chunks(session: Session, doc_id: uuid.UUID, chunks: list[ChunkData]) -> int:
    """Bulk-insert chunks (RAW content; embedding filled later in Sprint 3)."""
    session.add_all([
        Chunk(
            doc_id=doc_id,
            chunk_index=c.chunk_index,
            content=c.content,
            page_number=c.page_number,
            section=c.section,
            token_count=c.token_count,
        )
        for c in chunks
    ])
    return len(chunks)


def count_chunks(session: Session, doc_id: uuid.UUID) -> int:
    return session.execute(
        select(func.count()).select_from(Chunk).where(Chunk.doc_id == doc_id)
    ).scalar_one()
