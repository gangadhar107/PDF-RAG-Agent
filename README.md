# PDF RAG Agent

A NotebookLM-style document intelligence app: upload **one PDF**, then ask follow-up
questions about it. Built as a retrieval-augmented generation (RAG) pipeline and
**benchmarked on [FinanceBench](https://github.com/patronus-ai/financebench)** — a hard
Q&A dataset over real SEC filings (10-Ks / 10-Qs).

Upload → live pipeline (validate → extract → chunk → embed → index) → chat, with a
document summary generated in parallel and streamed progress over SSE.

---

## Highlights

- **Hybrid retrieval** — dense vectors (Gemini Embedding 2, pgvector) **+** sparse keyword
  search (Postgres `tsvector`), fused with **Reciprocal Rank Fusion** — all in a single SQL query.
- **Table-aware chunking** — a 3-pass chunker keeps financial tables atomic (69% of
  FinanceBench evidence is tabular) and enriches each chunk with section/company/period context.
- **A real evaluation harness** — 3 tiers (retrieval / generation / end-to-end) with an
  error-attribution triple that localizes every failure to a specific layer.
- **Swappable everything** — PDF extractor, LLM provider (Gemini/Groq), reranker, and
  retrieval mode are all pluggable and ablated against the benchmark.
- **Streaming ingestion** — background pipeline with live per-stage SSE progress
  (embedding shows a real %), decoupled parallel summarization.

## Evaluation results (FinanceBench subset, n=14)

**Retrieval (hit-rate — did the gold-evidence page reach the candidate set?):**

| mode          | hit@20 | hit@6 |
|---------------|:------:|:-----:|
| vector_only   | 100%   | 71%   |
| **hybrid**    | 93%    | **79%** |
| bm25_only     | 50%    | 29%   |

**End-to-end answer accuracy:** **71%** (best config: hybrid + RRF).
Tier-2 (given gold evidence) = 71% → confirms retrieval, not reasoning, is the bottleneck.

**Notable finding:** adding an off-the-shelf cross-encoder reranker (FlashRank, MS-MARCO)
*raised raw recall* on vector-only (+14 pt hit@6) but *degraded* end-to-end accuracy (−29 pt)
via generation failures from domain-mismatched reordering — so the simpler RRF-only pipeline
was kept, and a finance-tuned reranker (Jina-v2) identified as the next step. *Measurement
over assumption.*

> Numbers are directional (n=14, 2 documents); the harness scales to the full 150-question set.

---

## Architecture

```
UPLOAD → validate → extract (PDF→Markdown) → content gate
       → [FORK]
          ├─ summary (map-reduce, non-blocking)         ← populates independently
          └─ chunk (3-pass, table-atomic) → embed → index → READY (unlocks chat)

QUERY  → rewrite follow-up→standalone (uses chat history)
       → embed question → dense + sparse retrieval → RRF fuse → rerank
       → assemble context (+section/page) → LLM answer (CoT + citations + refusal)
       → answer + sources
```

**Stack:** Python 3.11 · FastAPI · Postgres + pgvector (Neon) · Gemini Embedding 2 ·
Gemini/Groq generation · FlashRank · React (TanStack Start + Vite) · SSE.

Design decisions and rationale live in
[`pdf-rag-agent-architecture.md`](./pdf-rag-agent-architecture.md); the full build log is in
[`tracker.md`](./tracker.md); a one-page project brief is [`AGENT.md`](./AGENT.md).

---

## Quick start

**Prerequisites:** a Postgres database with pgvector (free at [neon.tech](https://neon.tech)),
a [Google Gemini API key](https://aistudio.google.com/app/apikey), and
[Node.js 18+](https://nodejs.org). (`uv` is auto-installed by the run script.)

### Option A: Run with Docker (Recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/). No local Node.js or Python environments required.

```bash
# 1. configure
cp .env.example .env          # then edit .env with your DATABASE_URL + GOOGLE_API_KEY

# 2. run with compose
docker compose up --build
```
Then open `http://localhost:3000` in your browser.

### Option B: Run locally (with bash)

```bash
git clone <your-repo-url>
cd pdf-rag-agent

# 1. configure
cp .env.example .env          # then edit .env with your keys + DATABASE_URL

# 2. create the database schema (once)
psql "$DATABASE_URL" -f db_bootstrap.sql

# 3. run everything (backend :8000 + frontend) with one command
bash run.sh
```

`run.sh` checks prerequisites, installs all dependencies, verifies the database, and starts
both servers. Open the URL it prints (usually `http://localhost:8080`). **Ctrl+C stops both.**

<details>
<summary>Run the servers separately (manual)</summary>

```bash
# backend
uv run uvicorn web.main:app --reload --port 8000
# frontend (new terminal)
cd frontend && npm install && npm run dev
```
</details>


---

## Evaluation harness

```bash
# retrieval hit-rate + mode ablation
uv run python -m eval.harness --docs AMD_2022_10K BOEING_2022_10K --mode hybrid

# generation eval (Tier-2 gold-evidence + Tier-3 end-to-end)
uv run python -m eval.gen_harness --docs AMD_2022_10K BOEING_2022_10K --mode hybrid

# full sweep: reranker × retrieval-mode → hit@6 + answer accuracy
uv run python -m eval.sweep --docs AMD_2022_10K BOEING_2022_10K
```

Requires the FinanceBench data under `data/financebench/` and an `ANTHROPIC_API_KEY`
(Claude Haiku is the LLM-as-judge for prose answers).

---

## Project layout

```
src/ragcore/      # the core library (UI-free, provider-agnostic)
  ingest/         #   validate → extract → chunk → embed pipeline
  retrieve/       #   hybrid search + RRF + query rewrite + rerankers
  generate/       #   CoT answer + map-reduce summary
  llm/            #   Gemini / Groq clients + provider dispatch
  db/             #   SQLAlchemy models + repositories
eval/             # FinanceBench harness (3-tier scoring, attribution)
web/              # FastAPI: /upload (+SSE), /query, /summary
frontend/         # React UI (TanStack Start + Vite)
```

The core is a pure library; `eval/` and `web/` are two entry points into it. This separation
is what makes the pipeline benchmark-testable without a running server.
