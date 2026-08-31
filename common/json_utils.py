"""JSON encoding helpers for exact project data."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from fractions import Fraction
import json
from typing import Any


def json_default(value: Any) -> Any:
    """Convert supported non-JSON values to JSON-compatible objects."""
    if isinstance(value, Fraction):
        return {
            "numerator": value.numerator,
            "denominator": value.denominator,
        }
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def json_text(
    value: Any,
    *,
    canonical: bool = False,
    indent: int | None = None,
) -> str:
    """Serialize project data, preserving fractions exactly."""
    return json.dumps(
        value,
        default=json_default,
        ensure_ascii=False,
        sort_keys=canonical,
        separators=(",", ":") if canonical else None,
        indent=indent,
    )


def optional_json_text(value: Any) -> str | None:
    """Serialize a value unless it is ``None``."""
    return None if value is None else json_text(value)
