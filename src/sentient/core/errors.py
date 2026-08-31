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
    QuotaExceeded       -> 429
    OutOfRange          -> 422
    VaultUnavailable    -> 503
    QueueFull           -> 503
    UpstreamFailure     -> 502

Each class also carries a stable ``code``. A status code alone is not always
enough for a client to know what happened: 409 is answered BOTH by the reindex
guard and by the API-key cap, and those two lead to opposite next actions ("wait,
it finishes on its own" against "revoke a key you are not using"). The console
mapped every 409 to the reindex sentence and so told a user at the key cap that
their lore was re-embedding. ``code`` is what lets a caller tell them apart; it
is a machine name, not HTTP, which is why it lives here rather than in api/.
"""

from __future__ import annotations


class SentientError(Exception):
    """Base for every domain error. Routers catch this to build a 500 fallback.

    ``code`` is part of the public API surface once a client branches on it, so
    treat these strings as you would a status code: add freely, never rename.
    """

    code: str = "error"


class Unauthenticated(SentientError):
    """No credential, or a credential the runtime could not verify. -> 401

    Covers both "authentication required" and the Bearer-scheme complaint.
    """

    code = "unauthenticated"


class NotOwned(SentientError):
    """The resource exists but does not belong to the calling key. -> 403

    Deliberately NOT a subclass of NotFound. The completions route answers
    403 "project not found for this key" (confirming existence) while the
    management routes answer 404 "project not found" (masking it). That
    inconsistency is real, has a security dimension, and is out of scope for
    R9 -- but the type system has to be able to express both, so these two
    must stay disjoint.
    """

    code = "not_owned"


class NotFound(SentientError):
    """A named resource does not exist, or is hidden from this caller. -> 404

    Raised for projects, threads and files alike; the caller supplies the
    exact wording.
    """

    code = "not_found"


class InvalidRequest(SentientError):
    """The request is well-formed but semantically wrong. -> 400

    e.g. "thread_id requires project_id", an unsupported upload type, a
    missing filename, an unknown provider.
    """

    code = "invalid_request"


class OutOfRange(SentientError):
    """A parameter parsed but fell outside its permitted bounds. -> 422

    Distinct from InvalidRequest because FastAPI already answers 422 for
    validation failures, and the one hand-rolled bound check
    ("limit must be between 1 and 200") matches that convention rather than
    the 400 used for semantic errors.
    """

    code = "out_of_range"


class ReindexInProgress(SentientError):
    """The project's index is being rebuilt; retrieval is unavailable. -> 409"""

    code = "reindex_in_progress"


class QuotaExceeded(SentientError):
    """The caller has spent their allowance for the current window. -> 429

    Deliberately distinct from the rate limiter's 429, which is about
    *frequency* and is answered in middleware before a route runs. This one is
    about *spend* and can only be known after identity is resolved, so it is a
    domain error like every other. Both share a status code because a client's
    correct reaction is the same: stop, and come back later.
    """

    code = "quota_exceeded"


class QueueFull(SentientError):
    """The in-process ingest queue has no capacity for this job. -> 503"""

    code = "queue_full"


class VaultUnavailable(SentientError):
    """The credential vault is unconfigured or its key cannot be used. -> 503"""

    code = "vault_unavailable"


class UpstreamFailure(SentientError):
    """A third-party service the runtime proxies to failed. -> 502

    Today only the STT proxy raises this.
    """

    code = "upstream_failure"


class SourceFilesMissing(SentientError):
    """A rebuild cannot run because the uploaded files it reads are gone.

    Deliberately has NO status code, unlike everything above it. It is raised
    inside a background queue worker, long after the response that queued the job
    was sent, so there is no request left to answer and inventing a status would
    imply a caller who could see it. The user learns about it from the document
    rows the job marks `failed`.

    Reachable whenever `data/` is not durable: the `documents` rows and the vectors
    both survive a restart while the uploaded files do not, and `run_reindex_job`
    re-reads those files to rebuild.
    """

    code = "source_files_missing"
