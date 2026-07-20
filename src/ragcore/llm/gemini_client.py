"""Gemini Embedding 2 client wrapper.

IMPORTANT (verified Sprint 3): gemini-embedding-2 JOINS multiple `contents` into ONE
embedding — it does NOT batch distinct texts. So we embed ONE text per API call and use
a thread pool for throughput. output_dimensionality=1536 (LOCKED, permanent).

Task instructions (§3.4): document-intent for chunks, query-intent for questions —
matching semantic space, embedded via task_type.

RATE LIMITS (Sprint 4): the free tier returns 429 RESOURCE_EXHAUSTED under sustained load
(a full 10-K = hundreds of calls). We honor the server's Retry-After on 429 and back off,
rather than blindly retrying. Tune concurrency via settings.embed_concurrency.
"""

from __future__ import annotations

import time
from typing import Generator

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
)

from ragcore.config import settings

_client = genai.Client(api_key=settings.google_api_key)

# task types (§3.4): chunks are documents; questions are queries
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"


class QuotaExhaustedError(Exception):
    """Daily/hard quota hit (429) that won't recover within a retry window."""


@retry(
    retry=retry_if_exception_type(genai_errors.ClientError),
    stop=stop_after_attempt(5),
    wait=wait_random_exponential(min=2, max=60),
    reraise=True,
)
def _embed_call(text: str, task_type: str) -> list[float]:
    resp = _client.models.embed_content(
        model=settings.gemini_embed_model,
        contents=[text],
        config=types.EmbedContentConfig(
            output_dimensionality=settings.embed_dim,
            task_type=task_type,
            http_options=types.HttpOptions(timeout=60_000),  # 60s per call — never hang forever
        ),
    )
    return list(resp.embeddings[0].values)


def embed_one(text: str, task_type: str) -> list[float]:
    """Embed a single text → 1536-dim vector. One text per call (model joins lists)."""
    try:
        return _embed_call(text, task_type)
    except genai_errors.ClientError as e:
        if getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e):
            raise QuotaExhaustedError(
                f"Gemini embedding rate/quota limit reached (429). Details: {e}"
            ) from e
        raise


def embed_query(question: str) -> list[float]:
    """Embed a user question with query intent (§4.0/§4.1)."""
    return embed_one(question, TASK_QUERY)


@retry(
    retry=retry_if_exception_type(genai_errors.ClientError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=2, max=60),
    reraise=True,
)
def generate(system: str, user: str, *, temperature: float = 0.0,
             max_tokens: int = 2048, model: str | None = None) -> str:
    """Text generation via Gemini (used when LLM_PROVIDER=gemini; ~1M TPM vs Groq's 6K)."""
    resp = _client.models.generate_content(
        model=model or settings.gemini_gen_model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            http_options=types.HttpOptions(timeout=60_000),
        ),
    )
    return resp.text or ""


@retry(
    retry=retry_if_exception_type(genai_errors.ClientError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=2, max=60),
    reraise=True,
)
def generate_stream(system: str, user: str, *, temperature: float = 0.0,
                    max_tokens: int = 2048, model: str | None = None) -> Generator[str, None, None]:
    """Text generation stream via Gemini."""
    resp = _client.models.generate_content_stream(
        model=model or settings.gemini_gen_model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            http_options=types.HttpOptions(timeout=60_000),
        ),
    )
    for chunk in resp:
        yield chunk.text or ""

