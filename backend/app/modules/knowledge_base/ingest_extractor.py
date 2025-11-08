"""由 unstructured 驱动的文档提取实用程序。"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, List, Mapping

from charset_normalizer import from_bytes
from unstructured.documents.elements import Element  # type: ignore
from unstructured.partition.auto import partition  # type: ignore

@dataclass(slots=True)
class ExtractedElement:
    """unstructured 返回的文档元素的规范化表示。"""

    text: str  # 提取的文本内容
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据字典
    category: str | None = None  # 元素类别
    is_code: bool = False  # 是否为代码
    language: str | None = None  # 代码语言

def _element_to_payload(element: Element) -> ExtractedElement | None:
    """将 unstructured 的 Element 对象转换为 ExtractedElement。"""
    # 获取并清理文本
    text = (getattr(element, "text", None) or "").strip()
    if not text:
        return None

    # 提取元数据
    metadata = {}
    meta_obj = getattr(element, "metadata", None)
    if meta_obj is not None:
        try:
            # 将元数据对象转换为字典，并过滤掉值为 None 的项
            metadata = {k: v for k, v in meta_obj.to_dict().items() if v is not None}
        except Exception:  # pragma: no cover - unstructured 的边缘情况
            metadata = {}

    # 获取类别并判断是否为代码
    category = getattr(element, "category", None)
    is_code = bool(category and category.lower() == "code")

    return ExtractedElement(
        text=text,
        metadata=metadata,
        category=category,
        is_code=is_code,
        language=None,  # 语言字段当前未处理
    )


def _process_partition_elements(
    elements: list[Element] | None,
    *,
    source_ref: str | None = None,
) -> list[ExtractedElement]:
    """处理分区后的元素列表。"""
    payloads: List[ExtractedElement] = []
    for item in elements or []:
        payload = _element_to_payload(item)
        if payload is None:
            continue
        # 如果元数据中没有 source，则添加 source_ref
        if source_ref and "source" not in payload.metadata:
            payload.metadata["source"] = source_ref
        payloads.append(payload)
    return payloads


def _decode_bytes_to_text(raw: bytes) -> str:
    """将字节解码为文本。"""
    if not raw:
        return ""

    try:
        # 尝试使用 charset_normalizer 自动检测并解码
        best = from_bytes(raw).best()
        if best is not None:
            return str(best)
    except Exception:  # pragma: no cover - 字符集检测失败
        pass

    # 如果失败，则使用 utf-8 解码并忽略错误
    return raw.decode("utf-8", errors="ignore")


def extract_from_text(
    content: str,
    *,
    source_ref: str | None = None,
) -> list[ExtractedElement]:
    """从原始文本输入中提取结构化元素。"""

    text = (content or "").strip()
    if not text:
        return []

    try:
        # 使用 unstructured 的 partition 函数进行分区
        elements = partition(
            text=text,
            metadata_filename=source_ref,
            include_metadata=True,
        )
    except Exception:  # pragma: no cover - 回退到纯文本块
        # 如果分区失败，则将整个文本作为一个元素返回
        return [ExtractedElement(text=text, metadata={"source": source_ref} if source_ref else {})]

    payloads = _process_partition_elements(elements, source_ref=source_ref)
    if payloads:
        return payloads

    # 如果处理后没有有效载荷，则将整个文本作为一个元素返回
    return [ExtractedElement(text=text, metadata={"source": source_ref} if source_ref else {})]


def extract_from_bytes(
    raw: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[str, list[ExtractedElement]]:
    """从二进制负载中提取结构化元素，并返回纯文本作为回退。"""

    # 首先解码为文本作为回退
    fallback = _decode_bytes_to_text(raw)
    if not raw:
        return fallback, []

    buffer = io.BytesIO(raw)

    try:
        # 使用 unstructured 的 partition 函数处理文件
        elements = partition(
            file=buffer,
            content_type=content_type,
            metadata_filename=filename,
            include_metadata=True,
        )
    except Exception:  # pragma: no cover - 回退到解码后的文本
        # 如果分区失败，则使用解码后的文本作为单个元素
        metadata = {"source": filename} if filename else {}
        return fallback, [ExtractedElement(text=fallback, metadata=metadata)]

    payloads = _process_partition_elements(elements, source_ref=filename)
    if payloads:
        return fallback, payloads

    # 如果处理后没有有效载荷，则使用解码后的文本作为单个元素
    metadata = {"source": filename} if filename else {}
    return fallback, [ExtractedElement(text=fallback, metadata=metadata)]


__all__ = ["ExtractedElement", "extract_from_text", "extract_from_bytes"]