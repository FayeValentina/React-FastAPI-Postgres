"""Document extraction utilities powered by unstructured."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, List, Mapping

from charset_normalizer import from_bytes
from unstructured.documents.elements import Element  # type: ignore
from unstructured.partition.auto import partition  # type: ignore

from .language import normalize_language_value

@dataclass(slots=True)
class ExtractedElement:
    """Normalized representation of a document element returned by unstructured."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    category: str | None = None
    is_code: bool = False
    language: str | None = None


def _extract_language(metadata: Mapping[str, Any], meta_obj: Any) -> str | None:
    for key in ("language", "languages"):
        if key in metadata:
            lang = normalize_language_value(metadata[key])
            if lang:
                return lang
    if meta_obj is not None:
        for key in ("language", "languages"):
            lang = normalize_language_value(getattr(meta_obj, key, None))
            if lang:
                return lang
    return None


def _element_to_payload(element: Element) -> ExtractedElement | None:
    text = (getattr(element, "text", None) or "").strip()
    if not text:
        return None

    metadata = {}
    meta_obj = getattr(element, "metadata", None)
    if meta_obj is not None:
        try:
            metadata = {k: v for k, v in meta_obj.to_dict().items() if v is not None}
        except Exception:  # pragma: no cover - unstructured edge cases
            metadata = {}

    category = getattr(element, "category", None)
    is_code = bool(category and category.lower() == "code")
    language = _extract_language(metadata, getattr(element, "metadata", None))

    return ExtractedElement(
        text=text,
        metadata=metadata,
        category=category,
        is_code=is_code,
        language=language,
    )


def _process_partition_elements(
    elements: list[Element] | None,
    *,
    source_ref: str | None = None,
) -> list[ExtractedElement]:
    payloads: List[ExtractedElement] = []
    for item in elements or []:
        payload = _element_to_payload(item)
        if payload is None:
            continue
        if source_ref and "source" not in payload.metadata:
            payload.metadata["source"] = source_ref
        payloads.append(payload)
    return payloads


def _decode_bytes_to_text(raw: bytes) -> str:
    if not raw:
        return ""

    try:
        best = from_bytes(raw).best()
        if best is not None:
            return str(best)
    except Exception:  # pragma: no cover - charset detection failure
        pass

    return raw.decode("utf-8", errors="ignore")


def extract_from_text(
    content: str,
    *,
    source_ref: str | None = None,
) -> list[ExtractedElement]:
    """Extract structured elements from raw text input."""

    text = (content or "").strip()
    if not text:
        return []

    try:
        elements = partition(
            text=text,
            metadata_filename=source_ref,
            include_metadata=True,
        )
    except Exception:  # pragma: no cover - fallback to plain text chunk
        return [ExtractedElement(text=text, metadata={"source": source_ref} if source_ref else {})]

    payloads = _process_partition_elements(elements, source_ref=source_ref)
    if payloads:
        return payloads

    return [ExtractedElement(text=text, metadata={"source": source_ref} if source_ref else {})]


def extract_from_bytes(
    raw: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[str, list[ExtractedElement]]:
    """Extract structured elements from a binary payload, returning plain text fallback."""

    fallback = _decode_bytes_to_text(raw)
    if not raw:
        return fallback, []

    buffer = io.BytesIO(raw)

    try:
        elements = partition(
            file=buffer,
            content_type=content_type,
            metadata_filename=filename,
            include_metadata=True,
        )
    except Exception:  # pragma: no cover - fallback to decoded text
        metadata = {"source": filename} if filename else {}
        return fallback, [ExtractedElement(text=fallback, metadata=metadata)]

    payloads = _process_partition_elements(elements, source_ref=filename)
    if payloads:
        return fallback, payloads

    metadata = {"source": filename} if filename else {}
    return fallback, [ExtractedElement(text=fallback, metadata=metadata)]


__all__ = ["ExtractedElement", "extract_from_text", "extract_from_bytes"]
