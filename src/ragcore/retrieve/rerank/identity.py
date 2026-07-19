"""Identity reranker (§4.5 placeholder) — preserves fusion order, trims to top_k.

Used in Sprint 4 so the funnel shape (top-20 -> top-6) is real before a real cross-encoder
lands in Sprint 6. Measuring hit-rate @20 (pre-rerank) vs @6 (this cut) quantifies what a
real reranker must beat.
"""

from __future__ import annotations

from ragcore.retrieve.hybrid import Candidate


class IdentityReranker:
    def rerank(self, query: str, candidates: list[Candidate], top_k: int) -> list[Candidate]:
        return candidates[:top_k]
