"""Domain error types shared across the runtime.

core/ is the bottom layer: nothing here may know about HTTP. Services raise
these; routers own the translation to a web response. That indirection is the
point -- it is what makes a service callable from somewhere other than its
own route handler.

Each class carries its message and nothing else. The router maps the *type*
to a status code and passes ``str(exc)`` through as the detail, so the exact
strings the API returns today survive the refactor unchanged -- including
their inconsistent casing ("project not found" but "File not found"). Do not
teach these classes to build their own messages; that would quietly rewrite
a public API string.

Mapping owned by the routers, measured from api.py on 2026-08-15:

    Unauthenticated     -> 401
    NotOwned            -> 403
    NotFound            -> 404
    InvalidRequest      -> 400
    ReindexInProgress   -> 409
    OutOfRange          -> 422
    VaultUnavailable    -> 503
    QueueFull           -> 503
    UpstreamFailure     -> 502
"""

from __future__ import annotations


class SentientError(Exception):
    """Base for every domain error. Routers catch this to build a 500 fallback."""


class Unauthenticated(SentientError):
    """No credential, or a credential the runtime could not verify. -> 401

    Covers both "authentication required" and the Bearer-scheme complaint.
    """


class NotOwned(SentientError):
    """The resource exists but does not belong to the calling key. -> 403

    Deliberately NOT a subclass of NotFound. The completions route answers
    403 "project not found for this key" (confirming existence) while the
    management routes answer 404 "project not found" (masking it). That
    inconsistency is real, has a security dimension, and is out of scope for
    R9 -- but the type system has to be able to express both, so these two
    must stay disjoint.
    """


class NotFound(SentientError):
    """A named resource does not exist, or is hidden from this caller. -> 404

    Raised for projects, threads and files alike; the caller supplies the
    exact wording.
    """


class InvalidRequest(SentientError):
    """The request is well-formed but semantically wrong. -> 400

    e.g. "thread_id requires project_id", an unsupported upload type, a
    missing filename, an unknown provider.
    """


class OutOfRange(SentientError):
    """A parameter parsed but fell outside its permitted bounds. -> 422

    Distinct from InvalidRequest because FastAPI already answers 422 for
    validation failures, and the one hand-rolled bound check
    ("limit must be between 1 and 200") matches that convention rather than
    the 400 used for semantic errors.
    """


class ReindexInProgress(SentientError):
    """The project's index is being rebuilt; retrieval is unavailable. -> 409"""


class QueueFull(SentientError):
    """The in-process ingest queue has no capacity for this job. -> 503"""


class VaultUnavailable(SentientError):
    """The credential vault is unconfigured or its key cannot be used. -> 503"""


class UpstreamFailure(SentientError):
    """A third-party service the runtime proxies to failed. -> 502

    Today only the STT proxy raises this.
    """
