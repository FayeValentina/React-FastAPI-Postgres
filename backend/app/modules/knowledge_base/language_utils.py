"""Shared helpers for normalising language hints across ingestion components."""

from __future__ import annotations

from typing import Any, Mapping, Iterable

LANGUAGE_ALIAS_MAP: dict[str, str] = {
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

_ALLOWED_CODE_LABELS = {"code"}


def _from_iterable(values: Iterable[Any], *, allow_code: bool) -> str | None:
    for item in values:
        normalised = normalize_language_value(item, allow_code=allow_code)
        if normalised:
            return normalised
    return None


def normalize_language_value(value: Any, *, allow_code: bool = True) -> str | None:
    """Normalise heterogenous language hints to short ISO-like codes.

    Supports strings (case-insensitive), mappings that expose a ``language`` key,
    and iterables of such hints. When ``allow_code`` is ``True`` (default), the
    literal ``"code"`` is preserved to signal code blocks.
    """

    if value is None:
        return None

    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            return None

        candidate = LANGUAGE_ALIAS_MAP.get(candidate, candidate)
        for separator in ("-", "_"):
            if separator in candidate:
                candidate = candidate.split(separator, 1)[0]

        if allow_code and candidate in _ALLOWED_CODE_LABELS:
            return "code"

        if len(candidate) == 2 and candidate.isalpha():
            return candidate

        return LANGUAGE_ALIAS_MAP.get(candidate)

    if isinstance(value, Mapping):
        return normalize_language_value(value.get("language"), allow_code=allow_code)

    if isinstance(value, (list, tuple, set)):
        return _from_iterable(value, allow_code=allow_code)

    return None


__all__ = ["LANGUAGE_ALIAS_MAP", "normalize_language_value"]
