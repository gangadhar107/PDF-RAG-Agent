"""Query rewriting for conversational continuity (§4.0).

A follow-up like "what about the same period last year?" is meaningless to retrieval in
isolation. Rewrite it into a STANDALONE question using recent chat history BEFORE embedding.
No-ops on already-standalone questions (so the FinanceBench eval — single-turn — is unaffected).
"""

from __future__ import annotations

from ragcore.llm.generate import generate

_REWRITE_SYSTEM = (
    "Given the conversation history and a follow-up question, rewrite the follow-up as a "
    "STANDALONE question that includes all necessary context (company, period, metric, etc.) "
    "so it can be understood without the history. If the follow-up is ALREADY standalone, "
    "return it unchanged. Return ONLY the rewritten question, nothing else."
)


def rewrite_question(question: str, history: list[dict] | None) -> str:
    """Return a standalone version of `question` given prior turns. No history → unchanged."""
    if not history:
        return question
    turns = "\n".join(f"{t['role']}: {t['content']}" for t in history[-5:])
    user = f"CONVERSATION HISTORY:\n{turns}\n\nFOLLOW-UP QUESTION: {question}\n\nSTANDALONE QUESTION:"
    try:
        out = generate(_REWRITE_SYSTEM, user, temperature=0.0, max_tokens=256).strip()
        return out or question
    except Exception:  # noqa: BLE001 — never block a query on rewrite failure; use original
        return question
