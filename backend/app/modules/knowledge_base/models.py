from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Text, String, func, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.infrastructure.database.postgres_base import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 来源类型与引用（例如 upload/url/crawl/api 等 + 具体标识）
    source_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="来源类型")
    source_ref: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="来源引用（URL/路径/外部ID/批次ID）")
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    mime: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    meta: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[List[str] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联的切片（级联删除）
    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="文档内块序")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="文本内容")
    # 384 维向量，需与所选嵌入模型维度一致
    embedding: Mapped[List[float]] = mapped_column(Vector(dim=384), nullable=False, comment="向量表示")
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="块语言/类型")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped[Optional[KnowledgeDocument]] = relationship(back_populates="chunks")
