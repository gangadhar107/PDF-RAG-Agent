"""Answer generation (§4.6) — Groq CoT 3-step + citations + refusal.

Assembles top-K ENRICHED chunks (+ section/page) into context, runs the 3-step CoT prompt,
and parses out the final answer + whether the model refused ("not found"). Recent chat
history (§4.0) is prepended for conversational continuity when provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ragcore.ingest.embed import build_enriched_text
from ragcore.llm.generate import generate
from ragcore.retrieve.hybrid import Candidate

_PROMPT_PATH = Path(__file__).parent.parent / "llm" / "prompts" / "answer.txt"
_SYSTEM = _PROMPT_PATH.read_text(encoding="utf-8")

NOT_FOUND_SENTINEL = "The answer is not found in the document."


@dataclass
class Answer:
    text: str                     # final answer sentence (STEP 3)
    full_response: str            # full CoT (kept for eval debugging of ✅✅❌ cases)
    not_found: bool
    sources: list[tuple[str | None, int | None]]  # (section, page) of context chunks


def _format_context(candidates: list[Candidate], company: str | None,
                    fiscal_period: str | None) -> str:
    blocks = []
    for i, c in enumerate(candidates, 1):
        enriched = build_enriched_text(c.content, c.section, company, fiscal_period)
        blocks.append(f"[Excerpt {i} | page {c.page_number}]\n{enriched}")
    return "\n\n".join(blocks)


def _parse_answer(response: str) -> tuple[str, bool]:
    if NOT_FOUND_SENTINEL.lower() in response.lower():
        return NOT_FOUND_SENTINEL, True
    # extract STEP 3 answer if present, else use the whole response
    marker = "STEP 3"
    if marker in response:
        tail = response.split(marker, 1)[1]
        tail = tail.split(":", 1)[1] if ":" in tail else tail
        return tail.strip(), False
    return response.strip(), False


def generate_answer(
    question: str,
    candidates: list[Candidate],
    *,
    company: str | None = None,
    fiscal_period: str | None = None,
    history: list[dict] | None = None,
) -> Answer:
    context = _format_context(candidates, company, fiscal_period)

    user_parts = []
    if history:
        turns = "\n".join(f"{t['role']}: {t['content']}" for t in history[-5:])
        user_parts.append(f"CONVERSATION SO FAR:\n{turns}\n")
    user_parts.append(f"CONTEXT:\n{context}\n\nQUESTION: {question}")
    user = "\n".join(user_parts)

    response = generate(_SYSTEM, user, temperature=0.0, max_tokens=2048)
    text, not_found = _parse_answer(response)

    return Answer(
        text=text,
        full_response=response,
        not_found=not_found,
        sources=[(c.section, c.page_number) for c in candidates],
    )
