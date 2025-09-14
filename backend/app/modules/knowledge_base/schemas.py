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


class KnowledgeIngestResult(BaseModel):
    document_id: int
    chunks: int
