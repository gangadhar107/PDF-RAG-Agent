# AGENT.md — Project Brain

**Read this first in any new chat.** It's the single-page mental model of the project.
Deep detail lives in `pdf-rag-agent-architecture.md` (the spec). Build log is `tracker.md`.

---

## What this is
A **NotebookLM-style single-PDF RAG agent**, evaluated on **FinanceBench**. User uploads
**one PDF per chat**, then asks follow-up questions about it. Upload disabled after ingest.
Goal: a working prototype + defensible eval numbers for a resume.

## Hard constraints (do not violate)
1. **One document per chat.** `doc_id` == chat identity. (Multi-doc shelved.)
2. Fixed to PDF.
3. **Groq is the only text-generation provider** → `llama-3.1-8b-instant`.
4. **Gemini Embedding 2 @ 1536 dims** for embeddings (Groq has no embeddings API). 1536 is PERMANENT.
5. Scale: <10 users (mostly the author). Build for correctness + de-risking, not scale.

## The governing architectural rule
**`src/ragcore/` is a pure, UI-free, benchmark-agnostic library. `eval/` and `web/` import
it; it imports neither.** Two entry points into one core. If you `import fastapi` or touch
FinanceBench inside `ragcore/` → STOP, wrong layer.

## The pipeline (end to end)
```
UPLOAD → validate → extract(PDF→md, pymupdf4llm) → CONTENT GATE (§2.1a, token<50 → failed)
       → [FORK]
          ├─ summary (map-reduce, OWN coarse split, non-blocking, Option B)
          └─ chunk (3-pass) → embed (Gemini, batched) → index → READY (unlocks chat)
QUERY  → [rewrite follow-up→standalone, §4.0] → embed(query) 
       → dense(pgvector cosine) + sparse(tsvector) → RRF fuse (k=60)
       → rerank top-20→top-6 (swappable) → assemble(+history+section/page)
       → Groq answer (CoT 3-step, cite figures, refuse if not found) → answer + sources
```

## Key design decisions (the "why", compressed)
- **Two independent state machines:** `status` (validating|processing|ready|failed) vs
  `summary_status` (pending|generating|completed|failed). Summary NEVER gates chat (Option B).
- **Chunking is 3-pass:** structural (header) split → **tables kept atomic** (69% of
  FinanceBench evidence is tabular!) → size-normalize + enrich. Oversized tables split by
  row-group repeating the header.
- **Raw vs enriched text (§3.4):** `content` column = RAW. Enrichment prefix
  (`Section: … | Company: … | Period: …`) reconstructed at embed/rerank/Groq time. Sparse
  index (`content_tsv`) reads RAW; embed/rerank/answer read ENRICHED.
- **Hybrid retrieval + RRF** because financial Qs have exact tokens (tickers, "FY2022") that
  dense embeddings blur → BM25/tsvector catches them.
- **Everything swappable:** extractor, reranker, retrieval_mode (hybrid|vector_only|bm25_only,
  a query-time eval knob). FinanceBench arbitrates the winners.
- **Failure = reupload** (single mental model). Hard-delete failed rows now; audit-later is a
  no-migration flip. Blank/scanned docs caught by the pre-fork content gate.
- **Continuity = conversation-history-in-context (§4.0), NOT a memory layer.** Mem0/Zep banked,
  gated on multi-doc/cross-session/window-overflow (none apply now).

## Eval (Layer 5) — the resume payload
- **3 tiers:** Retrieval (did gold evidence get retrieved?) / Generation (given gold evidence,
  does Groq answer right?) / End-to-end. Identity: `E2E ≈ Retrieval × Generation`.
- **Error-attribution triple** per question per config: `{retrieval_hit, in_top6, answer_correct}`
  → localizes each failure to retrieval / reranker / generation. Watch for "suspicious pass"
  (correct answer w/o gold evidence = possible hallucination).
- **Scoring:** retrieval = page-match ±1, hit-rate @20 AND @6. Numeric (73 Qs) = normalize +
  1% rel-tolerance + **zero-gold branch**. Prose = **Claude Haiku 4.5 judge** (independent 3rd vendor).
- ⚠️ **8B is a known risk on the ~43 numeric-reasoning Qs.** Tier-2 will quantify it; swap to a
  bigger Groq model is a one-line config change. "Let FinanceBench earn the upgrade."

## Stack / environment
- Python 3.11 (via uv), Neon Postgres+pgvector (hosted; `pool_pre_ping` for autosuspend).
- Config in `src/ragcore/config.py` (pydantic-settings ← `.env`). All tuning params live there.
- Schema owned by `db_bootstrap.sql` (idempotent) + Alembic (`alembic stamp head` done; changes
  go via migrations henceforth). `alembic check` currently clean.
