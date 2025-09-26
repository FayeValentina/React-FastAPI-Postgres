import pytest

from app.modules.knowledge_base.repository import crud_knowledge_base


@pytest.mark.asyncio
async def test_search_by_bm25_empty_query_returns_empty() -> None:
    result = await crud_knowledge_base.search_by_bm25(None, "", 5)
    assert result == []


@pytest.mark.asyncio
async def test_search_by_bm25_zero_limit_returns_empty() -> None:
    result = await crud_knowledge_base.search_by_bm25(None, "hello", 0)
    assert result == []
