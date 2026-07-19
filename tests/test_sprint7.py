"""Sprint 7 tests — coarse windowing for map-reduce summary. Pure logic, no API/DB."""

from __future__ import annotations

from ragcore.generate.summarize import _coarse_windows


def test_windows_nonempty_on_empty():
    assert _coarse_windows("") == [""] or _coarse_windows("")


def test_windows_split_on_headers():
    md = "# A\n" + ("word " * 500) + "\n# B\n" + ("term " * 500)
    w = _coarse_windows(md, window_tokens=300)
    assert len(w) >= 2


def test_windows_strip_page_markers():
    md = "<!-- page:1 -->\n# Sec\nReal content here for the section body text.\n<!-- page:2 -->\nmore"
    w = _coarse_windows(md)
    assert all("<!-- page:" not in x for x in w)


def test_oversized_section_hard_sliced():
    md = "# Big\n" + ("token " * 5000)  # one huge section
    w = _coarse_windows(md, window_tokens=500)
    assert len(w) > 1  # got sliced
