"""Reranker interface (§4.5) — swappable: rerank(query, candidates) -> reranked order.

Sprint 4 ships only the identity placeholder (pass-through). FlashRank / Jina v2 land in
Sprint 6's bake-off. The reranker reads the ENRICHED chunk text (§3.4).
"""

from __future__ import annotations

from typing import Protocol

from ragcore.retrieve.hybrid import Candidate


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[Candidate], top_k: int) -> list[Candidate]: ...


def get_reranker(name: str) -> Reranker:
    if name in ("identity", "none"):
        from ragcore.retrieve.rerank.identity import IdentityReranker
        return IdentityReranker()
    if name == "flashrank":
        from ragcore.retrieve.rerank.flashrank_reranker import FlashRankReranker
        return FlashRankReranker()
    raise ValueError(f"Unknown reranker: {name!r}")
