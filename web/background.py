"""Background ingestion task — runs the core ingest() in a thread, publishing SSE stage events.

/upload creates the doc row and returns doc_id immediately; this runs the pipeline off the
request path (§ scale stance: ingestion must NOT block the HTTP request). The on_stage callback
bridges the worker thread → the asyncio EventBus via publish_threadsafe.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from pathlib import Path

from ragcore.ingest.pipeline import ingest
from ragcore.sse.events import StageEvent, bus


def start_ingest(pdf_path: Path, doc_id: uuid.UUID, loop: asyncio.AbstractEventLoop) -> None:
    """Spawn the ingest pipeline in a daemon thread, streaming stage events to the bus."""
    did = str(doc_id)

    def on_stage(stage: str, status: str, progress=None, message=None) -> None:
        bus.publish_threadsafe(loop, StageEvent(
            stage=stage, status=status, progress=progress, message=message, doc_id=did,
        ))

    def _run() -> None:
        try:
            ingest(pdf_path, doc_id=doc_id, on_stage=on_stage, run_summary=True)
        except Exception:  # noqa: BLE001 — on_stage already emitted the failure event
            pass

    threading.Thread(target=_run, daemon=True).start()