- Frontend: TanStack Start + React 19 + Tailwind v4 in `frontend/` (UI-only prototype, no API
  wired). Its TS types (StageKey, StageStatus, Source, Message) ARE the API contract and already
  match our SSE stages. Wiring happens in Sprint 8.

## Sprint roadmap (de-risking order — build core, prove on eval, THEN web/UI)
| # | Sprint | State |
|---|---|---|
| 0 | Skeleton & seam | ✅ DONE |
| 1 | Extraction + table-fidelity checkpoint + prod metadata extract | ✅ DONE (pymupdf4llm kept — tables survive) |
| 2 | 3-pass chunking | ✅ DONE (488 chunks/10-K, tables atomic, DB round-trip verified) |
| 3 | Embedding + indexing | ✅ DONE (gemini-embedding-2 @8192; cosine search finds right table) |
| 4 | Retrieval + Tier-1 eval (**first hit-rate number**) | ✅ DONE (full ablation: vector@20=100%, hybrid@6=79%, bm25@6=29%) |
| 5 | Generation + Tier-2/3 eval | ✅ DONE (Tier-2=71%, Tier-3=78% on 14 Qs; provider→Gemini) |
| 6 | Sweeps (reranker bake-off, chunk sizes, retrieval_mode) — resume metrics | ✅ DONE (FlashRank bake-off; hybrid+identity best @ 71% acc) |
| 7 | Summary path (late, decoupled) | ✅ DONE (map-reduce, non-blocking, 837-char AMD summary) |
| 8 | Web layer (FastAPI + SSE) + query rewriting + wire frontend | ✅ DONE (backend live-verified; frontend wired, needs user `npm run dev`) |
| 9 | Polish & deploy (Docker + Answer Streaming) | ✅ DONE (Multi-container Compose + streaming CoT) |

## Watch-outs / open items
- ⚠️ **Generation provider is Gemini (LLM_PROVIDER=gemini).** Only working provider:
  - Groq (llama-3.1-8b): 6K TPM wall + out of wallet.
  - Cerebras (key present in GROQ_API_KEY env, `csk-...`): key authenticates but ALL models
    (`gpt-oss-120b`, `zai-glm-4.7`, `gemma-4-31b`) return `payment_required` — free tier needs
    billing. Unusable now. If billing added later, `gpt-oss-120b` worth benchmarking vs Gemini
    (add a `cerebras` provider to llm/generate.py — OpenAI-compatible at api.cerebras.ai/v1).
  - Gemini `gemini-flash-latest`: billed, works, 71% eval. **The default. Keep it.**
- ✅ RESOLVED: Gemini billing ON (embeddings + generation). Claude judge key works.
- ⚠️ `gemini-embedding-2` does NOT batch — one text per call (thread-pool concurrency 10).
- ⚠️ Sparse retrieval MUST use OR-tsquery (`&`→`|`); already fixed in hybrid.py.
- ⚠️ Answer scoring: score the STEP-3 text only; terse-numeric→numeric_match, reasoning-with-
  number→judge (is_pure_numeric_answer). Don't revert to naive first-number extraction.
- All API clients have 60s timeouts (a call hung forever without one).
- Docker: Docker compose setup completed (runs backend and frontend).
- DB: AMD (352/352) + BOEING (543/543) fully embedded, status=ready. 2 docs = 14 Qs available.

## Eval numbers so far (subset: AMD + Boeing, n=14 — DIRECTIONAL, wide error bars)
- Tier-1 retrieval: vector_only @20=100%/@6=71%; hybrid @20=92%/@6=78%; bm25 @20=50%/@6=28%.
- Best end-to-end config: **hybrid + identity reranker = 71% answer accuracy** (Tier-3).
- Reranker bake-off: FlashRank (MS-MARCO MiniLM) HURT accuracy (hybrid 71→50, vector 71→42)
  despite lifting vector recall — domain mismatch (web-trained vs SEC filings). Kept RRF-only.
  Next reranker to try: Jina-v2 (finance/table-tuned).
- Sweep harness: `uv run python -m eval.sweep --docs ... [--modes ...] [--rerankers ...] [--no-answers]`
- ⚠️ n=14 → scale to more docs for publishable numbers (no blocker, just time+embed cost).

## How to run things
```bash
cd ~/Downloads/pdf-rag-agent
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev          # install deps
uv run python -c "from ragcore.config import settings; print(settings.groq_model)"
uv run alembic check         # schema drift check
psql "$DATABASE_URL" -f db_bootstrap.sql   # (re)apply schema — idempotent
```
