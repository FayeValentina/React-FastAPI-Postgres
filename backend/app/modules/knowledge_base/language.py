"""Minimal heuristics shared between ingestion and retrieval."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

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

_CODE_FENCE_RE = re.compile(r"(?m)^[ \t]*(```|~~~)")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_HIRAGANA_RE = re.compile(r"[\u3040-\u309f]")
_KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]")


def _from_iterable(values: Iterable[Any]) -> str | None:
    for item in values:
        normalized = normalize_language_value(item)
        if normalized:
            return normalized
    return None


def normalize_language_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            return None
        if candidate in LANGUAGE_ALIAS_MAP:
            return LANGUAGE_ALIAS_MAP[candidate]
        for separator in ("-", "_"):
            if separator in candidate:
                candidate = candidate.split(separator, 1)[0]
                break
        if len(candidate) == 2 and candidate.isalpha():
            return candidate
        return LANGUAGE_ALIAS_MAP.get(candidate)
    if isinstance(value, Mapping):
        return normalize_language_value(value.get("language"))
    if isinstance(value, (list, tuple, set)):
        return _from_iterable(value)
    return None


def is_probable_code(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if _CODE_FENCE_RE.search(stripped):
        return True
    punctuation_hits = sum(stripped.count(symbol) for symbol in ("{", "}", "(", ")", ";", "::", "</"))
    alphabetic = sum(1 for ch in stripped if ch.isalpha())
    return punctuation_hits >= 5 and punctuation_hits >= max(3, alphabetic // 3)


def is_cjk_text(text: str | None) -> bool:
    if not text:
        return False
    sample = text.strip()
    if not sample:
        return False
    if _HIRAGANA_RE.search(sample) or _KATAKANA_RE.search(sample):
        return True
    return bool(_CJK_RE.search(sample))


def detect_language(text: str, default: str = "en") -> str:
    if not text:
        return default
    if is_probable_code(text):
        return "code"
    if _HIRAGANA_RE.search(text) or _KATAKANA_RE.search(text):
        return "ja"
    if _CJK_RE.search(text):
        return "zh"
    return default


def detect_language_meta(text: str | None, default: str = "en") -> dict[str, str | bool]:
    """Return lightweight metadata about the detected language."""
    normalized_default = normalize_language_value(default) or "en"
    sample = (text or "").strip()
    if not sample:
        return {"language": normalized_default, "is_code": False, "is_cjk": False}
    is_code = is_probable_code(sample)
    if is_code:
        return {"language": "code", "is_code": True, "is_cjk": False}
    detected = detect_language(sample, normalized_default)
    return {"language": detected, "is_code": False, "is_cjk": detected in {"zh", "ja"} or is_cjk_text(sample)}


__all__ = [
    "LANGUAGE_ALIAS_MAP",
    "normalize_language_value",
    "is_probable_code",
    "is_cjk_text",
    "detect_language",
    "detect_language_meta",
]
