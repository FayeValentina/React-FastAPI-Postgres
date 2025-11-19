"基于 LangChain 文本分割器构建的分块实用程序。"

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, List, Mapping

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
)

from .ingest_extractor import ExtractedElement

HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

DEFAULT_ENCODING = "cl100k_base"
MAX_CHUNK_TOKENS = 2000
CHUNK_OVERLAP = 200
CODE_TOKENS_PER_LINE = 12


@dataclass(slots=True)
class SplitChunk:
    content: str
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_code: bool = False


@lru_cache(maxsize=1)
def _markdown_splitter() -> MarkdownHeaderTextSplitter:
    return MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False)


def _text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=MAX_CHUNK_TOKENS,
        chunk_overlap=CHUNK_OVERLAP,
        encoding_name=DEFAULT_ENCODING,
    )


def _code_splitter() -> TokenTextSplitter:
    return TokenTextSplitter(
        encoding_name=DEFAULT_ENCODING,
        chunk_size=max(512, CODE_TOKENS_PER_LINE * MAX_CHUNK_TOKENS // 8),
        chunk_overlap=CODE_TOKENS_PER_LINE * 2,
        keep_separator=False,
    )


def _split_code(text: str) -> List[str]:
    stripped = text.strip("\n")
    if not stripped:
        return []

    splitter = _code_splitter()
    try:
        pieces = [frag.strip("\n") for frag in splitter.split_text(stripped) if frag.strip()]
    except Exception:
        pieces = [stripped]
    return pieces or [stripped]


def _split_text(text: str) -> List[str]:
    splitter = _text_splitter()
    try:
        pieces = [frag.strip() for frag in splitter.split_text(text) if frag.strip()]
    except Exception:
        pieces = []
    if pieces:
        return pieces
    stripped = text.strip()
    return [stripped] if stripped else []


def _markdown_sections(text: str, base_metadata: Mapping[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    splitter = _markdown_splitter()
    try:
        documents = splitter.split_text(text)
    except Exception:
        yield text, dict(base_metadata)
        return

    if not documents:
        yield text, dict(base_metadata)
        return

    for doc in documents:
        metadata = dict(base_metadata)
        extra = getattr(doc, "metadata", {}) or {}
        for key, value in extra.items():
            if value:
                metadata[str(key)] = value
        yield doc.page_content, metadata


def split_elements(
    elements: Iterable[ExtractedElement],
) -> List[SplitChunk]:
    chunks: List[SplitChunk] = []

    for element in elements:
        text = (element.text or "").strip()
        if not text:
            continue

        base_meta = dict(element.metadata or {})
        if element.is_code:
            for chunk in _split_code(text):
                chunks.append(
                    SplitChunk(
                        content=chunk,
                        language=None,
                        metadata=dict(base_meta),
                        is_code=True,
                    )
                )
            continue

        for section_text, metadata in _markdown_sections(text, base_meta):
            section_meta = dict(metadata)
            for part in _split_text(section_text):
                chunks.append(
                    SplitChunk(
                        content=part,
                        language=None,
                        metadata=dict(section_meta),
                        is_code=False,
                    )
                )

    return chunks


__all__ = ["SplitChunk", "split_elements"]
