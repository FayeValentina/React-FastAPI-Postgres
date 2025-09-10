"""
支持 Pydantic 和 SQLAlchemy 的缓存序列化器（使用全限定类名）。
"""

import json
import logging
from typing import Any, Dict, Type, Union

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeMeta # 假设使用现代的SQLAlchemy
from sqlalchemy.inspection import inspect

logger = logging.getLogger(__name__)

# 为 Pydantic 模型和 SQLAlchemy 模型分别创建注册表（使用全限定名）
PYDANTIC_MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}
SQLALCHEMY_MODEL_REGISTRY: Dict[str, Type[DeclarativeMeta]] = {}

# --- 注册器 ---

def _fqn(cls: Type[Any]) -> str:
    """获取类的全限定名（module + name）。"""
    return f"{cls.__module__}.{cls.__name__}"


def register_pydantic_model(model_class: Type[BaseModel]):
    """注册 Pydantic 模型到序列化器（使用全限定名作为键）"""
    PYDANTIC_MODEL_REGISTRY[_fqn(model_class)] = model_class
    return model_class

def register_sqlalchemy_model(model_class: Type[DeclarativeMeta]):
    """注册 SQLAlchemy 模型到序列化器（使用全限定名作为键）"""
    # 确保传入的是一个 SQLAlchemy 模型类
    if not hasattr(model_class, '__mapper__'):
        raise TypeError(f"{model_class.__name__} 不是一个有效的 SQLAlchemy 模型。")
    SQLALCHEMY_MODEL_REGISTRY[_fqn(model_class)] = model_class
    return model_class


# --- 序列化器核心类 ---

class CacheSerializer:
    """
    基于 Pydantic 和 SQLAlchemy 的缓存序列化器。
    在序列化后的数据中加入了 `__type__` 字段来区分模型类型。
    """
    
    @staticmethod
    def _sqlalchemy_to_dict(obj: Any) -> Dict[str, Any]:
        """将 SQLAlchemy 模型实例转换为字典，只包含列属性。"""
        # 使用 inspect 来安全地获取列属性，避免加载关系等额外数据
        mapper = inspect(obj).mapper
        return {c.key: getattr(obj, c.key) for c in mapper.column_attrs}

    @staticmethod
    def serialize(obj: Any) -> bytes:
        """
        序列化 Pydantic 或 SQLAlchemy 模型为字节流。
        """
        model_name = _fqn(obj.__class__)
        payload = {"__model__": model_name}

        try:
            # 判断对象类型并选择相应的序列化方法
            if isinstance(obj, BaseModel):
                payload["__type__"] = "pydantic"
                payload["__data__"] = obj.model_dump(mode='json')
            # 检查是否有 _sa_instance_state 属性是判断 SQLAlchemy 实例的可靠方法
            elif hasattr(obj, '_sa_instance_state'):
                payload["__type__"] = "sqlalchemy"
                payload["__data__"] = CacheSerializer._sqlalchemy_to_dict(obj)
            elif isinstance(obj, dict):
                payload["__type__"] = "dict"
                payload["__data__"] = obj
            elif isinstance(obj, (list, tuple)):
                payload["__type__"] = "list" if isinstance(obj, list) else "tuple"
                # 对列表/元组元素进行逐项序列化：
                # - Pydantic/SQLAlchemy 元素包装为 {__type__, __model__, __data__}
                # - 其他元素保持原样（由 json.dumps(default=str) 处理）
                serialized_items = []
                for item in obj:
                    if isinstance(item, BaseModel):
                        serialized_items.append({
                            "__type__": "pydantic",
                            "__model__": _fqn(item.__class__),
                            "__data__": item.model_dump(mode='json'),
                        })
                    elif hasattr(item, '_sa_instance_state'):
                        serialized_items.append({
                            "__type__": "sqlalchemy",
                            "__model__": _fqn(item.__class__),
                            "__data__": CacheSerializer._sqlalchemy_to_dict(item),
                        })
                    else:
                        serialized_items.append(item)
                payload["__data__"] = serialized_items
            elif isinstance(obj, (str, int, float, bool)) or obj is None:
                payload["__type__"] = "primitive"
                payload["__data__"] = obj
            else:
                raise TypeError(f"不支持的序列化对象类型: {type(obj)}")

            # 序列化为JSON字节流
            # 使用 default=str 来处理日期、Decimal 等非原生JSON类型
            return json.dumps(payload, default=str).encode('utf-8')

        except Exception as e:
            logger.error(f"序列化对象 {model_name} 失败: {e}")
            raise

    @staticmethod
    def deserialize(data: Union[str, bytes]) -> Union[BaseModel, Any]:
        """
        反序列化字节流为 Pydantic 或 SQLAlchemy 模型实例。
        """
        try:
            # 解码并解析JSON（支持 bytes 或 str）
            if isinstance(data, (bytes, bytearray)):
                payload = json.loads(data.decode('utf-8'))
            elif isinstance(data, str):
                payload = json.loads(data)
            else:
                raise TypeError("deserialize 仅支持 bytes 或 str 数据")
            
            model_name = payload.get("__model__")
            model_data = payload.get("__data__")
            model_type = payload.get("__type__", "pydantic") # 兼容旧版，默认pydantic

            if not model_name or model_data is None:
                raise ValueError("无效的缓存数据格式，缺少'__model__'或'__data__'字段")

            # 根据模型类型从不同的注册表查找并重建实例
            if model_type == "pydantic":
                model_class = PYDANTIC_MODEL_REGISTRY.get(model_name)
                if not model_class:
                    raise ValueError(f"未注册的 Pydantic 模型类: {model_name}")
                return model_class.model_validate(model_data)
            
            elif model_type == "sqlalchemy":
                model_class = SQLALCHEMY_MODEL_REGISTRY.get(model_name)
                if not model_class:
                    raise ValueError(f"未注册的 SQLAlchemy 模型类: {model_name}")
                # 直接用字典数据初始化模型实例
                return model_class(**model_data)
            
            elif model_type == "dict":
                return model_data
            
            elif model_type in ("list", "tuple"):
                # 逐项重建
                def _rebuild(item: Any) -> Any:
                    if isinstance(item, dict) and "__type__" in item and "__model__" in item and "__data__" in item:
                        itype = item.get("__type__")
                        iname = item.get("__model__")
                        idata = item.get("__data__")
                        if itype == "pydantic":
                            cls = PYDANTIC_MODEL_REGISTRY.get(iname)
                            if not cls:
                                raise ValueError(f"未注册的 Pydantic 模型类: {iname}")
                            return cls.model_validate(idata)
                        elif itype == "sqlalchemy":
                            cls = SQLALCHEMY_MODEL_REGISTRY.get(iname)
                            if not cls:
                                raise ValueError(f"未注册的 SQLAlchemy 模型类: {iname}")
                            return cls(**idata)
                    return item
                rebuilt = [_rebuild(it) for it in model_data]
                return rebuilt if model_type == "list" else tuple(rebuilt)
            
            elif model_type == "primitive":
                return model_data

            else:
                raise ValueError(f"不支持的模型类型: {model_type}")

        except Exception as e:
            logger.error(f"反序列化失败: {e}")
            raise
