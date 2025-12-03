"""Minimal heuristics shared between ingestion and retrieval.
摄取和检索之间共享的最小启发式方法。
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

# 语言别名映射，用于标准化语言代码
LANGUAGE_ALIAS_MAP: dict[str, str] = {
    "english": "en",
    "eng": "en",
    "en-us": "en",
    "en_gb": "en",
    "en": "en",
    "mandarin": "zh",
    "chinese": "zh",
    "zh-cn": "zh",
    "zh": "zh",
    "jp": "ja",
    "japanese": "ja",
    "ja": "ja",
}

# 预编译的正则表达式
_CODE_FENCE_RE = re.compile(r"(?m)^[ \t]*(```|~~~)")  # 代码块标记
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")  # 中日韩统一表意文字
_HIRAGANA_RE = re.compile(r"[\u3040-\u309f]")  # 平假名
_KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]")  # 片假名


def _from_iterable(values: Iterable[Any]) -> str | None:
    """Helper to try extracting language from an iterable.
    尝试从可迭代对象中提取语言的辅助函数。
    """
    for item in values:
        normalized = normalize_language_value(item)
        if normalized:
            return normalized
    return None


def normalize_language_value(value: Any) -> str | None:
    """Normalize various inputs (str, list, dict) into a 2-letter ISO code.
    将各种输入（字符串、列表、字典）标准化为 2 字母 ISO 代码。
    """
    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            return None
        # 检查别名映射
        if candidate in LANGUAGE_ALIAS_MAP:
            return LANGUAGE_ALIAS_MAP[candidate]
        # 尝试去除区域后缀 (例如 "en-US" -> "en")
        for separator in ("-", "_"):
            if separator in candidate:
                candidate = candidate.split(separator, 1)[0]
                break
        # 如果是两个字母的字符串，假设它是有效的 ISO 代码
        if len(candidate) == 2 and candidate.isalpha():
            return candidate
        return LANGUAGE_ALIAS_MAP.get(candidate)
    if isinstance(value, Mapping):
        # 如果是字典，尝试获取 "language" 键
        return normalize_language_value(value.get("language"))
    if isinstance(value, (list, tuple, set)):
        # 如果是列表/元组/集合，尝试从元素中提取
        return _from_iterable(value)
    return None


def is_probable_code(text: str | None) -> bool:
    """Heuristic check if text looks like code.
    启发式检查文本是否看起来像代码。
    """
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    # 检查是否有代码块标记
    if _CODE_FENCE_RE.search(stripped):
        return True
    # 统计标点符号密度
    punctuation_hits = sum(stripped.count(symbol) for symbol in ("{", "}", "(", ")", ";", "::", "</"))
    alphabetic = sum(1 for ch in stripped if ch.isalpha())
    # 如果标点符号足够多，且相对于字母的比例较高，则认为是代码
    return punctuation_hits >= 5 and punctuation_hits >= max(3, alphabetic // 3)


def is_cjk_text(text: str | None) -> bool:
    """Check if text contains CJK characters.
    检查文本是否包含 CJK (中日韩) 字符。
    """
    if not text:
        return False
    sample = text.strip()
    if not sample:
        return False
    # 检查平假名或片假名 (日语)
    if _HIRAGANA_RE.search(sample) or _KATAKANA_RE.search(sample):
        return True
    # 检查中日韩统一表意文字
    return bool(_CJK_RE.search(sample))


def detect_language(text: str, default: str = "en") -> str:
    """Simple language detection based on heuristics.
    基于启发式方法的简单语言检测。
    """
    if not text:
        return default
    if is_probable_code(text):
        return "code"
    # 优先检测日语
    if _HIRAGANA_RE.search(text) or _KATAKANA_RE.search(text):
        return "ja"
    # 检测中文
    if _CJK_RE.search(text):
        return "zh"
    return default


def detect_language_meta(text: str | None, default: str = "en") -> dict[str, str | bool]:
    """Return lightweight metadata about the detected language.
    返回关于检测到的语言的轻量级元数据。
    """
    normalized_default = normalize_language_value(default) or "en"
    sample = (text or "").strip()
    if not sample:
        return {"language": normalized_default, "is_code": False, "is_cjk": False}

    detected = detect_language(sample, normalized_default)
    if detected == "code":
        return {"language": "code", "is_code": True, "is_cjk": False}

    return {
        "language": detected,
        "is_code": False,
        "is_cjk": detected in {"zh", "ja"} or is_cjk_text(sample),
    }


__all__ = [
    "LANGUAGE_ALIAS_MAP",
    "normalize_language_value",
    "is_probable_code",
    "is_cjk_text",
    "detect_language",
    "detect_language_meta",
]
