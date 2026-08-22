from __future__ import annotations

import unittest

import httpx


class LocalDevOriginTests(unittest.IsolatedAsyncioTestCase):
    """The frontend spec listed B4 (CORS for the console origin) as a BLOCKER for
    F1 on the grounds that `CORS_ALLOW_ORIGINS` is empty. It is empty, and it does
    not matter: `api/app.py` also sets an `allow_origin_regex` covering every
    local dev-server port. This pins that, so the correction cannot rot back into
    a blocker nobody re-measured.
    """

    async def asyncSetUp(self):
        from sentient.api import app as api

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        )
        self.addAsyncCleanup(self.client.aclose)

    async def _preflight(self, origin: str) -> httpx.Response:
        return await self.client.options(
            "/v1/projects",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    async def test_any_localhost_port_is_allowed(self):
        # Vite takes the next free port whenever 5173 is busy, which is why this
        # is a regex and not a fixed list.
        for origin in ("http://localhost:5173", "http://localhost:5178", "http://localhost:3000"):
            response = await self._preflight(origin)
            self.assertEqual(response.status_code, 200, origin)
            self.assertEqual(response.headers["access-control-allow-origin"], origin)

    async def test_the_ipv4_loopback_literal_is_allowed_too(self):
        """Clients are told to use 127.0.0.1 rather than localhost on Windows, so
        the browser origin is that literal and it has to be covered."""
        response = await self._preflight("http://127.0.0.1:5173")
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:5173")

    async def test_an_unrelated_origin_is_not_allowed(self):
        response = await self._preflight("https://evil.example.com")
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
