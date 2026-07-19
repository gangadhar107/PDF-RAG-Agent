"""Extractor interface — the #1 risk seam (§ Library Stack).

PDF table fidelity dominates FinanceBench score (69% tabular evidence). This interface
keeps the extractor swappable so Sprint 1's table-fidelity checkpoint can swap
pymupdf4llm -> docling without touching anything downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class ExtractionResult:
    markdown: str
    page_count: int


class Extractor(Protocol):
    """Any extractor: PDF path -> markdown + page count."""

    def extract(self, pdf_path: Path) -> ExtractionResult: ...


def get_extractor(name: str) -> Extractor:
    """Factory keyed on config.pdf_extractor. Add new backends here."""
    if name == "pymupdf4llm":
        from ragcore.ingest.extract.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
        return PyMuPDF4LLMExtractor()
    if name == "docling":
        from ragcore.ingest.extract.docling_extractor import DoclingExtractor
        return DoclingExtractor()
    raise ValueError(f"Unknown PDF_EXTRACTOR: {name!r}")
