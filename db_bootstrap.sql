-- ============================================================================
--  PDF RAG Agent — Neon bootstrap schema
--  IDEMPOTENT: every statement is safe to run multiple times (no errors on re-run).
--  Mirrors the locked schema in pdf-rag-agent-architecture.md §1.2 / §1.3.
--
--  Usage (Neon SQL editor or psql):
--     psql "$DATABASE_URL" -f db_bootstrap.sql
--  Then tell Alembic the schema exists (Sprint 0):
--     alembic stamp head
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Extensions  (pgvector is NOT on by default on Neon — this turns it on)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector: the VECTOR(1536) column
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid() for PK defaults

-- ---------------------------------------------------------------------------
-- 2. documents table  (§1.2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    doc_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename              TEXT NOT NULL,
    uploaded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    page_count            INT,
    markdown_path         TEXT,
    status                TEXT NOT NULL DEFAULT 'validating',  -- validating|processing|ready|failed
    error_message         TEXT,
    summary_text          TEXT,
    summary_status        TEXT NOT NULL DEFAULT 'pending',     -- pending|generating|completed|failed
    summary_model         TEXT,
    summary_generated_at  TIMESTAMPTZ,
    content_hash          TEXT,                                -- banked for future dedup
    company               TEXT,                                -- doc-level enrichment (nullable)
    fiscal_period         TEXT,                                -- e.g. "FY2022" (nullable)
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 3. chunks table  (§1.3)
--    content = RAW text; content_tsv generated from it; embedding over enriched text.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id       UUID NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index  INT NOT NULL,
    content      TEXT NOT NULL,
    embedding    VECTOR(1536),
    page_number  INT,
    section      TEXT,
    token_count  INT,
    content_tsv  TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 4. CHECK constraints (enum-like guards)  — DO blocks: add only if missing
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'documents_status_chk'
    ) THEN
        ALTER TABLE documents ADD CONSTRAINT documents_status_chk
            CHECK (status IN ('validating','processing','ready','failed'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'documents_summary_status_chk'
    ) THEN
        ALTER TABLE documents ADD CONSTRAINT documents_summary_status_chk
            CHECK (summary_status IN ('pending','generating','completed','failed'));
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 5. Indexes  (§1.3)  — all IF NOT EXISTS
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_content_tsv_gin
    ON chunks USING gin (content_tsv);

CREATE INDEX IF NOT EXISTS chunks_doc_id_idx
    ON chunks (doc_id);

-- helpful for chunk ordering within a doc
CREATE INDEX IF NOT EXISTS chunks_doc_order_idx
    ON chunks (doc_id, chunk_index);

-- ---------------------------------------------------------------------------
-- 6. updated_at auto-touch trigger  (§1.2: "overwritten each update")
--    CREATE OR REPLACE the function; guard the trigger creation.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'documents_touch_updated_at'
    ) THEN
        CREATE TRIGGER documents_touch_updated_at
            BEFORE UPDATE ON documents
            FOR EACH ROW
            EXECUTE FUNCTION touch_updated_at();
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 7. Sanity report (prints what now exists — harmless on every run)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    has_vector BOOLEAN;
    n_docs     BIGINT;
    n_chunks   BIGINT;
BEGIN
    SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector') INTO has_vector;
    SELECT count(*) FROM documents INTO n_docs;
    SELECT count(*) FROM chunks    INTO n_chunks;
    RAISE NOTICE '--- PDF RAG bootstrap OK ---';
    RAISE NOTICE 'pgvector enabled : %', has_vector;
    RAISE NOTICE 'documents rows   : %', n_docs;
    RAISE NOTICE 'chunks rows      : %', n_chunks;
END $$;
