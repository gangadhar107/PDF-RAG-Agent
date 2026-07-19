"""pymupdf4llm extractor — PDF_EXTRACTOR default.

Converts PDF -> Markdown with page markers. Table fidelity is validated in Sprint 1's
checkpoint; if it mangles FinanceBench tables, swap to docling via config (no other change).
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pymupdf4llm

from ragcore.ingest.extract.base import ExtractionResult


class PyMuPDF4LLMExtractor:
    def extract(self, pdf_path: Path) -> ExtractionResult:
        pdf_path = Path(pdf_path)
        # page_chunks=True yields per-page dicts so we can preserve page boundaries.
        pages = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)

        parts: list[str] = []
        for i, page in enumerate(pages, start=1):
            text = page["text"] if isinstance(page, dict) else str(page)
            # explicit page marker so the chunker can attribute page_number downstream
            parts.append(f"<!-- page:{i} -->\n{text}")
        markdown = "\n\n".join(parts)

        # authoritative page count from the raw doc (not the markdown split)
        with pymupdf.open(str(pdf_path)) as doc:
            page_count = doc.page_count

        return ExtractionResult(markdown=markdown, page_count=page_count)
