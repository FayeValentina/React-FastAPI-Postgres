from __future__ import annotations

from typing import List, Optional
from functools import lru_cache
import os

from sentence_transformers import SentenceTransformer
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
#from pgvector.sqlalchemy import cosine_distance

from app.core.config import settings
from . import models
from .schemas import KnowledgeDocumentCreate
from markdown import markdown
from bs4 import BeautifulSoup


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


def _strip_markdown(content: str) -> str:
    """将 Markdown 文本转换为纯文本。

    策略：先用 markdown 库转 HTML，再用 BeautifulSoup 提取纯文本；
    移除脚本/样式、代码块、图片，并保留链接的可见文字。
    """
    if not content:
        return ""
    try:
        html = markdown(content, output_format="html")
    except Exception:
        # 回退：若 markdown 渲染失败，直接使用原文
        html = content

    soup = BeautifulSoup(html, "html.parser")

    # 移除无关或噪声节点
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # 移除代码相关内容（块/行内）
    for tag in soup(["pre", "code", "kbd", "samp"]):
        tag.decompose()
    # 移除图片
    for img in soup.find_all("img"):
        img.decompose()

    # 提取文本并进行基本的空白规范化
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


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


async def ingest_document_content(db: AsyncSession, document_id: int, content: str, overwrite: bool = False) -> int:
    """将文本切分并写入指定文档的知识块，返回块数量。

    注意：split_text 与 _model.encode 为同步且可能耗时的 CPU 密集操作，
    放入线程池以避免阻塞事件循环。
    """
    # 新增步骤：在所有操作之前，先清理传入的 content
    plain_text_content = _strip_markdown(content)

    # 根据覆盖标志，先删除旧分块，避免数据冗余
    if overwrite:
        await db.execute(delete(models.KnowledgeChunk).where(models.KnowledgeChunk.document_id == document_id))

    # 在线程池中进行分句（使用清理后的纯文本）
    chunks = await run_in_threadpool(split_text, plain_text_content)
    if not chunks:
        # 若选择覆盖且新内容为空，确保删除提交
        if overwrite:
            await db.commit()
        return 0
    # 在线程池中进行向量编码
    vectors = await run_in_threadpool(_model.encode, chunks, normalize_embeddings=True)
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
    """按余弦距离检索最相似的知识块。

    _model.encode 为同步且可能耗时，放入线程池执行。
    """
    # 在线程池中进行查询向量编码
    q_emb = (await run_in_threadpool(_model.encode, [query], normalize_embeddings=True))[0]
    stmt = (
        select(models.KnowledgeChunk)
        .order_by(models.KnowledgeChunk.embedding.cosine_distance(q_emb))
        .limit(top_k)
    )
    result = await db.scalars(stmt)
    return result.all()


async def get_all_documents(db: AsyncSession, skip: int = 0, limit: int = 100):
    """分页获取文档列表。"""
    stmt = (
        select(models.KnowledgeDocument)
        .order_by(models.KnowledgeDocument.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return result.all()


async def get_document_by_id(db: AsyncSession, document_id: int):
    """根据 ID 获取单个文档。"""
    return await db.get(models.KnowledgeDocument, document_id)


async def update_document_metadata(db: AsyncSession, document_id: int, updates: dict):
    """更新文档的元信息（部分字段）。"""
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
    for k, v in (updates or {}).items():
        if k in allowed_fields:
            setattr(doc, k, v)

    await db.commit()
    await db.refresh(doc)
    return doc
