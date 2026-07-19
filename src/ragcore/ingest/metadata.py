"""Enrichment metadata extraction (§2.1b) — PRODUCTION mode.

company / fiscal_period feed the chunk enrichment prefix. Two sourcing modes:
  - EVAL: the eval wrapper looks them up in financebench_document_information.jsonl and
    passes them into ingest(...) directly — this module is NOT called.
  - PRODUCTION: ingest() calls extract_metadata() over the first page(s) of markdown.

Regex-first (SEC cover pages are predictable) → small Groq fallback. Both nullable:
on failure/low-confidence, return (None, None) → enrichment prefix simply omits them
(graceful degradation, never a hard failure).
"""

from __future__ import annotations

import json
import re

from ragcore.llm.generate import generate

# ~ first 2 pages worth of markdown is enough for a cover page
_FIRST_PAGES_CHARS = 6000

# fiscal year like "fiscal year ended December 31, 2022" / "FY2022" / "Form 10-K ... 2022"
_YEAR_RE = re.compile(r"\b(?:fiscal(?:\s+year)?|for the year ended|FY)\D{0,20}(19|20)\d{2}\b", re.I)
_BARE_YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")

_METADATA_PROMPT = (
    "You extract two fields from the first page of a financial filing. "
    "Return ONLY compact JSON: {\"company\": <str|null>, \"fiscal_period\": <str|null>}. "
    "company = the reporting entity's name. fiscal_period = the fiscal year/period "
    "(e.g. \"FY2022\"). Use null if not clearly present. No prose."
)


def _regex_pass(head: str) -> tuple[str | None, str | None]:
    period = None
    m = _YEAR_RE.search(head)
    if m:
        ys = re.search(r"(19|20)\d{2}", m.group(0))
        if ys:
            period = f"FY{ys.group(0)}"
    return None, period  # company is hard via regex; leave to LLM fallback


def _llm_pass(head: str) -> tuple[str | None, str | None]:
    try:
        raw = generate(_METADATA_PROMPT, head, max_tokens=100)
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        c = data.get("company")
        p = data.get("fiscal_period")
        return (c or None), (p or None)
    except Exception:  # noqa: BLE001 - metadata is non-load-bearing; degrade to null
        return None, None


def extract_metadata(markdown: str) -> tuple[str | None, str | None]:
    """Return (company, fiscal_period); either/both may be None (graceful degradation)."""
    head = markdown[:_FIRST_PAGES_CHARS]

    _, period = _regex_pass(head)
    company, llm_period = _llm_pass(head)

    # prefer regex period (cheap, deterministic) then LLM
    return company, (period or llm_period)
