from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .schemas import KnowledgeDocumentCreate


async def create_document(
    db: AsyncSession, data: KnowledgeDocumentCreate
) -> models.KnowledgeDocument:
    """Persist a new knowledge document without committing."""
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


async def delete_document(db: AsyncSession, document_id: int) -> None:
    """Remove a document and cascade to its chunks."""
    await db.execute(
        delete(models.KnowledgeDocument).where(models.KnowledgeDocument.id == document_id)
    )
    await db.commit()


async def get_all_documents(
    db: AsyncSession, skip: int = 0, limit: int = 100
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
    db: AsyncSession, document_id: int
) -> Optional[models.KnowledgeDocument]:
    return await db.get(models.KnowledgeDocument, document_id)


async def update_document_metadata(
    db: AsyncSession, document_id: int, updates: dict
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
    db: AsyncSession, document_id: int
) -> list[models.KnowledgeChunk]:
    stmt = (
        select(models.KnowledgeChunk)
        .where(models.KnowledgeChunk.document_id == document_id)
        .order_by(models.KnowledgeChunk.chunk_index.asc(), models.KnowledgeChunk.id.asc())
    )
    result = await db.scalars(stmt)
    return result.all()


async def delete_chunks_by_document_id(db: AsyncSession, document_id: int) -> None:
    await db.execute(
        delete(models.KnowledgeChunk).where(models.KnowledgeChunk.document_id == document_id)
    )


async def get_chunk_by_id(
    db: AsyncSession, chunk_id: int
) -> Optional[models.KnowledgeChunk]:
    return await db.get(models.KnowledgeChunk, chunk_id)


async def persist_chunk(db: AsyncSession, chunk: models.KnowledgeChunk) -> models.KnowledgeChunk:
    await db.commit()
    await db.refresh(chunk)
    return chunk


async def delete_chunk(db: AsyncSession, chunk: models.KnowledgeChunk) -> None:
    await db.delete(chunk)
    await db.commit()
