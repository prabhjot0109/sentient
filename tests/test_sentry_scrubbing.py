"""The one thing about error tracking that can make the product less safe.

The game route carries the API key in the URL *path*
(`/v1/{api_key}/{project_id}/chat/completions`). An error tracker with default
settings collects the full path on every event, so switching Sentry on without a
scrubber would copy other people's credentials into a third-party SaaS.
`SECURITY.md` accepts the key-in-path for logs the operator owns; Sentry is not
one of those.

These tests drive `core/scrubbing.py` directly, which is why it is pure string
work in `core/` and not a closure inside `api/app.py`: the assertions run with
`sentry-sdk` absent, which is how a fresh clone is installed.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from sentient.core.config import load_rag_settings
from sentient.core.scrubbing import REDACTED, scrub_event, scrub_url, sentry_init_options

_UUID = "8d2f1a44-0000-4000-8000-1c2b3a4d5e6f"


def _settings(**overrides):
    return replace(load_rag_settings(), **overrides)


class SentryEnablementTests(unittest.TestCase):
    def test_disabled_by_default(self):
        """A fresh clone reports to nobody. `sentry_init_options` returns None
        rather than a dict with an empty DSN, so the caller cannot accidentally
        initialise a client that quietly buffers events forever."""
        self.assertIsNone(sentry_init_options(_settings()))

    def test_send_default_pii_is_off(self):
        options = sentry_init_options(_settings(sentry_dsn="https://k@example.test/1"))
        assert options is not None
        self.assertIs(options["send_default_pii"], False)

    def test_tracing_is_off_by_default_because_langfuse_owns_it(self):
        """Traces are H8's job. Paying a second vendor for the same spans is
        waste, so the sample rate defaults to 0.0 and is a knob, not a constant."""
        options = sentry_init_options(_settings(sentry_dsn="https://k@example.test/1"))
        assert options is not None
        self.assertEqual(options["traces_sample_rate"], 0.0)

    def test_the_scrubber_is_wired_in_as_before_send(self):
        options = sentry_init_options(_settings(sentry_dsn="https://k@example.test/1"))
        assert options is not None
        self.assertIs(options["before_send"], scrub_event)


class UrlScrubbingTests(unittest.TestCase):
    def test_the_game_route_key_is_removed_and_the_rest_of_the_path_survives(self):
        """A scrubber that redacts the whole path makes every event useless for
        finding the bug, so only the credential segment goes."""
        scrubbed = scrub_url(
            f"https://sentient-api.example/v1/sk-sent-abc123/{_UUID}/chat/completions"
        )
        self.assertNotIn("sk-sent-abc123", scrubbed)
        self.assertEqual(
            scrubbed,
            f"https://sentient-api.example/v1/{REDACTED}/{_UUID}/chat/completions",
        )

    def test_the_two_segment_game_route_is_scrubbed_too(self):
        """`/v1/{api_key}/chat/completions` has no project id and is just as
        much of a carrier."""
        self.assertEqual(
            scrub_url("https://api.example/v1/sk-sent-abc123/chat/completions"),
            f"https://api.example/v1/{REDACTED}/chat/completions",
        )

    def test_a_provider_key_in_that_position_is_scrubbed_as_well(self):
        """The segment is not always a `sk-sent-` product key: the same route
        accepts a raw provider key, which is a costlier credential to leak. The
        rule is positional for that reason, not prefix-matched."""
        self.assertEqual(
            scrub_url("https://api.example/v1/AIzaSyNotARealGoogleKey/chat/completions"),
            f"https://api.example/v1/{REDACTED}/chat/completions",
        )

    def test_the_keyless_completions_route_is_left_alone(self):
        """`/v1/chat/completions` carries its key in a header. Redacting `chat`
        here would be a scrubber inventing a secret."""
        url = "https://api.example/v1/chat/completions"
        self.assertEqual(scrub_url(url), url)

    def test_an_ordinary_management_route_is_left_alone(self):
        url = f"https://api.example/v1/projects/{_UUID}/documents"
        self.assertEqual(scrub_url(url), url)

    def test_a_bare_path_with_no_origin_works(self):
        """Sentry's `request.url` is normally absolute, but the ASGI integration
        has shipped relative values; the scrubber must not depend on which."""
        self.assertEqual(
            scrub_url(f"/v1/sk-sent-abc123/{_UUID}/chat/completions"),
            f"/v1/{REDACTED}/{_UUID}/chat/completions",
        )

    def test_a_query_string_survives(self):
        self.assertEqual(
            scrub_url("https://api.example/v1/sk-sent-k/chat/completions?stream=true"),
            f"https://api.example/v1/{REDACTED}/chat/completions?stream=true",
        )


class EventScrubbingTests(unittest.TestCase):
    def test_the_api_key_header_is_removed(self):
        """`X-API-Key` is the other carrier, and `Authorization` carries either a
        product key or a Neon Auth JWT."""
        event = scrub_event(
            {
                "request": {
                    "url": "https://api.example/v1/projects",
                    "headers": {
                        "X-API-Key": "sk-sent-abc123",
                        "authorization": "Bearer ey.J.token",
                        "User-Agent": "Mantella/1.0",
                    },
                }
            },
            None,
        )
        assert event is not None
        headers = event["request"]["headers"]
        self.assertEqual(headers["X-API-Key"], REDACTED)
        self.assertEqual(headers["authorization"], REDACTED)
        self.assertEqual(headers["User-Agent"], "Mantella/1.0")

    def test_it_scrubs_the_url_on_a_real_event_shape(self):
        event = scrub_event(
            {"request": {"url": f"https://api.example/v1/sk-sent-k/{_UUID}/chat/completions"}},
            None,
        )
        assert event is not None
        self.assertNotIn("sk-sent-k", event["request"]["url"])

    def test_an_event_with_no_request_does_not_raise(self):
        """`before_send` runs on every event, including ones with no HTTP context
        at all (a lifespan failure, a background task). A KeyError here loses the
        event *and* the exception it was carrying."""
        event = {"level": "error", "message": "queue worker died"}
        self.assertEqual(scrub_event(event, None), event)

    def test_a_request_with_no_url_or_headers_does_not_raise(self):
        self.assertEqual(scrub_event({"request": {}}, None), {"request": {}})

    def test_a_non_dict_request_does_not_raise(self):
        """Defensive because the cost of being wrong is asymmetric: a raising
        `before_send` drops the event, so the failure mode is silence."""
        self.assertEqual(scrub_event({"request": "??"}, None), {"request": "??"})


if __name__ == "__main__":
    unittest.main()
