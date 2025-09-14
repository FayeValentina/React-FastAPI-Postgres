from __future__ import annotations

from typing import List, Optional
from functools import lru_cache
import os

from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
#from pgvector.sqlalchemy import cosine_distance

from app.core.config import settings
from . import models
from .schemas import KnowledgeDocumentCreate


# 嵌入模型（CPU 上加载，保持与 DB 维度一致）
_model = SentenceTransformer(settings.EMBEDDING_MODEL)


@lru_cache(maxsize=8)
def get_spacy_nlp_for_lang(lang: str):
    """按语言惰性加载 spaCy 模型，失败返回 None。

    优先使用对应语言的 PATH 变量，其次按模型名称加载；
    不支持的语言回退为中文配置。
    """
    try:
        import spacy  # type: ignore
        l = (lang or "").lower().strip()
        if l not in {"zh", "en", "ja"}:
            l = "en"

        # 读取路径优先
        path_map = {
            "zh": getattr(settings, "SPACY_MODEL_PATH_ZH", None) or os.getenv("SPACY_MODEL_PATH_ZH"),
            "en": getattr(settings, "SPACY_MODEL_PATH_EN", None) or os.getenv("SPACY_MODEL_PATH_EN"),
            "ja": getattr(settings, "SPACY_MODEL_PATH_JA", None) or os.getenv("SPACY_MODEL_PATH_JA"),
        }
        name_map = {
            "zh": getattr(settings, "SPACY_MODEL_ZH", None) or "zh_core_web_sm",
            "en": getattr(settings, "SPACY_MODEL_EN", None) or "en_core_web_sm",
            "ja": getattr(settings, "SPACY_MODEL_JA", None) or "ja_core_news_sm",
        }

        path = path_map.get(l)
        if path and os.path.exists(str(path)):
            return spacy.load(str(path))
        return spacy.load(str(name_map[l]))
    except Exception:
        return None


def split_text(content: str, target: int = 300, overlap: int = 50) -> List[str]:
    """按句分块（自动检测语言，优先使用对应 spaCy 模型分句）。

    - target: 目标块大小（约字符数）
    - overlap: 相邻块重叠字符数
    - 英文句子合并时在句子间插入空格，中文/日文不插入空格
    """
    text = content or ""

    # 语言检测（失败则回退 en）
    lang = "en"
    try:
        from langdetect import detect
        if text.strip():
            detected = detect(text)
            # 规范化
            if detected.startswith("zh"):
                lang = "zh"
            elif detected.startswith("en"):
                lang = "en"
            elif detected.startswith("ja"):
                lang = "ja"
            else:
                lang = "en"
    except Exception:
        lang = "en"

    sentences: List[str]
    nlp = get_spacy_nlp_for_lang(lang)
    if nlp is not None and text:
        try:
            doc = nlp(text)
            sentences = [s.text.strip() for s in getattr(doc, "sents", []) if s.text and s.text.strip()]
        except Exception:
            sentences = []
    else:
        sentences = []

    if not sentences:
        # 回退：中文/日文标点 + 英文常见终止符 + 换行
        import re
        sentences = [s.strip() for s in re.split(r"[。！？.!?\n]+", text) if s.strip()]

    # 若仍为空，直接以原文返回（避免空入库）
    if not sentences:
        return [text] if text else []

    chunks: List[str] = []
    cur = ""
    sep = " " if lang == "en" else ""
    for s in sentences:
        if not s:
            continue
        if not cur:
            cur = s
            continue
        if len(cur) + len(sep) + len(s) <= target:
            cur = f"{cur}{sep}{s}"
        else:
            chunks.append(cur)
            # 下一块以 overlap 个字符作为前缀
            prefix = cur[-overlap:] if overlap > 0 and len(cur) > overlap else ""
            cur = f"{prefix}{s}" if prefix else s
    if cur:
        chunks.append(cur)
    return chunks or ([text] if text else [])


async def create_document(db: AsyncSession, data: KnowledgeDocumentCreate) -> models.KnowledgeDocument:
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
    await db.flush()  # 分配 ID
    return doc


async def ingest_document_content(db: AsyncSession, document_id: int, content: str) -> int:
    """将文本切分并写入指定文档的知识块，返回块数量。"""
    chunks = split_text(content)
    if not chunks:
        return 0
    vectors = _model.encode(chunks, normalize_embeddings=True)
    for idx, (c, v) in enumerate(zip(chunks, vectors)):
        db.add(models.KnowledgeChunk(document_id=document_id, chunk_index=idx, content=c, embedding=v))
    await db.commit()
    return len(chunks)


async def delete_document(db: AsyncSession, document_id: int) -> None:
    """删除文档（级联删除知识块）。"""
    # 直接删除 Document，依赖外键和 ORM 级联清理 chunks
    await db.execute(delete(models.KnowledgeDocument).where(models.KnowledgeDocument.id == document_id))
    await db.commit()


async def search_similar_chunks(db: AsyncSession, query: str, top_k: int):
    """按余弦距离检索最相似的知识块。"""
    q_emb = _model.encode([query], normalize_embeddings=True)[0]
    stmt = (
        select(models.KnowledgeChunk)
        .order_by(models.KnowledgeChunk.embedding.cosine_distance(q_emb))
        .limit(top_k)
    )
    result = await db.scalars(stmt)
    return result.all()
