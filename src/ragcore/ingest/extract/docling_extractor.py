"""Docling extractor — swap target if pymupdf4llm fails the Sprint 1 table checkpoint.

Not installed by default (heavier dep). To use: add `docling` to pyproject and set
PDF_EXTRACTOR=docling.
"""

from __future__ import annotations

from pathlib import Path

from ragcore.ingest.extract.base import ExtractionResult


class DoclingExtractor:
    def extract(self, pdf_path: Path) -> ExtractionResult:
        raise NotImplementedError(
            "Docling not wired yet — swap target if pymupdf4llm mangles tables (Sprint 1)."
        )
