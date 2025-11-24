from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Text, String, func, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.infrastructure.database.postgres_base import Base


class KnowledgeDocument(Base):
    """知识库文档模型"""
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 来源类型与引用（例如 upload/url/crawl/api 等 + 具体标识）
    source_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="来源类型")
    source_ref: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="来源引用（URL/路径/外部ID/批次ID）")
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="文档标题")
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="文档语言")
    mime: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="MIME 类型")
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="文件校验和")
    meta: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True, comment="自定义元数据")
    tags: Mapped[List[str] | None] = mapped_column(JSONB, nullable=True, comment="标签列表")
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="创建者")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联的块（级联删除）
    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class KnowledgeChunk(Base):
    """知识库块（Chunk）模型"""
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="所属文档ID"
    )
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="文档内块的序号")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="文本内容")
    embedding: Mapped[List[float]] = mapped_column(
        Vector(dim=settings.EMBEDDING_DIM),
        nullable=False,
        comment="嵌入向量表示",
    )
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="块语言或类型")
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR(), nullable=True, comment="用于全文检索的 tsvector"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联的文档
    document: Mapped[Optional[KnowledgeDocument]] = relationship(back_populates="chunks")
