"""Request-local progress signals, independent of HTTP and conversation history."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

ProgressPhase = Literal[
    "starting", "understanding", "searching", "planning", "generating",
    "reviewing", "finalizing", "completed", "failed", "cancelled",
]

_observer: ContextVar[Callable[[ProgressPhase], None] | None] = ContextVar(
    "chat_progress_observer", default=None,
)


@contextmanager
def observe_progress(
    callback: Callable[[ProgressPhase], None],
) -> Iterator[None]:
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def report_progress(phase: ProgressPhase) -> None:
    observer = _observer.get()
    if observer is not None:
        observer(phase)
