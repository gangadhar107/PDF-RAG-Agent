"""Tier-1 retrieval eval harness (Sprint 4).

Ingests a subset of FinanceBench docs ONCE, then runs each of their questions through
hybrid retrieval and scores retrieval hit-rate (page-match ±1) at two cut points:
  hit@retrieval (top-20)  vs  hit@rerank (top-6, identity reranker for now).
The gap = future reranker headroom.

Usage:
    uv run python -m eval.harness --docs AMD_2022_10K BOEING_2022_10K --mode hybrid
    uv run python -m eval.harness --max-docs 3 --mode hybrid
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections import defaultdict

from ragcore.config import settings
from ragcore.db.engine import get_session
from ragcore.db.models import Document
from ragcore.llm.gemini_client import embed_query
from ragcore.retrieve.hybrid import hybrid_search
from ragcore.retrieve.rerank.base import get_reranker
from sqlalchemy import select

from eval.ingest_wrapper import ingest_financebench_doc
from eval.scoring.retrieval import gold_pages, is_hit


def load_questions() -> list[dict]:
    return [json.loads(l) for l in open(settings.financebench_questions, encoding="utf-8") if l.strip()]


def _existing_ready_doc(name: str) -> uuid.UUID | None:
    """Reuse an already-ingested+ready doc (avoids re-embedding — saves quota)."""
    with get_session() as s:
        row = s.execute(
            select(Document.doc_id)
            .where(Document.filename == f"{name}.pdf", Document.status == "ready")
            .order_by(Document.uploaded_at.desc())
        ).first()
        return row[0] if row else None


def pick_subset(questions: list[dict], docs: list[str] | None, max_docs: int | None) -> list[str]:
    if docs:
        return docs
    counts: dict[str, int] = defaultdict(int)
    for q in questions:
        counts[q["doc_name"]] += 1
    ranked = sorted(counts, key=lambda d: counts[d], reverse=True)
    return ranked[: (max_docs or 3)]


def run(docs: list[str], mode: str) -> None:
    questions = load_questions()
    subset_docs = pick_subset(questions, docs, None)
    print(f"=== Tier-1 eval | mode={mode} | docs={subset_docs} ===\n")

    # 1) ingest each doc once (reuse if already ready — saves embedding quota)
    doc_ids: dict[str, uuid.UUID] = {}
    for name in subset_docs:
        existing = _existing_ready_doc(name)
        if existing:
            doc_ids[name] = existing
            print(f"reusing {name} (already ready: {existing})")
            continue
        print(f"ingesting {name} ...", end=" ", flush=True)
        try:
            done = {"n": 0}
            def prog(d, t):  # noqa: E306
                done["n"] = d
            doc_ids[name] = ingest_financebench_doc(name, embed_progress=prog)
            print(f"ok ({done['n']} chunks embedded)")
        except Exception as e:  # noqa: BLE001
            print(f"FAILED: {type(e).__name__}: {e}")

    # 2) run questions for docs that ingested successfully
    reranker = get_reranker("identity")
    qs = [q for q in questions if q["doc_name"] in doc_ids]
    print(f"\nrunning {len(qs)} questions...\n")
    if not qs:
        print("No ingested docs available — nothing to score (likely quota). Aborting.")
        return

    hit20 = hit6 = 0
    rows = []
    with get_session() as s:
        for q in qs:
            gold = gold_pages(q.get("evidence", []))
            qv = embed_query(q["question"])
            cands = hybrid_search(s, doc_ids[q["doc_name"]], qv, q["question"],
                                  mode=mode, top_n=settings.retrieval_top_n_each)
            top6 = reranker.rerank(q["question"], cands, settings.rerank_top_k)
            h20, h6 = is_hit(cands, gold), is_hit(top6, gold)
            hit20 += h20
            hit6 += h6
            rows.append((q["financebench_id"], q["doc_name"], h20, h6, sorted(gold)))

    n = len(qs)
    print("financebench_id            doc                     hit@20 hit@6  gold_pages")
    for fid, dn, h20, h6, gp in rows:
        print(f"  {fid:24} {dn:22} {'Y' if h20 else '.':5} {'Y' if h6 else '.':5} {gp}")
    print(f"\n=== RESULTS (n={n}, mode={mode}) ===")
    print(f"  hit-rate @ retrieval (top-20): {hit20}/{n} = {100*hit20/n:.0f}%")
    print(f"  hit-rate @ rerank    (top-6) : {hit6}/{n} = {100*hit6/n:.0f}%")
    print(f"  reranker headroom (gap)      : {100*(hit20-hit6)/n:.0f} pts")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", nargs="*", help="explicit doc_names; else top-N by #questions")
    ap.add_argument("--max-docs", type=int, default=3)
    ap.add_argument("--mode", default="hybrid", choices=["hybrid", "vector_only", "bm25_only"])
    args = ap.parse_args()
    docs = args.docs or pick_subset(load_questions(), None, args.max_docs)
    run(docs, args.mode)


if __name__ == "__main__":
    main()
