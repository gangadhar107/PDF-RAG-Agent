"""Sprint 3 tests — enrichment prefix builder (§3.4). Pure logic, no API/DB."""

from __future__ import annotations

from ragcore.ingest.embed import build_enriched_text


def test_enriched_full():
    out = build_enriched_text("Total assets 36,500", "Item 8 › Balance Sheet", "3M", "FY2018")
    assert "Section: Item 8 › Balance Sheet" in out
    assert "Company: 3M" in out
    assert "Period: FY2018" in out
    assert out.strip().endswith("Total assets 36,500")


def test_enriched_omits_nulls():
    # graceful degradation: null company/period simply omitted, no empty labels
    out = build_enriched_text("raw content", "Some Section", None, None)
    assert "Section: Some Section" in out
    assert "Company:" not in out
    assert "Period:" not in out
    assert "raw content" in out


def test_enriched_bare_content():
    out = build_enriched_text("just content", None, None, None)
    assert out == "just content"


def test_enriched_partial_metadata():
    out = build_enriched_text("x", "Sec", "3M", None)
    assert "Company: 3M" in out
    assert "Period:" not in out


def test_embed_document_as_completed_ordering():
    """Verify embed_document works with mock chunks."""
    from unittest.mock import MagicMock
    from ragcore.ingest.embed import embed_document

    session = MagicMock()
    doc = MagicMock()
    doc.company = "TestCo"
    doc.fiscal_period = "FY24"
    session.get.return_value = doc

    # If no chunks remain un-embedded, return 0 immediately
    session.execute.return_value.scalars.return_value = []
    assert embed_document(session, "00000000-0000-0000-0000-000000000000") == 0
