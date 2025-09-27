from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

import numpy as np

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import models
from .schemas import KnowledgeDocumentCreate
from .tokenizer import tokenize_for_search


class CRUDKnowledgeBase:
    """Repository wrapper for knowledge documents and chunks."""

    @staticmethod
    def _apply_chunk_filters(
        stmt,
        filters: Mapping[str, Any] | None,
    ):
        payload = filters or {}

        document_ids = payload.get("document_ids")
        if document_ids:
            stmt = stmt.where(models.KnowledgeChunk.document_id.in_(document_ids))

        language = payload.get("language")
        if language:
            stmt = stmt.where(models.KnowledgeChunk.language == language)

        return stmt

    async def create_document(
        self, db: AsyncSession, data: KnowledgeDocumentCreate
    ) -> models.KnowledgeDocument:
        """Persist a new knowledge document (without commit)."""
        doc = models.KnowledgeDocument(
            source_type=data.source_type,
            source_ref=data.source_ref,
            title=data.title,
            language=data.language,
            mime=data.mime,
            checksum=data.checksum,
            meta=data.meta,
            tags=data.tags,
            created_by=data.created_by,
        )
        db.add(doc)
        await db.flush()
        return doc

    async def delete_document(self, db: AsyncSession, document_id: int) -> None:
        """Remove a document and cascade to its chunks."""
        await db.execute(
            delete(models.KnowledgeDocument).where(models.KnowledgeDocument.id == document_id)
        )
        await db.commit()

    async def get_all_documents(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[models.KnowledgeDocument]:
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
        return await db.get(models.KnowledgeDocument, document_id)

    async def update_document_metadata(
        self, db: AsyncSession, document_id: int, updates: dict
    ) -> Optional[models.KnowledgeDocument]:
        doc = await db.get(models.KnowledgeDocument, document_id)
        if not doc:
            return None

        allowed_fields = {
            "source_type",
            "source_ref",
            "title",
            "language",
            "mime",
            "checksum",
            "meta",
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
        stmt = (
            select(models.KnowledgeChunk)
            .where(models.KnowledgeChunk.document_id == document_id)
            .order_by(models.KnowledgeChunk.chunk_index.asc(), models.KnowledgeChunk.id.asc())
        )
        result = await db.scalars(stmt)
        return result.all()

    async def delete_chunks_by_document_id(
        self, db: AsyncSession, document_id: int, *, commit: bool = False
    ) -> None:
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
        """Persist a batch of chunks for a document."""

        created = 0
        for chunk_index, content, embedding, language in chunks:
            search_text = tokenize_for_search(content, language)
            db.add(
                models.KnowledgeChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=content,
                    embedding=np.asarray(embedding),
                    language=language,
                    search_vector=func.to_tsvector("simple", search_text),
                )
            )
            created += 1

        if commit:
            await db.commit()
        else:
            await db.flush()

        return created

    async def get_chunk_by_id(
        self, db: AsyncSession, chunk_id: int
    ) -> Optional[models.KnowledgeChunk]:
        return await db.get(models.KnowledgeChunk, chunk_id)

    async def persist_chunk(
        self, db: AsyncSession, chunk: models.KnowledgeChunk
    ) -> models.KnowledgeChunk:
        await db.commit()
        await db.refresh(chunk)
        return chunk

    async def delete_chunk(self, db: AsyncSession, chunk: models.KnowledgeChunk) -> None:
        await db.delete(chunk)
        await db.commit()

    async def fetch_chunk_candidates_by_embedding(
        self,
        db: AsyncSession,
        query_embedding: np.ndarray,
        limit: int,
    ):
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
        filters: Mapping[str, Any] | None = None,
        query_language: str | None = None,
    ) -> list[tuple[models.KnowledgeChunk, float]]:
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

        stmt = self._apply_chunk_filters(stmt, filters)

        stmt = stmt.order_by(rank_expr.desc()).limit(limit)

        rows = await db.execute(stmt)
        return rows.all()


crud_knowledge_base = CRUDKnowledgeBase()
