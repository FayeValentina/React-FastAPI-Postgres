from __future__ import annotations

import logging
import threading
from typing import Optional

from sentence_transformers import SentenceTransformer

from app.core.config import settings

# 获取日志记录器
logger = logging.getLogger(__name__)

# 用于嵌入器单例的线程锁
_EMBEDDER_LOCK = threading.Lock()
# 全局嵌入器实例 (SentenceTransformer)
_EMBEDDER: Optional[SentenceTransformer] = None

def get_embedder() -> SentenceTransformer:
    """返回一个单例的 SentenceTransformer 实例，延迟初始化。"""
    global _EMBEDDER
    # 如果实例已存在，直接返回
    if _EMBEDDER is not None:
        return _EMBEDDER

    # 使用线程锁确保线程安全
    with _EMBEDDER_LOCK:
        # 再次检查实例是否存在，防止多线程下重复创建
        if _EMBEDDER is None:
            # 从设置中获取嵌入模型的名称
            model_name = settings.EMBEDDING_MODEL
            if not model_name:
                # 如果模型名称未配置，则抛出运行时错误
                raise RuntimeError("EMBEDDING_MODEL 未配置")
            # 记录正在加载模型的日志
            logger.info("正在加载嵌入模型 %s", model_name)
            # 初始化 SentenceTransformer 实例
            _EMBEDDER = SentenceTransformer(model_name)
    return _EMBEDDER


def reset_models_for_tests() -> None:
    """测试工具，用于清除缓存的模型实例。"""
    global _EMBEDDER
    with _EMBEDDER_LOCK:
        _EMBEDDER = None


# 导出模块内的主要函数
__all__ = ["get_embedder", "reset_models_for_tests"]
