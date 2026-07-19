"""Central configuration — reads .env via pydantic-settings.

Single source of truth for keys, DB URL, pinned models, and the locked tuning
parameters (RRF k, chunk sizes, top-K). Import `settings` anywhere in ragcore.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = two levels up from this file (src/ragcore/config.py -> repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- secrets / connection ---
    database_url: str = Field(..., alias="DATABASE_URL")
    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")
    google_api_key: str | None = Field(None, alias="GOOGLE_API_KEY")   # Sprint 3 blocker if unset
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")  # eval-only

    # --- pinned models ---
    llm_provider: str = Field("gemini", alias="LLM_PROVIDER")  # groq | gemini (swappable generation)
    groq_model: str = Field("llama-3.1-8b-instant", alias="GROQ_MODEL")
    gemini_gen_model: str = Field("gemini-flash-latest", alias="GEMINI_GEN_MODEL")  # generation (Groq wallet-blocked)
    gemini_embed_model: str = Field("gemini-embedding-2", alias="GEMINI_EMBED_MODEL")  # D2 CONFIRMED (real model ID)
    judge_model: str = Field("claude-haiku-4-5", alias="JUDGE_MODEL")

    # --- embeddings ---
    embed_dim: int = 1536                 # LOCKED — matches VECTOR(1536); permanent
    embed_max_input_tokens: int = 8192    # D3 CONFIRMED from API (gemini-embedding-2 inputTokenLimit)
    embed_concurrency: int = 10           # parallel embed calls (billing enabled → higher throughput)

    # --- ingestion ---
    pdf_extractor: str = Field("pymupdf4llm", alias="PDF_EXTRACTOR")   # swappable
    markdown_dir: Path = Field(REPO_ROOT / "data" / "markdown", alias="MARKDOWN_DIR")
    content_gate_min_tokens: int = 50     # §2.1a — below this => failed (empty/scanned)

    # --- chunking (§3.2 sweep center-points) ---
    chunk_target_tokens: int = 640        # 512-768 band midpoint
    chunk_max_tokens: int = 1024          # hard ceiling before force-split
    chunk_overlap_ratio: float = 0.15     # ~15% prose overlap; 0 for tables
    chunk_min_tokens: int = 15            # drop tiny prose noise (ToC/page-num fragments); tables exempt

    # --- retrieval (Layer 4) ---
    retrieval_top_n_each: int = 20        # per-retriever candidates before fusion
    rrf_k: int = 60                       # D6 — RRF constant
    rerank_top_k: int = 6                 # final context size (§4.4; max evidence 3 x2)
    history_window_turns: int = 5         # §4.0 conversational continuity

    # --- eval (Layer 5) ---
    financebench_dir: Path = REPO_ROOT / "data" / "financebench"
    numeric_rel_tolerance: float = 0.01   # §5.4
    numeric_zero_epsilon: float = 1e-6    # D5 — zero-gold branch
    retrieval_page_tolerance: int = 1     # §5.3 ±1 page match

    @property
    def financebench_questions(self) -> Path:
        return self.financebench_dir / "questions.jsonl"

    @property
    def financebench_doc_info(self) -> Path:
        return self.financebench_dir / "financebench_document_information.jsonl"

    @property
    def financebench_pdfs(self) -> Path:
        return self.financebench_dir / "pdfs"


settings = Settings()  # import this
