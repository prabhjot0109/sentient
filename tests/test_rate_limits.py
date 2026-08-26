"""D6: the rate limiter, both halves.

The arithmetic is tested without a clock or a server -- `TokenBucket` takes
`now` as an argument precisely so that "an idle hour must not buy an hour's
burst" is a two-line assertion instead of a sleep.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

import httpx

from sentient.core.limits import BucketRegistry, TokenBucket


class TokenBucketTests(unittest.TestCase):
    def test_a_fresh_bucket_allows_up_to_capacity(self):
        bucket = TokenBucket(capacity=3, refill_per_second=1)
        self.assertTrue(bucket.take(now=0))
        self.assertTrue(bucket.take(now=0))
        self.assertTrue(bucket.take(now=0))
        self.assertFalse(bucket.take(now=0))

    def test_it_refills_over_time(self):
        bucket = TokenBucket(capacity=3, refill_per_second=1)
        for _ in range(3):
            bucket.take(now=0)
        self.assertFalse(bucket.take(now=0.5))
        self.assertTrue(bucket.take(now=1.0))

    def test_it_never_refills_past_capacity(self):
        # An idle hour must not buy an hour's burst. This is the whole reason a
        # bucket beats a fixed window and it is the easiest part to get wrong.
        bucket = TokenBucket(capacity=3, refill_per_second=1)
        bucket.take(now=0)
        for _ in range(3):
            self.assertTrue(bucket.take(now=3600))
        self.assertFalse(bucket.take(now=3600))

    def test_retry_after_is_when_the_next_token_lands(self):
        bucket = TokenBucket(capacity=1, refill_per_second=2)
        bucket.take(now=0)
        self.assertAlmostEqual(bucket.retry_after(now=0), 0.5, places=3)

    def test_retry_after_is_zero_while_the_bucket_still_has_tokens(self):
        bucket = TokenBucket(capacity=2, refill_per_second=1)
        self.assertEqual(bucket.retry_after(now=0), 0.0)

    def test_a_refused_take_costs_nothing(self):
        # A rejected request must not drain the bucket further, or a client that
        # keeps retrying would push its own recovery further away every time.
        bucket = TokenBucket(capacity=1, refill_per_second=1)
        bucket.take(now=0)
        for _ in range(10):
            self.assertFalse(bucket.take(now=0))
        self.assertTrue(bucket.take(now=1.0))

    def test_time_never_goes_backwards(self):
        # perf_counter is monotonic, but a bucket handed a smaller `now` must not
        # mint negative elapsed time and silently drain itself.
        bucket = TokenBucket(capacity=2, refill_per_second=1)
        bucket.take(now=10)
        self.assertTrue(bucket.take(now=5))


class BucketRegistryTests(unittest.TestCase):
    def test_two_identities_do_not_share_a_budget(self):
        registry = BucketRegistry(capacity=1, refill_per_second=1)
        self.assertEqual(registry.allow("user-a", now=0)[0], True)
        self.assertEqual(registry.allow("user-a", now=0)[0], False)
        self.assertEqual(registry.allow("user-b", now=0)[0], True)

    def test_a_refusal_reports_how_long_to_wait(self):
        registry = BucketRegistry(capacity=1, refill_per_second=2)
        registry.allow("user-a", now=0)
        allowed, retry_after = registry.allow("user-a", now=0)
        self.assertFalse(allowed)
        self.assertAlmostEqual(retry_after, 0.5, places=3)

    def test_it_evicts_rather_than_growing_without_bound(self):
        # An unauthenticated flood from many hosts must not become a memory leak
        # -- the limiter becoming the outage it exists to prevent.
        registry = BucketRegistry(capacity=1, refill_per_second=1, maxsize=2)
        for index in range(50):
            registry.allow(f"host-{index}", now=0)
        self.assertLessEqual(len(registry), 2)


class RateLimitMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    """The HTTP half, over a purpose-built app rather than the real one.

    `api/app.py` builds its FastAPI instance at import time, so the flag is read
    once per process. Reloading that module to flip it would leave a mutated
    global behind for every test after this file. `configure_middleware` exists
    so the identical stack can be built over a throwaway app instead -- and the
    routes below are the real path shapes, which is what the bucket selector and
    the identity extractor actually key on.
    """

    def _app(self, **overrides):
        from fastapi import FastAPI

        from sentient.api.app import configure_middleware
        from sentient.core.config import load_rag_settings

        knobs = {
            "rate_limit_enabled": True,
            "rate_limit_completions_per_minute": 3,
            "rate_limit_uploads_per_hour": 2,
            "rate_limit_default_per_minute": 5,
        }
        settings = replace(load_rag_settings(), **{**knobs, **overrides})
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "online"}

        @app.get("/v1/projects")
        async def projects():
            return {"projects": []}

        @app.post("/v1/upload")
        async def upload():
            return {"accepted": True}

        @app.post("/v1/chat/completions")
        async def completions():
            return {"ok": True}

        @app.post("/v1/{api_key}/{project_id}/chat/completions")
        async def game(api_key: str, project_id: str):
            return {"ok": True, "key": api_key}

        configure_middleware(app, settings)
        return app

    def _client(self, app, client=("127.0.0.1", 4242)):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=client),
            base_url="http://test",
        )

    async def test_it_is_off_when_the_flag_is_off(self):
        # The default, and a hard constraint: a fresh clone must behave like main.
        async with self._client(self._app(rate_limit_enabled=False)) as client:
            for _ in range(100):
                response = await client.post(
                    "/v1/chat/completions", headers={"X-API-Key": "sk-sent-a"}
                )
                self.assertEqual(response.status_code, 200)

    async def test_a_completion_flood_from_one_user_gets_429(self):
        async with self._client(self._app()) as client:
            headers = {"X-API-Key": "sk-sent-a"}
            for _ in range(3):
                self.assertEqual(
                    (await client.post("/v1/chat/completions", headers=headers)).status_code, 200
                )
            self.assertEqual(
                (await client.post("/v1/chat/completions", headers=headers)).status_code, 429
            )

    async def test_the_429_carries_retry_after(self):
        async with self._client(self._app()) as client:
            headers = {"X-API-Key": "sk-sent-a"}
            for _ in range(4):
                response = await client.post("/v1/chat/completions", headers=headers)
            self.assertEqual(response.status_code, 429)
            self.assertGreaterEqual(int(response.headers["retry-after"]), 1)
            # A string detail, the same shape every other error here uses, so the
            # console's seam types it and describe() can speak for it.
            self.assertIsInstance(response.json()["detail"], str)

    async def test_two_users_do_not_share_a_budget(self):
        async with self._client(self._app()) as client:
            for _ in range(4):
                await client.post("/v1/chat/completions", headers={"X-API-Key": "sk-sent-a"})
            self.assertEqual(
                (
                    await client.post("/v1/chat/completions", headers={"X-API-Key": "sk-sent-b"})
                ).status_code,
                200,
            )

    async def test_health_is_never_throttled(self):
        # The platform's health check hits this on a schedule forever. Throttling
        # it would take the service out of the load balancer under exactly the
        # load the limiter exists to survive.
        async with self._client(self._app()) as client:
            for _ in range(50):
                self.assertEqual((await client.get("/health")).status_code, 200)

    async def test_an_unauthenticated_caller_is_bucketed_by_client_host(self):
        app = self._app()
        async with (
            self._client(app, client=("10.0.0.1", 5000)) as first,
            self._client(app, client=("10.0.0.2", 5000)) as second,
        ):
            for _ in range(6):
                await first.get("/v1/projects")
            self.assertEqual((await first.get("/v1/projects")).status_code, 429)
            # Same app, same bucket registry, different host: still served.
            self.assertEqual((await second.get("/v1/projects")).status_code, 200)

    async def test_the_key_in_the_url_path_is_the_identity(self):
        """The Mantella shape carries no header, so the path segment is all there is."""
        async with self._client(self._app()) as client:
            for _ in range(4):
                response = await client.post("/v1/sk-sent-a/proj-1/chat/completions")
            self.assertEqual(response.status_code, 429)
            self.assertEqual(
                (await client.post("/v1/sk-sent-b/proj-1/chat/completions")).status_code, 200
            )

    async def test_uploads_have_their_own_tighter_bucket(self):
        """Exhausting one bucket must not spend another's.

        Uploads cost embedding calls per byte, which is why they are separated
        from the completions budget at all.
        """
        async with self._client(self._app()) as client:
            headers = {"X-API-Key": "sk-sent-a"}
            for _ in range(2):
                self.assertEqual(
                    (await client.post("/v1/upload", headers=headers)).status_code, 200
                )
            self.assertEqual((await client.post("/v1/upload", headers=headers)).status_code, 429)
            self.assertEqual(
                (await client.post("/v1/chat/completions", headers=headers)).status_code, 200
            )

    async def test_a_throttled_response_still_carries_cors_headers(self):
        """The ordering pin.

        Starlette puts the last-added middleware outermost. If the limiter ended
        up in front of CORS, a browser would see its 429 as a network failure
        with no status at all -- the console would lose the one error it most
        needs to explain, and nothing but this test would notice.
        """
        origin = "http://localhost:5173"
        async with self._client(self._app()) as client:
            headers = {"X-API-Key": "sk-sent-a", "Origin": origin}
            for _ in range(4):
                response = await client.post("/v1/chat/completions", headers=headers)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["access-control-allow-origin"], origin)
