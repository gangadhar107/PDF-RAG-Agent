# Tracker — build log

Chronological record of what's been done. Newest at top. Companion to `AGENT.md`
(the project brain) and `pdf-rag-agent-architecture.md` (the design spec).

---

## Sprint 9 — Polish & Deploy (Docker compose) + Frontend Refactor ✅ DONE (2026-07-19)

**Goal:** Clean up the frontend monolith by separating presentation and state logic, remove mock credentials/history, and construct a Docker Compose deployment flow.
**Checkpoint:** frontend monolith split into 7 modular files, TypeScript compiles with zero errors, and `docker compose up --build` launches backend and frontend containers successfully.

### Sprint 9.1 — Frontend Refactoring (2026-07-19)
- Refactored `PdfRagApp.tsx` (715 lines → 66 lines) to act as a thin layout shell.
- Extracted shared types and constants into `types.ts`.
- Implemented a custom hook `usePdfRag.ts` managing all application state, file uploads, SSE listeners, and chatbot history/queries.
- Created standalone screen components: `UploadScreen.tsx`, `ProcessingScreen.tsx`, `ChatScreen.tsx`, and `SideDrawer.tsx`.
- Completely removed `MOCK_HISTORY` and `MOCK_PROFILE` mock variables. Commented out the user profile sidebar section with a `TODO: auth` marker, passing an empty chat history array for an honest initial state.
- Verified TypeScript compatibility via `npx tsc --noEmit`.

### Sprint 9.2 — Docker Containerization (2026-07-19)
- Built `Dockerfile` for the Python backend leveraging `uv` for lightning-fast multi-stage dependency caching.
- Built `frontend/Dockerfile` targeting the Node.js runtime to host the Vite development server.
- Authored `docker-compose.yml` to orchestrate both services, wiring environment variables from `.env` to the backend and mapping `VITE_API_URL` to route requests.
- Included service health checking to guarantee Node starts only after the FastAPI backend responds.
- Added `.dockerignore` files for root and frontend contexts to exclude virtual environments, build outputs, and the FinanceBench dataset.
- Documented Docker quickstart guidelines in `README.md` and updated `AGENT.md`.

### Sprint 9.3 — Answer Streaming (2026-07-19)
- Implemented real-time token-by-token answer streaming on both backend and frontend.
- Added `generate_stream` and `chat_stream` support inside Gemini and Groq clients.
- Introduced `query_stream` in the core pipeline yielding intermediate tokens and final results.
- Added POST `/query/stream` returning a FastAPI `StreamingResponse` using SSE.
- Updated React `ChatScreen` and `MessageRow` to parse the 3-step Chain-of-Thought (CoT) on the fly, rendering it under a beautiful, collapsible "Thinking Process" block while streaming the final answer directly to the message bubble.

---

## Sprint 8 — Web layer (FastAPI + SSE) + frontend wiring ✅ DONE (2026-07-16)

