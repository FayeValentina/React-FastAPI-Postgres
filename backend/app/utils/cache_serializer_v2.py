"""Utilities for serializing Pydantic models for Redis caching."""

from __future__ import annotations

from typing import Dict, Type, TypeVar

import cbor2
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)

# Registry to map model class names to actual Pydantic models.
MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}


def register_model(model: Type[ModelT]) -> Type[ModelT]:
    """Register a Pydantic model class for cache serialization."""
    MODEL_REGISTRY[model.__name__] = model
    return model


class CacheSerializerV2:
    """Serialize and deserialize Pydantic models using CBOR."""

    @staticmethod
    def serialize(obj: BaseModel) -> bytes:
        payload = {
            "model": obj.__class__.__name__,
            "data": obj.model_dump(mode="json"),
        }
        return cbor2.dumps(payload)

    @staticmethod
    def deserialize(raw: bytes) -> BaseModel:
        payload = cbor2.loads(raw)
        model_name = payload["model"]
        data = payload["data"]
        model_cls = MODEL_REGISTRY.get(model_name)
        if model_cls is None:
            raise ValueError(f"Model {model_name} is not registered for caching")
        return model_cls.model_validate(data)
