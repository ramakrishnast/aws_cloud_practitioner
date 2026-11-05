"""Single source of "now" so timers can be tested deterministically."""
from __future__ import annotations

from datetime import datetime, timezone

_override: datetime | None = None


def utcnow() -> datetime:
    """Naive UTC datetime (SQLite stores naive datetimes)."""
    if _override is not None:
        return _override
    return datetime.now(timezone.utc).replace(tzinfo=None)


def set_now(value: datetime | None) -> None:
    """Freeze the clock (tests only). Pass None to unfreeze."""
    global _override
    _override = value
