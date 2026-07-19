"""Core ingestion entry point.

    ingest(pdf, company=None, fiscal_period=None, ...) -> doc_id

This is ONE of the two public core signatures. Both the eval harness and the web
layer call this; it never imports them. Pipeline:
validate -> extract -> content gate -> [FORK: summary || chunk -> embed -> index] -> ready

Stage progress is surfaced via an OPTIONAL `on_stage` callback (kept UI-free: the web layer
passes a callback that publishes SSE events; the eval passes None). Summary runs in a real
parallel thread (the fork) and is non-blocking (Option B) — Ready fires on embed+index only.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from pathlib import Path

from ragcore.config import settings
from ragcore.db import repositories as repo
from ragcore.db.engine import get_session
from ragcore.generate.summarize import summarize_document
from ragcore.ingest.chunk import chunk_markdown
from ragcore.ingest.content_gate import EmptyDocumentError, check_content
from ragcore.ingest.embed import embed_document
from ragcore.ingest.extract.base import get_extractor
from ragcore.ingest.metadata import extract_metadata
from ragcore.ingest.validate import validate_pdf
from ragcore.llm.gemini_client import QuotaExhaustedError

ProgressCb = Callable[[int, int], None]
# on_stage(stage, status, progress|None, message|None)
StageCb = Callable[[str, str, "float | None", "str | None"], None]


def _noop_stage(stage: str, status: str, progress: float | None = None,
                message: str | None = None) -> None:
    pass


def ingest(
    pdf: str | Path,
    company: str | None = None,
    fiscal_period: str | None = None,
    *,
    doc_id: uuid.UUID | None = None,
    on_stage: StageCb | None = None,
    run_summary: bool = True,
) -> uuid.UUID:
    """Ingest one PDF, return its doc_id.

    doc_id: pre-created row (web /upload creates it first to return the id, then background-
        ingests). If None, a row is created here.
    on_stage: progress callback (web → SSE). None in eval.
    """
    pdf = Path(pdf)
    stage = on_stage or _noop_stage
    validate_pdf(pdf)

    if doc_id is None:
        with get_session() as s:
            doc_id = repo.create_document(s, filename=pdf.name, status="processing").doc_id

    def _fail(stg: str, msg: str, status_val: str = "failed") -> None:
        stage(stg, "failed", None, msg)
        with get_session() as s:
            repo.set_status(s, doc_id, status_val, error_message=msg)

    try:
        stage("validating", "completed")

        stage("extracting", "running")
        extractor = get_extractor(settings.pdf_extractor)
        result = extractor.extract(pdf)
        check_content(result.markdown)  # §2.1a pre-fork gate

        settings.markdown_dir.mkdir(parents=True, exist_ok=True)
        md_path = settings.markdown_dir / f"{doc_id}.md"
        md_path.write_text(result.markdown, encoding="utf-8")

        if company is None and fiscal_period is None:
            company, fiscal_period = extract_metadata(result.markdown)
        stage("extracting", "completed")

        # ---- FORK: summary runs in parallel; Ready gates on embed+index only (Option B) ----
        summary_thread: threading.Thread | None = None
        if run_summary:
            def _run_summary() -> None:
                stage("summarizing", "running")
                try:
                    summarize_document(doc_id, result.markdown)
                    stage("summarizing", "completed")
                except Exception as e:  # noqa: BLE001 — non-blocking
                    stage("summarizing", "failed", None, str(e))
            summary_thread = threading.Thread(target=_run_summary, daemon=True)
            summary_thread.start()

        # ---- critical path: chunk -> embed -> index ----
        stage("chunking", "running")
        chunks = chunk_markdown(result.markdown)
        with get_session() as s:
            repo.set_document_meta(
                s, doc_id, page_count=result.page_count, markdown_path=str(md_path),
                company=company, fiscal_period=fiscal_period,
            )
            repo.insert_chunks(s, doc_id, chunks)
        stage("chunking", "completed")

        stage("embedding", "running", 0.0)
        def _embed_prog(done: int, total: int) -> None:
            stage("embedding", "running", round(100 * done / total, 1))
        with get_session() as s:
            embed_document(s, doc_id, progress=_embed_prog)
        stage("embedding", "completed", 100.0)

        stage("indexing", "running")
        # vectors + content_tsv are already indexed on write (HNSW/GIN); this is a nominal step
        stage("indexing", "completed")

        with get_session() as s:
            repo.set_status(s, doc_id, "ready")
        stage("ready", "completed")

        return doc_id

    except QuotaExhaustedError as e:
        _fail("embedding", str(e), status_val="processing")  # resumable, not a hard fail
        raise
    except EmptyDocumentError as e:
        _fail("extracting", str(e))
        raise
    except Exception as e:  # noqa: BLE001
        _fail("extracting", f"{type(e).__name__}: {e}")
        raise
