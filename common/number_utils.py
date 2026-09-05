import re
from fractions import Fraction
from typing import Any


EXACT_RATIONAL_TEXT_RE = re.compile(r"\+?\d+(?:/\d+)?\Z")


def as_nonnegative_fraction(value: Any, field_name: str) -> Fraction:
    """Return an exact nonnegative rational supplied without a float."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(
            f"{field_name} must be an exact nonnegative rational"
        )

    if isinstance(value, str):
        compact = value.strip()
        if EXACT_RATIONAL_TEXT_RE.fullmatch(compact) is None:
            raise ValueError(
                f"{field_name} must be an exact nonnegative rational"
            )
        value = compact

    try:
        result = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        try:
            result = Fraction(str(value))
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(
                f"{field_name} must be an exact nonnegative rational"
            ) from exc

    if result < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return result


def as_positive_fraction(value: Any, field_name: str) -> Fraction:
    """Return an exact positive rational supplied without a float."""
    result = as_nonnegative_fraction(value, field_name)
    if result == 0:
        raise ValueError(f"{field_name} must be positive")
    return result


def as_integer(value: Any, field_name: str) -> int:
    """Return an exact integer without accepting booleans or floats."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{field_name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if result != value:
        raise ValueError(f"{field_name} must be an integer")
    return result


def as_nonnegative_int(value: Any, field_name: str) -> int:
    """Return an exact non-negative integer without accepting booleans or floats."""
    result = as_integer(value, field_name)
    if result < 0:
        raise ValueError(f"{field_name} must be a nonnegative integer")
    return result
