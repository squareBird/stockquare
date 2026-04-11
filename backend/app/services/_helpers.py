"""Shared private helpers for service layer modules."""

from __future__ import annotations


def to_int(value: str | None) -> int:
    """Coerce a KIS response string into an integer, defaulting to 0."""
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def to_float(value: str | None) -> float:
    """Coerce a KIS response string into a float, defaulting to 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
