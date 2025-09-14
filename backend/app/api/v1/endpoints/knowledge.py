from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.postgres_base import get_async_session
from app.modules.knowledge_base.schemas import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentRead,
    KnowledgeDocumentIngestRequest,
    KnowledgeIngestResult,
)
from app.modules.knowledge_base import models
from app.modules.knowledge_base.service import (
    create_document,
    ingest_document_content,
    delete_document,
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
    count = await ingest_document_content(db, document_id, body.content)
    return {"document_id": document_id, "chunks": count}


@router.delete("/documents/{document_id}", status_code=204)
async def remove_document(document_id: int, db: AsyncSession = Depends(get_async_session)):
    await delete_document(db, document_id)
    return None
