import logging
from typing import Awaitable, Callable, Dict

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
    KnowledgeSearchResult,
)
from app.modules.knowledge_base import models
from app.modules.knowledge_base.repository import crud_knowledge_base
from app.infrastructure.dynamic_settings import (
    DynamicSettingsService,
    get_dynamic_settings_service,
)
from app.modules.knowledge_base.bm25 import fetch_bm25_matches
from app.modules.knowledge_base.language import detect_language
from app.modules.knowledge_base.ingestion import (
    ingest_document_content,
    ingest_document_file,
    update_chunk,
    delete_chunk,
)
from app.infrastructure.utils.coerce_utils import coerce_float, coerce_int


router = APIRouter(prefix="/knowledge", tags=["knowledge"])
logger = logging.getLogger(__name__)

UPLOAD_ERROR_MAP: Dict[str, tuple[int, str]] = {
    "unsupported_file_type": (
        400,
        "Unsupported file type. Please upload text-based files only.",
    ),
    "missing_file": (400, "No file uploaded"),
}


async def _get_document_or_404(
    document_id: int,
    db: AsyncSession,
) -> models.KnowledgeDocument:
    doc = await db.get(models.KnowledgeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def _ingest_document(
    document_id: int,
    db: AsyncSession,
    operation: Callable[[models.KnowledgeDocument], Awaitable[int]],
    *,
    error_map: Dict[str, tuple[int, str]] | None = None,
) -> dict[str, int]:
    doc = await _get_document_or_404(document_id, db)
    try:
        count = await operation(doc)
    except ValueError as exc:
        if error_map is None:
            raise
        reason = str(exc)
        status_code, message = error_map.get(reason, (400, "Failed to process uploaded file"))
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {"document_id": document_id, "chunks": count}


@router.post("/documents", response_model=KnowledgeDocumentRead, status_code=201)
async def create_knowledge_document(payload: KnowledgeDocumentCreate, db: AsyncSession = Depends(get_async_session)):
    doc = await crud_knowledge_base.create_document(db, payload)
    # refresh to include created_at
    await db.refresh(doc)
    return doc


@router.post("/documents/{document_id}/ingest", response_model=KnowledgeIngestResult, status_code=201)
async def ingest_content(
    document_id: int,
    body: KnowledgeDocumentIngestRequest,
    db: AsyncSession = Depends(get_async_session),
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
):
    async def _operation(doc: models.KnowledgeDocument) -> int:
        return await ingest_document_content(
            db,
            document_id,
            body.content,
            overwrite=body.overwrite,
            document=doc,
            dynamic_settings_service=dynamic_settings_service,
        )

    return await _ingest_document(document_id, db, _operation)


@router.post("/documents/{document_id}/ingest/upload", response_model=KnowledgeIngestResult, status_code=201)
async def ingest_content_upload(
    document_id: int,
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    db: AsyncSession = Depends(get_async_session),
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
):
    async def _operation(doc: models.KnowledgeDocument) -> int:
        return await ingest_document_file(
            db,
            document_id,
            file,
            overwrite=overwrite,
            document=doc,
            dynamic_settings_service=dynamic_settings_service,
        )

    return await _ingest_document(
        document_id,
        db,
        _operation,
        error_map=UPLOAD_ERROR_MAP,
    )


@router.delete("/documents/{document_id}", status_code=204)
async def remove_document(document_id: int, db: AsyncSession = Depends(get_async_session)):
    await crud_knowledge_base.delete_document(db, document_id)
    return None


@router.get("/documents", response_model=list[KnowledgeDocumentRead])
async def list_documents(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=200, description="返回的最大记录数"),
    db: AsyncSession = Depends(get_async_session),
):
    docs = await crud_knowledge_base.get_all_documents(db, skip=skip, limit=limit)
    return docs


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentRead)
async def get_document(document_id: int, db: AsyncSession = Depends(get_async_session)):
    doc = await crud_knowledge_base.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentRead)
async def patch_document(
    document_id: int,
    payload: KnowledgeDocumentUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    doc = await crud_knowledge_base.update_document_metadata(
        db, document_id, payload.model_dump(exclude_unset=True)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/search", response_model=list[KnowledgeSearchResult])
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_async_session),
    dynamic_settings_service: DynamicSettingsService = Depends(get_dynamic_settings_service),
):
    top_k_value = max(1, min(payload.top_k, 100))
    language = detect_language(payload.query, None)

    try:
        config = await dynamic_settings_service.get_all()
    except Exception:
        config = settings.dynamic_settings_defaults()
    if not isinstance(config, dict):
        config = settings.dynamic_settings_defaults()

    bm25_enabled = True

    bm25_min_score = coerce_float(
        config,
        "BM25_MIN_SCORE",
        settings.BM25_MIN_SCORE,
        minimum=0.0,
    )
    default_bm25_top_k = coerce_int(
        config,
        "BM25_TOP_K",
        settings.BM25_TOP_K,
        minimum=1,
        maximum=100,
    )
    bm25_limit = default_bm25_top_k
    bm25_limit = max(1, min(100, bm25_limit))
    search_limit = min(100, max(bm25_limit, top_k_value))

    logger.info(
        "knowledge_search_bm25",
        extra={
            "top_k": top_k_value,
            "bm25_limit": search_limit,
            "bm25_min_score": bm25_min_score,
            "bm25_enabled": bm25_enabled,
        },
    )

    search_result = await fetch_bm25_matches(
        db,
        payload.query,
        search_limit,
        min_score=bm25_min_score,
        language=language,
    )

    matches = search_result.matches[:top_k_value]
    response: list[KnowledgeSearchResult] = []
    for match in matches:
        chunk = match.chunk
        response.append(
            KnowledgeSearchResult(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                language=getattr(chunk, "language", None),
                created_at=chunk.created_at,
                score=float(match.normalized_score),
                similarity=float(match.normalized_score),
                bm25_score=float(match.raw_score),
                retrieval_source="bm25",
            )
        )

    return response


@router.get("/documents/{document_id}/chunks", response_model=list[KnowledgeChunkRead])
async def list_document_chunks(document_id: int, db: AsyncSession = Depends(get_async_session)):
    # 确认文档存在
    exist = await db.get(models.KnowledgeDocument, document_id)
    if not exist:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = await crud_knowledge_base.get_chunks_by_document_id(db, document_id)
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
