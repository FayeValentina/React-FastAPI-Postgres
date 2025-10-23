from __future__ import annotations

from typing import List

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.dynamic_settings import DynamicSettingsService

from . import models
from .config import DynamicSettingsMapping, resolve_dynamic_settings
from .embeddings import get_embedder
from .ingest_extractor import ExtractedElement, extract_from_bytes, extract_from_text
from .ingest_splitter import SplitChunk, split_elements
from .language import detect_language_meta
from .repository import crud_knowledge_base
from .tokenizer import tokenize_for_search


async def _split_elements_async(
    elements: list[ExtractedElement],
    config: DynamicSettingsMapping | None,
) -> List[SplitChunk]:
    if not elements:
        return []
    return await run_in_threadpool(split_elements, elements, config=config)


async def _persist_chunks(
    db: AsyncSession,
    *,
    document_id: int,
    elements: list[ExtractedElement],
    overwrite: bool,
    dynamic_settings_service: DynamicSettingsService | None,
) -> int:
    config = await resolve_dynamic_settings(dynamic_settings_service)
    split_chunks = await _split_elements_async(elements, config)
    if not split_chunks:
        if overwrite:
            await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=True)
        return 0

    if overwrite:
        await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=False)

    embedder = get_embedder()
    texts = [chunk.content for chunk in split_chunks]
    vectors = await run_in_threadpool(embedder.encode, texts, normalize_embeddings=True)
    payloads = [
        (idx, chunk.content, vector, chunk.language)
        for idx, (chunk, vector) in enumerate(zip(split_chunks, vectors))
    ]

    await crud_knowledge_base.bulk_create_document_chunks(
        db,
        document_id,
        payloads,
        commit=True,
    )

    return len(payloads)


async def ingest_document_file(
    db: AsyncSession,
    document_id: int,
    upload: UploadFile,
    overwrite: bool = False,
    document: models.KnowledgeDocument | None = None,
    dynamic_settings_service: DynamicSettingsService | None = None,
) -> int:
    """Ingest an uploaded document by extracting, chunking, and storing its elements."""
    if upload is None:
        raise ValueError("missing_file")

    raw = await upload.read()
    if document is None:
        document = await crud_knowledge_base.get_document_by_id(db, document_id)

    filename = upload.filename or (document.source_ref if document else None)
    content_type = upload.content_type

    _, elements = await run_in_threadpool(
        extract_from_bytes,
        raw,
        filename=filename,
        content_type=content_type,
    )

    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=elements,
        overwrite=overwrite,
        dynamic_settings_service=dynamic_settings_service,
    )


async def ingest_document_content(
    db: AsyncSession,
    document_id: int,
    content: str,
    overwrite: bool = False,
    document: models.KnowledgeDocument | None = None,
    dynamic_settings_service: DynamicSettingsService | None = None,
) -> int:
    """Ingest raw text content provided directly via API."""
    if document is None:
        document = await crud_knowledge_base.get_document_by_id(db, document_id)

    source_ref = document.source_ref if document and document.source_ref else None
    elements = await run_in_threadpool(extract_from_text, content or "", source_ref=source_ref)

    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=elements,
        overwrite=overwrite,
        dynamic_settings_service=dynamic_settings_service,
    )


async def update_chunk(
    db: AsyncSession,
    chunk_id: int,
    updates: dict,
) -> models.KnowledgeChunk | None:
    """Update a stored chunk and recalculate embedding when content changes."""
    chunk = await crud_knowledge_base.get_chunk_by_id(db, chunk_id)
    if not chunk:
        return None

    content_changed = False

    if "content" in updates:
        new_content = updates.get("content")
        if new_content is not None and new_content != chunk.content:
            chunk.content = new_content
            content_changed = True
        elif new_content is None and chunk.content is not None:
            chunk.content = ""
            content_changed = True

    if "chunk_index" in updates:
        chunk.chunk_index = updates.get("chunk_index")

    needs_persist = content_changed or ("chunk_index" in updates)

    if content_changed:
        embedder = get_embedder()
        vector = (
            await run_in_threadpool(embedder.encode, [chunk.content], normalize_embeddings=True)
        )[0]
        chunk.embedding = vector
        stripped = (chunk.content or "").strip()
        meta = detect_language_meta(stripped or "")
        chunk.language = meta["language"]

    if content_changed:
        search_text = tokenize_for_search(chunk.content, chunk.language)
        chunk.search_vector = func.to_tsvector("simple", search_text)

    if needs_persist:
        await crud_knowledge_base.persist_chunk(db, chunk)

    return chunk


async def delete_chunk(db: AsyncSession, chunk_id: int) -> bool:
    """Delete a chunk by id."""
    chunk = await crud_knowledge_base.get_chunk_by_id(db, chunk_id)
    if not chunk:
        return False

    await crud_knowledge_base.delete_chunk(db, chunk)
    return True


__all__ = [
    "ingest_document_file",
    "ingest_document_content",
    "update_chunk",
    "delete_chunk",
]
