"""Provider-agnostic text generation (swappable: groq | gemini).

Set LLM_PROVIDER in .env. Groq (llama-3.1-8b-instant) is the intended primary but its free
tier is 6K TPM — too tight for RAG context. Gemini (gemini-flash-latest, ~1M TPM, already
billed) is the working default. Flip the env var to switch; both share this signature so
answer/summary/rewrite code is provider-independent. Also enables a provider ablation.
"""

from __future__ import annotations

from typing import Generator
from ragcore.config import settings


def generate(system: str, user: str, *, temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    """Dispatch a single-shot generation to the configured provider."""
    provider = settings.llm_provider.lower()
    if provider == "groq":
        from ragcore.llm.groq_client import chat
        return chat(system, user, temperature=temperature, max_tokens=max_tokens)
    if provider == "gemini":
        from ragcore.llm.gemini_client import generate as gemini_generate
        return gemini_generate(system, user, temperature=temperature, max_tokens=max_tokens)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r} (use groq|gemini)")


def generate_stream(system: str, user: str, *, temperature: float = 0.0,
                    max_tokens: int = 2048) -> Generator[str, None, None]:
    """Dispatch a generation stream to the configured provider."""
    provider = settings.llm_provider.lower()
    if provider == "groq":
        from ragcore.llm.groq_client import chat_stream
        return chat_stream(system, user, temperature=temperature, max_tokens=max_tokens)
    if provider == "gemini":
        from ragcore.llm.gemini_client import generate_stream as gemini_generate_stream
        return gemini_generate_stream(system, user, temperature=temperature, max_tokens=max_tokens)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r} (use groq|gemini)")
