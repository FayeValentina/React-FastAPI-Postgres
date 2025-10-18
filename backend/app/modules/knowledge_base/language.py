"""Language normalisation and detection helpers shared across ingestion and retrieval."""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Iterable, Mapping, TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:  # pragma: no cover
    from lingua import Language as T_Language
    from lingua import LanguageDetector as T_LanguageDetector
    from lingua import LanguageDetectorBuilder as T_LanguageDetectorBuilder
else:  # pragma: no cover - runtime fallbacks
    T_Language = Any
    T_LanguageDetector = Any
    T_LanguageDetectorBuilder = Any

try:  # pragma: no cover - optional dependency
    from lingua import Language as _Language
    from lingua import LanguageDetector as _LanguageDetector
    from lingua import LanguageDetectorBuilder as _LanguageDetectorBuilder
except Exception:  # pragma: no cover - fallback when lingua unavailable
    _Language = None  # type: ignore
    _LanguageDetector = None  # type: ignore
    _LanguageDetectorBuilder = None  # type: ignore


logger = logging.getLogger(__name__)

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

_CODE_FENCE_RE = re.compile(r"(?m)^[ \t]*(```|~~~)")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_HIRAGANA_RE = re.compile(r"[\u3040-\u309f]")
_KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]")
_LINGUA_LOCK = threading.Lock()
_LINGUA_DETECTOR: T_LanguageDetector | None = None
_LINGUA_AVAILABLE = (_Language is not None and _LanguageDetectorBuilder is not None)


def _from_iterable(values: Iterable[Any], *, allow_code: bool) -> str | None:
    for item in values:
        normalised = normalize_language_value(item, allow_code=allow_code)
        if normalised:
            return normalised
    return None


def normalize_language_value(value: Any, *, allow_code: bool = True) -> str | None:
    """Normalise heterogenous language hints to short ISO-like codes."""
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


def is_probable_code(text: str | None) -> bool:
    """Heuristically determine whether the payload looks like a code block."""
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
    """Return True when the payload contains CJK (Chinese/Japanese) characters."""
    if not text:
        return False
    sample = text.strip()
    if not sample:
        return False
    if _HIRAGANA_RE.search(sample) or _KATAKANA_RE.search(sample):
        return True
    return bool(_CJK_RE.search(sample))


def _should_use_lingua(config: Mapping[str, Any] | None) -> bool:
    """Return whether Lingua should be used based on settings and overrides."""
    flag = settings.RAG_USE_LINGUA
    if config is not None:
        candidate = config.get("RAG_USE_LINGUA", flag)
        if isinstance(candidate, str):
            flag = candidate.strip().lower() in {"1", "true", "yes", "on"}
        else:
            flag = bool(candidate)
    return bool(flag and (_LanguageDetectorBuilder is not None))


def _build_lingua_detector() -> T_LanguageDetector | None:
    if _LanguageDetectorBuilder is None or _Language is None:  # pragma: no cover
        return None

    languages = [_Language.ENGLISH, _Language.CHINESE, _Language.JAPANESE]
    try:
        logger.debug("language: building lingua detector...")
        det = (
            _LanguageDetectorBuilder.from_languages(*languages)
            .with_preloaded_language_models()
            .build()
        )
        logger.debug("language: lingua detector built successfully")
        return det
    except Exception:  # pragma: no cover - should rarely fail
        logger.warning("language: failed to build lingua detector; falling back to heuristics", exc_info=logger.isEnabledFor(logging.DEBUG))
        return None


def _get_lingua_detector() -> T_LanguageDetector | None:
    global _LINGUA_DETECTOR
    if _LINGUA_DETECTOR is not None:
        return _LINGUA_DETECTOR

    with _LINGUA_LOCK:
        if _LINGUA_DETECTOR is None:
            _LINGUA_DETECTOR = _build_lingua_detector()
    return _LINGUA_DETECTOR


def lingua_status(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Expose runtime status for debugging/logging."""
    return {
        "installed": _LINGUA_AVAILABLE,
        "enabled_by_config": _should_use_lingua(config),
        "detector_cached": _LINGUA_DETECTOR is not None,
    }


def detect_language_meta(
    text: str,
    *,
    config: Mapping[str, Any] | None = None,
    default: str = "en",
) -> dict[str, Any]:
    """Return language metadata including ``language`` and ``is_code`` flags."""
    if not text:
        return {"language": default, "is_code": False}

    if is_probable_code(text):
        logger.debug("language.detect: code block detected")
        return {"language": "code", "is_code": True}

    language = None

    if _should_use_lingua(config):
        detector = _get_lingua_detector()
        if detector is not None:
            try:
                detected = detector.detect_language_of(text)
            except Exception:
                logger.warning(
                    "language.detect: lingua failed; falling back to heuristics",
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
                detected = None

            if _Language and detected == _Language.CHINESE:
                language = "zh"
            elif _Language and detected == _Language.JAPANESE:
                language = "ja"
            elif _Language and detected == _Language.ENGLISH:
                language = "en"

    if language is None:
        language = _heuristic_language(text) or default

    return {"language": language, "is_code": False}


def detect_language(
    text: str,
    config: Mapping[str, Any] | None = None,
    default: str = "en",
) -> str:
    """Detect language, normalising to en/zh/ja/code with graceful fallbacks."""
    result = detect_language_meta(text, config=config, default=default)
    return result["language"]


def _heuristic_language(text: str) -> str:
    if not text:
        return "en"

    if _HIRAGANA_RE.search(text) or _KATAKANA_RE.search(text):
        return "ja"
    if _CJK_RE.search(text):
        return "zh"
    return "en"


__all__ = [
    "LANGUAGE_ALIAS_MAP",
    "normalize_language_value",
    "is_probable_code",
    "is_cjk_text",
    "detect_language_meta",
    "detect_language",
    "lingua_status",
]
