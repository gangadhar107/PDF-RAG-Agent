# ── Backend (Python / FastAPI) ────────────────────────────────────────────────
# Build:  docker build -t pdf-rag-backend .
# Run:    docker run --env-file .env -p 8000:8000 pdf-rag-backend

FROM python:3.11-slim

# uv — fast Python package manager
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /app

# 1. Install dependencies (cached — only re-runs when deps change)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra web --extra rerank --no-install-project

# 2. Copy source and install the project itself
COPY src/ src/
COPY web/ web/
COPY alembic.ini ./
COPY migrations/ migrations/
COPY db_bootstrap.sql ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra web --extra rerank

# 3. Data directories (docker-compose volume mounts over these)
RUN mkdir -p data/markdown data/uploads

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
