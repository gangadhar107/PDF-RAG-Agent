"""Hybrid retrieval — dense + sparse + RRF in a single SQL CTE (§3.4, §4.1-4.4).

One round-trip: pgvector cosine (dense) UNION tsvector ts_rank_cd (sparse), fused by
Reciprocal Rank Fusion. `retrieval_mode` (§4.3) selects hybrid | vector_only | bm25_only.
Returns fused top-N candidates; the reranker (Sprint 6) trims to top-6 downstream.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from ragcore.config import settings


@dataclass
class Candidate:
    chunk_id: uuid.UUID
    content: str
    section: str | None
    page_number: int | None
    is_dense: bool
    is_sparse: bool
    rrf_score: float


# Single-query hybrid: dense + sparse ranked lists → RRF fuse. Parameterized by mode.
# Sparse uses OR semantics: plainto_tsquery ANDs all terms, which returns 0 rows for a
# long natural-language question (every word must appear). We rewrite &->| so a chunk
# matching ANY query term ranks, ordered by ts_rank_cd (more shared terms = higher).
_HYBRID_SQL = text("""
WITH tsq AS (
    SELECT replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery AS q
),
dense AS (
    SELECT chunk_id,
           row_number() OVER (ORDER BY embedding <=> CAST(:qv AS vector)) AS rnk
    FROM chunks
    WHERE doc_id = :doc_id AND embedding IS NOT NULL AND :use_dense
    ORDER BY embedding <=> CAST(:qv AS vector)
    LIMIT :top_n
),
sparse AS (
    SELECT c.chunk_id,
           row_number() OVER (
             ORDER BY ts_rank_cd(c.content_tsv, tsq.q) DESC
           ) AS rnk
    FROM chunks c, tsq
    WHERE c.doc_id = :doc_id
      AND :use_sparse
      AND c.content_tsv @@ tsq.q
    ORDER BY ts_rank_cd(c.content_tsv, tsq.q) DESC
    LIMIT :top_n
),
fused AS (
    SELECT chunk_id,
           SUM(score) AS rrf_score,
           bool_or(src = 'dense')  AS is_dense,
           bool_or(src = 'sparse') AS is_sparse
    FROM (
        SELECT chunk_id, 1.0 / (:rrf_k + rnk) AS score, 'dense'  AS src FROM dense
        UNION ALL
        SELECT chunk_id, 1.0 / (:rrf_k + rnk) AS score, 'sparse' AS src FROM sparse
    ) u
    GROUP BY chunk_id
)
SELECT c.chunk_id, c.content, c.section, c.page_number,
       f.is_dense, f.is_sparse, f.rrf_score
FROM fused f JOIN chunks c ON c.chunk_id = f.chunk_id
ORDER BY f.rrf_score DESC
LIMIT :top_n
""")


def hybrid_search(
    session: Session,
    doc_id: uuid.UUID,
    query_vector: list[float],
    query_text: str,
    *,
    mode: str = "hybrid",
    top_n: int | None = None,
) -> list[Candidate]:
    """Return fused top-N candidates for a doc. mode: hybrid|vector_only|bm25_only."""
    top_n = top_n or settings.retrieval_top_n_each
    use_dense = mode in ("hybrid", "vector_only")
    use_sparse = mode in ("hybrid", "bm25_only")

    rows = session.execute(_HYBRID_SQL, {
        "qv": str(query_vector),
        "q": query_text,
        "doc_id": str(doc_id),
        "rrf_k": settings.rrf_k,
        "top_n": top_n,
        "use_dense": use_dense,
        "use_sparse": use_sparse,
    }).fetchall()

    return [
        Candidate(
            chunk_id=r.chunk_id, content=r.content, section=r.section,
            page_number=r.page_number, is_dense=r.is_dense,
            is_sparse=r.is_sparse, rrf_score=float(r.rrf_score),
        )
        for r in rows
    ]
