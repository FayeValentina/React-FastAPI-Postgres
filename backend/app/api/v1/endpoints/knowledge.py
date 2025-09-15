from fastapi import APIRouter, Depends, HTTPException, Query
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
)
from app.modules.knowledge_base import models
from app.modules.knowledge_base.service import (
    create_document,
    ingest_document_content,
    delete_document,
    get_all_documents,
    get_document_by_id,
    update_document_metadata,
    search_similar_chunks,
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
