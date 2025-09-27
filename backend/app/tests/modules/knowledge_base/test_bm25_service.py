from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from app.core.config import settings
from app.modules.knowledge_base import service, bm25


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
    
    mock_db_session = AsyncMock()
    
    # 1. 直接模拟底层接触数据库的函数。
    async def fake_fetch_vector_candidates(_db, _embedding, _limit):
        # 这个函数应返回 `fetch_chunk_candidates_by_embedding` 所期望的格式
        return [(vector_chunk, 0.2)]  # (区块, 距离)

    async def fake_search_by_bm25(_db, _query, _top_k, **_kwargs):
        # 这个函数应返回 `crud_knowledge_base.search_by_bm25` 所期望的格式
        return [(bm25_chunk, 12.0)]  # (区块, 原始分数)

    async def fake_run_in_threadpool(func, *args, **kwargs):
        # 修正以正确处理 AsyncMock
        if isinstance(func, AsyncMock):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    # 2. 应用更精确的补丁，直接替换 repository 层的函数。
    monkeypatch.setattr(service.crud_knowledge_base, "fetch_chunk_candidates_by_embedding", fake_fetch_vector_candidates)
    monkeypatch.setattr(service.crud_knowledge_base, "search_by_bm25", fake_search_by_bm25)

    # 这些补丁保持不变。
    monkeypatch.setattr(service, "run_in_threadpool", fake_run_in_threadpool)
    monkeypatch.setattr(service, "_model", DummyEncoder())
    monkeypatch.setattr(service, "_detect_language", lambda _text, _config: "en")

    config = settings.dynamic_settings_defaults()
    config.update(
        {
            "BM25_ENABLED": True,
            "BM25_TOP_K": 3,
            "BM25_WEIGHT": 0.5,
            "RAG_RERANK_ENABLED": False,
            "RAG_MIN_SIM": 0.0,
        }
    )
    
    results = await service.search_similar_chunks(
        db=mock_db_session,
        query="test",
        top_k=5,
        dynamic_settings_service=None,
        config=config,
    )

    assert len(results) == 2

    vec = next(item for item in results if item.chunk.id == 1)
    keyword = next(item for item in results if item.chunk.id == 2)

    # *** 这是核心的修改 ***
    # 1. 从配置中获取语言奖励值
    lang_bonus = config.get("RAG_SAME_LANG_BONUS", settings.RAG_SAME_LANG_BONUS)

    # 2. 在断言中包含这个奖励值
    # 向量区块分数 = (1-0.5)*0.8 + bonus = 0.4 + bonus
    assert vec.score == pytest.approx(0.4 + lang_bonus)
    assert vec.retrieval_source == "vector"

    # 关键词区块分数 = (1-0.5)*0.6 + 0.5*0.8 + bonus = 0.3 + 0.4 + bonus = 0.7 + bonus
    assert keyword.score == pytest.approx(0.8 + lang_bonus)
    assert keyword.retrieval_source == "bm25"
    assert keyword.bm25_score == pytest.approx(12.0)

