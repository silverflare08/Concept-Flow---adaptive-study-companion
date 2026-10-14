"""Cooperative cancellation between model calls and before persistence."""
from contextvars import ContextVar
from threading import Event
from functools import wraps

current_cancel: ContextVar[Event | None] = ContextVar("generation_cancel", default=None)
requests: dict[str, Event] = {}

class GenerationStopped(ValueError):
    pass

def check_cancelled() -> None:
    event = current_cancel.get()
    if event is not None and event.is_set():
        raise GenerationStopped("Stopped by you.")

def cancellable(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        check_cancelled()
        result = function(*args, **kwargs)
        check_cancelled()
        return result
    return wrapped
