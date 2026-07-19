"""LLM-as-judge (§5.4) — Claude Haiku 4.5, an independent 3rd vendor (not Groq/Gemini).

Judges prose-judgment answers (the ~half that aren't pure numbers). Binary correct/incorrect
+ one-line justification (logged for the ✅✅❌ disagreement analysis).
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ragcore.config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_JUDGE_SYSTEM = (
    "You are grading an answer against a gold answer. Mark CORRECT only if the response "
    "conveys the same factual conclusion as the gold answer. Ignore phrasing, formatting, "
    "and extra explanation. For numeric claims, the number must match the gold within "
    "rounding. Reply with EXACTLY one line: 'CORRECT: <reason>' or 'INCORRECT: <reason>'."
)


@dataclass
class Judgement:
    correct: bool
    reason: str


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
def judge_answer(question: str, gold: str, predicted: str) -> Judgement:
    msg = (
        f"QUESTION: {question}\n\n"
        f"GOLD ANSWER: {gold}\n\n"
        f"MODEL ANSWER: {predicted}"
    )
    resp = _client.messages.create(
        model=settings.judge_model,
        max_tokens=150,
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": msg}],
    )
    text = resp.content[0].text.strip()
    correct = text.upper().startswith("CORRECT")
    reason = text.split(":", 1)[1].strip() if ":" in text else text
    return Judgement(correct=correct, reason=reason)
