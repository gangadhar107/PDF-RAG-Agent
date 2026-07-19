"""FlashRank reranker (§4.5) — local CPU cross-encoder, no API/wallet needed.

Re-scores each candidate against the full query jointly (unlike independent retrieval
scores), then trims to top_k. Reads the ENRICHED chunk text (§3.4) — same view the embedder
and answer step see — so section/company/period context informs the rerank.

Model loads lazily & once (module-level cache). Default: ms-marco-MiniLM-L-12-v2 (small, CPU).
"""

from __future__ import annotations

from ragcore.retrieve.hybrid import Candidate

_ranker = None


def _get_ranker():
    global _ranker
    if _ranker is None:
        from flashrank import Ranker
        _ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    return _ranker


class FlashRankReranker:
    def rerank(self, query: str, candidates: list[Candidate], top_k: int) -> list[Candidate]:
        if not candidates:
            return []
        from flashrank import RerankRequest

        # id -> candidate so we can map results back
        passages = [
            {"id": i, "text": c.content, "meta": {}}
            for i, c in enumerate(candidates)
        ]
        results = _get_ranker().rerank(RerankRequest(query=query, passages=passages))
        # results are sorted by score desc; map ids back to candidates
        ordered = [candidates[r["id"]] for r in results]
        return ordered[:top_k]
