"""在摄入和检索之间共享的语言规范化和检测辅助工具。"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Iterable, Mapping, TYPE_CHECKING

from app.core.config import settings

# 类型检查时导入，避免循环依赖
if TYPE_CHECKING:  # pragma: no cover
    from lingua import Language as T_Language
    from lingua import LanguageDetector as T_LanguageDetector
    from lingua import LanguageDetectorBuilder as T_LanguageDetectorBuilder
else:  # pragma: no cover - runtime fallbacks
    T_Language = Any
    T_LanguageDetector = Any
    T_LanguageDetectorBuilder = Any

# 尝试导入可选的 lingua 库
try:  # pragma: no cover - 可选依赖
    from lingua import Language as _Language
    from lingua import LanguageDetector as _LanguageDetector
    from lingua import LanguageDetectorBuilder as _LanguageDetectorBuilder
except Exception:  # pragma: no cover - lingua 不可用时的回退
    _Language = None  # type: ignore
    _LanguageDetector = None  # type: ignore
    _LanguageDetectorBuilder = None  # type: ignore


logger = logging.getLogger(__name__)

# 语言别名到规范 ISO 代码的映射
LANGUAGE_ALIAS_MAP: dict[str, str] = {
    "english": "en",
    "eng": "en",
    "en-us": "en",
    "en_us": "en",
    "en-gb": "en",
    "chinese": "zh",
    "zh-cn": "zh",
    "zh_cn": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
    "zh-tw": "zh",
    "mandarin": "zh",
    "cn": "zh",
    "japanese": "ja",
    "jp": "ja",
}

# 允许的代码标签集合
_ALLOWED_CODE_LABELS = {"code"}

# 正则表达式定义
_CODE_FENCE_RE = re.compile(r"(?m)^[ \t]*(```|~~~)")  # 代码块标记
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")  # 中日韩统一表意文字
_HIRAGANA_RE = re.compile(r"[\u3040-\u309f]")  # 日语平假名
_KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]")  # 日语片假名

# Lingua 检测器的线程锁和全局实例
_LINGUA_LOCK = threading.Lock()
_LINGUA_DETECTOR: T_LanguageDetector | None = None
_LINGUA_AVAILABLE = (_Language is not None and _LanguageDetectorBuilder is not None)


def _from_iterable(values: Iterable[Any], *, allow_code: bool) -> str | None:
    """从可迭代对象中找到第一个有效的、规范化的语言代码。"""
    for item in values:
        normalised = normalize_language_value(item, allow_code=allow_code)
        if normalised:
            return normalised
    return None


def normalize_language_value(value: Any, *, allow_code: bool = True) -> str | None:
    """将各种形式的语言提示规范化为简短的类 ISO 代码。"""
    if value is None:
        return None

    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            return None

        # 首先通过别名映射进行转换
        candidate = LANGUAGE_ALIAS_MAP.get(candidate, candidate)
        # 处理 en-US, zh-CN 等形式
        for separator in ("-", "_"):
            if separator in candidate:
                candidate = candidate.split(separator, 1)[0]

        # 检查是否为允许的代码标签
        if allow_code and candidate in _ALLOWED_CODE_LABELS:
            return "code"

        # 检查是否为两位字母代码
        if len(candidate) == 2 and candidate.isalpha():
            return candidate

        # 再次尝试通过别名映射
        return LANGUAGE_ALIAS_MAP.get(candidate)

    if isinstance(value, Mapping):
        return normalize_language_value(value.get("language"), allow_code=allow_code)

    if isinstance(value, (list, tuple, set)):
        return _from_iterable(value, allow_code=allow_code)

    return None


def is_probable_code(text: str | None) -> bool:
    """启发式地判断负载是否像一个代码块。"""
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False

    # 检查是否存在代码块标记
    if _CODE_FENCE_RE.search(stripped):
        return True

    # 基于标点符号和字母的比例进行启发式判断
    punctuation_hits = sum(stripped.count(symbol) for symbol in ("{", "}", "(", ")", ";", "::", "</"))
    alphabetic = sum(1 for ch in stripped if ch.isalpha())
    return punctuation_hits >= 5 and punctuation_hits >= max(3, alphabetic // 3)


def is_cjk_text(text: str | None) -> bool:
    """当负载包含 CJK (中日韩) 字符时返回 True。"""
    if not text:
        return False
    sample = text.strip()
    if not sample:
        return False
    # 日语假名优先判断
    if _HIRAGANA_RE.search(sample) or _KATAKANA_RE.search(sample):
        return True
    # 判断是否存在中日韩统一表意文字
    return bool(_CJK_RE.search(sample))


def _should_use_lingua(config: Mapping[str, Any] | None) -> bool:
    """根据设置和覆盖决定是否应使用 Lingua。"""
    flag = settings.RAG_USE_LINGUA
    if config is not None:
        candidate = config.get("RAG_USE_LINGUA", flag)
        if isinstance(candidate, str):
            flag = candidate.strip().lower() in {"1", "true", "yes", "on"}
        else:
            flag = bool(candidate)
    return bool(flag and (_LanguageDetectorBuilder is not None))


def _build_lingua_detector() -> T_LanguageDetector | None:
    """构建 Lingua 语言检测器实例。"""
    if _LanguageDetectorBuilder is None or _Language is None:  # pragma: no cover
        return None

    # 仅限检测英语、中文、日语
    languages = [_Language.ENGLISH, _Language.CHINESE, _Language.JAPANESE]
    try:
        logger.debug("language: 正在构建 lingua 检测器...")
        det = (
            _LanguageDetectorBuilder.from_languages(*languages)
            .with_preloaded_language_models()
            .build()
        )
        logger.debug("language: lingua 检测器构建成功")
        return det
    except Exception:  # pragma: no cover - 应该很少失败
        logger.warning("language: 构建 lingua 检测器失败；回退到启发式方法", exc_info=logger.isEnabledFor(logging.DEBUG))
        return None


def _get_lingua_detector() -> T_LanguageDetector | None:
    """获取单例的 Lingua 检测器实例。"""
    global _LINGUA_DETECTOR
    if _LINGUA_DETECTOR is not None:
        return _LINGUA_DETECTOR

    with _LINGUA_LOCK:
        if _LINGUA_DETECTOR is None:
            _LINGUA_DETECTOR = _build_lingua_detector()
    return _LINGUA_DETECTOR


def lingua_status(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """暴露运行时状态以用于调试/日志记录。"""
    return {
        "installed": _LINGUA_AVAILABLE,  # Lingua 是否已安装
        "enabled_by_config": _should_use_lingua(config),  # 配置是否启用了 Lingua
        "detector_cached": _LINGUA_DETECTOR is not None,  # 检测器是否已缓存
    }


def detect_language_meta(
    text: str,
    *,
    config: Mapping[str, Any] | None = None,
    default: str = "en",
) -> dict[str, Any]:
    """返回语言元数据，包括 `language` 和 `is_code` 标志。"""
    if not text:
        return {"language": default, "is_code": False}

    # 首先检查是否为代码
    if is_probable_code(text):
        logger.debug("language.detect: 检测到代码块")
        return {"language": "code", "is_code": True}

    language = None

    # 如果配置允许，使用 Lingua 进行检测
    if _should_use_lingua(config):
        detector = _get_lingua_detector()
        if detector is not None:
            try:
                detected = detector.detect_language_of(text)
            except Exception:
                logger.warning(
                    "language.detect: lingua 失败；回退到启发式方法",
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )
                detected = None

            if _Language and detected == _Language.CHINESE:
                language = "zh"
            elif _Language and detected == _Language.JAPANESE:
                language = "ja"
            elif _Language and detected == _Language.ENGLISH:
                language = "en"

    # 如果 Lingua 未能检测出语言，则使用启发式方法
    if language is None:
        language = _heuristic_language(text) or default

    return {"language": language, "is_code": False}


def detect_language(
    text: str,
    config: Mapping[str, Any] | None = None,
    default: str = "en",
) -> str:
    """检测语言，规范化为 en/zh/ja/code，并提供优雅的回退。"""
    result = detect_language_meta(text, config=config, default=default)
    return result["language"]


def _heuristic_language(text: str) -> str:
    """基于字符集的简单启发式语言检测。"""
    if not text:
        return "en"

    if _HIRAGANA_RE.search(text) or _KATAKANA_RE.search(text):
        return "ja"
    if _CJK_RE.search(text):
        return "zh"
    return "en"


__all__ = [
    "LANGUAGE_ALIAS_MAP",
    "normalize_language_value",
    "is_probable_code",
    "is_cjk_text",
    "detect_language_meta",
    "detect_language",
    "lingua_status",
]