"""Sprint 6 sweep harness — the resume-metrics table.

Sweeps {reranker} x {retrieval_mode} over the ready docs and reports, per config:
  - hit@20 (pre-rerank retrieval)   — reranker-independent, shown once per mode
  - hit@6  (post-rerank)            — the reranker's effect
  - Tier-3 answer accuracy          — end-to-end
  - attribution counts

Embeddings + generation both use Gemini (billed). FlashRank runs locally (no wallet).

Usage:
    uv run python -m eval.sweep --docs AMD_2022_10K BOEING_2022_10K
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
from ragcore.retrieve.hybrid import hybrid_search
from ragcore.retrieve.rerank.base import get_reranker

from eval.attribution import Attribution, summarize
from eval.scoring import score_answer
from eval.scoring.retrieval import gold_pages, is_hit


def load_questions() -> list[dict]:
    return [json.loads(l) for l in open(settings.financebench_questions, encoding="utf-8") if l.strip()]


def ready_docs(names: list[str]) -> dict[str, tuple[uuid.UUID, str | None, str | None]]:
    out = {}
    with get_session() as s:
        for name in names:
            row = s.execute(
                select(Document.doc_id, Document.company, Document.fiscal_period)
                .where(Document.filename == f"{name}.pdf", Document.status == "ready")
            ).first()
            if row:
                out[name] = (row[0], row[1], row[2])
    return out


def run(docs: list[str], modes: list[str], rerankers: list[str], answer_eval: bool) -> None:
    questions = load_questions()
    ready = ready_docs(docs)
    qs = [q for q in questions if q["doc_name"] in ready]
    print(f"=== Sprint 6 sweep | docs={list(ready)} | n={len(qs)} | "
          f"modes={modes} | rerankers={rerankers} | answers={answer_eval} ===\n")

    # cache query embeddings + candidate lists per (mode, question) so we don't re-embed per reranker
    results = []
    with get_session() as s:
        for mode in modes:
            # retrieval is reranker-independent → compute candidates once per mode
            per_q = []
            for q in qs:
                doc_id, company, period = ready[q["doc_name"]]
                gold = gold_pages(q.get("evidence", []))
                qv = embed_query(q["question"])
                cands = hybrid_search(s, doc_id, qv, q["question"], mode=mode,
                                      top_n=settings.retrieval_top_n_each)
                per_q.append((q, cands, gold, company, period))
            hit20 = sum(is_hit(c, g) for _, c, g, _, _ in per_q)

            for rr_name in rerankers:
                rr = get_reranker(rr_name)
                hit6 = 0
                correct = 0
                attrs = []
                for q, cands, gold, company, period in per_q:
                    top6 = rr.rerank(q["question"], cands, settings.rerank_top_k)
                    h6 = is_hit(top6, gold)
                    hit6 += h6
                    ok = False
                    if answer_eval:
                        ans = generate_answer(q["question"], top6, company=company,
                                              fiscal_period=period)
                        ok, _ = score_answer(q["question"], q["answer"], ans.text, ans.not_found)
                        correct += ok
                    attrs.append(Attribution(is_hit(cands, gold), h6, ok))
                results.append({
                    "mode": mode, "reranker": rr_name, "n": len(qs),
                    "hit20": hit20, "hit6": hit6,
                    "acc": correct if answer_eval else None,
                    "attr": summarize(attrs) if answer_eval else {},
                })
                tag = f"{mode:12} {rr_name:10}"
                acc = f"acc={100*correct//len(qs)}%" if answer_eval else "acc=--"
                print(f"  {tag} hit@20={100*hit20//len(qs):3}% "
                      f"hit@6={100*hit6//len(qs):3}% {acc}", flush=True)

    # final table
    print("\n=== SWEEP RESULTS ===")
    print(f"{'mode':13}{'reranker':11}{'hit@20':8}{'hit@6':7}{'answer_acc':11}")
    for r in results:
        acc = f"{100*r['acc']//r['n']}%" if r["acc"] is not None else "--"
        print(f"{r['mode']:13}{r['reranker']:11}{100*r['hit20']//r['n']:>5}% "
              f"{100*r['hit6']//r['n']:>5}% {acc:>9}")
    if answer_eval:
        print("\nattribution per config:")
        for r in results:
            print(f"  {r['mode']:12} {r['reranker']:10} {r['attr']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", nargs="+", required=True)
    ap.add_argument("--modes", nargs="+", default=["hybrid", "vector_only", "bm25_only"])
    ap.add_argument("--rerankers", nargs="+", default=["identity", "flashrank"])
    ap.add_argument("--no-answers", action="store_true", help="skip Tier-3 answer eval (retrieval only)")
    args = ap.parse_args()
    run(args.docs, args.modes, args.rerankers, answer_eval=not args.no_answers)


if __name__ == "__main__":
    main()
