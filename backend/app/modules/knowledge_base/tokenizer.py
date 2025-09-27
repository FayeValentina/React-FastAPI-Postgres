from __future__ import annotations

from functools import lru_cache
import logging
from typing import Iterable

from app.core.config import settings
from .ingest_language import detect_language_meta, is_cjk_text

try:  # pragma: no cover - optional dependency at runtime
    import spacy
    from spacy.language import Language
except Exception:  # pragma: no cover - graceful fallback when spaCy unavailable
    spacy = None
    Language = None  # type: ignore


logger = logging.getLogger(__name__)


def _should_use_spacy(text: str, language: str | None) -> bool:
    lang = (language or "").lower()
    if lang.startswith("zh") or lang.startswith("ja"):
        return True
    meta = detect_language_meta(text, default=lang or "en")
    candidate = (meta.get("language") or "").lower()
    if candidate in {"zh", "ja"}:
        return True
    return is_cjk_text(text)


@lru_cache(maxsize=1)
def _load_zh_pipeline() -> Language:
    if spacy is None:
        raise RuntimeError("spaCy is not installed")
    model_name = settings.SPACY_MODEL_NAME
    logger.info("Loading spaCy pipeline %s for Chinese tokenization", model_name)
    return spacy.load(model_name)


def _iter_tokens(doc: "Language" | None, text: str) -> Iterable[str]:
    if not doc:
        return []
    parsed = doc(text)
    return (token.text.strip() for token in parsed if token.text.strip())


def tokenize_for_search(text: str, language: str | None = None) -> str:
    """Return a whitespace separated token string suitable for PostgreSQL simple config."""
    text = (text or "").strip()
    if not text:
        return ""

    if _should_use_spacy(text, language):
        try:
            pipeline = _load_zh_pipeline()
            tokens = [token for token in _iter_tokens(pipeline, text) if token]
            if tokens:
                return " ".join(tokens)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("spaCy tokenization failed, falling back to raw text: %s", exc)

    return " ".join(text.lower().split())
