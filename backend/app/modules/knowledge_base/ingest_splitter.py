"基于 LangChain 文本分割器构建的分块实用程序。"

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, List, Mapping

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from .ingest_extractor import ExtractedElement

# 定义用于 Markdown 分割的标题级别
HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

# 默认编码和分块参数
DEFAULT_ENCODING = "cl100k_base"
MAX_CHUNK_TOKENS = 2000  # 最大分块 token 数
CHUNK_OVERLAP = 200  # 分块重叠 token 数


@dataclass(slots=True)
class SplitChunk:
    """Represents a single chunk of text after splitting.
    表示分割后的单个文本块。
    """
    content: str  # 文本内容
    language: str | None = None  # 语言 (可选)
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据


@lru_cache(maxsize=1)
def _markdown_splitter() -> MarkdownHeaderTextSplitter:
    """Cached Markdown splitter instance.
    缓存的 Markdown 分割器实例。
    """
    return MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False)


def _text_splitter() -> RecursiveCharacterTextSplitter:
    """Create a recursive character text splitter with tiktoken encoder.
    创建一个使用 tiktoken 编码器的递归字符文本分割器。
    """
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=MAX_CHUNK_TOKENS,
        chunk_overlap=CHUNK_OVERLAP,
        encoding_name=DEFAULT_ENCODING,
    )


def _split_text(text: str) -> List[str]:
    """Split plain text into chunks using the recursive splitter.
    使用递归分割器将纯文本分割成块。
    """
    splitter = _text_splitter()
    try:
        # 分割文本并去除空白字符
        pieces = [frag.strip() for frag in splitter.split_text(text) if frag.strip()]
    except Exception:
        # 如果分割失败，返回空列表
        pieces = []
    if pieces:
        return pieces
    # 如果没有生成分块，返回去除空白后的原始文本（如果不为空）
    stripped = text.strip()
    return [stripped] if stripped else []


def _markdown_sections(text: str, base_metadata: Mapping[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """Split text by Markdown headers first, yielding sections with updated metadata.
    首先按 Markdown 标题分割文本，生成带有更新元数据的部分。
    """
    splitter = _markdown_splitter()
    try:
        documents = splitter.split_text(text)
    except Exception:
        # 如果 Markdown 分割失败，按原样返回
        yield text, dict(base_metadata)
        return

    if not documents:
        # 如果没有生成文档，按原样返回
        yield text, dict(base_metadata)
        return

    for doc in documents:
        metadata = dict(base_metadata)
        # 获取文档特定的元数据（例如标题信息）
        extra = getattr(doc, "metadata", {}) or {}
        for key, value in extra.items():
            if value:
                metadata[str(key)] = value
        yield doc.page_content, metadata


def split_elements(
    elements: Iterable[ExtractedElement],
) -> List[SplitChunk]:
    """Split extracted elements into smaller chunks.
    将提取的元素分割成更小的块。
    """
    chunks: List[SplitChunk] = []

    for element in elements:
        text = (element.text or "").strip()
        if not text:
            continue

        base_meta = dict(element.metadata or {})
        # 首先尝试按 Markdown 章节分割
        for section_text, metadata in _markdown_sections(text, base_meta):
            section_meta = dict(metadata)
            # 然后对每个章节进行递归字符分割
            for part in _split_text(section_text):
                chunks.append(
                    SplitChunk(
                        content=part,
                        language=None,
                        metadata=dict(section_meta),
                    )
                )

    return chunks


__all__ = ["SplitChunk", "split_elements"]
