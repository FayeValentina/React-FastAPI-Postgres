from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest

from app.core.config import settings
from app.modules.knowledge_base import service


class DummyEncoder:
    def encode(self, texts, normalize_embeddings=True):  # pragma: no cover - simple stub
        if isinstance(texts, (list, tuple)):
            return [np.array([1.0, 0.0], dtype=np.float32) for _ in texts]
        return np.array([1.0, 0.0], dtype=np.float32)


class DummyChunk:
    def __init__(self, chunk_id: int, embedding: np.ndarray, language: str = "en") -> None:
        self.id = chunk_id
        self.document_id = 1
        self.chunk_index = 0
        self.content = f"chunk-{chunk_id}"
        self.language = language
        self.created_at = datetime.utcnow()
        self.embedding = embedding
        self.document = SimpleNamespace(title=f"Doc {chunk_id}")


@pytest.mark.asyncio
async def test_bm25_fusion_combines_vector_and_keyword(monkeypatch) -> None:
    vector_chunk = DummyChunk(1, np.array([1.0, 0.0], dtype=np.float32))
    bm25_chunk = DummyChunk(2, np.array([0.6, 0.8], dtype=np.float32))

    async def fake_fetch(_db, _embedding, _limit):
        return [(vector_chunk, 0.2)]

    async def fake_bm25(_db, _query, _limit, filters=None):
        return [(bm25_chunk, 12.0)]

    async def fake_run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(service, "run_in_threadpool", fake_run_in_threadpool)
    monkeypatch.setattr(service, "_model", DummyEncoder())
    monkeypatch.setattr(service.crud_knowledge_base, "fetch_chunk_candidates_by_embedding", fake_fetch)
    monkeypatch.setattr(service.crud_knowledge_base, "search_by_bm25", fake_bm25)
    monkeypatch.setattr(service, "_detect_language", lambda _text, _config: "en")

    config = settings.dynamic_settings_defaults()
    config.update(
        {
            "BM25_ENABLED": True,
            "BM25_TOP_K": 3,
            "BM25_WEIGHT": 0.5,
            "BM25_MIN_SCORE": 0.0,
            "RAG_RERANK_ENABLED": False,
            "RAG_MIN_SIM": 0.0,
        }
    )

    results = await service.search_similar_chunks(
        db=None,
        query="test",
        top_k=5,
        dynamic_settings_service=None,
        config=config,
    )

    assert len(results) == 2

    vec = next(item for item in results if item.chunk.id == 1)
    keyword = next(item for item in results if item.chunk.id == 2)

    assert pytest.approx(vec.score, rel=1e-5) == 0.4
    assert vec.retrieval_source == "vector"

    assert keyword.retrieval_source == "bm25"
    assert keyword.bm25_score == pytest.approx(12.0)
    assert pytest.approx(keyword.score, rel=1e-5) == 0.8
