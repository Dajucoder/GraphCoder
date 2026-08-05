"""Event helpers shared by runners and the server."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

Emitter = Callable[[str, dict[str, Any]], None]


def make_event(kind: str, **payload: Any) -> dict[str, Any]:
    return {"type": kind, "ts": time.time(), **payload}


class EventSink:
    """Collect events so the graph can append them to state for streaming."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, kind: str, **payload: Any) -> None:
        self.events.append(make_event(kind, **payload))
