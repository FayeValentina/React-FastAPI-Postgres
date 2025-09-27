"""Language detection utilities for knowledge base ingestion."""

from __future__ import annotations

import re
import threading
from typing import Any, Dict, Mapping, TYPE_CHECKING
import logging

from app.core.config import settings

# ---- type-only aliases (keep type names stable for Pylance) ----
if TYPE_CHECKING:
    from lingua import Language as T_Language
    from lingua import LanguageDetector as T_LanguageDetector
    from lingua import LanguageDetectorBuilder as T_LanguageDetectorBuilder
else:
    T_Language = Any 
    T_LanguageDetector = Any
    T_LanguageDetectorBuilder = Any

try:  # pragma: no cover - optional dependency
    from lingua import Language as _Language
    from lingua import LanguageDetector as _LanguageDetector
    from lingua import LanguageDetectorBuilder as _LanguageDetectorBuilder
except Exception:  # pragma: no cover - optional dependency, graceful fallback
    _Language = None  # type: ignore
    _LanguageDetector = None  # type: ignore
    _LanguageDetectorBuilder = None  # type: ignore

_CODE_FENCE_RE = re.compile(r"(?m)^[ \t]*(```|~~~)")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_HIRAGANA_RE = re.compile(r"[\u3040-\u309f]")
_KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]")
_LINGUA_LOCK = threading.Lock()
_LINGUA_DETECTOR: T_LanguageDetector | None = None
logger = logging.getLogger(__name__)
_LINGUA_AVAILABLE = (_Language is not None and _LanguageDetectorBuilder is not None)
logger.debug("ingest_language: lingua installed=%s", _LINGUA_AVAILABLE)


def _should_use_lingua(config: Mapping[str, Any] | None) -> bool:
    """Return whether Lingua should be used based on settings and overrides."""

    flag = settings.RAG_USE_LINGUA
    if config is not None:
        candidate = config.get("RAG_USE_LINGUA", flag)
        if isinstance(candidate, str):
            flag = candidate.strip().lower() in {"1", "true", "yes", "on"}
        else:
            flag = bool(candidate)
    use = bool(flag and (_LanguageDetectorBuilder is not None))
    logger.debug("ingest_language: should_use_lingua=%s (flag=%s, installed=%s)", use, flag, _LINGUA_AVAILABLE)
    return use


def _build_lingua_detector() -> T_LanguageDetector | None:
    if _LanguageDetectorBuilder is None or _Language is None:  # pragma: no cover - optional path
        return None

    languages = [_Language.ENGLISH, _Language.CHINESE, _Language.JAPANESE]
    try:
        logger.debug("ingest_language: building lingua detector...")
        det = (
            _LanguageDetectorBuilder.from_languages(*languages)
            .with_preloaded_language_models()
            .build()
        )
        logger.debug("ingest_language: lingua detector built successfully")
        return det
    except Exception:  # pragma: no cover - instantiation should rarely fail
        logger.warning("ingest_language: failed to build lingua detector; falling back to heuristics", exc_info=logger.isEnabledFor(logging.DEBUG))
        return None


def _get_lingua_detector() -> T_LanguageDetector | None:
    global _LINGUA_DETECTOR
    if _LINGUA_DETECTOR is not None:
        return _LINGUA_DETECTOR

    with _LINGUA_LOCK:
        if _LINGUA_DETECTOR is None:
            _LINGUA_DETECTOR = _build_lingua_detector()
            if _LINGUA_DETECTOR is None:
                logger.debug("ingest_language: lingua detector unavailable")
    return _LINGUA_DETECTOR


def is_probable_code(text: str | None) -> bool:
    """Heuristically determine whether the payload looks like a code block."""

    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False

    if _CODE_FENCE_RE.search(stripped):
        return True

    # Count common programming punctuation to supplement detection.
    punctuation_hits = sum(stripped.count(symbol) for symbol in ("{", "}", "(", ")", ";", "::", "</"))
    alphabetic = sum(1 for ch in stripped if ch.isalpha())
    return punctuation_hits >= 5 and punctuation_hits >= max(3, alphabetic // 3)


def _heuristic_language(text: str) -> str:
    """Fallback language detection relying on character classes."""

    if not text:
        return "en"

    # 优先检测假名；若出现假名，基本可判定为日语
    if _HIRAGANA_RE.search(text) or _KATAKANA_RE.search(text):
        return "ja"
    # 仅有 CJK（多为汉字）时，文本可能是中文或“只有汉字的日文标题”，此时归为 zh
    if _CJK_RE.search(text):
        return "zh"
    return "en"


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


def detect_language(
    text: str,
    config: Mapping[str, Any] | None = None,
    default: str = "en",
) -> str:
    """Detect language, normalising to en/zh/ja/code with graceful fallbacks."""

    result = detect_language_meta(text, config=config, default=default)
    return result["language"]


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
) -> Dict[str, Any]:
    """Return language metadata including ``language`` and ``is_code`` flags."""

    if not text:
        return {"language": default, "is_code": False}

    if is_probable_code(text):
        logger.debug("ingest_language.detect: path=code")
        return {"language": "code", "is_code": True}

    language = None

    if _should_use_lingua(config):
        detector = _get_lingua_detector()
        if detector is not None:
            try:
                detected = detector.detect_language_of(text)
            except Exception:
                logger.warning(
                    "ingest_language.detect: lingua failed; falling back to heuristics",
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
                detected = None

            if _Language and detected == _Language.CHINESE:
                language = "zh"
                logger.debug("ingest_language.detect: path=lingua lang=zh")
            elif _Language and detected == _Language.JAPANESE:
                language = "ja"
                logger.debug("ingest_language.detect: path=lingua lang=ja")
            elif _Language and detected == _Language.ENGLISH:
                language = "en"
                logger.debug("ingest_language.detect: path=lingua lang=en")

    if language is None:
        language = _heuristic_language(text) or default
        logger.debug("ingest_language.detect: path=heuristic lang=%s", language)

    return {"language": language, "is_code": False}


__all__ = [
    "detect_language",
    "detect_language_meta",
    "is_probable_code",
    "is_cjk_text",
    "lingua_status",
]
