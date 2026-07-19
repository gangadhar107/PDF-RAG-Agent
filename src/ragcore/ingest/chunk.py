"""3-pass chunker (§3.1).

    markdown -> [Pass 1 structural split] -> [Pass 2 table handling]
             -> [Pass 3 size-normalize + clean] -> list[ChunkData]

Design facts locked from Sprint 1's real 3M 10-K:
  - headers span levels 1-4, wrapped in **bold**/<u> markup -> cleaned to plain section labels
  - page position tracked via `<!-- page:N -->` markers injected by the extractor
  - tables are standard markdown (with `|---|` separators); kept ATOMIC (69% of evidence)
  - heavy `<br>` / `**` markup noise -> stripped from content before storage

`content` is RAW (cleaned of markup, no enrichment prefix); the enrichment prefix is
reconstructed at embed/rerank/answer time from section + company/period (§3.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ragcore.config import settings
from ragcore.tokens import count_tokens

# ---------------------------------------------------------------------------
# regexes
# ---------------------------------------------------------------------------
_PAGE_RE = re.compile(r"<!--\s*page:(\d+)\s*-->")
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BR_RE = re.compile(r"<br\s*/?>", re.I)
_TAG_RE = re.compile(r"</?u>|</?b>|</?i>", re.I)
_BOLD_RE = re.compile(r"\*\*")
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")


def clean_markup(text: str) -> str:
    """Strip pymupdf4llm noise: <br>, **bold**, <u> tags. Preserve table pipes & newlines."""
    text = _BR_RE.sub(" ", text)
    text = _TAG_RE.sub("", text)
    text = _BOLD_RE.sub("", text)
    text = _MULTISPACE_RE.sub(" ", text)
    return text.strip()


def _clean_header(text: str) -> str:
    return clean_markup(text).strip("# ").strip()


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
@dataclass
class ChunkData:
    content: str            # RAW cleaned text (no enrichment prefix)
    section: str | None     # heading path e.g. "Item 8 › Consolidated Balance Sheet"
    page_number: int | None
    is_table: bool
    token_count: int
    chunk_index: int = -1   # assigned at the end


@dataclass
class _Section:
    section_path: str | None
    page_number: int | None
    lines: list[str] = field(default_factory=list)


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _is_separator_row(line: str) -> bool:
    return bool(re.match(r"^\s*\|[\s:|-]+\|\s*$", line))


# ---------------------------------------------------------------------------
# Pass 1 — structural split (header-aware) + page tracking
# ---------------------------------------------------------------------------
def _pass1_sections(markdown: str) -> list[_Section]:
    heading_stack: dict[int, str] = {}
    current_page: int | None = None
    sections: list[_Section] = []
    cur = _Section(section_path=None, page_number=None)

    def path() -> str | None:
        if not heading_stack:
            return None
        return " › ".join(heading_stack[lvl] for lvl in sorted(heading_stack))

    for raw in markdown.splitlines():
        pm = _PAGE_RE.search(raw)
        if pm:
            current_page = int(pm.group(1))
            continue  # marker itself is not content

        hm = _HEADER_RE.match(raw)
        if hm:
            level = len(hm.group(1))
            label = _clean_header(hm.group(2))
            # new heading closes the current section
            if cur.lines:
                sections.append(cur)
            # update stack: set this level, drop deeper levels
            for lvl in [l for l in heading_stack if l > level]:
                heading_stack.pop(lvl)
            if label:
                heading_stack[level] = label
            cur = _Section(section_path=path(), page_number=current_page)
            continue

        if cur.page_number is None and raw.strip():
            cur.page_number = current_page
        cur.lines.append(raw)

    if cur.lines:
        sections.append(cur)
    return sections


# ---------------------------------------------------------------------------
# Pass 2 — separate atomic table blocks from prose within a section
# ---------------------------------------------------------------------------
@dataclass
class _Block:
    text: str
    is_table: bool


def _pass2_blocks(section: _Section) -> list[_Block]:
    blocks: list[_Block] = []
    buf: list[str] = []
    buf_is_table = False

    def flush():
        nonlocal buf, buf_is_table
        if buf:
            text = "\n".join(buf).strip()
            if text:
                blocks.append(_Block(text=text, is_table=buf_is_table))
        buf = []
        buf_is_table = False

    for line in section.lines:
        is_tbl = _is_table_row(line) or _is_separator_row(line)
        if is_tbl != buf_is_table and buf:
            flush()
        buf_is_table = is_tbl
        buf.append(line)
    flush()
    return blocks


# ---------------------------------------------------------------------------
# Pass 3 — size-normalize + clean
# ---------------------------------------------------------------------------
def _split_prose(text: str, target: int, hard_max: int, overlap_tokens: int) -> list[str]:
    """Greedy paragraph packing to `target`; oversized paragraphs split by sentence.
    Consecutive chunks share ~overlap_tokens of trailing text."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units: list[str] = []
    for p in paras:
        if count_tokens(p) <= hard_max:
            units.append(p)
        else:
            units.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip())

    chunks: list[str] = []
    cur: list[str] = []
    for u in units:
        trial = "\n\n".join([*cur, u])
        if cur and count_tokens(trial) > target:
            chunks.append("\n\n".join(cur))
            # seed overlap from the tail of the just-finished chunk
            if overlap_tokens > 0:
                tail = "\n\n".join(cur)
                cur = [_tail_tokens(tail, overlap_tokens), u]
            else:
                cur = [u]
        else:
            cur.append(u)
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def _tail_tokens(text: str, n: int) -> str:
    words = text.split()
    # approx: ~1.3 tokens/word -> take last n/1.3 words; cheap and good enough for overlap
    keep = max(1, int(n / 1.3))
    return " ".join(words[-keep:])


