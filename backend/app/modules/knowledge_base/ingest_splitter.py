"""Chunking utilities built on LangChain text splitters."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, List, Mapping

from langchain_text_splitters import (  # type: ignore
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
)

from app.core.config import settings

from .ingest_extractor import ExtractedElement
from .language import (
    detect_language_meta,
    normalize_language_value,
)


HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

DEFAULT_ENCODING = "cl100k_base"
CODE_TOKENS_PER_LINE = 12

@dataclass(slots=True)
class SplitChunk:
    content: str
    language: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_code: bool = False


@dataclass(slots=True)
class ChunkingParameters:
    target_tokens_en: int
    target_tokens_cjk: int
    target_tokens_default: int
    overlap_ratio: float
    code_max_lines: int
    code_overlap_lines: int

    def target_tokens(self, lang: str | None) -> int:
        code = (lang or "en").lower()
        if code == "en":
            return self.target_tokens_en
        if code in {"zh", "ja"}:
            return self.target_tokens_cjk
        return self.target_tokens_default

    def overlap_tokens(self, chunk_tokens: int) -> int:
        if chunk_tokens <= 0:
            return 0
        overlap = int(chunk_tokens * max(0.0, min(1.0, self.overlap_ratio)))
        return max(0, overlap)

    @property
    def code_chunk_tokens(self) -> int:
        return max(16, self.code_max_lines * CODE_TOKENS_PER_LINE)

    @property
    def code_overlap_tokens(self) -> int:
        return max(0, self.code_overlap_lines * CODE_TOKENS_PER_LINE)


@lru_cache(maxsize=1)
def _markdown_splitter() -> MarkdownHeaderTextSplitter:
    return MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False)


def build_chunking_parameters() -> ChunkingParameters:
    """Construct ingestion chunking parameters using static settings."""

    return ChunkingParameters(
        target_tokens_en=max(1, settings.RAG_CHUNK_TARGET_TOKENS_EN),
        target_tokens_cjk=max(1, settings.RAG_CHUNK_TARGET_TOKENS_CJK),
        target_tokens_default=max(1, settings.RAG_CHUNK_TARGET_TOKENS_DEFAULT),
        overlap_ratio=min(
            1.0,
            max(0.0, float(settings.RAG_CHUNK_OVERLAP_RATIO)),
        ),
        code_max_lines=max(1, settings.RAG_CODE_CHUNK_MAX_LINES),
        code_overlap_lines=max(0, settings.RAG_CODE_CHUNK_OVERLAP_LINES),
    )


def _encoding_for_language(lang: str | None) -> str:
    # cl100k_base handles multilingual text including CJK.
    return DEFAULT_ENCODING


def _text_splitter(lang: str | None, params: ChunkingParameters) -> RecursiveCharacterTextSplitter:
    chunk_tokens = max(1, params.target_tokens(lang))
    overlap_tokens = params.overlap_tokens(chunk_tokens)
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_tokens,
        chunk_overlap=overlap_tokens,
        encoding_name=_encoding_for_language(lang),
    )


def _code_splitter(params: ChunkingParameters) -> TokenTextSplitter:
    return TokenTextSplitter(
        encoding_name=_encoding_for_language("code"),
        chunk_size=params.code_chunk_tokens,
        chunk_overlap=params.code_overlap_tokens,
        keep_separator=False,
    )


def _split_code(text: str, params: ChunkingParameters) -> List[str]:
    stripped = text.strip("\n")
    if not stripped:
        return []

    header = None
    footer = None
    fence = None
    lines = stripped.splitlines()
    if lines:
        first_line = lines[0].strip()
        if first_line.startswith("```") or first_line.startswith("~~~"):
            fence = first_line[:3]
            header = lines[0]
            lines = lines[1:]
            if lines and lines[-1].strip().startswith(fence):
                footer = lines.pop()

    body = "\n".join(lines).strip("\n") if lines else stripped
    splitter = _code_splitter(params)
    try:
        pieces = [frag.strip("\n") for frag in splitter.split_text(body) if frag.strip()]
    except Exception:  # pragma: no cover - defensive
        pieces = [body]

    if not pieces:
        pieces = [body] if body else []

    wrapped: List[str] = []
    for piece in pieces:
        if header:
            closing = footer or fence or "```"
            chunk = f"{header}\n{piece}\n{closing}".strip("\n")
        else:
            chunk = piece
        if chunk:
            wrapped.append(chunk)
    return wrapped


def _split_text(text: str, lang: str | None, params: ChunkingParameters) -> List[str]:
    splitter = _text_splitter(lang, params)
    try:
        pieces = [frag.strip() for frag in splitter.split_text(text) if frag.strip()]
    except Exception:  # pragma: no cover - defensive
        pieces = []

    if pieces:
        return pieces

    stripped = text.strip()
    return [stripped] if stripped else []


def _markdown_sections(text: str, base_metadata: Mapping[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    splitter = _markdown_splitter()
    try:
        documents = splitter.split_text(text)
    except Exception:  # pragma: no cover - fallback to raw text
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
    *,
    config: Mapping[str, Any] | None = None,
) -> List[SplitChunk]:
    params = build_chunking_parameters()
    chunks: List[SplitChunk] = []

    for element in elements:
        text = (element.text or "").strip()
        if not text:
            continue

        base_meta = dict(element.metadata or {})
        meta_lang = normalize_language_value(base_meta.get("language"))
        element_lang = normalize_language_value(element.language)
        if element_lang:
            base_meta["language"] = element_lang
        elif meta_lang:
            base_meta["language"] = meta_lang

        default_language = normalize_language_value(base_meta.get("language")) or "en"
        element_meta = detect_language_meta(text, config=config, default=default_language)
        detected_lang = normalize_language_value(element_meta["language"]) or default_language

        if (
            element.is_code
            or element_meta.get("is_code")
            or detected_lang == "code"
        ):
            base_meta.setdefault("language", "code")
            code_chunks = _split_code(text, params)
            for chunk in code_chunks:
                chunks.append(
                    SplitChunk(
                        content=chunk,
                        language="code",
                        metadata=dict(base_meta),
                        is_code=True,
                    )
                )
            continue

        default_section_lang = "en" if detected_lang == "code" else (detected_lang or "en")

        for section_text, metadata in _markdown_sections(text, base_meta):
            section_meta = dict(metadata)
            section_default = (
                element_lang
                or normalize_language_value(section_meta.get("language"))
                or default_section_lang
            )
            section_info = detect_language_meta(
                section_text, config=config, default=section_default
            )
            section_lang = normalize_language_value(section_info["language"]) or section_default
            section_meta.setdefault("language", section_lang)

            if section_info.get("is_code") or section_lang == "code":
                code_meta = dict(section_meta)
                code_meta["language"] = "code"
                for chunk in _split_code(section_text, params):
                    chunks.append(
                        SplitChunk(
                            content=chunk,
                            language="code",
                            metadata=dict(code_meta),
                            is_code=True,
                        )
                    )
                continue

            for part in _split_text(section_text, section_lang, params):
                chunks.append(
                    SplitChunk(
                        content=part,
                        language=section_lang,
                        metadata=dict(section_meta),
                        is_code=False,
                    )
                )

    return chunks


__all__ = ["SplitChunk", "split_elements", "build_chunking_parameters"]
