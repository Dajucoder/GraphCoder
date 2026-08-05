"""Event bus for the runtime (thread-safe emit to an asyncio listener)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

Listener = Callable[[str, dict[str, Any]], None]


class EventBus:
    """Routes runtime events (Codex item/turn/thread primitives) to a listener."""

    def __init__(self, listener: Listener | None = None, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self.listener = listener
        self.loop = loop

    def set_listener(self, listener: Listener | None, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self.listener = listener
        if loop is not None:
            self.loop = loop

    def emit(self, event_type: str, **payload: Any) -> None:
        """Thread-safe emit; marshals to the asyncio loop when needed."""
        payload.setdefault("ts", time.time())
        if self.listener is None:
            return
        try:
            if self.loop is not None and self.loop.is_running():
                if asyncio.get_running_loop() is self.loop:
                    self.listener(event_type, payload)
                else:
                    self.loop.call_soon_threadsafe(self.listener, event_type, payload)
            else:
                self.listener(event_type, payload)
        except Exception:
            import logging

            logging.getLogger(__name__).debug("event listener error", exc_info=True)
