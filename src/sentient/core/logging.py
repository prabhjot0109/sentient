"""Process logging: one configuration point, one request-scoped field bag.

`core/` has no I/O and no framework, and a logger is neither — it is a sink the
api layer configures at startup and every layer writes to.

The ContextVar is what makes a log line useful. A message saying "retrieved 0
chunks" is noise; the same line carrying user_key and project_id is a diagnosis.
Never bind a credential into it: `user_key` is already an opaque hash, which is
exactly why it is the field to use.

A ContextVar rather than a thread-local, because one event-loop thread serves
every tenant. Each asyncio Task gets a copy of the context when it is created,
so a bind inside one request is invisible to concurrent requests, and the task
`defer()` spawns inherits the fields of the turn that scheduled it.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any

# None, not {}: a mutable ContextVar default is one shared dict across every
# context, so a single in-place mutation anywhere would make one request's tenant
# visible to the next. Making the default immutable removes the whole class of
# bug rather than relying on every writer to copy first.
_FIELDS: ContextVar[dict[str, str] | None] = ContextVar("sentient_log_fields", default=None)

# Everything the stdlib already puts on a record, so the formatters below can
# tell "a field someone bound" from "a field logging owns". Derived from a real
# record rather than hand-listed: the set gains members across Python versions
# (3.12 added taskName), and a stale hand-written copy would start leaking
# internals into every JSON line.
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


def bind(**fields: Any) -> None:
    """Merge fields into the current context. A None value removes a field.

    Copies before writing, so a field bag captured by an already-running task is
    never mutated underneath it.
    """
    current = dict(_FIELDS.get() or {})
    for key, value in fields.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = str(value)
    _FIELDS.set(current)


def current_fields() -> dict[str, str]:
    return dict(_FIELDS.get() or {})


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in (_FIELDS.get() or {}).items():
            if key not in _RESERVED:
                setattr(record, key, value)
        return True


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED and not key.startswith("_")
    }


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_extras(record),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extras = " ".join(f"{key}={value}" for key, value in _extras(record).items())
        base = f"{record.levelname:<7} {record.name} {record.getMessage()}"
        line = f"{base}  {extras}" if extras else base
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


def configure_logging(settings: Any) -> None:
    """Idempotent: safe to call from every lifespan start, including in tests.

    Handlers are replaced, not appended. The test suite builds many app
    instances, and appending would multiply every line by the instance count.
    """
    root = logging.getLogger("sentient")
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.addFilter(_ContextFilter())
    handler.setFormatter(
        _JsonFormatter() if getattr(settings, "log_format", "text") == "json" else _TextFormatter()
    )
    root.addHandler(handler)
    root.setLevel(getattr(logging, getattr(settings, "log_level", "INFO"), logging.INFO))
    # The record stops here. Propagating would hand it to the root logger, whose
    # handlers know nothing about the bound fields and would print it a second
    # time under whatever format uvicorn configured.
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
