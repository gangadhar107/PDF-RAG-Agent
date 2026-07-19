"""Numeric answer scoring (§5.4).

Normalize (currency symbols, commas, scale words, percent, accounting negatives) → compare
with 1% relative tolerance, with a ZERO-GOLD branch (absolute epsilon) to avoid div-by-zero
on legit exact-zero answers ($0 dividends, $0 YoY change).
"""

from __future__ import annotations

import re

from ragcore.config import settings

_SCALE = {
    "thousand": 1e3, "thousands": 1e3, "k": 1e3,
    "million": 1e6, "millions": 1e6, "mm": 1e6, "mn": 1e6, "m": 1e6,
    "billion": 1e9, "billions": 1e9, "bn": 1e9, "b": 1e9,
    "trillion": 1e12, "trillions": 1e12,
}
_NUM_RE = re.compile(r"[-+]?\$?\(?\d[\d,]*\.?\d*\)?")


def extract_number(text: str) -> float | None:
    """Best-effort: pull the primary numeric value from an answer string, applying scale
    words, percent, accounting parens (negatives). Returns None if no number found."""
    if text is None:
        return None
    s = text.strip().lower()

    m = _NUM_RE.search(s)
    if not m:
        return None
    raw = m.group(0)

    neg = raw.startswith("(") and raw.endswith(")") or raw.startswith("-")
    cleaned = raw.replace("$", "").replace(",", "").replace("(", "").replace(")", "").replace("+", "")
    try:
        val = float(cleaned)
    except ValueError:
        return None
    if neg:
        val = -abs(val)

    tail = s[m.end(): m.end() + 20]
    for word, mult in _SCALE.items():
        if re.search(rf"\b{re.escape(word)}\b", tail):
            val *= mult
            break

    return val


def numeric_match(gold: str, predicted: str,
                  rel_tol: float | None = None, zero_eps: float | None = None) -> bool:
    """True if the predicted number matches gold within tolerance (§5.4)."""
    rel_tol = settings.numeric_rel_tolerance if rel_tol is None else rel_tol
    zero_eps = settings.numeric_zero_epsilon if zero_eps is None else zero_eps

    g = extract_number(gold)
    p = extract_number(predicted)
    if g is None or p is None:
        return False

    if g == 0:
        return abs(p) < zero_eps            # zero-gold branch (Bug-4 fix)
    return abs(p - g) / abs(g) < rel_tol


_WORD_RE = re.compile(r"[a-zA-Z]{4,}")  # words of 4+ letters = prose signal


def is_pure_numeric_answer(gold: str) -> bool:
    """Route to numeric_match ONLY for terse numeric golds (e.g. "$1,577 million", "12.5%").

    A reasoning answer that merely CONTAINS a number ("Yes. The quick ratio is 1.57,
    calculated as ...") must go to the JUDGE — naive numeric extraction would grab the wrong
    figure from either side. Heuristic: has a number AND few prose words.
    """
    if extract_number(gold) is None:
        return False
    prose_words = len(_WORD_RE.findall(gold))
    return prose_words <= 3

