"""Error-attribution triple (§5.2).

Per question, per config: {retrieval_hit, in_top6_after_rerank, answer_correct}
→ localizes each failure to retrieval / reranker / generation, and flags SUSPICIOUS PASS
(correct answer without gold evidence in context — possible hallucination).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attribution:
    retrieval_hit: bool      # gold evidence in top-20
    in_top6: bool            # gold evidence survived to top-6
    answer_correct: bool

    @property
    def diagnosis(self) -> str:
        r, t, a = self.retrieval_hit, self.in_top6, self.answer_correct
        if a and not t:
            return "SUSPICIOUS_PASS"      # correct w/o gold in top-6 (hallucination? dup? metric FN)
        if r and t and a:
            return "success"
        if not r:
            return "retrieval_miss"
        if r and not t:
            return "reranker_buried"
        if r and t and not a:
            return "generation_failure"
        return "unknown"


def summarize(attrs: list[Attribution]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in attrs:
        counts[a.diagnosis] = counts.get(a.diagnosis, 0) + 1
    return counts
