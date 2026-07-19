"""Tier-1 retrieval scoring (§5.3).

hit = a retrieved chunk's page_number is within ±tolerance of any gold evidence page.
Page is the finest granularity FinanceBench provides (evidence_page_num). We report
hit-rate at two cut points so their gap = the reranker's contribution:
  - hit@retrieval  (top-20, pre-rerank)
  - hit@rerank     (top-6, post-rerank)
"""

from __future__ import annotations

from ragcore.config import settings
from ragcore.retrieve.hybrid import Candidate


def gold_pages(evidence: list[dict]) -> set[int]:
    """Extract the set of gold evidence page numbers from a FinanceBench question."""
    pages: set[int] = set()
    for ev in evidence or []:
        p = ev.get("evidence_page_num")
        if isinstance(p, int):
            pages.add(p)
        elif isinstance(p, str) and p.isdigit():
            pages.add(int(p))
    return pages


def is_hit(candidates: list[Candidate], gold: set[int],
           tolerance: int | None = None) -> bool:
    """True if any candidate's page is within ±tolerance of any gold page."""
    tol = settings.retrieval_page_tolerance if tolerance is None else tolerance
    if not gold:
        return False
    for c in candidates:
        if c.page_number is None:
            continue
        if any(abs(c.page_number - g) <= tol for g in gold):
            return True
    return False
