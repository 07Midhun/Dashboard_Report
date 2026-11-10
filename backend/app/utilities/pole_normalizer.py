import math
import re
from typing import Any


_WHITESPACE_RE = re.compile(r"\s+")


def cell_to_display_str(value: Any) -> str:
    """
    Convert an Excel cell value to a clean displayed string without losing
    meaningful formatting or creating '.0' artifacts on whole numbers.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return format(value, "g")
    return str(value).strip()


def normalize_pole_key(value: Any) -> str | None:
    """
    Return canonical uppercase trimmed key for comparison, or None if blank.
    """
    display = cell_to_display_str(value)
    if not display:
        return None
    collapsed = _WHITESPACE_RE.sub(" ", display).strip().upper()
    return collapsed or None


def normalize_header_name(value: Any) -> str:
    """Normalize column header names for flexible matching and signature hashing."""
    display = cell_to_display_str(value)
    if not display:
        return ""
    return _WHITESPACE_RE.sub(" ", display).strip().lower()

