"""Content gate — post-extraction, PRE-FORK (§2.1a).

File-level validation happens at upload; content-level emptiness can only be detected
after extraction. Gates on TOKEN COUNT ONLY — chunks don't exist yet at this point
(chunking is post-fork), so chunk count cannot be a criterion.

Catches: empty PDFs, scanned/image-only PDFs (no text layer). Fail => existing
Processing-Failed flow.
"""

from __future__ import annotations

from ragcore.config import settings
from ragcore.tokens import count_tokens

EMPTY_DOC_MESSAGE = (
    "No extractable text found. The document may be empty or image-only (scanned)."
)


class EmptyDocumentError(Exception):
    """Raised when extracted markdown has too little text to be usable."""


def check_content(markdown: str) -> int:
    """Return token count if the doc passes; raise EmptyDocumentError if effectively empty.

    Threshold = settings.content_gate_min_tokens (~50). Genuinely-tiny-but-real docs pass.
    """
    n_tokens = count_tokens(markdown)
    if n_tokens < settings.content_gate_min_tokens:
        raise EmptyDocumentError(EMPTY_DOC_MESSAGE)
    return n_tokens
