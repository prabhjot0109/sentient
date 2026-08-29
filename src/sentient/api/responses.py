"""Shared response details the routers agree on.

Small on purpose. It exists because the header name below has to be spelled
identically by every router that emits it and by the CORS allow-list that makes
it readable from a browser -- four places, and a typo in any one of them is
invisible until a client silently falls back to its default.
"""

from __future__ import annotations

from sentient.core.errors import SentientError

#: Carries `SentientError.code` beside the status. Additive: the JSON body is
#: unchanged, so a client that does not read this header sees exactly what it saw
#: before. It MUST be named in the CORS `expose_headers` list -- a response header
#: a browser has not been told to expose is not merely hidden from JavaScript, it
#: is unreadable, and the failure looks like the server never sent it.
ERROR_CODE_HEADER = "X-Error-Code"


def error_headers(error: SentientError | str) -> dict[str, str]:
    """The headers to attach to an `HTTPException` raised from `error`.

    Accepts a bare string for the routes that raise an HTTP error directly
    without a domain type behind it -- the API-key cap in `routers/keys.py` is
    the only one today, and it is precisely the case that needed a code.
    """
    return {ERROR_CODE_HEADER: error if isinstance(error, str) else error.code}
