"""
Shared low-level helpers. Importable by both loader.py (Teammate 1) and
cleaner.py (Teammate 2) without circular dependencies.

Both teammates can extend this file but coordinate via chat first.
"""

from __future__ import annotations


def normalize_id(raw: object) -> str:
    """Lowercase + strip. Handles None safely.

    >>> normalize_id("REP_001")
    'rep_001'
    >>> normalize_id(" rep_004 ")
    'rep_004'
    >>> normalize_id(None)
    ''
    """
    if raw is None:
        return ""
    return str(raw).strip().lower()


def safe_float(value: object, default: float | None = None) -> float | None:
    """
    Best-effort float coercion. Returns None on failure (so callers can
    decide whether to drop, default, or impute).

    >>> safe_float("70")
    70.0
    >>> safe_float(None) is None
    True
    >>> safe_float("high") is None
    True
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default
