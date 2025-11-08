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

from app.core.config import settings

from .ingest_extractor import ExtractedElement

# 定义 Markdown 中用于分割的标题级别
HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

# 默认的编码方式
DEFAULT_ENCODING = "cl100k_base"
# 每行代码近似的 token 数
CODE_TOKENS_PER_LINE = 12

@dataclass(slots=True)
class SplitChunk:
    """表示一个分割后的文本块。"""
    content: str  # 块内容
    language: str | None = None  # 语言
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据
    is_code: bool = False  # 是否为代码


@dataclass(slots=True)
class ChunkingParameters:
    """定义分块过程的参数。"""
    target_tokens_en: int  # 英文文本的目标 token 数
    target_tokens_cjk: int  # 中日韩文本的目标 token 数
    target_tokens_default: int  # 默认的目标 token 数
    overlap_ratio: float  # 块之间的重叠比例
    code_max_lines: int  # 代码块的最大行数
    code_overlap_lines: int  # 代码块的重叠行数

    def target_tokens(self, lang: str | None) -> int:
        """根据语言确定目标 token 数。"""
        code = (lang or "en").lower()
        if code == "en":
            return self.target_tokens_en
        if code in {"zh", "ja"}:
            return self.target_tokens_cjk
        return self.target_tokens_default

    def overlap_tokens(self, chunk_tokens: int) -> int:
        """计算重叠的 token 数。"""
        if chunk_tokens <= 0:
            return 0
        overlap = int(chunk_tokens * max(0.0, min(1.0, self.overlap_ratio)))
        return max(0, overlap)

    @property
    def code_chunk_tokens(self) -> int:
        """计算代码块的目标 token 数。"""
        return max(16, self.code_max_lines * CODE_TOKENS_PER_LINE)

    @property
    def code_overlap_tokens(self) -> int:
        """计算代码块的重叠 token 数。"""
        return max(0, self.code_overlap_lines * CODE_TOKENS_PER_LINE)


@lru_cache(maxsize=1)
def _markdown_splitter() -> MarkdownHeaderTextSplitter:
    """获取一个单例的 MarkdownHeaderTextSplitter。"""
    return MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False)


def build_chunking_parameters() -> ChunkingParameters:
    """使用应用程序设置构造摄入分块参数。"""
    return ChunkingParameters(
        target_tokens_en=settings.RAG_CHUNK_TARGET_TOKENS_EN,
        target_tokens_cjk=settings.RAG_CHUNK_TARGET_TOKENS_CJK,
        target_tokens_default=settings.RAG_CHUNK_TARGET_TOKENS_DEFAULT,
        overlap_ratio=settings.RAG_CHUNK_OVERLAP_RATIO,
        code_max_lines=settings.RAG_CODE_CHUNK_MAX_LINES,
        code_overlap_lines=settings.RAG_CODE_CHUNK_OVERLAP_LINES,
    )


def _encoding_for_language(lang: str | None) -> str:
    """为给定语言返回编码方式。"""
    # cl100k_base 支持包括 CJK 在内的多语言文本。
    return DEFAULT_ENCODING


def _text_splitter(lang: str | None, params: ChunkingParameters) -> RecursiveCharacterTextSplitter:
    """为普通文本创建分割器。"""
    chunk_tokens = max(1, params.target_tokens(lang))
    overlap_tokens = params.overlap_tokens(chunk_tokens)
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_tokens,
        chunk_overlap=overlap_tokens,
        encoding_name=_encoding_for_language(lang),
    )


def _code_splitter(params: ChunkingParameters) -> TokenTextSplitter:
    """为代码创建分割器。"""
    return TokenTextSplitter(
        encoding_name=_encoding_for_language("code"),
        chunk_size=params.code_chunk_tokens,
        chunk_overlap=params.code_overlap_tokens,
        keep_separator=False,
    )


def _split_code(text: str, params: ChunkingParameters) -> List[str]:
    """分割代码文本，保留代码块的包围结构。"""
    stripped = text.strip("\n")
    if not stripped:
        return []

    header = None
    footer = None
    fence = None
    lines = stripped.splitlines()
    # 识别并分离代码块的起始和结束标记
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

    # 将分割后的代码片段重新用代码块标记包裹起来
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
    """分割普通文本。"""
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
    """将 Markdown 文本按标题分割成多个部分。"""
    splitter = _markdown_splitter()
    try:
        documents = splitter.split_text(text)
    except Exception:  # pragma: no cover - 回退到原始文本
        yield text, dict(base_metadata)
        return

    if not documents:
        yield text, dict(base_metadata)
        return

    for doc in documents:
        metadata = dict(base_metadata)
        extra = getattr(doc, "metadata", {}) or {}
        # 合并从标题中提取的元数据
        for key, value in extra.items():
            if value:
                metadata[str(key)] = value
        yield doc.page_content, metadata


def split_elements(
    elements: Iterable[ExtractedElement],
) -> List[SplitChunk]:
    """分割从文档中提取的元素列表。"""
    params = build_chunking_parameters()
    chunks: List[SplitChunk] = []

    for element in elements:
        text = (element.text or "").strip()
        if not text:
            continue

        base_meta = dict(element.metadata or {})
        # 仅根据 extractor 的结构分类来切分代码，不做语言检测
        if element.is_code:
            code_chunks = _split_code(text, params)
            for chunk in code_chunks:
                chunks.append(
                    SplitChunk(
                        content=chunk,
                        language=None,
                        metadata=dict(base_meta),
                        is_code=True,
                    )
                )
            continue

        # 普通文本：可按 Markdown 小节拆分，再按默认 token 规则拆块
        for section_text, metadata in _markdown_sections(text, base_meta):
            section_meta = dict(metadata)
            for part in _split_text(section_text, None, params):  # 不传语言 -> 走默认 chunk 大小
                chunks.append(
                    SplitChunk(
                        content=part,
                        language=None, # 语言在 ingestion 阶段判定
                        metadata=dict(section_meta), # 原始元数据透传
                        is_code=False,
                    )
                )

    return chunks


__all__ = ["SplitChunk", "split_elements", "build_chunking_parameters"]