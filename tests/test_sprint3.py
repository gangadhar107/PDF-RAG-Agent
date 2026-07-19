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
