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
from .ingest_language import detect_language, is_probable_code


HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

DEFAULT_ENCODING = "cl100k_base"
CODE_TOKENS_PER_LINE = 12

_LANGUAGE_ALIAS_MAP = {
    "english": "en",
    "eng": "en",
    "en-us": "en",
    "en_us": "en",
    "en-gb": "en",
    "chinese": "zh",
    "zh-cn": "zh",
    "zh_cn": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
    "zh-tw": "zh",
    "mandarin": "zh",
    "cn": "zh",
    "japanese": "ja",
    "jp": "ja",
}


def _normalise_lang_code(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        code = value.strip().lower()
        if not code:
            return None
        code = _LANGUAGE_ALIAS_MAP.get(code, code)
        for separator in ("-", "_"):
            if separator in code:
                code = code.split(separator, 1)[0]
        if code == "code":
            return "code"
        if len(code) == 2 and code.isalpha():
            return code
        return _LANGUAGE_ALIAS_MAP.get(code)

    if isinstance(value, Mapping):
        return _normalise_lang_code(value.get("language"))

    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalised = _normalise_lang_code(item)
            if normalised:
                return normalised

    return None


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


def _coerce_value(
    config: Mapping[str, Any] | None,
    key: str,
    default: Any,
    caster,
):
    if config is None:
        return caster(default)
    candidate = config.get(key, default)
    try:
        return caster(candidate)
    except (TypeError, ValueError):
        return caster(default)


def build_chunking_parameters(config: Mapping[str, Any] | None = None) -> ChunkingParameters:
    return ChunkingParameters(
        target_tokens_en=_coerce_value(
            config, "RAG_CHUNK_TARGET_TOKENS_EN", settings.RAG_CHUNK_TARGET_TOKENS_EN, int
        ),
        target_tokens_cjk=_coerce_value(
            config, "RAG_CHUNK_TARGET_TOKENS_CJK", settings.RAG_CHUNK_TARGET_TOKENS_CJK, int
        ),
        target_tokens_default=_coerce_value(
            config,
            "RAG_CHUNK_TARGET_TOKENS_DEFAULT",
            settings.RAG_CHUNK_TARGET_TOKENS_DEFAULT,
            int,
        ),
        overlap_ratio=_coerce_value(
            config, "RAG_CHUNK_OVERLAP_RATIO", settings.RAG_CHUNK_OVERLAP_RATIO, float
        ),
        code_max_lines=_coerce_value(
            config, "RAG_CODE_CHUNK_MAX_LINES", settings.RAG_CODE_CHUNK_MAX_LINES, int
        ),
        code_overlap_lines=_coerce_value(
            config,
            "RAG_CODE_CHUNK_OVERLAP_LINES",
            settings.RAG_CODE_CHUNK_OVERLAP_LINES,
            int,
        ),
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
    params = build_chunking_parameters(config)
    chunks: List[SplitChunk] = []

    @lru_cache(maxsize=2048)
    def _detect_cached(text: str, default_lang: str) -> str:
        return detect_language(text, config=config, default=default_lang)

    def _resolve_language(text: str, *, default_lang: str) -> str:
        normalized_default = _normalise_lang_code(default_lang) or "en"
        if not text:
            return normalized_default
        detected = _detect_cached(text, normalized_default)
        normalised = _normalise_lang_code(detected)
        return normalised if normalised else normalized_default

    for element in elements:
        text = (element.text or "").strip()
        if not text:
            continue

        base_meta = dict(element.metadata or {})
        meta_lang = _normalise_lang_code(base_meta.get("language"))
        element_lang = _normalise_lang_code(element.language)
        base_language = element_lang or meta_lang
        if base_language:
            base_meta.setdefault("language", base_language)

        lang = base_language or _resolve_language(
            text, default_lang=base_meta.get("language", "en")
        )

        if element.is_code or lang == "code" or is_probable_code(text):
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

        default_section_lang = "en" if lang == "code" else (lang or "en")

        for section_text, metadata in _markdown_sections(text, base_meta):
            section_meta = dict(metadata)
            section_default = (
                element_lang
                or _normalise_lang_code(section_meta.get("language"))
                or default_section_lang
            )
            section_lang = element_lang or _resolve_language(
                section_text, default_lang=section_default
            )
            section_meta.setdefault("language", section_lang)
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