def _split_table_rowgroups(table: str, hard_max: int) -> list[str]:
    """Oversized table -> split by row-groups, REPEATING header rows on each part (§3.1)."""
    rows = [r for r in table.splitlines() if r.strip()]
    # header = leading rows up to & including the separator row
    header: list[str] = []
    body_start = 0
    for i, r in enumerate(rows):
        header.append(r)
        if _is_separator_row(r):
            body_start = i + 1
            break
    else:
        header = rows[:1]
        body_start = 1

    body = rows[body_start:]
    parts: list[str] = []
    cur: list[str] = []
    for row in body:
        trial = "\n".join(header + cur + [row])
        if cur and count_tokens(trial) > hard_max:
            parts.append("\n".join(header + cur))
            cur = [row]
        else:
            cur.append(row)
    if cur:
        parts.append("\n".join(header + cur))
    return parts or [table]


def chunk_markdown(markdown: str) -> list[ChunkData]:
    target = settings.chunk_target_tokens
    hard_max = settings.chunk_max_tokens
    embed_max = settings.embed_max_input_tokens
    overlap = int(target * settings.chunk_overlap_ratio)

    out: list[ChunkData] = []
    for section in _pass1_sections(markdown):
        for block in _pass2_blocks(section):
            cleaned = clean_markup(block.text)
            if not cleaned:
                continue

            if block.is_table:
                # atomic up to the embedder limit; else row-group split (repeat header)
                if count_tokens(cleaned) <= embed_max:
                    pieces = [cleaned]
                else:
                    pieces = [clean_markup(p) for p in _split_table_rowgroups(block.text, embed_max)]
                for piece in pieces:
                    out.append(ChunkData(piece, section.section_path, section.page_number,
                                         True, count_tokens(piece)))
            else:
                for piece in _split_prose(cleaned, target, hard_max, overlap):
                    tc = count_tokens(piece)
                    # drop tiny prose noise (page numbers, "None.", ToC fragments).
                    # tables are NEVER dropped — a short table can be real evidence.
                    if tc < settings.chunk_min_tokens:
                        continue
                    out.append(ChunkData(piece, section.section_path, section.page_number,
                                         False, tc))

    for i, c in enumerate(out):
        c.chunk_index = i
    return out
