"""Eval-mode metadata lookup (§2.1b) — EVAL entry point, NOT core.

Looks up company / doc_period by doc_name in financebench_document_information.jsonl and
feeds them into ingest(...). Keeps ragcore benchmark-agnostic: the core never reads
FinanceBench files; this wrapper does, then calls the same public ingest() signature.
"""

from __future__ import annotations

import json
import uuid
from functools import lru_cache
from pathlib import Path

from ragcore.config import settings
from ragcore.ingest.pipeline import ingest


@lru_cache(maxsize=1)
def _doc_info() -> dict[str, dict]:
    """doc_name -> {company, doc_period, ...} from the FinanceBench info file."""
    index: dict[str, dict] = {}
    with open(settings.financebench_doc_info, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                index[row["doc_name"]] = row
    return index


def lookup_metadata(doc_name: str) -> tuple[str | None, str | None]:
    """Return (company, fiscal_period) for a FinanceBench doc_name; (None, None) if absent."""
    row = _doc_info().get(doc_name)
    if not row:
        return None, None
    period = row.get("doc_period")
    return row.get("company"), (f"FY{period}" if period else None)


def ingest_financebench_doc(doc_name: str, **kwargs) -> uuid.UUID:
    """Ingest a FinanceBench PDF by doc_name, injecting known-good metadata (eval mode)."""
    pdf = settings.financebench_pdfs / f"{doc_name}.pdf"
    if not pdf.exists():
        raise FileNotFoundError(f"FinanceBench PDF not found: {pdf}")
    company, fiscal_period = lookup_metadata(doc_name)
    return ingest(pdf, company=company, fiscal_period=fiscal_period, **kwargs)
