from __future__ import annotations

import logging
import threading
from typing import Optional

from sentence_transformers import CrossEncoder, SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)

_EMBEDDER_LOCK = threading.Lock()
_EMBEDDER: Optional[SentenceTransformer] = None

_RERANKER_LOCK = threading.Lock()
_RERANKER: Optional[CrossEncoder] = None


def get_embedder() -> SentenceTransformer:
    """Return a singleton SentenceTransformer instance, initialised lazily."""
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER

    with _EMBEDDER_LOCK:
        if _EMBEDDER is None:
            model_name = settings.EMBEDDING_MODEL
            if not model_name:
                raise RuntimeError("EMBEDDING_MODEL is not configured")
            logger.info("Loading embedding model %s", model_name)
            _EMBEDDER = SentenceTransformer(model_name)
    return _EMBEDDER


def get_reranker() -> CrossEncoder:
    """Return a singleton CrossEncoder instance, initialised lazily."""
    global _RERANKER
    if _RERANKER is not None:
        return _RERANKER

    with _RERANKER_LOCK:
        if _RERANKER is None:
            model_name = settings.RERANKER_MODEL
            if not model_name:
                raise RuntimeError("RERANKER_MODEL is not configured")
            logger.info("Loading reranker model %s", model_name)
            _RERANKER = CrossEncoder(model_name)
    return _RERANKER


def reset_models_for_tests() -> None:
    """Testing utility to clear cached model instances."""
    global _EMBEDDER, _RERANKER
    with _EMBEDDER_LOCK:
        _EMBEDDER = None
    with _RERANKER_LOCK:
        _RERANKER = None


__all__ = ["get_embedder", "get_reranker", "reset_models_for_tests"]
