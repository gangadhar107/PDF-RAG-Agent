"""Map-reduce document summarization (§2.4).

Runs its OWN coarse split over the extracted markdown — NOT the retrieval `chunks` table
(the summary branch forks in parallel with chunking, so those rows may not exist yet; a
dependency would secretly re-serialize the fork).

map:    summarize each coarse window (section-sized) → window summaries
reduce: synthesize window summaries → final document summary

Non-load-bearing (Option B): a failure sets summary_status='failed' but never blocks chat.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from ragcore.config import settings
from ragcore.db import repositories as repo
from ragcore.db.engine import get_session
from ragcore.llm.generate import generate
from ragcore.tokens import count_tokens

_MAP_PROMPT = (Path(__file__).parent.parent / "llm" / "prompts" / "summarize_map.txt").read_text(encoding="utf-8")
_REDUCE_PROMPT = (Path(__file__).parent.parent / "llm" / "prompts" / "summarize_reduce.txt").read_text(encoding="utf-8")

_PAGE_RE = re.compile(r"<!--\s*page:\d+\s*-->")


def _coarse_windows(markdown: str, window_tokens: int = 3000) -> list[str]:
    """Split markdown into large section-sized windows for the map step.

    Prefer header boundaries; greedily pack sections up to ~window_tokens. Independent of the
    retrieval chunker (§2.4)."""
    md = _PAGE_RE.sub("", markdown)
    # split on top-level headers, keep the header with its body
    parts = re.split(r"(?m)^(?=#{1,3}\s)", md)
    parts = [p.strip() for p in parts if p.strip()]

    windows: list[str] = []
    cur: list[str] = []
    cur_tok = 0
    for p in parts:
        pt = count_tokens(p)
        if cur and cur_tok + pt > window_tokens:
            windows.append("\n\n".join(cur))
            cur, cur_tok = [], 0
        # a single oversized section: hard-slice by chars to fit
        if pt > window_tokens:
            approx = window_tokens * 4  # ~4 chars/token
            for i in range(0, len(p), approx):
                windows.append(p[i:i + approx])
            continue
        cur.append(p)
        cur_tok += pt
    if cur:
        windows.append("\n\n".join(cur))
    return windows or [md[:12000]]


def summarize_document(doc_id: uuid.UUID, markdown: str,
                       max_windows: int = 40) -> str:
    """Map-reduce summarize; persist to documents row. Returns the final summary.

    Sets summary_status generating→completed (or failed). Never raises to the caller's
    critical path — summary is non-load-bearing (Option B)."""
    with get_session() as s:
        repo.set_summary(s, doc_id, status="generating", model=settings.gemini_gen_model)

    try:
        windows = _coarse_windows(markdown)[:max_windows]

        # MAP
        window_summaries = []
        for w in windows:
            window_summaries.append(generate(_MAP_PROMPT, w, temperature=0.0, max_tokens=800))

        # REDUCE
        joined = "\n\n".join(f"- {ws}" for ws in window_summaries)
        final = generate(_REDUCE_PROMPT, joined, temperature=0.0, max_tokens=2048).strip()

        with get_session() as s:
            repo.set_summary(s, doc_id, text=final, status="completed",
                             model=settings.gemini_gen_model)
        return final

    except Exception as e:  # noqa: BLE001 — non-load-bearing; record failure, don't propagate to chat
        with get_session() as s:
            repo.set_summary(s, doc_id, status="failed")
        raise RuntimeError(f"Summary failed for {doc_id}: {e}") from e
