"""Sprint 2 tests — the 3-pass chunker. Fast, no-DB, no-network."""

from __future__ import annotations

from ragcore.ingest.chunk import chunk_markdown, clean_markup


def test_clean_markup_strips_noise():
    assert clean_markup("**$**<br>**32,765**") == "$ 32,765"
    assert "<br>" not in clean_markup("a<br>b")
    assert "**" not in clean_markup("**bold**")


def test_page_marker_tracking():
    md = (
        "<!-- page:1 -->\n# Intro\n"
        + ("Hello world this is genuine content on the first page. " * 8)
        + "\n<!-- page:2 -->\n## Next\n"
        + ("More genuine content lives here on the second page of text. " * 8)
    )
    chunks = chunk_markdown(md)
    assert chunks, "expected at least one chunk"
    pages = {c.page_number for c in chunks}
    assert pages <= {1, 2}
    assert pages, "page numbers should be tracked"


def test_section_labels_inherited():
    md = "# Item 8\n## Balance Sheet\n" + ("Real sentence of content. " * 20)
    chunks = chunk_markdown(md)
    assert any(c.section and "Balance Sheet" in c.section for c in chunks)


def test_table_kept_atomic_and_flagged():
    md = (
        "# Financials\n"
        "|(Millions)|2018|2017|\n"
        "|---|---|---|\n"
        "|Net sales|$32,765|$31,657|\n"
        "|Total assets|$36,500|$37,987|\n"
    )
    chunks = chunk_markdown(md)
    tables = [c for c in chunks if c.is_table]
    assert len(tables) == 1
    assert "Net sales" in tables[0].content
    assert "Total assets" in tables[0].content  # not split


def test_tiny_prose_dropped_tables_kept():
    md = "# H\nNone.\n\n|a|b|\n|---|---|\n|1|2|"
    chunks = chunk_markdown(md)
    # "None." prose is dropped; the tiny table survives
    assert all(not (c.content == "None." and not c.is_table) for c in chunks)
    assert any(c.is_table for c in chunks)


def test_chunk_index_sequential():
    md = "# A\n" + ("Sentence content here for testing. " * 40)
    chunks = chunk_markdown(md)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
