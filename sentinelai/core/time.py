"""Timezone-aware time helpers (``datetime.utcnow`` is deprecated and naive)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(value: Any, default: Optional[datetime] = None) -> Optional[datetime]:
    """Coerce a datetime / ISO-8601 string into an aware UTC datetime.

    Naive values are assumed to already be UTC. Unparseable input returns
    ``default`` so callers never crash on a bad timestamp.
    """
    if value is None:
        return default
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return default
    if not isinstance(value, datetime):
        return default
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
