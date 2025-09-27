from __future__ import annotations

from typing import Any, Callable, Mapping, TypeVar

T = TypeVar("T")

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def ensure_bool(value: Any, default: bool) -> bool:
    """Best-effort boolean parsing with fallback to a default."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUTHY:
            return True
        if lowered in _FALSY:
            return False
        return default
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def ensure_int(
    value: Any,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Parse an integer value clamped within optional boundaries."""

    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = default

    if minimum is not None and candidate < minimum:
        candidate = minimum
    if maximum is not None and candidate > maximum:
        candidate = maximum
    return candidate


def ensure_float(
    value: Any,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Parse a floating point value with optional min/max constraints."""

    try:
        candidate = float(value)
    except (TypeError, ValueError):
        candidate = default

    if minimum is not None and candidate < minimum:
        candidate = minimum
    if maximum is not None and candidate > maximum:
        candidate = maximum
    return candidate


def coerce_bool(
    config: Mapping[str, Any] | None,
    key: str,
    default: bool,
) -> bool:
    source = default if config is None else config.get(key, default)
    return ensure_bool(source, default)


def coerce_int(
    config: Mapping[str, Any] | None,
    key: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    source = default if config is None else config.get(key, default)
    return ensure_int(source, default, minimum=minimum, maximum=maximum)


def coerce_float(
    config: Mapping[str, Any] | None,
    key: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    source = default if config is None else config.get(key, default)
    return ensure_float(source, default, minimum=minimum, maximum=maximum)


def coerce_value(
    config: Mapping[str, Any] | None,
    key: str,
    default: T,
    caster: Callable[[Any], T],
) -> T:
    source = default if config is None else config.get(key, default)
    try:
        return caster(source)
    except (TypeError, ValueError):
        return caster(default)


__all__ = [
    "coerce_bool",
    "coerce_float",
    "coerce_int",
    "coerce_value",
    "ensure_bool",
    "ensure_float",
    "ensure_int",
]
