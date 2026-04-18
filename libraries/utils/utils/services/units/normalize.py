"""Coerce a freeform unit string to its canonical `units.name` token.

The cache layout is two sets:

  * `_canonical_units`  — every value in `units.name`. Hit means the
    input is already canonical, return as-is.
  * `_alias_map`        — `unit_aliases.alias` → `unit_aliases.canonical_unit`.
    Hit means coerce to the canonical token.

Cache loads once per worker / FastAPI process. Lazy-init on first call
covers test environments that don't fire `worker_process_init`.
A miss still returns the (trimmed/lowercased/stripped-punctuation)
input — the caller persists *something* — and emits one audit row via
`log_unit_alias_miss` so the alias seed can grow over time.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from utils.logging.unit_logging import log_unit_alias_miss
from utils.models.unit import Unit
from utils.models.unit_alias import UnitAlias

logger = logging.getLogger(__name__)

# Strip these characters from the end of an input before lookup. Matches
# what the Flutter `_coerceUnit` does (riip-5 cursor lock-in).
_TRAILING_PUNCT_RE = re.compile(r"[.,;]+$")

# Module-level cache. Treat as immutable from outside; use
# `reload_unit_alias_cache()` to refresh.
_canonical_units: set[str] = set()
_alias_map: dict[str, str] = {}
_cache_lock = threading.Lock()
_cache_initialized = False


def _normalize_input(raw: str) -> str:
    """Lowercase + trim + strip trailing punctuation."""
    trimmed = raw.strip().lower()
    return _TRAILING_PUNCT_RE.sub("", trimmed)


def reload_unit_alias_cache(session: Session) -> None:
    """Reload both halves of the cache from the database.

    Wired to FastAPI startup + Celery `worker_process_init`; tests call
    it directly to reset between cases. Safe to call concurrently — the
    rebuild swaps in fresh dicts under a lock.
    """
    global _canonical_units, _alias_map, _cache_initialized

    canonical_rows = session.execute(select(Unit.name)).scalars().all()
    alias_rows = session.execute(
        select(UnitAlias.alias, UnitAlias.canonical_unit)
    ).all()

    new_canonical = {name for name in canonical_rows if name}
    new_aliases = {alias: canonical for alias, canonical in alias_rows}

    with _cache_lock:
        _canonical_units = new_canonical
        _alias_map = new_aliases
        _cache_initialized = True

    logger.info(
        "unit_alias cache loaded: %d canonical, %d aliases",
        len(new_canonical),
        len(new_aliases),
    )


def _ensure_cache(session: Session) -> None:
    """Lazy-init for environments that don't fire startup hooks."""
    if _cache_initialized:
        return
    with _cache_lock:
        if _cache_initialized:
            return
    reload_unit_alias_cache(session)


def normalize_unit_display(
    raw: str | None,
    session: Session,
    *,
    context: dict[str, Any] | None = None,
) -> str | None:
    """Coerce a freeform unit string to its canonical display token.

    Behavior:
      - `None` or empty input → returned unchanged.
      - Trim + lowercase + strip trailing `.,;`.
      - If the result is in `units.name` → return as-is (already canonical).
      - Else lookup in `unit_aliases` → return canonical on hit.
      - Miss → emit `log_unit_alias_miss(raw, context)` and return the
        normalized input (trimmed/lowercased/punctuation-stripped) so
        the caller still has a stable token to persist.

    `context` is merged into the audit row's metadata so we can grep for
    e.g. `{"path": "extract_recipe_task"}` later.
    """
    if raw is None:
        return None
    if not raw or not raw.strip():
        return raw

    _ensure_cache(session)

    normalized = _normalize_input(raw)
    if not normalized:
        return raw

    if normalized in _canonical_units:
        return normalized

    canonical = _alias_map.get(normalized)
    if canonical is not None:
        return canonical

    log_unit_alias_miss(raw, context=context)
    return normalized


def is_cache_initialized() -> bool:
    """Test helper — answer whether the cache has been loaded yet."""
    return _cache_initialized


def reset_unit_alias_cache_for_tests() -> None:
    """Test helper — clear cache state so the next call re-loads."""
    global _canonical_units, _alias_map, _cache_initialized
    with _cache_lock:
        _canonical_units = set()
        _alias_map = {}
        _cache_initialized = False
