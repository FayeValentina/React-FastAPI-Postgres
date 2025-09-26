from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KnowledgeDocumentBase(BaseModel):
    source_type: Optional[str] = Field(None, description="来源类型：upload/url/crawl/api 等")
    source_ref: Optional[str] = Field(None, description="来源引用：URL/路径/外部ID/批次ID")
    title: Optional[str] = None
    language: Optional[str] = Field(None, description="文档语言代码，如 zh/en/ja")
    mime: Optional[str] = None
    checksum: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    created_by: Optional[str] = None


class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    pass


class KnowledgeDocumentRead(KnowledgeDocumentBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeDocumentIngestRequest(BaseModel):
    content: str = Field(..., description="要切分并入库的全文内容")
    overwrite: bool = Field(False, description="是否覆盖已有分块（true 将先清空原分块）")


class KnowledgeIngestResult(BaseModel):
    document_id: int
    chunks: int


class KnowledgeDocumentUpdate(KnowledgeDocumentBase):
    """文档元数据更新（全部字段可选）"""
    pass


class KnowledgeChunkRead(BaseModel):
    id: int
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None
    content: str
    language: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeChunkUpdate(BaseModel):
    content: Optional[str] = Field(None, description="更新后的文本内容")
    chunk_index: Optional[int] = Field(
        None, description="文档内块序，允许为空表示未指定"
    )
    language: Optional[str] = Field(None, description="块语言，通常自动推断")


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索的查询文本")
    top_k: int = Field(5, ge=1, le=50, description="返回最相似的结果数量（1-50）")
    bm25_enabled: Optional[bool] = Field(
        None, description="是否启用 BM25 关键字检索，默认遵循后端配置"
    )
    bm25_top_k: Optional[int] = Field(
        None, ge=1, le=100, description="BM25 候选数量上限"
    )
    bm25_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="BM25 得分在融合时的权重"
    )
    bm25_min_score: Optional[float] = Field(
        None, ge=0.0, description="筛除低于该 BM25 原始分数的候选"
    )


class KnowledgeSearchResult(BaseModel):
    id: int
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None
    content: str
    language: Optional[str] = None
    created_at: datetime
    score: float = Field(..., description="融合后的综合得分（0-1）")
    similarity: float = Field(..., description="向量相似度分量（0-1）")
    bm25_score: Optional[float] = Field(
        None, description="BM25 原始分数，未命中则为空"
    )
    retrieval_source: str = Field(
        ..., description="召回来源：vector/bm25/hybrid"
    )

    model_config = {"from_attributes": True}
