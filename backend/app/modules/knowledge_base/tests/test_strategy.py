import asyncio
import os

import pytest

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "postgres")
os.environ.setdefault("PGADMIN_DEFAULT_EMAIL", "admin@example.com")
os.environ.setdefault("PGADMIN_DEFAULT_PASSWORD", "admin")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.modules.knowledge_base import intent_classifier
from app.modules.knowledge_base.strategy import (
    StrategyContext,
    resolve_rag_parameters,
)


BASE_CONFIG = {
    "RAG_STRATEGY_ENABLED": True,
    "RAG_TOP_K": 5,
    "RAG_PER_DOC_LIMIT": 1,
    "RAG_MIN_SIM": 0.4,
    "RAG_OVERSAMPLE": 5,
    "RAG_MAX_CANDIDATES": 100,
    "RAG_RERANK_CANDIDATES": 40,
    "RAG_RERANK_SCORE_THRESHOLD": 0.5,
    "RAG_CONTEXT_MAX_EVIDENCE": 12,
    "RAG_CONTEXT_TOKEN_BUDGET": 2000,
}


def test_strategy_disabled_returns_base_config():
    base = dict(BASE_CONFIG)
    base["RAG_STRATEGY_ENABLED"] = False
    ctx = StrategyContext(channel="rest")

    result = asyncio.run(resolve_rag_parameters("anything", base, request_ctx=ctx))

    assert result.scenario == "disabled"
    assert result.config == base
    assert result.overrides == {}


def test_strategy_broad_query_increases_top_k_and_relaxes_threshold():
    ctx = StrategyContext(top_k_request=5, channel="rest")
    query = "请给我一个产品功能的全面介绍和总结"

    result = asyncio.run(resolve_rag_parameters(query, BASE_CONFIG, request_ctx=ctx))

    assert result.scenario == "broad"
    assert result.overrides["RAG_TOP_K"] == 9
    assert result.overrides["RAG_PER_DOC_LIMIT"] == 3
    assert result.overrides["RAG_MIN_SIM"] == pytest.approx(0.3)
    assert result.overrides["RAG_OVERSAMPLE"] == 7
    assert result.overrides["RAG_MAX_CANDIDATES"] == 108
    assert result.overrides["RAG_RERANK_CANDIDATES"] == 54
    assert result.overrides["RAG_RERANK_SCORE_THRESHOLD"] == pytest.approx(0.45)
    assert result.overrides["RAG_CONTEXT_MAX_EVIDENCE"] == 18
    assert result.overrides["RAG_CONTEXT_TOKEN_BUDGET"] == 2800


def test_strategy_precise_query_focuses_results():
    ctx = StrategyContext(top_k_request=6, channel="rest")
    query = "redis_pool timeout"

    result = asyncio.run(resolve_rag_parameters(query, BASE_CONFIG, request_ctx=ctx))

    assert result.scenario == "precise"
    assert result.overrides["RAG_TOP_K"] == 3
    assert result.overrides["RAG_PER_DOC_LIMIT"] == 5
    assert result.overrides["RAG_MIN_SIM"] == pytest.approx(0.55, rel=1e-3)
    assert result.overrides["RAG_OVERSAMPLE"] == 3
    assert result.overrides["RAG_MAX_CANDIDATES"] == 80
    assert result.overrides["RAG_RERANK_CANDIDATES"] == 9
    assert result.overrides["RAG_RERANK_SCORE_THRESHOLD"] == pytest.approx(0.6)
    assert result.overrides["RAG_CONTEXT_MAX_EVIDENCE"] == 10
    assert result.overrides["RAG_CONTEXT_TOKEN_BUDGET"] == 1800


def test_strategy_document_focus_raises_min_similarity():
    ctx = StrategyContext(document_id=42, channel="websocket")
    query = "展示该文档的关键内容"

    result = asyncio.run(resolve_rag_parameters(query, BASE_CONFIG, request_ctx=ctx))

    assert result.scenario == "document_focus"
    assert result.overrides["RAG_PER_DOC_LIMIT"] == 6
    assert result.overrides["RAG_MIN_SIM"] == pytest.approx(0.6)
    assert result.overrides["RAG_OVERSAMPLE"] == 6
    assert result.overrides["RAG_MAX_CANDIDATES"] == 160
    assert result.overrides["RAG_RERANK_CANDIDATES"] == 120
    assert result.overrides["RAG_CONTEXT_MAX_EVIDENCE"] == 16
    assert result.overrides["RAG_CONTEXT_TOKEN_BUDGET"] == 2600


def test_strategy_error_path_falls_back(monkeypatch):
    from app.modules.knowledge_base import strategy as strategy_module

    def raising(*_args, **_kwargs):  # pragma: no cover - invoked for fallback
        raise RuntimeError("boom")

    monkeypatch.setattr(strategy_module, "_classify_query", raising)

    ctx = StrategyContext(channel="rest")
    result = asyncio.run(resolve_rag_parameters("boom", BASE_CONFIG, request_ctx=ctx))

    assert result.scenario == "error"
    assert result.config == BASE_CONFIG


def test_strategy_llm_high_confidence_applies(monkeypatch):
    base = dict(BASE_CONFIG)
    base["RAG_STRATEGY_LLM_CLASSIFIER_ENABLED"] = True
    base["RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD"] = 0.6

    async def fake_classify(query, ctx):
        return intent_classifier.ClassificationResult(
            scenario="troubleshooting",
            confidence=0.82,
            reason="diagnosing errors",
            tags=("troubleshooting",),
        )

    monkeypatch.setattr(intent_classifier, "classify", fake_classify)

    ctx = StrategyContext(channel="rest")
    result = asyncio.run(resolve_rag_parameters("service is failing", base, request_ctx=ctx))

    assert result.scenario == "question"
    assert result.classifier is not None
    assert result.classifier.get("applied") is True
    assert result.classifier.get("label") == "troubleshooting"


def test_strategy_llm_low_confidence_fallback(monkeypatch):
    base = dict(BASE_CONFIG)
    base["RAG_STRATEGY_LLM_CLASSIFIER_ENABLED"] = True
    base["RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD"] = 0.8

    async def fake_classify(query, ctx):
        return intent_classifier.ClassificationResult(
            scenario="compare",
            confidence=0.3,
            reason="uncertain",
            tags=("compare",),
        )

    monkeypatch.setattr(intent_classifier, "classify", fake_classify)

    ctx = StrategyContext(channel="rest")
    query = "compare pricing"
    result = asyncio.run(resolve_rag_parameters(query, base, request_ctx=ctx))

    assert result.scenario == "precise"
    assert result.classifier is not None
    assert result.classifier.get("applied") is False
    assert result.classifier.get("cause") == "low_confidence"
