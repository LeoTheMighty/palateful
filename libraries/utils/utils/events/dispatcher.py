"""In-process synchronous event dispatcher.

Handlers register by event name. ``dispatch`` invokes them in registration
order. A failing handler logs at ERROR and does NOT prevent subsequent
handlers from running, so one broken subscriber can't poison the others.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_HANDLERS: dict[str, list[Callable[[Any], None]]] = {}


def register(event_name: str, handler: Callable[[Any], None]) -> None:
    """Register a handler for a named event.

    Handlers are invoked in registration order. Re-registering the same
    handler is idempotent (the handler is NOT added twice).
    """
    handlers = _HANDLERS.setdefault(event_name, [])
    if handler not in handlers:
        handlers.append(handler)


def unregister(event_name: str, handler: Callable[[Any], None]) -> None:
    """Remove a handler. A no-op if the handler isn't registered."""
    handlers = _HANDLERS.get(event_name)
    if not handlers:
        return
    with contextlib.suppress(ValueError):
        handlers.remove(handler)


def dispatch(event_name: str, payload: Any) -> None:
    """Dispatch an event synchronously to every registered handler.

    Exceptions raised by a handler are caught and logged; the caller never
    sees them. Unregistered event names are a silent no-op.
    """
    handlers = _HANDLERS.get(event_name)
    if not handlers:
        return
    for handler in list(handlers):
        try:
            handler(payload)
        except Exception:
            logger.exception(
                "event handler %r failed for event %s",
                handler,
                event_name,
            )


def _reset_for_tests() -> None:
    """Test-only helper to clear registered handlers between cases."""
    _HANDLERS.clear()
