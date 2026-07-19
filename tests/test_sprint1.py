"""Sprint 1 tests — validation, content gate, extractor factory, eval metadata lookup.

Fast, no-network tests. The extraction + metadata LLM checks are done manually in the
Sprint 1 checkpoint (see tracker.md), not here.
"""

from __future__ import annotations

import pytest

from ragcore.ingest.content_gate import EmptyDocumentError, check_content
from ragcore.ingest.extract.base import get_extractor
from ragcore.ingest.validate import ValidationError, validate_pdf


def test_validate_missing_file():
    with pytest.raises(ValidationError):
        validate_pdf("/nonexistent/file.pdf")


def test_validate_non_pdf(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("hello")
    with pytest.raises(ValidationError):
        validate_pdf(f)


def test_content_gate_rejects_empty():
    with pytest.raises(EmptyDocumentError):
        check_content("tiny")


def test_content_gate_passes_real_text():
    text = "This is a real document. " * 50
    assert check_content(text) > 50


def test_extractor_factory_unknown():
    with pytest.raises(ValueError):
        get_extractor("does-not-exist")


def test_extractor_factory_pymupdf4llm():
    assert get_extractor("pymupdf4llm") is not None
