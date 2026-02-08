from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

import numpy as np

from sqlalchemy import delete, select, func, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import models
from .schemas import KnowledgeDocumentCreate
from .tokenizer import tokenize_for_search


class CRUDKnowledgeBase:
    """知识库文档和块的存储库包装器。"""

    async def create_document(
        self, db: AsyncSession, data: KnowledgeDocumentCreate
    ) -> models.KnowledgeDocument:
        """持久化一个新的知识库文档（不提交）。"""
        doc = models.KnowledgeDocument(
            source_type=data.source_type,
            source_ref=data.source_ref,
            title=data.title,
            tags=data.tags,
            created_by=data.created_by,
        )
        db.add(doc)
        await db.flush()
        return doc

    async def delete_document(self, db: AsyncSession, document_id: int) -> None:
        """删除一个文档并级联删除其块。"""
        await db.execute(
            delete(models.KnowledgeDocument).where(models.KnowledgeDocument.id == document_id)
        )
        await db.commit()

    async def get_all_documents(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[models.KnowledgeDocument]:
        """获取所有文档。"""
        stmt = (
            select(models.KnowledgeDocument)
            .order_by(models.KnowledgeDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.scalars(stmt)
        return result.all()

    async def get_document_by_id(
        self, db: AsyncSession, document_id: int
    ) -> Optional[models.KnowledgeDocument]:
        """按 ID 获取文档。"""
        return await db.get(models.KnowledgeDocument, document_id)

    async def update_document_metadata(
        self, db: AsyncSession, document_id: int, updates: dict
    ) -> Optional[models.KnowledgeDocument]:
        """更新文档元数据。"""
        doc = await db.get(models.KnowledgeDocument, document_id)
        if not doc:
            return None

        allowed_fields = {
            "source_type",
            "source_ref",
            "title",
            "tags",
            "created_by",
        }

        for key, value in (updates or {}).items():
            if key in allowed_fields:
                setattr(doc, key, value)

        await db.commit()
        await db.refresh(doc)
        return doc

    async def get_chunks_by_document_id(
        self, db: AsyncSession, document_id: int
    ) -> list[models.KnowledgeChunk]:
        """按文档 ID 获取块。"""
        stmt = (
            select(models.KnowledgeChunk)
            .where(models.KnowledgeChunk.document_id == document_id)
            .order_by(models.KnowledgeChunk.chunk_index.asc(), models.KnowledgeChunk.id.asc())
        )
        result = await db.scalars(stmt)
        return result.all()

    async def get_max_chunk_index(
        self,
        db: AsyncSession,
        document_id: int,
    ) -> int:
        """获取指定文档当前的最大 chunk_index，若不存在则返回 -1。"""
        stmt = select(func.max(models.KnowledgeChunk.chunk_index)).where(
            models.KnowledgeChunk.document_id == document_id
        )
        result = await db.execute(stmt)
        max_index = result.scalar_one_or_none()
        return -1 if max_index is None else int(max_index)

    async def delete_chunks_by_document_id(
        self, db: AsyncSession, document_id: int, *, commit: bool = False
    ) -> None:
        """按文档 ID 删除块。"""
        await db.execute(
            delete(models.KnowledgeChunk).where(models.KnowledgeChunk.document_id == document_id)
        )
        if commit:
            await db.commit()

    async def bulk_create_document_chunks(
        self,
        db: AsyncSession,
        document_id: int,
        chunks: Iterable[tuple[int, str, Sequence[float], Optional[str]]],
        *,
        commit: bool = True,
    ) -> int:
        """为一个文档持久化一批块。"""

        records: list[dict[str, Any]] = []
        for chunk_index, content, embedding, language in chunks:
            search_text = tokenize_for_search(content, language)
            vector = np.asarray(embedding).tolist()
            records.append(
                {
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "content": content,
                    "embedding": vector,
                    "language": language,
                    "search_vector": func.to_tsvector("simple", search_text),
                }
            )

        if not records:
            if commit:
                await db.commit()
            else:
                await db.flush()
            return 0

        stmt = insert(models.KnowledgeChunk).values(records)
        await db.execute(stmt)

        if commit:
            await db.commit()
        else:
            await db.flush()

        return len(records)

    async def get_chunk_by_id(
        self, db: AsyncSession, chunk_id: int
    ) -> Optional[models.KnowledgeChunk]:
        """按 ID 获取块。"""
        return await db.get(models.KnowledgeChunk, chunk_id)

    async def persist_chunk(
        self, db: AsyncSession, chunk: models.KnowledgeChunk
    ) -> models.KnowledgeChunk:
        """持久化一个块。"""
        await db.commit()
        await db.refresh(chunk)
        return chunk

    async def delete_chunk(self, db: AsyncSession, chunk: models.KnowledgeChunk) -> None:
        """删除一个块。"""
        await db.delete(chunk)
        await db.commit()

    async def search_by_vector(
        self,
        db: AsyncSession,
        query_embedding: np.ndarray,
        limit: int,
    ):
        """通过嵌入获取块候选项。"""
        distance_expr = models.KnowledgeChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(models.KnowledgeChunk, distance_expr.label("distance"))
            .options(selectinload(models.KnowledgeChunk.document))
            .order_by(distance_expr.asc())
            .limit(limit)
        )

        rows = await db.execute(stmt)
        return rows.all()

    async def search_by_bm25(
        self,
        db: AsyncSession,
        query: str,
        limit: int,
        *,
        query_language: str | None = None,
        min_rank: float | None = None
    ) -> list[tuple[models.KnowledgeChunk, float]]:
        """通过 BM25 进行搜索。"""
        normalized_query = tokenize_for_search(query, query_language)

        if not normalized_query or limit <= 0:
            return []

        ts_query = func.plainto_tsquery("simple", normalized_query)
        rank_expr = func.ts_rank_cd(models.KnowledgeChunk.search_vector, ts_query)

        stmt = (
            select(models.KnowledgeChunk, rank_expr.label("bm25_score"))
            .options(selectinload(models.KnowledgeChunk.document))
            .where(models.KnowledgeChunk.search_vector.isnot(None))
            .where(models.KnowledgeChunk.search_vector.op("@@")(ts_query))
        )

        # 绝对阈值（稳定语义）在数据库侧进行 gating
        if min_rank is not None:
            stmt = stmt.where(rank_expr >= min_rank)

        stmt = stmt.order_by(rank_expr.desc()).limit(limit)

        rows = await db.execute(stmt)
        return rows.all()


crud_knowledge_base = CRUDKnowledgeBase()
