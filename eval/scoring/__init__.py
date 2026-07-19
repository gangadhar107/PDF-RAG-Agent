"""Answer-correctness router (§5.4): numeric-match for TERSE numeric golds, Claude judge
for prose AND reasoning-with-number golds (judge handles embedded figures correctly)."""

from __future__ import annotations

from eval.scoring.judge import judge_answer
from eval.scoring.numeric import is_pure_numeric_answer, numeric_match


def score_answer(question: str, gold: str, predicted: str, not_found: bool) -> tuple[bool, str]:
    """Return (correct, method). `predicted` should already be the STEP-3 final answer.
    Refusals are never 'correct'."""
    if not_found:
        return False, "refused"
    if is_pure_numeric_answer(gold):
        return numeric_match(gold, predicted), "numeric"
    j = judge_answer(question, gold, predicted)
    return j.correct, f"judge:{j.reason[:50]}"
