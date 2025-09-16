from __future__ import annotations

from typing import Iterable, List, Optional
from functools import lru_cache
import os

from sentence_transformers import SentenceTransformer
from fastapi.concurrency import run_in_threadpool
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
#from pgvector.sqlalchemy import cosine_distance

from app.core.config import settings
from . import models
from . import repository
from markdown import markdown
from bs4 import BeautifulSoup


# 嵌入模型（CPU 上加载，保持与 DB 维度一致）
_model = SentenceTransformer(settings.EMBEDDING_MODEL)


TEXT_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/tab-separated-values",
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
}

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
}


def _allowed_text_mime(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ctype = content_type.split(";", 1)[0].strip().lower()
    return ctype in TEXT_MIME_TYPES or ctype.startswith("text/")


def _allowed_text_suffix(filename: Optional[str]) -> bool:
    if not filename:
        return False
    suffix = os.path.splitext(filename)[1].lower()
    return suffix in TEXT_EXTENSIONS


def _decode_bytes_to_text(raw: bytes, encodings: Iterable[str] = ("utf-8", "utf-8-sig", "gbk")) -> str:
    if not raw:
        return ""
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


@lru_cache(maxsize=8)
def _get_spacy_nlp_for_lang(lang: str):
    """按语言惰性加载 spaCy 模型，失败返回 None。"""
    try:
        import spacy  # type: ignore
        language = (lang or "").lower().strip()
        if language not in {"zh", "en", "ja"}:
            language = "en"

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

        path = path_map.get(language)
        if path and os.path.exists(str(path)):
            return spacy.load(str(path))
        return spacy.load(str(name_map[language]))
    except Exception:
        return None


async def get_spacy_nlp_for_lang(lang: str):
    """在线程池中加载 spaCy 模型以避免阻塞事件循环。"""
    return await run_in_threadpool(_get_spacy_nlp_for_lang, lang)


def _split_text_sync(content: str, target: int = 300, overlap: int = 50) -> List[str]:
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
    nlp = _get_spacy_nlp_for_lang(lang)
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


async def split_text(content: str, target: int = 300, overlap: int = 50) -> List[str]:
    """在线程池中执行分句逻辑，避免阻塞事件循环。"""
    return await run_in_threadpool(_split_text_sync, content, target, overlap)


def _strip_markdown_sync(content: str) -> str:
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


async def _strip_markdown(content: str) -> str:
    """在线程池中清洗 Markdown 内容，避免阻塞事件循环。"""
    return await run_in_threadpool(_strip_markdown_sync, content)


async def ingest_document_file(
    db: AsyncSession,
    document_id: int,
    upload: UploadFile,
    overwrite: bool = False,
) -> int:
    """读取上传的纯文本/Markdown 文件并复用文本注入逻辑。"""
    if upload is None:
        raise ValueError("missing_file")

    if not (_allowed_text_mime(upload.content_type) or _allowed_text_suffix(upload.filename)):
        raise ValueError("unsupported_file_type")

    raw = await upload.read()
    # 尝试以常见编码解码为字符串
    content = _decode_bytes_to_text(raw)

    return await ingest_document_content(
        db,
        document_id,
        content,
        overwrite=overwrite,
    )


async def ingest_document_content(db: AsyncSession, document_id: int, content: str, overwrite: bool = False) -> int:
    """将文本切分并写入指定文档的知识块，返回块数量。

    注意：文本清洗、分句与向量编码均在线程池中执行，以避免阻塞事件循环。
    """
    # 新增步骤：在所有操作之前，先清理传入的 content
    plain_text_content = await _strip_markdown(content)

    # 根据覆盖标志，先删除旧分块，避免数据冗余
    if overwrite:
        await repository.delete_chunks_by_document_id(db, document_id)

    # 在线程池中进行分句（使用清理后的纯文本）
    chunks = await split_text(plain_text_content)
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


async def update_chunk(
    db: AsyncSession,
    chunk_id: int,
    updates: dict,
) -> models.KnowledgeChunk | None:
    """更新指定知识块内容或排序，并在内容变化时重计算向量。"""
    chunk = await repository.get_chunk_by_id(db, chunk_id)
    if not chunk:
        return None

    content_changed = False

    if "content" in updates:
        new_content = updates.get("content")
        if new_content is not None and new_content != chunk.content:
            chunk.content = new_content
            content_changed = True
        elif new_content is None and chunk.content is not None:
            # 允许显式清空内容
            chunk.content = ""
            content_changed = True

    if "chunk_index" in updates:
        chunk.chunk_index = updates.get("chunk_index")

    needs_persist = content_changed or ("chunk_index" in updates)

    if content_changed:
        vector = (
            await run_in_threadpool(_model.encode, [chunk.content], normalize_embeddings=True)
        )[0]
        chunk.embedding = vector

    if needs_persist:
        await repository.persist_chunk(db, chunk)

    return chunk


async def delete_chunk(db: AsyncSession, chunk_id: int) -> bool:
    """删除指定知识块。"""
    chunk = await repository.get_chunk_by_id(db, chunk_id)
    if not chunk:
        return False

    await repository.delete_chunk(db, chunk)
    return True


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
