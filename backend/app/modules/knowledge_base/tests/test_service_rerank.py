import asyncio
from types import SimpleNamespace
import importlib
import sys
import numpy as np
import pytest


class DummyReranker:
    def __init__(self, outputs, *, raise_on_call=False):
        self.outputs = outputs
        self.raise_on_call = raise_on_call
        self.calls = 0

    def predict(self, pairs, convert_to_numpy=True, batch_size=None, show_progress_bar=False):
        self.calls += 1
        if self.raise_on_call:
            raise RuntimeError("boom")
        return self.outputs[: len(pairs)]


@pytest.fixture()
def service(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres")
    monkeypatch.setenv("POSTGRES_DB", "postgres")
    monkeypatch.setenv("PGADMIN_DEFAULT_EMAIL", "admin@example.com")
    monkeypatch.setenv("PGADMIN_DEFAULT_PASSWORD", "admin")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    import types

    dummy_model = SimpleNamespace(
        encode=lambda texts, normalize_embeddings=True: [np.zeros(3, dtype=np.float32)]
    )

    module_name_stub = "sentence_transformers"
    if module_name_stub in sys.modules:
        sentence_transformers = sys.modules[module_name_stub]
    else:
        sentence_transformers = types.ModuleType(module_name_stub)
        sys.modules[module_name_stub] = sentence_transformers

    class _DummySentenceTransformer:
        def __init__(self, *args, **kwargs):
            self._model = dummy_model

        def encode(self, texts, normalize_embeddings=True):
            return dummy_model.encode(texts, normalize_embeddings=normalize_embeddings)

    class _DummyCrossEncoder:
        def __init__(self, *args, **kwargs):
            pass

    sentence_transformers.SentenceTransformer = _DummySentenceTransformer
    sentence_transformers.CrossEncoder = _DummyCrossEncoder
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    module_name = "app.modules.knowledge_base.service"
    if module_name in sys.modules:
        del sys.modules[module_name]

    service_module = importlib.import_module(module_name)
    monkeypatch.setattr(service_module, "_model", dummy_model, raising=False)
    async def _immediate(func, *args, **kwargs):
        return func(*args, **kwargs)
    monkeypatch.setattr(service_module, "run_in_threadpool", _immediate, raising=False)
    return service_module


def test_rerank_applies_scores(monkeypatch, service):

    async def fake_fetch(_db, _emb, limit):
        chunk1 = SimpleNamespace(
            id=1,
            document_id=1,
            chunk_index=1,
            content="Alpha chunk content.",
            language="en",
            document=None,
            embedding=[0.1, 0.2, 0.3],
        )
        chunk2 = SimpleNamespace(
            id=2,
            document_id=1,
            chunk_index=2,
            content="Beta chunk content with more detail.",
            language="en",
            document=None,
            embedding=[0.2, 0.1, 0.2],
        )
        rows = [(chunk1, 0.25), (chunk2, 0.35)]
        return rows[:limit]

    dummy_reranker = DummyReranker([2.0, -5.0])

    monkeypatch.setattr(service.crud_knowledge_base, "fetch_chunk_candidates_by_embedding", fake_fetch)
    monkeypatch.setattr(service, "_detect_language", lambda _q: "en")
    monkeypatch.setattr(service, "_get_reranker", lambda: dummy_reranker)

    config_map = {
        "RAG_RERANK_ENABLED": True,
        "RAG_RERANK_CANDIDATES": 10,
        "RAG_RERANK_SCORE_THRESHOLD": 0.5,
        "RAG_RERANK_MAX_BATCH": 4,
        "RAG_TOP_K": 1,
        "RAG_MIN_SIM": 0.0,
        "RAG_PER_DOC_LIMIT": 10,
        "RAG_OVERSAMPLE": 5,
        "RAG_MAX_CANDIDATES": 100,
        "RAG_SAME_LANG_BONUS": 0.0,
    }

    results = asyncio.run(
        service.search_similar_chunks(
            db=None,
            query="test query",
            top_k=1,
            dynamic_settings_service=None,
            config=config_map,
        )
    )

    assert len(results) == 1
    assert results[0].chunk.id == 1
    assert results[0].rerank_score is not None and results[0].rerank_score > 0.73
    assert dummy_reranker.calls >= 1


def test_rerank_failure_falls_back(monkeypatch, service):
    chunk = SimpleNamespace(
        id=1,
        document_id=1,
        chunk_index=1,
        content="Gamma chunk",
        language="en",
        document=None,
        embedding=[0.1, 0.2, 0.3],
    )

    async def fake_fetch(_db, _emb, limit):
        return [(chunk, 0.1)]

    monkeypatch.setattr(service.crud_knowledge_base, "fetch_chunk_candidates_by_embedding", fake_fetch)
    monkeypatch.setattr(service, "_detect_language", lambda _q: "en")

    failing_reranker = DummyReranker([], raise_on_call=True)
    monkeypatch.setattr(service, "_get_reranker", lambda: failing_reranker)

    config_map = {
        "RAG_RERANK_ENABLED": True,
        "RAG_RERANK_CANDIDATES": 5,
        "RAG_RERANK_SCORE_THRESHOLD": 0.5,
        "RAG_RERANK_MAX_BATCH": 2,
        "RAG_TOP_K": 1,
        "RAG_MIN_SIM": 0.0,
        "RAG_PER_DOC_LIMIT": 3,
        "RAG_OVERSAMPLE": 2,
        "RAG_MAX_CANDIDATES": 10,
        "RAG_SAME_LANG_BONUS": 0.0,
    }

    results = asyncio.run(
        service.search_similar_chunks(
            db=None,
            query="fallback",
            top_k=1,
            dynamic_settings_service=None,
            config=config_map,
        )
    )

    assert len(results) == 1
    assert results[0].chunk.id == 1
    assert results[0].rerank_score is None  # fallback restores baseline
