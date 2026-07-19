"""Core query entry point (§4.0-4.6) — the second public core signature.

    query(doc_id, question, config, history=None) -> QueryResult

Pipeline: [rewrite follow-up→standalone] → embed(query) → dense+sparse+RRF → rerank
→ assemble enriched context → LLM answer (CoT + citations + refusal) → answer + sources.

UI-free and provider-agnostic. Both the web layer and eval call this; it imports neither.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Generator

from sqlalchemy import select

from ragcore.config import settings
from ragcore.db.engine import get_session
from ragcore.db.models import Document
from ragcore.generate.answer import generate_answer
from ragcore.llm.gemini_client import embed_query
from ragcore.retrieve.hybrid import hybrid_search
from ragcore.retrieve.query_rewrite import rewrite_question
from ragcore.retrieve.rerank.base import get_reranker


@dataclass
class Source:
    section: str | None
    page: int | None


@dataclass
class QueryResult:
    answer: str
    sources: list[Source] = field(default_factory=list)
    not_found: bool = False               # §4.6 refusal path
    rewritten_question: str | None = None  # §4.0 — logged for debugging


@dataclass
class QueryConfig:
    """Query-time knobs — includes the retrieval_mode eval ablation (§4.3)."""
    retrieval_mode: str = "hybrid"        # hybrid | vector_only | bm25_only
    reranker: str = "identity"            # identity | flashrank (Sprint 6: identity wins on FinanceBench)


def query(
    doc_id: uuid.UUID,
    question: str,
    config: QueryConfig | None = None,
    history: list[dict] | None = None,
) -> QueryResult:
    """Answer a question about one document."""
    config = config or QueryConfig()

    # §4.0 — rewrite follow-up into a standalone question (no-op if standalone/no history)
    standalone = rewrite_question(question, history)

    with get_session() as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            return QueryResult(answer="Document not found.", not_found=True)
        company, period = doc.company, doc.fiscal_period

        qv = embed_query(standalone)
        cands = hybrid_search(s, doc_id, qv, standalone, mode=config.retrieval_mode,
                              top_n=settings.retrieval_top_n_each)
        top_k = get_reranker(config.reranker).rerank(standalone, cands, settings.rerank_top_k)

        ans = generate_answer(standalone, top_k, company=company,
                              fiscal_period=period, history=history)

    return QueryResult(
        answer=ans.text,
        sources=[Source(section=sec, page=pg) for sec, pg in ans.sources],
        not_found=ans.not_found,
        rewritten_question=standalone if standalone != question else None,
    )


def query_stream(
    doc_id: uuid.UUID,
    question: str,
    config: QueryConfig | None = None,
    history: list[dict] | None = None,
) -> Generator[dict, None, None]:
    """Stream answer generation for a question about one document."""
    config = config or QueryConfig()

    standalone = rewrite_question(question, history)
    yield {"type": "rewritten", "text": standalone if standalone != question else None}

    with get_session() as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            yield {"type": "done", "text": "Document not found.", "notFound": True, "sources": []}
            return
        company, period = doc.company, doc.fiscal_period

        qv = embed_query(standalone)
        cands = hybrid_search(s, doc_id, qv, standalone, mode=config.retrieval_mode,
                               top_n=settings.retrieval_top_n_each)
        top_k = get_reranker(config.reranker).rerank(standalone, cands, settings.rerank_top_k)

        # Assemble context
        from ragcore.generate.answer import _format_context, _SYSTEM, _parse_answer
        context = _format_context(top_k, company, period)

        user_parts = []
        if history:
            turns = "\n".join(f"{t['role']}: {t['content']}" for t in history[-5:])
            user_parts.append(f"CONVERSATION SO FAR:\n{turns}\n")
        user_parts.append(f"CONTEXT:\n{context}\n\nQUESTION: {standalone}")
        user = "\n".join(user_parts)

        # Start streaming
        from ragcore.llm.generate import generate_stream
        token_stream = generate_stream(_SYSTEM, user, temperature=0.0, max_tokens=2048)

        accumulated = []
        for token in token_stream:
            accumulated.append(token)
            yield {"type": "token", "text": token}

        full_response = "".join(accumulated)
        text, not_found = _parse_answer(full_response)

        yield {
            "type": "done",
            "text": text,
            "notFound": not_found,
            "sources": [{"section": c.section, "page": c.page_number} for c in top_k],
        }
