from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres_base import get_async_session
from app.modules.knowledge_base.schemas import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentRead,
    KnowledgeDocumentIngestRequest,
    KnowledgeIngestResult,
    KnowledgeDocumentUpdate,
    KnowledgeChunkRead,
    KnowledgeSearchRequest,
    KnowledgeChunkUpdate,
)
from app.modules.knowledge_base import models
from app.modules.knowledge_base.repository import (
    create_document,
    delete_document,
    get_all_documents,
    get_document_by_id,
    update_document_metadata,
    get_chunks_by_document_id,
)
from app.modules.knowledge_base.service import (
    ingest_document_content,
    ingest_document_file,
    search_similar_chunks,
    update_chunk,
    delete_chunk,
)


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents", response_model=KnowledgeDocumentRead, status_code=201)
async def create_knowledge_document(payload: KnowledgeDocumentCreate, db: AsyncSession = Depends(get_async_session)):
    doc = await create_document(db, payload)
    # refresh to include created_at
    await db.refresh(doc)
    return doc


@router.post("/documents/{document_id}/ingest", response_model=KnowledgeIngestResult, status_code=201)
async def ingest_content(document_id: int, body: KnowledgeDocumentIngestRequest, db: AsyncSession = Depends(get_async_session)):
    # 简单校验文档存在
    exist = await db.get(models.KnowledgeDocument, document_id)
    if not exist:
        raise HTTPException(status_code=404, detail="Document not found")
    count = await ingest_document_content(db, document_id, body.content, overwrite=body.overwrite)
    return {"document_id": document_id, "chunks": count}


@router.post("/documents/{document_id}/ingest/upload", response_model=KnowledgeIngestResult, status_code=201)
async def ingest_content_upload(
    document_id: int,
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    db: AsyncSession = Depends(get_async_session),
):
    exist = await db.get(models.KnowledgeDocument, document_id)
    if not exist:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        count = await ingest_document_file(db, document_id, file, overwrite=overwrite)
    except ValueError as exc:
        reason = str(exc)
        if reason == "unsupported_file_type":
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload text-based files only.")
        if reason == "missing_file":
            raise HTTPException(status_code=400, detail="No file uploaded")
        raise HTTPException(status_code=400, detail="Failed to process uploaded file") from exc

    return {"document_id": document_id, "chunks": count}


@router.delete("/documents/{document_id}", status_code=204)
async def remove_document(document_id: int, db: AsyncSession = Depends(get_async_session)):
    await delete_document(db, document_id)
    return None


@router.get("/documents", response_model=list[KnowledgeDocumentRead])
async def list_documents(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=200, description="返回的最大记录数"),
    db: AsyncSession = Depends(get_async_session),
):
    docs = await get_all_documents(db, skip=skip, limit=limit)
    return docs


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentRead)
async def get_document(document_id: int, db: AsyncSession = Depends(get_async_session)):
    doc = await get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentRead)
async def patch_document(
    document_id: int,
    payload: KnowledgeDocumentUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    doc = await update_document_metadata(db, document_id, payload.model_dump(exclude_unset=True))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/search", response_model=list[KnowledgeChunkRead])
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_async_session),
):
    chunks = await search_similar_chunks(db, query=payload.query, top_k=payload.top_k)
    return chunks


@router.get("/documents/{document_id}/chunks", response_model=list[KnowledgeChunkRead])
async def list_document_chunks(document_id: int, db: AsyncSession = Depends(get_async_session)):
    # 确认文档存在
    exist = await db.get(models.KnowledgeDocument, document_id)
    if not exist:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = await get_chunks_by_document_id(db, document_id)
    return chunks


@router.patch("/chunks/{chunk_id}", response_model=KnowledgeChunkRead)
async def patch_chunk(
    chunk_id: int,
    payload: KnowledgeChunkUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        chunk = await db.get(models.KnowledgeChunk, chunk_id)
        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found")
        return chunk

    chunk = await update_chunk(db, chunk_id, updates)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return chunk


@router.delete("/chunks/{chunk_id}", status_code=204)
async def remove_chunk(
    chunk_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    deleted = await delete_chunk(db, chunk_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return None
