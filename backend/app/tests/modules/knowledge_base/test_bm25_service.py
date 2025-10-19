import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from app.core.config import settings
from app.modules.knowledge_base import retrieval, repository, embeddings, language, bm25
from app.modules.knowledge_base.retrieval import LANGUAGE_MATCH_BONUS, search_similar_chunks


class _TestBM25DummyEncoder:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - simple stub
        pass

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

    # 修正：模拟 fetch_bm25_matches 的返回对象，而不仅仅是 search_by_bm25
    async def fake_fetch_bm25_matches(_db, _query, _top_k, **_kwargs):
        match = bm25.BM25Match(
            chunk=bm25_chunk,
            raw_score=12.0,
            normalized_score=0.8,  # 假设归一化后的分数
        )
        return bm25.BM25SearchResult(
            matches=[match], raw_hits=1, after_threshold=1, max_score=15.0, min_score=12.0
        )

    async def fake_run_in_threadpool(func, *args, **kwargs):
        # 简化并使其更健壮：总是返回一个可等待对象
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        future.set_result(func(*args, **kwargs))
        return await future

    # 2. 应用更精确的补丁，直接替换 repository 层的函数。
    monkeypatch.setattr(repository.crud_knowledge_base, "fetch_chunk_candidates_by_embedding", fake_fetch_vector_candidates)
    monkeypatch.setattr(retrieval, "fetch_bm25_matches", fake_fetch_bm25_matches)

    # 这些补丁保持不变。
    # 关键修复：直接修补 embeddings 模块中的 SentenceTransformer 类，
    # 以避免来自其他测试文件（如 test_admin_settings.py）的全局 sys.modules 补丁造成的污染。
    # 这确保了 get_embedder() 在此测试中总是使用我们本地的、正确的虚拟编码器。
    monkeypatch.setattr(embeddings, "SentenceTransformer", _TestBM25DummyEncoder)
    monkeypatch.setattr(retrieval, "run_in_threadpool", fake_run_in_threadpool)
    monkeypatch.setattr(language, "detect_language", lambda _text, _config: "en")

    config = settings.dynamic_settings_defaults()
    config.update(
        {
            "BM25_TOP_K": 3,
            "BM25_WEIGHT": 0.5,
            "RAG_RERANK_ENABLED": False,
            "RAG_MIN_SIM": 0.0,
        }
    )
    
    results = await search_similar_chunks(
        db=mock_db_session,
        query="test",
        top_k=5,
        dynamic_settings_service=None,
        config=config,
    )

    assert len(results) == 2

    vec = next(item for item in results if item.chunk.id == 1)
    keyword = next(item for item in results if item.chunk.id == 2)

    # 固定语言奖励常量维护了向量与 BM25 融合时的同语言加成
    lang_bonus = LANGUAGE_MATCH_BONUS

    # 在断言中包含这个奖励值
    # 向量区块分数 = (1-0.5) * similarity + 0.5 * bm25_norm + bonus
    # similarity = 1 - distance = 1 - 0.2 = 0.8
    # bm25_norm for vector chunk is 0.0 as it's not in bm25 results
    # score = (1-0.5)*0.8 + 0.5*0.0 + bonus = 0.4 + bonus
    assert vec.score == pytest.approx(0.4 + lang_bonus, abs=1e-4)
    assert vec.retrieval_source == "vector"

    # 关键词区块分数 = (1-0.5)*similarity + 0.5*bm25_norm + bonus
    # similarity = np.dot([1,0], [0.6, 0.8]) = 0.6
    # bm25_norm = 0.8 (from fake_fetch_bm25_matches)
    # score = (1-0.5)*0.6 + 0.5*0.8 + bonus = 0.3 + 0.4 + bonus = 0.7 + bonus
    assert keyword.score == pytest.approx(0.7 + lang_bonus, abs=1e-4)
    assert keyword.retrieval_source == "bm25"
    assert keyword.bm25_score == pytest.approx(12.0)
