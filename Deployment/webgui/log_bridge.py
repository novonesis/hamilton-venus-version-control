"""Thread-safe log buffer and Loguru sink factory for the pywebview GUI.

Replaces ``gui/shared.py``'s tkinter-dependent ``make_gui_sink()`` with a
polling-friendly ring buffer that JavaScript fetches on a timer.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class LogBuffer:
    """Per-tab ring buffer holding the most recent *maxlen* log lines.

    Thread-safe: multiple writer threads (Loguru sinks) and one reader
    (the JS polling call) can operate concurrently.

    Args:
        maxlen: Maximum number of lines retained.
    """

    def __init__(self, maxlen: int = 2000) -> None:
        self._lines: deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._cursor: int = 0  # monotonically increasing write counter

    def append(self, line: str) -> None:
        """Append a single log line."""
        with self._lock:
            self._lines.append(line)
            self._cursor += 1

    def read_new(self, last_seen: int) -> tuple[list[str], int]:
        """Return lines added since *last_seen* and the new cursor.

        Args:
            last_seen: The cursor value from the previous call.

        Returns:
            A ``(new_lines, cursor)`` tuple.
        """
        with self._lock:
            total = self._cursor
            available = len(self._lines)
            unseen = total - last_seen
            if unseen <= 0:
                return [], total
            # Only return lines that are still in the deque
            count = min(unseen, available)
            new_lines = list(self._lines)[-count:]
            return new_lines, total

    def clear(self) -> None:
        """Discard all buffered lines and reset the cursor."""
        with self._lock:
            self._lines.clear()
            self._cursor = 0


def make_log_sink(buffer: LogBuffer) -> Callable[[str], None]:
    """Create a Loguru-compatible sink that appends to *buffer*.

    Args:
        buffer: The :class:`LogBuffer` to write into.

    Returns:
        A callable suitable for ``logger.add(sink=...)``.
    """

    def sink(message: str) -> None:
        buffer.append(str(message).rstrip("\n"))

    return sink


def make_tab_filter(tab_name: str) -> Callable[[dict[str, Any]], bool]:
    """Create a Loguru filter accepting only records bound to *tab_name*.

    Identical to ``gui/shared.py``'s version but kept here so ``webgui``
    has no dependency on the old ``gui`` package.
    """

    def tab_filter(record: dict[str, Any]) -> bool:
        return record["extra"].get("tab") == tab_name

    return tab_filter
