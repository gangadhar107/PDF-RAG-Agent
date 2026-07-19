"""SSE event shapes (§2.2 / §2.2a) — the pipeline→frontend contract.

Pure data + an in-memory pub/sub bus. Stage names/statuses match the frontend's TS types
(StageKey / StageStatus) exactly. Transport (the HTTP SSE stream) lives in web/sse.py.

NOTE (§ scale stance): this in-memory bus is single-instance only. For >1 API instance,
relocate to Redis pub/sub — a known, isolated change.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass

# stage keys — MUST match frontend StageKey
STAGES = ["validating", "extracting", "chunking", "embedding", "indexing", "ready", "summarizing"]
# statuses — MUST match frontend StageStatus
PENDING, RUNNING, COMPLETED, FAILED = "pending", "running", "completed", "failed"


@dataclass
class StageEvent:
    stage: str                 # one of STAGES
    status: str                # pending|running|completed|failed
    progress: float | None = None   # 0..100, only for 'embedding' (§2.2a)
    message: str | None = None       # error text on failure
    doc_id: str | None = None

    def to_sse(self) -> str:
        return f"data: {json.dumps(asdict(self))}\n\n"


class EventBus:
    """Per-doc_id async queue fan-out. One producer (ingest task), one consumer (SSE stream)."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def queue_for(self, doc_id: str) -> asyncio.Queue:
        return self._queues.setdefault(doc_id, asyncio.Queue())

    async def publish(self, event: StageEvent) -> None:
        await self.queue_for(event.doc_id).put(event)

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, event: StageEvent) -> None:
        """Called from the ingest worker thread → schedule onto the event loop."""
        asyncio.run_coroutine_threadsafe(self.publish(event), loop)

    async def stream(self, doc_id: str):
        q = self.queue_for(doc_id)
        while True:
            event = await q.get()
            yield event.to_sse()
            # terminal conditions — close the stream so the client doesn't hang:
            if event.status == FAILED:
                # any hard failure (extract/chunk/embed/index) ends the stream
                if event.stage != "summarizing":  # summary failure is non-fatal; keep streaming
                    break
                # summarizing failed: only terminal if ready already fired is handled below
            if event.stage == "summarizing" and event.status in (COMPLETED, FAILED):
                break


bus = EventBus()
