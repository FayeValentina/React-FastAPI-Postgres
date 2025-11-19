from __future__ import annotations

from typing import List

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .embeddings import get_embedder
from .ingest_extractor import ExtractedElement, extract_from_bytes, extract_from_text
from .ingest_splitter import SplitChunk, split_elements
from .language import detect_language_meta
from .repository import crud_knowledge_base
from .tokenizer import tokenize_for_search


async def _split_elements_async(
    elements: list[ExtractedElement],
) -> List[SplitChunk]:
    """异步地将提取的元素分割成块。"""
    if not elements:
        return []
    # 在线程池中运行 `split_elements` 以避免阻塞事件循环
    return await run_in_threadpool(split_elements, elements)


async def _persist_chunks(
    db: AsyncSession,
    *,
    document_id: int,
    elements: list[ExtractedElement],
    overwrite: bool,
) -> int:
    """将分割后的块持久化到数据库。"""
    split_chunks = await _split_elements_async(elements)
    if not split_chunks:
        # 如果没有块，且需要覆盖，则删除该文档的所有现有块
        if overwrite:
            await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=True)
        return 0

    if overwrite:
        # 如果需要覆盖，先删除旧的块
        await crud_knowledge_base.delete_chunks_by_document_id(db, document_id, commit=False)
        start_index = 0
    else:
        # 非覆盖模式下，将新 chunk 附加在现有索引之后
        max_index = await crud_knowledge_base.get_max_chunk_index(db, document_id)
        start_index = max_index + 1

    # 获取嵌入模型
    embedder = get_embedder()
    texts = [chunk.content for chunk in split_chunks]
    # 在线程池中为所有文本块生成嵌入向量
    vectors = await run_in_threadpool(embedder.encode, texts, normalize_embeddings=True)

    payloads = []
    # 为每个块准备持久化所需的数据
    for idx, (chunk, vector) in enumerate(zip(split_chunks, vectors)):
        # 检测块的语言
        meta = detect_language_meta((chunk.content or "").strip())
        lang = meta["language"]
        payloads.append((start_index + idx, chunk.content, vector, lang))

    # 批量创建文档块
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
) -> int:
    """通过提取、分块和存储元素来摄入上传的文档文件。"""
    if upload is None:
        raise ValueError("缺少文件")

    raw = await upload.read()
    if document is None:
        document = await crud_knowledge_base.get_document_by_id(db, document_id)

    filename = upload.filename or (document.source_ref if document else None)
    content_type = upload.content_type

    # 在线程池中从文件字节中提取元素
    _, elements = await run_in_threadpool(
        extract_from_bytes,
        raw,
        filename=filename,
        content_type=content_type,
    )

    # 持久化提取出的块
    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=elements,
        overwrite=overwrite,
    )


async def ingest_document_content(
    db: AsyncSession,
    document_id: int,
    content: str,
    overwrite: bool = False,
    document: models.KnowledgeDocument | None = None,
) -> int:
    """摄入通过 API 直接提供的原始文本内容。"""
    if document is None:
        document = await crud_knowledge_base.get_document_by_id(db, document_id)

    source_ref = document.source_ref if document and document.source_ref else None
    # 在线程池中从文本内容中提取元素
    elements = await run_in_threadpool(extract_from_text, content or "", source_ref=source_ref)

    # 持久化提取出的块
    return await _persist_chunks(
        db,
        document_id=document_id,
        elements=elements,
        overwrite=overwrite,
    )


async def update_chunk(
    db: AsyncSession,
    chunk_id: int,
    updates: dict,
) -> models.KnowledgeChunk | None:
    """更新存储的块，并在内容更改时重新计算嵌入。"""
    chunk = await crud_knowledge_base.get_chunk_by_id(db, chunk_id)
    if not chunk:
        return None

    content_changed = False

    # 检查内容是否有更新
    if "content" in updates:
        new_content = updates.get("content")
        if new_content is not None and new_content != chunk.content:
            chunk.content = new_content
            content_changed = True
        elif new_content is None and chunk.content is not None:
            chunk.content = ""
            content_changed = True

    # 检查块索引是否有更新
    if "chunk_index" in updates:
        chunk.chunk_index = updates.get("chunk_index")

    chunk_index_changed = "chunk_index" in updates

    # 如果内容已更改，则重新计算嵌入和搜索向量
    if content_changed:
        embedder = get_embedder()
        # 重新计算嵌入向量
        vector = (
            await run_in_threadpool(embedder.encode, [chunk.content], normalize_embeddings=True)
        )[0]
        chunk.embedding = vector
        stripped = (chunk.content or "").strip()
        # 重新检测语言
        meta = detect_language_meta(stripped or "")
        chunk.language = meta["language"]

        # 为全文搜索重新生成 tsvector
        search_text = tokenize_for_search(chunk.content, chunk.language)
        chunk.search_vector = func.to_tsvector("simple", search_text)

    needs_persist = content_changed or chunk_index_changed

    # 如果有任何更改，则持久化块
    if needs_persist:
        await crud_knowledge_base.persist_chunk(db, chunk)

    return chunk


async def delete_chunk(db: AsyncSession, chunk_id: int) -> bool:
    """按 ID 删除一个块。"""
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
