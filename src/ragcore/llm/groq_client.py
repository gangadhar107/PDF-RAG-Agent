"""Groq chat client wrapper — the single generation provider (llama-3.1-8b-instant).

Thin wrapper with retry/backoff. Used by metadata extraction (§2.1b), summary (§2.4),
query rewrite (§4.0), and answer generation (§4.6).

RATE LIMITS (Sprint 5): the free tier rate-limits (RateLimitError). We disable the SDK's
own silent retries (max_retries=0) so tenacity controls backoff visibly, and we retry
RateLimitError with long exponential waits rather than hanging.
"""

from __future__ import annotations

from typing import Generator

from groq import Groq, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ragcore.config import settings

_client = Groq(api_key=settings.groq_api_key, timeout=60.0, max_retries=0)

_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError)


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(6),
    wait=wait_exponential(min=4, max=90),
    reraise=True,
)
def chat(
    system: str,
    user: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    model: str | None = None,
) -> str:
    """Single-shot chat completion → returns the assistant message content."""
    resp = _client.chat.completions.create(
        model=model or settings.groq_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(6),
    wait=wait_exponential(min=4, max=90),
    reraise=True,
)
def chat_stream(
    system: str,
    user: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    model: str | None = None,
) -> Generator[str, None, None]:
    """Stream chat completion from Groq."""
    resp = _client.chat.completions.create(
        model=model or settings.groq_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in resp:
        yield chunk.choices[0].delta.content or ""
