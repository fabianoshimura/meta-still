"""Running the pipeline off the UI thread.

Tkinter is not thread-safe: touching a widget from a worker thread produces
crashes that look random and appear weeks later. So the worker only ever puts
events on a queue, and the window drains that queue from its own thread.

Nothing here imports tkinter, which is what makes it testable.
"""

from __future__ import annotations

import queue
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Log:
    text: str


@dataclass(frozen=True)
class Step:
    done: int
    total: int


@dataclass(frozen=True)
class Finished:
    value: Any = None
    error: str | None = None


Report = Callable[[object], None]
Work = Callable[[Report, Callable[[], bool]], Any]


class BackgroundJob:
    """One unit of work on a worker thread, reporting through a queue."""

    def __init__(self) -> None:
        self._events: queue.Queue[object] = queue.Queue()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, work: Work) -> None:
        if self.running:
            raise RuntimeError("a job is already running")
        self._cancel.clear()
        self._thread = threading.Thread(target=self._run, args=(work,), daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def drain(self) -> list[object]:
        """Every event posted since the last call. Never blocks."""
        events: list[object] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def _run(self, work: Work) -> None:
        try:
            value = work(self._events.put, self._cancel.is_set)
        except Exception as exc:  # a crash must reach the window, not vanish
            self._events.put(Log(traceback.format_exc()))
            self._events.put(Finished(error=str(exc)))
        else:
            self._events.put(Finished(value=value))
