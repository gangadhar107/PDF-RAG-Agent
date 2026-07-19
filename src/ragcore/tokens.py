"""Shared tokenizer helper — tiktoken approximation (§3.2 note; Gemini tokenizer later)."""

from __future__ import annotations

import tiktoken

# cl100k_base is a reasonable, cheap approximation; not Gemini's exact tokenizer.
_ENC = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text or ""))
