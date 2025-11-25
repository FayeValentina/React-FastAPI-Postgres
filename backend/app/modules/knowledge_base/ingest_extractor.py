"""Lightweight text extraction utilities for ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from charset_normalizer import from_bytes


@dataclass(slots=True)
class ExtractedElement:
    """Minimal representation of an extracted text block."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    category: str | None = None
    is_code: bool = False
    language: str | None = None


def _decode_bytes_to_text(raw: bytes) -> str:
    """Decode bytes into text, leaning on charset_normalizer when available."""
    if not raw:
        return ""

    try:
        best = from_bytes(raw).best()
        if best is not None:
            return str(best)
    except Exception:  # pragma: no cover - charset detection can fail
        pass

    return raw.decode("utf-8", errors="ignore")


def extract_from_text(content: str, *, source_ref: str | None = None) -> list[ExtractedElement]:
    """Normalize plain text input into a single ExtractedElement list."""
    text = (content or "").strip()
    if not text:
        return []

    metadata = {"source": source_ref} if source_ref else {}
    return [ExtractedElement(text=text, metadata=metadata)]


def extract_from_bytes(
    raw: bytes,
    *,
    filename: str | None = None,
) -> tuple[str, list[ExtractedElement]]:
    """Decode text files into ExtractedElements; only text payloads are supported."""
    decoded = _decode_bytes_to_text(raw)
    if not decoded:
        return "", []

    elements = extract_from_text(decoded, source_ref=filename)
    return decoded, elements


__all__ = ["ExtractedElement", "extract_from_text", "extract_from_bytes"]
