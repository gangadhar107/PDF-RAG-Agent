# Running the app (Topology A: two servers)

## 1. Backend (FastAPI, port 8000)
```bash
cd ~/Downloads/pdf-rag-agent
export PATH="$HOME/.local/bin:$PATH"
uv run uvicorn web.main:app --reload --port 8000
```
Health check: http://localhost:8000/health  → `{"status":"ok"}`
API docs (Swagger): http://localhost:8000/docs

Endpoints:
- `POST /upload`         (multipart file) → `{doc_id, filename}`, starts background ingest
- `GET  /events/{id}`    SSE stream of pipeline stage events (§2.2)
- `POST /query`          `{doc_id, question, history[], retrieval_mode, reranker}` → `{text, sources, notFound, rewritten}`
- `GET  /summary/{id}`   → `{summary, summary_status}`
- `GET  /status/{id}`    → `{status, filename, error_message, summary_status}`

## 2. Frontend (TanStack Start / Vite — needs Node)
```bash
cd ~/Downloads/pdf-rag-agent/frontend
npm install        # first time
npm run dev        # serves the UI (its own port, e.g. 3000)
```
Optional: point the frontend at a non-default backend URL:
```bash
echo 'VITE_API_URL=http://localhost:8000' > .env.local
```
(Defaults to http://localhost:8000 if unset.)

## Flow
Upload a PDF → watch the real pipeline stages stream live (embedding shows %) →
chat unlocks when Ready fires → summary appears in its panel when it lands (independently).

## Notes
- Generation provider is Gemini (LLM_PROVIDER=gemini in .env). Groq/Cerebras need billing.
- The backend `.env` holds all keys + DATABASE_URL (Neon). Never commit it.
- CORS is open (`*`) for the prototype; tighten to the frontend origin before any real deploy.
