from __future__ import annotations

from functools import lru_cache
import logging
from typing import Iterable, Optional

from app.core.config import settings
from .language import detect_language_meta
import spacy
from spacy.language import Language


logger = logging.getLogger(__name__)


def _should_use_spacy(text: str, language: str | None) -> bool:
    """判断是否应使用 spaCy 进行分词"""
    lang = (language or "").lower()
    # 如果语言是中文或日文，则使用 spaCy
    if lang.startswith("zh") or lang.startswith("ja"):
        return True
    # 检测文本元数据，获取语言信息
    meta = detect_language_meta(text, default=lang or "en")
    candidate = (meta.get("language") or "").lower()
    # 如果检测到的语言是中文或日文，则使用 spaCy
    return candidate in {"zh", "ja"}


@lru_cache(maxsize=1)
def _load_zh_pipeline() -> Optional[Language]:
    """加载中文 spaCy 模型"""
    if spacy is None:
        logger.debug("spaCy not installed; skipping spaCy tokenisation")
        return None
    model_name = settings.SPACY_MODEL_NAME
    if not model_name:
        logger.debug("spaCy model name empty; skipping spaCy tokenisation")
        return None
    try:
        logger.info("Loading spaCy pipeline %s for Chinese tokenization", model_name)
        # 加载指定的 spaCy 模型
        return spacy.load(model_name)
    except OSError as exc:
        logger.warning(
            "spaCy model %s not available: %s; tokenization will fall back to raw text",
            model_name,
            exc,
        )
        return None


def _iter_tokens(doc: "Language" | None, text: str) -> Iterable[str]:
    """迭代处理过的文档中的词元"""
    if not doc:
        return []
    # 使用 spaCy 处理文本
    parsed = doc(text)
    # 返回去除首尾空格的词元
    return (token.text.strip() for token in parsed if token.text.strip())


def tokenize_for_search(text: str, language: str | None = None) -> str:
    """将文本分词成一个用空格分隔的字符串，适用于 PostgreSQL 的 simple config"""
    text = (text or "").strip()
    if not text:
        return ""

    # 判断是否需要使用 spaCy
    if _should_use_spacy(text, language):
        try:
            # 加载 spaCy pipeline
            pipeline = _load_zh_pipeline()
            # 获取分词结果
            tokens = [token for token in _iter_tokens(pipeline, text) if token]
            if tokens:
                # 将词元用空格连接成字符串
                return " ".join(tokens)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("spaCy tokenization failed, falling back to raw text: %s", exc)

    # 如果不使用 spaCy，则按空格分割文本并转换为小写
    return " ".join(text.lower().split())
