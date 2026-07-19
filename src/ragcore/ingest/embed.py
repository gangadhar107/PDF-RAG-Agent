"""Embedding + indexing (Sprint 3).

For each stored chunk: reconstruct the ENRICHED text (§3.4) — RAW content prefixed with
section + company/period — embed it (Gemini, doc intent, 1536-dim), and write the vector.

Enrichment is reconstructed at embed time and NEVER stored in `content` (which stays raw
for the sparse index). Per-chunk progress is emitted for the §2.2a embedding % bar.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from ragcore.config import settings
from ragcore.db.models import Chunk, Document
from ragcore.llm.gemini_client import TASK_DOCUMENT, embed_one

ProgressCb = Callable[[int, int], None]  # (done, total)

_COMMIT_EVERY = 25  # incremental commit cadence (resumability vs. round-trips)


def build_enriched_text(content: str, section: str | None,
                        company: str | None, fiscal_period: str | None) -> str:
    """Reconstruct the §3.4 enrichment prefix + raw content. Null fields are omitted."""
    lines: list[str] = []
    if section:
        lines.append(f"Section: {section}")
    ctx = " | ".join(x for x in (
        f"Company: {company}" if company else "",
        f"Period: {fiscal_period}" if fiscal_period else "",
    ) if x)
    if ctx:
        lines.append(ctx)
    lines.append(content)
    return "\n".join(lines)


def embed_document(session: Session, doc_id: uuid.UUID,
                   progress: ProgressCb | None = None) -> int:
    """Embed & store vectors for every UN-embedded chunk of a document.

    RESUMABLE: only fetches chunks whose embedding IS NULL, and commits incrementally
    (every _COMMIT_EVERY chunks). So a mid-doc quota 429 keeps the vectors already written —
    re-running resumes where it left off instead of starting over. Returns count embedded
    this call.
    """
    doc = session.get(Document, doc_id)
    if doc is None:
        raise ValueError(f"Document not found: {doc_id}")

    chunks = list(session.execute(
        select(Chunk).where(Chunk.doc_id == doc_id, Chunk.embedding.is_(None))
        .order_by(Chunk.chunk_index)
    ).scalars())
    total = len(chunks)
    if total == 0:
        return 0

    def _embed(chunk: Chunk) -> tuple[uuid.UUID, list[float]]:
        text = build_enriched_text(chunk.content, chunk.section, doc.company, doc.fiscal_period)
        return chunk.chunk_id, embed_one(text, TASK_DOCUMENT)

    done = 0
    with ThreadPoolExecutor(max_workers=settings.embed_concurrency) as pool:
        for chunk_id, vector in pool.map(_embed, chunks):
            session.get(Chunk, chunk_id).embedding = vector
            done += 1
            if done % _COMMIT_EVERY == 0:
                session.commit()  # persist progress so a later 429 doesn't lose it
            if progress:
                progress(done, total)

    session.commit()
    return done