**Goal:** FastAPI wrapping the proven core: /upload + SSE progress + /query + /summary +
query rewriting (§4.0); wire the TanStack frontend. Topology A (two servers + CORS).
**Checkpoint:** the three wireframe screens work end-to-end against the real core. ✅ (backend
fully verified live; frontend wired + static-checked — can't run node in this sandbox).

### Sprint 8.1 — bugfix: "stuck at extracting" (2026-07-16, post user test)
User reported browser upload stuck at extracting. Root causes found:
1. **UnicodeEncodeError (the real crash):** `md_path.write_text(markdown)` used the OS DEFAULT
   encoding. On the user's terminal locale that was `charmap` (non-UTF-8) → crashed writing the
   Amazon 10-K markdown (curly quotes/em-dashes). FIX: added `encoding="utf-8"` to ALL file I/O
   (pipeline write, prompt reads, eval jsonl reads — 8 sites). Verified: sandbox is utf-8 so it
   never reproduced here, but charmap is the smoking gun.
2. **SSE stream didn't terminate on failure:** `bus.stream()` only broke on ready/summarizing
   terminal events, NOT on extract/chunk/embed failure → on a crash the client hung open (looked
   "stuck") even though a `failed` event was emitted. FIX: stream now breaks on ANY non-summary
   `status==failed`.
3. **Stale uvicorn instances:** 2 old servers from prior sessions still bound :8000 (address
   already in use). Killed all; documented `pkill -9 -f "uvicorn web.main"` before restart.

VERIFIED: re-uploaded the exact AMAZON_2020_10K.pdf that crashed → now runs clean
extracting→chunking→embedding 0-100%→ready. ✅
Also note: large 10-Ks take ~20-60s in extraction (pymupdf4llm on 37MB/129pp = 22s) — genuinely
slow, not stuck. A spinner/elapsed-time hint in the UI would help perception.

Built (core):
- `retrieve/query_rewrite.py` — §4.0 rewrite follow-up→standalone (no-op if standalone/no history).
- `query.py` — IMPLEMENTED the real `query()` (was a stub!): rewrite→embed→hybrid→rerank→answer.
  `QueryConfig` gained `reranker` field.
- `sse/events.py` — StageEvent + in-memory EventBus (per-doc asyncio queue; publish_threadsafe
  from worker thread). Stage names/statuses match frontend TS types exactly.
- `ingest/pipeline.py` — REFACTORED: added `on_stage` callback + `doc_id` param; summary now
  runs in a real parallel THREAD (the fork); Ready gates on embed+index only (Option B). Emits
  every stage event incl. embedding % (§2.2a).

Built (web):
- `web/main.py` — FastAPI app + CORS (open for prototype).
- `web/background.py` — start_ingest: runs ingest in a daemon thread, bridges stage callback →
  EventBus via publish_threadsafe (keeps ingestion OFF the request path).
- `web/routes/upload.py` — POST /upload (multipart→doc row→bg ingest), GET /events/{id} (SSE).
- `web/routes/query.py` — POST /query, GET /summary/{id}, GET /status/{id}.
- pyproject: web extra + python-multipart.

Wired (frontend):
- `frontend/src/components/pdf-rag/api.ts` — API client (uploadPdf, subscribeEvents via
  EventSource, askQuestion, fetchSummary; VITE_API_URL configurable).
- `PdfRagApp.tsx` — replaced 3 mock points: runProcessing (setTimeout sim → real SSE),
  handleFile (→ real upload), sendMessage (→ real /query with history for rewriting).
  Removed MOCK_SUMMARY. Braces balanced, imports clean, static checks pass.
- `RUNNING.md` — two-server run guide.

**LIVE BACKEND VERIFICATION (curl against Neon):**
- /health ok; all 6 routes registered.
- /query on ready AMD doc → "AMD net revenue FY2022 was $23.6 billion" + correct sources. ✅
- Multi-turn: "What about gross margin?" + history → rewritten to "What was AMD's gross margin
  in FY2022?" → answered 45%. §4.0 WORKS. ✅
- Full upload→SSE→ready→query on a fresh J&J 8-K: SSE streamed
  validating→extracting→[summarizing∥chunking]→embedding 0-100%→indexing→ready (parallel fork
  visible!), summary completed independently, then queryable. ✅

⚠️ LIMITATION: node/npm not reachable in this sandbox → couldn't run `tsc`/`npm run dev` to
compile the frontend. Frontend wiring verified by static review only (structure, types, braces,
imports). USER must `npm install && npm run dev` to confirm the UI end-to-end.

**NEXT-SESSION TODO:** user runs frontend (npm run dev) + backend (uvicorn) together, tests the
full UI flow. Then Sprint 9 (polish + Docker — user does Docker). Optionally scale eval.

---

## Sprint 7 — Summary path ✅ DONE (2026-07-16)

**Goal:** map-reduce summary (§2.4) over the doc's OWN coarse split (not chunks table),
decoupled + non-blocking (Option B), writes summary_text/status/generated_at.
**Checkpoint:** summary populates independently; a failure never blocks query. ✅ PASS.

Built:
- `llm/prompts/summarize_map.txt` + `summarize_reduce.txt` — per-section + synthesis prompts.
- `generate/summarize.py` — `_coarse_windows()` (own header-based split, ~3000 tok windows,
  page-marker stripped, oversized sections hard-sliced; NOT the chunks table per §2.4) +
  `summarize_document()` (map each window → reduce → persist; status generating→completed/
  failed; model logged).
- `ingest/pipeline.py` — summary wired as **non-blocking** step (`run_summary=True` param):
  try/except that records failure but NEVER fails ingest (Option B). In web layer (Sprint 8)
  this becomes the parallel background fork.
- `tests/test_sprint7.py` — 4 windowing tests.

**CHECKPOINT (real AMD_2022_10K, 8-window cap):**
- Map-reduce ran in 37s → high-quality 837-char summary: company, FY2022, 4 segments
  (Data Center/Client/Gaming/Embedded), product brands, R&D/outsourcing, Intel competition,
  even the $3.9M Superfund environmental liability. Factual, no hallucination.
- Persisted: summary_status=completed, summary_generated_at set, model=gemini-flash-latest.

Bug fixed:
- Gemini-flash "thinking tokens" truncated output (summary cut at 102 chars mid-sentence).
  Bumped map max_tokens 300→800, reduce 600→2048. Now full summaries. (Same flash quirk seen
  in generation — flash spends part of the output budget on internal reasoning.)

Verified: ✅ 20/20 pytest; ✅ live map-reduce summary persisted; ✅ no circular import from
pipeline→summarize; ✅ non-blocking (summary failure caught, ingest proceeds to ready).

**NEXT-SESSION TODO:** Sprint 8 — web layer (FastAPI + SSE progress + query rewriting) + wire
the TanStack Start frontend. Then Sprint 9 polish/deploy (Docker — user does). Optionally
scale eval to more docs for tighter numbers.

---

## Sprint 6 — Sweeps (reranker bake-off + mode ablation) ✅ DONE (2026-07-16)

**Goal:** reranker bake-off (identity vs FlashRank), retrieval_mode × reranker ablation on
hit@6 AND answer accuracy. **Checkpoint:** defensible before/after numbers per lever. ✅ PASS.

Built:
- `retrieve/rerank/flashrank_reranker.py` — local CPU cross-encoder (ms-marco-MiniLM-L-12-v2,
  no wallet). Reads enriched text; lazy-loads model.
- `eval/sweep.py` — sweeps {mode} × {reranker}, reports hit@20 / hit@6 / answer_acc +
  attribution. Caches candidates per mode (retrieval is reranker-independent).
- pyproject `rerank` extra (flashrank).

**FULL SWEEP (AMD + Boeing, n=14, gemini generation):**
| mode        | reranker  | hit@20 | hit@6 | answer_acc |
|-------------|-----------|:------:|:-----:|:----------:|
| hybrid      | identity  | 92%    | 78%   | **71%** ⭐ |
| hybrid      | flashrank | 92%    | 64%   | 50%        |
| vector_only | identity  | 100%   | 71%   | **71%** ⭐ |
| vector_only | flashrank | 100%   | **85%**| 42% ⚠️    |

**KEY FINDING (counterintuitive, defensible):** FlashRank *improved raw recall* on vector_only
(hit@6 71→85, +14) but *tanked answer accuracy* (71→42, −29). Attribution explains it:
vector_only+flashrank had **6 generation_failures** (vs 2 elsewhere) — the MS-MARCO web-trained
cross-encoder reorders top-6 by textual similarity, but on financial questions the most
similar chunk ≠ the one with computable numbers, so the LLM anchored wrong. FlashRank also
HURT hybrid (78→64 hit@6) — RRF fusion already ordered well; the reranker disagreed.

**DECISION: keep `hybrid + identity` (no cross-encoder reranker)** — best-balanced (78% hit@6,
71% acc). Documented Jina-v2 (finance/table-tuned) as the next reranker to try — MS-MARCO
MiniLM is the wrong training domain for SEC filings.

⚠️ CAVEAT: n=14 (2 docs) → wide error bars. Numbers are directional, not final. Scaling the
eval to more docs is the top follow-up (embeddings billed, generation on Gemini ~1M TPM — no
blocker, just time).

Resume story: "Benchmarked FlashRank across retrieval modes; it lifted raw recall on
vector-only (+14pt hit@6) but degraded end-to-end accuracy (−29pt) via generation failures
from domain-mismatched reordering, so I kept the simpler RRF-only pipeline and identified a
finance-tuned reranker as the next step. Also confirmed E2E accuracy tracks hit@6."

Verified: ✅ retrieval-only sweep (6 configs) + answer sweep (4 configs) end-to-end.

**NEXT-SESSION TODO:** Sprint 7 (summary path) — OR scale eval to more docs first for tighter
numbers. Then Sprint 8 (web + SSE + wire frontend).

---

## Sprint 5 — Generation + Tier-2/3 eval ✅ DONE (2026-07-16)

**Goal:** Groq CoT answer (§4.6), numeric scorer, Claude judge, attribution triple,
Tier-2 (gold evidence) + Tier-3 (end-to-end). **Checkpoint:** E2E ≈ Retrieval × Generation
numbers + attribution logged. ✅ **PASS.**

**RESULTS (AMD + Boeing, n=14, hybrid, gemini-flash-latest generation):**
| Tier | Accuracy |
|---|---|
| Tier-2 (gold evidence → answer; generation ceiling) | **71%** (10/14) |
| Tier-3 (end-to-end) | **78%** (11/14) |

Attribution: {success:10, generation_failure:1, retrieval_miss:1, reranker_buried:1,
SUSPICIOUS_PASS:1}.

Insights:
- Tier-3 (78%) ≈/> Tier-2 (71%): Tier-2 feeds ONLY the single gold snippet; some questions
  need neighboring context that top-6 retrieval supplies → tiered eval surfaced this honestly.
- Attribution triple works: caught 1 SUSPICIOUS_PASS (correct w/o gold in top-6 → possible
  hallucination/dup, flagged for review, §5.2), and cleanly separated retrieval vs reranker
  vs generation failures.
- gemini-flash handles numeric reasoning well — the 8B numeric-risk is moot under this provider.

**KEY DECISION — generation provider swapped Groq → Gemini (swappable):**
- Groq free tier = **6000 TPM**; our RAG context ≈4,700 tok/call → ~1 call/min → constant 429s,
  runs crashed. User out of wallet (can't upgrade Groq).
- Gemini already billed, ~1M TPM. Added swappable provider: `LLM_PROVIDER=groq|gemini`
  (config), `llm/generate.py` dispatcher, `gemini_client.generate()` (gemini-flash-latest).
  answer.py + metadata.py now call provider-agnostic generate(). Flip env var to switch back
  to Groq later; also enables a provider ablation.
- 14 Qs ran in ~3.5min, ~15s each, zero rate-limit crashes.

Built:
- `llm/prompts/answer.txt` — 3-step CoT + citations + refusal.
- `generate/answer.py` — enriched context assembly, CoT, STEP-3 parse / not_found.
- `eval/scoring/numeric.py` — normalize + 1% rel-tol + zero-gold epsilon; `is_pure_numeric_answer`
  routes reasoning-with-number golds to the judge (not naive extraction).
- `eval/scoring/judge.py` — Claude Haiku 4.5 judge.
- `eval/scoring/__init__.py` — score_answer router (STEP-3 text, terse-numeric vs judge).
- `eval/attribution.py` — Attribution triple + SUSPICIOUS_PASS.
- `eval/gen_harness.py` — Tier-2 (gold evidence_text context) + Tier-3 (real retrieval).
- `llm/generate.py` — provider dispatcher; `llm/gemini_client.generate()`.

Robustness fixes: 60s timeouts on Gemini+Groq clients (was hanging forever); Groq
max_retries=0 + tenacity RateLimit/timeout backoff.

Bugs fixed:
- Scoring router read the FIRST number in Groq's CoT ("STEP 1 EXTRACT: Cash $4,835…") instead
  of the STEP-3 conclusion → Tier-2 spuriously 0. Fixed: score STEP-3 only + route
  reasoning-with-number golds to judge. Routing verified 5/5.

Verified: ✅ 16/16 pytest; ✅ full Tier-2/3 run on 2 docs.

**NEXT-SESSION TODO:** Sprint 6 sweeps (reranker bake-off FlashRank→Jina v2, chunk sizes,
retrieval_mode ablation on generation accuracy). Optionally scale eval to more docs.

---

## Sprint 4 — Retrieval + Tier-1 eval ✅ DONE / COMPLETED (2026-07-16)

**Goal:** dense+sparse+RRF retrieval, retrieval_mode, identity reranker, Tier-1 hit-rate
(page ±1, @20 and @6). **Checkpoint:** real hit-rate numbers. ✅ **PASS — full ablation.**

**UPDATE (billing enabled):** Gemini billing turned on → quota gone (40 concurrent OK).
Bumped embed_concurrency 4→10. Fully embedded AMD (352) + Boeing (543) in ~66s total
(resumable design picked up AMD from 75). Both status=ready.

**FULL TIER-1 ABLATION (AMD + Boeing, n=14):**

| mode         | hit@20 (top-20) | hit@6 (top-6) | reranker headroom |
|--------------|:---------------:|:-------------:|:-----------------:|
| vector_only  | **100%** (14/14)| 71% (10/14)   | 29 pts            |
| hybrid       | 93% (13/14)     | **79%** (11/14)| 14 pts           |
| bm25_only    | 50% (7/14)      | 29% (4/14)    | 21 pts            |

Insights (resume-grade):
- Dense (Gemini) embeddings dominate recall on FinanceBench — 100% @20 alone.
- **Hybrid wins @6 (79% vs 71%)**: fusing BM25 *reorders* candidates so more gold lands in
  the top-6 that reaches the LLM — the actual point of hybrid, demonstrated.
- BM25 alone weak (50%) but additive in fusion (lifts @6). Not useless, not essential —
  it's a precision-at-cut booster.
- Reranker headroom 14-29 pts (right chunks retrieved, below top-6) → Sprint 6's real
  reranker target.

Done (code):
- `retrieve/hybrid.py` — dense+sparse+RRF single CTE; retrieval_mode; **OR-tsquery** fix.
- `retrieve/rerank/base.py` + `identity.py` — swappable reranker; identity trims top_k.
- `eval/scoring/retrieval.py` — gold_pages + is_hit (±1).
- `eval/harness.py` — subset runner, reuse-if-ready, 3-mode ablation, n=0 guard.
- `ingest/pipeline.py` — sync ingest path; QuotaExhaustedError→'processing' (resumable).
- `ingest/embed.py` — RESUMABLE (NULL-only, commit every 25).
- `config.py` — embed_concurrency 10.

Bugs fixed: plainto_tsquery ANDs terms (→0 matches) fixed with OR-tsquery; harness
div-by-zero; dropped settings import.

Keys verified: Gemini billing ✅ (40 concurrent), Claude judge ✅ (`claude-haiku-4-5` → pong).

Verified: ✅ 16/16 pytest; ✅ full 3-mode ablation on 2 fully-embedded 10-Ks.

DB state: AMD (352/352 ready), BOEING (543/543 ready).

---

## Sprint 3 — Embedding + indexing ✅ DONE (2026-07-16)

**Goal:** batched Gemini embedding over ENRICHED text, write vectors, per-batch progress %.
**Checkpoint:** a doc is embedded & indexed; progress % computable; cosine search works. ✅ PASS.

**Blocker resolution (GOOGLE_API_KEY):**
- First key → HTTP 400 "API key not valid" (both SDK and raw REST — proven not our code).
  User regenerated it.
- Second key → HTTP 200 ✅. Verified via raw REST model listing.

**D2 + D3 CONFIRMED from the live API (models.list):**
- `gemini-embedding-2` IS a real model ID (inputTokenLimit **8192**).
- Also available: `gemini-embedding-2-preview` (8192), `gemini-embedding-001` (2048).
- **D2 = gemini-embedding-2**, **D3 = 8192** → updated config (`embed_max_input_tokens` 2048→8192).
  Bonus: bigger tables now fit without row-group split.

**CRITICAL API behavior discovered:** `gemini-embedding-2` **JOINS** a `contents` list into
ONE embedding — it does NOT batch distinct texts (verified: 3 inputs → 1 vector, cos 0.72 vs
single). → design: **one text per API call**, parallelized with a ThreadPoolExecutor
(concurrency 8) for throughput. Documented in gemini_client.py.

Done:
- `llm/gemini_client.py` — `embed_one(text, task_type)` (1536-dim, tenacity retry) +
  `embed_query()`; TASK_DOCUMENT / TASK_QUERY constants (§3.4 matching intents).
- `ingest/embed.py` — `build_enriched_text()` (§3.4 prefix reconstruction; null fields
  omitted → graceful degradation) + `embed_document()` (concurrent embed loop, per-chunk
  `progress(done,total)` callback for §2.2a, writes vectors).
- `config.py` — D2/D3 confirmed values.
- `tests/test_sprint3.py` — 4 enrichment-builder tests.

**CHECKPOINT (real 3M_2018_10K, 60-chunk subset for cost/time):**
- Enriched text verified: embeds `Section: … | Company: 3M | Period: FY2018` + raw content;
  `content` column stays RAW (§3.4 end-to-end). ✅
- Embedded 60 chunks in 9.4s (~6.4/s, concurrency 8); progress callback fired 1→60. ✅
- Vectors persisted at dim 1536. ✅
- **Cosine search works:** query "3M total assets 2018" → top hit (d=0.158) = **Selected
  Financial Data table, page 14** — the correct table, from dense retrieval alone. ✅
- Cleanup via CASCADE. ✅

Verified:
- ✅ 16/16 pytest pass.
- ✅ live embed + vector write + HNSW cosine search on Neon.

Notes:
- Full-doc embed (488 chunks) not run to save cost/quota — subset proves the path; Sprint 4
  eval will embed real docs at scale.

---

## Sprint 2 — 3-pass chunking ✅ DONE (2026-07-16)

**Goal:** the §3.1 chunker (structural → table-atomic → size-normalize+enrich) + DB persistence.
**Checkpoint:** chunks for a real 10-K look sane in the DB — tables intact, sections labeled,
pages tracked. ✅ **PASS.**

Done:
- `ingest/chunk.py` — full 3-pass chunker:
  - **Pass 1** `_pass1_sections`: header-aware split (levels 1-6), maintains a heading stack →
    `section_path` like "3M COMPANY › NOTE 7. Supplemental Balance Sheet Information"; tracks
    page via `<!-- page:N -->` markers.
  - **Pass 2** `_pass2_blocks`: separates atomic table blocks from prose within a section
    (detects `|...|` rows + `|---|` separators).
  - **Pass 3** `chunk_markdown`: tables kept ATOMIC (row-group split w/ repeated header only if
    > embed_max); prose greedy-packed to target with ~15% overlap; oversized paras split by
    sentence.
  - `clean_markup()` strips pymupdf4llm noise (`<br>`, `**`, `<u>`) — the Sprint 1 carry-forward.
  - Tiny-prose filter (`chunk_min_tokens=15`) drops ToC/page-num fragments; **tables exempt**.
  - `content` = RAW cleaned text (no enrichment prefix — reconstructed later, §3.4).
- `config.py` — added `chunk_min_tokens=15`.
- `db/repositories.py` — document CRUD (create/get/set_status/set_document_meta/delete),
  summary setter, `insert_chunks` (bulk), `count_chunks`. (Hybrid RRF query lands Sprint 4.)
- `tests/test_sprint2.py` — 6 tests (markup cleaning, page tracking, section inheritance,
  table atomicity, tiny-prose drop, sequential index).

**CHECKPOINT (real 3M_2018_10K):**
- 488 chunks (107 tables / 381 prose) after tiny-noise filter (was 517 pre-filter).
- tokens: min=15 max=1129 mean≈270; **0 chunks over embed_max** (2048).
- section label on 487/488; page on 488/488; **0 residual `<br>`/`**` markup**.
- **Consolidated/Supplemental Balance Sheet table = ONE coherent 481-tok chunk** with every
  line item + both years' figures intact. ✅ (exactly what FinanceBench numeric Qs need)
- **DB round-trip verified on live Neon:** 488 inserted → `content_tsv` auto-generated by
  Postgres (sparse index self-populating ✅) → section/page persisted → `ON DELETE CASCADE`
  cleanup 488→0 ✅.

Verified:
- ✅ 12/12 pytest pass.
- ✅ end-to-end chunk→store→read→delete against Neon.

Notes / carry-forward:
- Cover-page addresses occasionally parse as long "headers" (harmless — real headings).
- Neon insert of 488 rows took ~60s (network + autosuspend cold start) — expected; Sprint 3
  embedding writes will batch.

---

## Sprint 1 — Extraction + table-fidelity checkpoint ✅ DONE (2026-07-16)

**Goal:** extraction interface, validate, content gate, production metadata extraction,
+ the table-fidelity checkpoint on a real 10-K.
**Checkpoint:** eyeball a FinanceBench 10-K — do tables survive? ✅ **PASS.**

Done:
- `ingest/extract/base.py` — `Extractor` Protocol + `ExtractionResult` + `get_extractor()`
  factory (swappable; the #1-risk seam).
- `ingest/extract/pymupdf4llm_extractor.py` — PDF→Markdown, `page_chunks=True`, injects
  `<!-- page:N -->` markers for downstream page attribution; authoritative page_count via PyMuPDF.
- `ingest/extract/docling_extractor.py` — placeholder swap target (raises NotImplemented).
- `ingest/validate.py` — file-level checks (exists / .pdf / size 0<x<100MB / corruption via
  PyMuPDF open + page_count>0). `ValidationError`.
- `ingest/content_gate.py` — §2.1a PRE-FORK gate on TOKEN COUNT only (chunks don't exist yet);
  `< settings.content_gate_min_tokens (50)` → `EmptyDocumentError`.
- `tokens.py` — tiktoken cl100k_base `count_tokens()` (approximation; Gemini tokenizer later).
- `ingest/metadata.py` — §2.1b PRODUCTION mode: regex (fiscal year) + Groq JSON fallback
  (company/period). Both nullable → graceful degradation.
- `llm/groq_client.py` — `chat()` wrapper w/ tenacity retry (used by metadata, later summary/
  rewrite/answer).
- `eval/ingest_wrapper.py` — §2.1b EVAL mode: `lookup_metadata(doc_name)` +
  `ingest_financebench_doc(doc_name)`; reads doc_info jsonl, injects known-good metadata.
- `tests/test_sprint1.py` — 6 tests (validate, gate, factory).

**TABLE-FIDELITY CHECKPOINT (the important hour):**
- Tested `3M_2018_10K.pdf` (160 pages) via pymupdf4llm.
- extract time 26.7s | 616K chars | 146K tokens | content gate PASS.
- **Tables SURVIVE cleanly** — 1,704 markdown-table rows; Selected Financial Data table
  renders `|Net sales|$32,765|$31,657|...` with numbers intact & column-aligned across 5 yrs.
- All 160 `<!-- page:N -->` markers preserved.
- **DECISION: keep pymupdf4llm** (no docling swap needed). ✅
- Metadata extraction verified: `3M_2018_10K` → company `'3M COMPANY'`, period `'FY2018'`
  (ground truth 3M / 2018). ✅

Verified:
- ✅ all Sprint 1 modules import.
- ✅ 6/6 pytest pass (harmless SWIG deprecation warnings from PyMuPDF).
- ✅ eval lookup: `3M_2018_10K → ('3M','FY2018')`, unknown → `(None,None)`.

⚠️ Carry-forward for Sprint 2 (chunking):
- pymupdf4llm cells contain `<br>` tags and `**bold**` markers (e.g. `**$**<br>**32,765**`).
  Numbers are fine, but the chunker should **strip this markup** before embedding.
- Multi-year tables are wide; watch the oversized-table row-group split (§3.1) in Sprint 2/3.

---

## Sprint 0 — Skeleton & seam ✅ DONE (2026-07-16)

**Goal:** repo skeleton, DB models, Alembic wired, core signatures stubbed.
**Checkpoint:** `alembic check` = no drift; core modules import. ✅ Met.

Done:
- Installed **uv 0.11.29**, pinned **Python 3.11.15** for the project.
- `pyproject.toml` — deps (pydantic, psycopg[binary], sqlalchemy, pgvector, alembic,
  pymupdf4llm, pymupdf, tiktoken, groq, google-genai, tenacity) + optional extras
  `eval` (pandas, anthropic) / `web` (fastapi, uvicorn) / `dev` (pytest, ruff).
- `src/ragcore/config.py` — pydantic-settings reading `.env`; pins models + all locked
  params (embed_dim=1536, rrf_k=60, chunk 640/1024/0.15, top_n=20, rerank_k=6,
  content_gate_min_tokens=50, numeric tolerances, FinanceBench paths).
- `src/ragcore/db/engine.py` — SQLAlchemy engine (forces `postgresql+psycopg://`,
  `pool_pre_ping` for Neon autosuspend) + `get_session()` context manager.
- `src/ragcore/db/models.py` — `Document` + `Chunk` ORM, 1:1 with `db_bootstrap.sql`
  (VECTOR(1536), content_tsv generated col, HNSW + GIN + fk indexes, CHECK constraints,
  ON DELETE CASCADE).
- `src/ragcore/ingest/pipeline.py` — `ingest(pdf, company=None, fiscal_period=None)` STUB.
- `src/ragcore/query.py` — `query(doc_id, question, config, history=None)` STUB +
  `QueryResult` / `Source` / `QueryConfig` dataclasses.
- Alembic: `alembic.ini` + `migrations/env.py` (pulls URL/metadata from ragcore),
  baseline migration `a5fd31ade13d` autogenerated, **`alembic stamp head`** applied
  (schema pre-built by `db_bootstrap.sql`).
- `.gitignore`.

Verified live:
- ✅ Groq API (`llama-3.1-8b-instant`) → HTTP 200.
- ✅ Neon connection → PostgreSQL 18.4; `db_bootstrap.sql` ran idempotently.
- ✅ pgvector enabled; `documents` + `chunks` tables; all 4 chunk indexes present.
- ✅ `alembic check` → "No new upgrade operations detected" (models == live DB).
- ✅ config / models / core stubs all import.

⚠️ Open blockers noted:
- **`GOOGLE_API_KEY` missing** in `.env` → blocks Sprint 3 (embedding). Add before then.
- `ANTHROPIC_API_KEY` absent (user deferred) → eval-only, needed Sprint 5.
- **D2** exact Gemini Embedding 2 model string + **D3** its max input tokens → confirm by Sprint 3.
  (config currently guesses `gemini-embedding-2` / 2048 tokens as placeholders.)

---

## Decisions locked (quick ref — full rationale in architecture doc)
- Provider: Groq generation only (`llama-3.1-8b-instant`); Gemini embeddings @ 1536.
- Store: one Neon Postgres + pgvector. Files local (`data/markdown`).
- Extractor: `pymupdf4llm` (swappable; table fidelity checked in Sprint 1).
- uv package manager; monorepo (frontend/ = TanStack Start, inside repo).
- RRF k=60; chunk 512-768 target / 15% overlap; retrieval top-20 → rerank top-6.
- Data at `data/financebench/` (questions.jsonl + financebench_document_information.jsonl + pdfs/).
