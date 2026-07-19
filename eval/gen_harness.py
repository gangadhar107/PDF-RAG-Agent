"""Tier-2 / Tier-3 generation eval (Sprint 5).

Tier-2 (generation ceiling): feed the GOLD evidence_text directly as context, bypassing
retrieval → isolates Groq's reasoning. Answers "if retrieval were perfect, how good is the LLM?"
Tier-3 (end-to-end): real hybrid retrieval → rerank → answer.

Emits per-question error-attribution (§5.2) and the E2E ≈ Retrieval × Generation picture.

Usage:
    uv run python -m eval.gen_harness --docs AMD_2022_10K BOEING_2022_10K --mode hybrid
"""

from __future__ import annotations

import argparse
import json
import uuid

from sqlalchemy import select

from ragcore.config import settings
from ragcore.db.engine import get_session
from ragcore.db.models import Document
from ragcore.generate.answer import generate_answer
from ragcore.llm.gemini_client import embed_query
from ragcore.retrieve.hybrid import Candidate, hybrid_search
from ragcore.retrieve.rerank.base import get_reranker

from eval.attribution import Attribution, summarize
from eval.scoring import score_answer
from eval.scoring.retrieval import gold_pages, is_hit


def load_questions() -> list[dict]:
    return [json.loads(l) for l in open(settings.financebench_questions, encoding="utf-8") if l.strip()]


def _ready_doc(name: str) -> tuple[uuid.UUID, str | None, str | None] | None:
    with get_session() as s:
        row = s.execute(
            select(Document.doc_id, Document.company, Document.fiscal_period)
            .where(Document.filename == f"{name}.pdf", Document.status == "ready")
        ).first()
        return (row[0], row[1], row[2]) if row else None


def gold_candidates(q: dict) -> list[Candidate]:
    """Build pseudo-candidates from gold evidence_text (Tier-2 context)."""
    out = []
    for ev in q.get("evidence", []):
        out.append(Candidate(
            chunk_id=uuid.uuid4(), content=ev.get("evidence_text", ""),
            section=None, page_number=ev.get("evidence_page_num"),
            is_dense=False, is_sparse=False, rrf_score=0.0,
        ))
    return out


def run(docs: list[str], mode: str) -> None:
    questions = load_questions()
    metas = {d: _ready_doc(d) for d in docs}
    ready = {d: m for d, m in metas.items() if m}
    print(f"=== Tier-2/3 eval | mode={mode} | ready docs={list(ready)} ===\n")

    qs = [q for q in questions if q["doc_name"] in ready]
    reranker = get_reranker("identity")
    print(f"scoring {len(qs)} questions (Tier-2 gold-evidence + Tier-3 end-to-end)...\n", flush=True)

    t2_correct = t3_correct = 0
    attrs: list[Attribution] = []
    rows = []

    with get_session() as s:
        for q in qs:
            doc_id, company, period = ready[q["doc_name"]]
            gold_ans = q["answer"]
            gold = gold_pages(q.get("evidence", []))

            # --- Tier 2: gold evidence as context ---
            t2 = generate_answer(q["question"], gold_candidates(q),
                                 company=company, fiscal_period=period)
            t2_ok, _ = score_answer(q["question"], gold_ans, t2.text, t2.not_found)
            t2_correct += t2_ok

            # --- Tier 3: real retrieval -> rerank -> answer ---
            qv = embed_query(q["question"])
            cands = hybrid_search(s, doc_id, qv, q["question"], mode=mode,
                                  top_n=settings.retrieval_top_n_each)
            top6 = reranker.rerank(q["question"], cands, settings.rerank_top_k)
            t3 = generate_answer(q["question"], top6, company=company, fiscal_period=period)
            t3_ok, method = score_answer(q["question"], gold_ans, t3.text, t3.not_found)
            t3_correct += t3_ok

            attrs.append(Attribution(
                retrieval_hit=is_hit(cands, gold),
                in_top6=is_hit(top6, gold),
                answer_correct=t3_ok,
            ))
            rows.append((q["financebench_id"][:20], t2_ok, t3_ok, method[:22]))
            print(f"  [{len(rows):2}/{len(qs)}] {q['financebench_id'][:18]:18} "
                  f"T2={'Y' if t2_ok else '.'} T3={'Y' if t3_ok else '.'}", flush=True)

    n = len(qs)
    print("financebench_id       T2  T3  method")
    for fid, a, b, m in rows:
        print(f"  {fid:20} {'Y' if a else '.'}   {'Y' if b else '.'}   {m}")
    print(f"\n=== RESULTS (n={n}, mode={mode}) ===")
    print(f"  Tier-2 (gold evidence)  answer accuracy: {t2_correct}/{n} = {100*t2_correct//n}%")
    print(f"  Tier-3 (end-to-end)     answer accuracy: {t3_correct}/{n} = {100*t3_correct//n}%")
    print(f"  attribution: {summarize(attrs)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", nargs="+", required=True)
    ap.add_argument("--mode", default="hybrid", choices=["hybrid", "vector_only", "bm25_only"])
    args = ap.parse_args()
    run(args.docs, args.mode)


if __name__ == "__main__":
    main()
