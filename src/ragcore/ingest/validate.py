"""File-level validation — runs at upload, BEFORE extraction (§ wireframe 1).

Checks type / size / corruption. Content-level emptiness is a separate concern handled
post-extraction by content_gate.py (§2.1a).
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

MAX_BYTES = 100 * 1024 * 1024  # 100 MB guard


class ValidationError(Exception):
    """Raised when a file fails pre-extraction validation."""


def validate_pdf(pdf_path: str | Path) -> None:
    """Raise ValidationError if the file isn't a usable PDF. Returns None on success."""
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise ValidationError(f"File not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValidationError(f"Not a PDF: {pdf_path.suffix!r} (only .pdf supported)")

    size = pdf_path.stat().st_size
    if size == 0:
        raise ValidationError("File is empty (0 bytes)")
    if size > MAX_BYTES:
        raise ValidationError(f"File too large: {size} bytes (max {MAX_BYTES})")

    # corruption check — can PyMuPDF open it and does it have pages?
    try:
        with pymupdf.open(str(pdf_path)) as doc:
            if doc.page_count == 0:
                raise ValidationError("PDF has no pages")
    except ValidationError:
        raise
    except Exception as e:  # noqa: BLE001 - surface any parse failure as a validation error
        raise ValidationError(f"Corrupt or unreadable PDF: {e}") from e
