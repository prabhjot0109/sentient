"""Redaction for the one path that leaves this process for a third party.

The game route carries the API key in the URL **path** --
`/v1/{api_key}/chat/completions` and `/v1/{api_key}/{project_id}/chat/completions`
-- because Mantella has no header field to put it in. `SECURITY.md` records that
as an accepted posture *for logs the operator controls*. An error tracker is not
one of those: with default settings it collects the full request URL on every
event and stores other people's credentials in a SaaS.

Pure string work, and in `core/` for two reasons. It is the only layer
`api/app.py` may import from without inverting the dependency direction, and it
is the only place these rules can be unit-tested with `sentry-sdk` absent --
which is how a fresh clone is installed, since the package lives in an optional
group.
"""

from __future__ import annotations

import re
from typing import Any

from sentient.core.config import RAGSettings

REDACTED = "[redacted]"

# Headers that carry a credential. Compared lower-case because a header name is
# case-insensitive on the wire and the SDK preserves whatever the client sent.
_CREDENTIAL_HEADERS = frozenset({"x-api-key", "authorization", "cookie"})

# The credential is the segment straight after `/v1/`, and only on the two routes
# that end in `/chat/completions` with something in between. The rule is
# positional rather than prefix-matched on purpose: the same segment accepts a
# raw provider key (`AIza…`, `gsk_…`) as readily as a `sk-sent-…` product key,
# and the provider key is the more expensive one to leak.
#
# `/v1/chat/completions` -- the keyless route, which carries its key in a header
# -- cannot match, because the optional middle group would have to swallow
# `/completions` and then leave nothing for the literal tail.
_KEY_IN_PATH = re.compile(
    r"^(?P<head>.*?/v1/)(?P<key>[^/]+)(?P<tail>(?:/[^/]+)?/chat/completions)$"
)


def scrub_url(url: str) -> str:
    """Replace the credential segment of a game-route URL, keeping everything else.

    Keeping the rest is not politeness: an event whose URL is entirely redacted
    cannot be told apart from any other event, which defeats the reason for
    sending it. The project id survives deliberately -- it is an identifier, not
    a secret, and it is what makes a report actionable.
    """
    path, sep, query = url.partition("?")
    match = _KEY_IN_PATH.match(path)
    if match is None:
        return url
    return f"{match['head']}{REDACTED}{match['tail']}{sep}{query}"


def scrub_event(event: dict[str, Any], hint: Any) -> dict[str, Any]:
    """Sentry's `before_send`: the last point at which an event is still ours.

    Every branch below is a guard rather than an assumption about the event
    shape, because the cost of being wrong is asymmetric. `before_send` runs on
    *every* event, including ones with no HTTP context at all -- a lifespan
    failure, a queue worker dying -- and an exception raised here does not
    surface anywhere: the SDK drops the event, taking the original exception
    with it. Silence is the failure mode this codebase keeps designing against.
    """
    request = event.get("request")
    if not isinstance(request, dict):
        return event

    url = request.get("url")
    if isinstance(url, str):
        request["url"] = scrub_url(url)

    headers = request.get("headers")
    if isinstance(headers, dict):
        for name in list(headers):
            if str(name).lower() in _CREDENTIAL_HEADERS:
                headers[name] = REDACTED

    return event


def sentry_init_options(settings: RAGSettings) -> dict[str, Any] | None:
    """The full `sentry_sdk.init(**…)` keyword set, or None when it is off.

    None rather than a dict carrying an empty DSN: the SDK treats an empty DSN
    as "collect but never send", which buffers events in a process that has no
    intention of reporting them. Off should mean off.
    """
    if not settings.sentry_dsn:
        return None

    return {
        "dsn": settings.sentry_dsn,
        "environment": settings.sentry_environment,
        # Traces are H8's job, via Langfuse, which also carries token counts and
        # cost. Paying a second vendor for the same spans is waste, so this
        # defaults to 0.0 and stays a knob for the case where it is not.
        "traces_sample_rate": settings.sentry_traces_sample_rate,
        # Off explicitly, not by relying on the SDK default: with it on, the
        # integration attaches request bodies, cookies and the client IP.
        "send_default_pii": False,
        "before_send": scrub_event,
    }
