"""Lightweight text extraction utilities for ingestion.
用于摄取的轻量级文本提取工具。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from charset_normalizer import from_bytes


@dataclass(slots=True)
class ExtractedElement:
    """Minimal representation of an extracted text block.
    提取的文本块的最小表示。
    """

    text: str  # 提取的文本内容
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据字典
    category: str | None = None  # 类别 (可选)
    is_code: bool = False  # 是否为代码
    language: str | None = None  # 语言 (如果是代码)


def _decode_bytes_to_text(raw: bytes) -> str:
    """Decode bytes into text, leaning on charset_normalizer when available.
    将字节解码为文本，如果可用则依赖 charset_normalizer 进行编码检测。
    """
    if not raw:
        return ""

    try:
        # 尝试检测最佳编码并解码
        best = from_bytes(raw).best()
        if best is not None:
            return str(best)
    except Exception:  # pragma: no cover - charset detection can fail
        # 字符集检测失败时忽略异常
        pass

    # 如果检测失败，回退到 utf-8 解码，忽略错误
    return raw.decode("utf-8", errors="ignore")


def extract_from_text(content: str, *, source_ref: str | None = None) -> list[ExtractedElement]:
    """Normalize plain text input into a single ExtractedElement list.
    将纯文本输入标准化为单个 ExtractedElement 列表。
    """
    text = (content or "").strip()
    if not text:
        return []

    # 如果提供了源引用，则添加到元数据中
    metadata = {"source": source_ref} if source_ref else {}
    return [ExtractedElement(text=text, metadata=metadata)]


def extract_from_bytes(
    raw: bytes,
    *,
    filename: str | None = None,
) -> tuple[str, list[ExtractedElement]]:
    """Decode text files into ExtractedElements; only text payloads are supported.
    将文本文件解码为 ExtractedElement；仅支持文本负载。
    """
    decoded = _decode_bytes_to_text(raw)
    if not decoded:
        return "", []

    # 从解码后的文本中提取元素
    elements = extract_from_text(decoded, source_ref=filename)
    return decoded, elements


__all__ = ["ExtractedElement", "extract_from_text", "extract_from_bytes"]
