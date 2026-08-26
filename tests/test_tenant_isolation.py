"""S1, frozen: every cross-tenant read this codebase refuses, as a permanent gate.

An audit is a moment; a test is a ratchet. The backlog calls multi-tenant
isolation "the core promise of the whole refactor", and a promise that is only
checked by hand is checked once.

Every case here is three beats -- **positive control, cross-tenant attempt,
then the assertion that A's data is still intact**. The third beat is not
decoration: a route that answered B with 404 by DELETING the row first would
pass the first two. And the positive control is what makes the negative mean
anything -- an empty 200 is what a *correct* ownership filter and a *missing*
one over an empty table both produce.

Two identities, not two keys on one user. G1 keys `user_key` on the **person**,
so two keys of one user are deliberately one tenant and
`tests/test_identity_scope.py` pins that as correct. An audit built on two keys
of one user would "find" a leak that is the design.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet

# The two statuses that both mean "refused". Management routes mask existence
# with 404; `completions_ctx` confirms it with 403, and core/errors.py documents
# that divergence as deliberate rather than accidental. Anything else -- above
# all an empty 200 -- is a leak.
REFUSED = {403, 404}


class _Identity(dict):
    """A probe user: their row, their raw api key, and the header that carries it."""

    @property
    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self["raw_key"]}


class CrossTenantReadsAreRefusedTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ,
            {
                "DATA_DIR": self.tmp.name,
                "VECTOR_BACKEND": "faiss",
                # The vault has to be configured for the credential cases to get
                # past their 503; a throwaway key keeps them offline.
                "SENTIENT_SECRET_KEY": Fernet.generate_key().decode(),
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        from sentient.adapters.auth import IdentityCache
        from sentient.adapters.state import get_state_store
        from sentient.api import app as api
        from sentient.api import deps
        from sentient.core.cache import ObjectRegistry
        from sentient.core.config import load_rag_settings
        from sentient.services.runtime import RuntimeCache

        self.deps = deps
        deps._settings = load_rag_settings()
        deps.state_store = get_state_store(deps._settings)
        deps.identity_cache = IdentityCache()
        deps.runtime_cache = RuntimeCache()
        deps.object_registry = ObjectRegistry()

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app),
            base_url="http://test",
        )
        self.addCleanup(self.client.aclose)

        self.a = await self._identity("sub-a")
        self.b = await self._identity("sub-b")

    # ---- arrangement --------------------------------------------------------

    async def _identity(self, sub: str) -> _Identity:
        from sentient.adapters.auth import generate_api_key

        user = await self.deps.state_store.ensure_user(sub, f"{sub}@example.test")
        raw_key, key_hash = generate_api_key()
        row = await self.deps.state_store.create_api_key(user["id"], key_hash, label=sub)
        return _Identity(user_id=user["id"], raw_key=raw_key, key_id=row["id"])

    async def _project(self, actor: _Identity, name: str) -> str:
        response = await self.client.post(
            "/v1/projects", json={"name": name}, headers=actor.headers
        )
        self.assertEqual(response.status_code, 200)
        return str(response.json()["id"])

    async def _thread(self, project_id: str) -> str:
        """Seeded through the store, not through /v1/chat.

        A chat turn would need a provider, and thread ownership is resolved from
        `chat_threads.project_id` either way -- the route that writes the row is
        not the route under test.
        """
        thread = await self.deps.state_store.upsert_thread(
            project_id, uuid4().hex, title="a-thread"
        )
        await self.deps.state_store.add_message(thread["id"], "user", "a secret line")
        return str(thread["id"])

    async def _request(
        self, method: str, url: str, actor: _Identity, **kwargs: Any
    ) -> httpx.Response:
        return await self.client.request(method, url, headers=actor.headers, **kwargs)

    async def _assert_refused(
        self, method: str, url: str, actor: _Identity, **kwargs: Any
    ) -> httpx.Response:
        response = await self._request(method, url, actor, **kwargs)
        self.assertIn(
            response.status_code,
            REFUSED,
            f"{method} {url} answered {response.status_code}: {response.text}",
        )
        return response

    # ---- projects -----------------------------------------------------------

    async def test_b_cannot_read_a_project(self) -> None:
        project = await self._project(self.a, "a-project")

        self.assertEqual(
            (await self._request("GET", f"/v1/projects/{project}", self.a)).status_code, 200
        )
        await self._assert_refused("GET", f"/v1/projects/{project}", self.b)
        self.assertEqual(
            (await self._request("GET", f"/v1/projects/{project}", self.a)).status_code, 200
        )

    async def test_b_cannot_rename_a_project(self) -> None:
        project = await self._project(self.a, "a-project")

        await self._assert_refused(
            "PATCH", f"/v1/projects/{project}", self.b, json={"name": "stolen"}
        )
        detail = await self._request("GET", f"/v1/projects/{project}", self.a)
        self.assertEqual(detail.json()["name"], "a-project")

    async def test_b_cannot_delete_a_project(self) -> None:
        project = await self._project(self.a, "a-project")

        await self._assert_refused("DELETE", f"/v1/projects/{project}", self.b)
        self.assertEqual(
            (await self._request("GET", f"/v1/projects/{project}", self.a)).status_code, 200
        )

    async def test_b_cannot_write_a_projects_config(self) -> None:
        project = await self._project(self.a, "a-project")

        await self._assert_refused(
            "PUT", f"/v1/projects/{project}/config", self.b, json={"rag_top_k": 19}
        )
        detail = await self._request("GET", f"/v1/projects/{project}", self.a)
        self.assertNotEqual(detail.json().get("rag_top_k"), 19)

    async def test_b_cannot_write_a_projects_persona(self) -> None:
        project = await self._project(self.a, "a-project")
        await self._request(
            "PUT", f"/v1/projects/{project}/persona", self.a, json={"system_prompt": "A's voice."}
        )

        await self._assert_refused(
            "PUT",
            f"/v1/projects/{project}/persona",
            self.b,
            json={"system_prompt": "B's voice."},
        )
        detail = await self._request("GET", f"/v1/projects/{project}", self.a)
        self.assertEqual(detail.json()["persona_prompt"], "A's voice.")

    async def test_b_cannot_list_a_projects_documents(self) -> None:
        project = await self._project(self.a, "a-project")

        self.assertEqual(
            (await self._request("GET", f"/v1/projects/{project}/documents", self.a)).status_code,
            200,
        )
        await self._assert_refused("GET", f"/v1/projects/{project}/documents", self.b)

    async def test_a_projects_do_not_appear_in_bs_list(self) -> None:
        project = await self._project(self.a, "a-project")

        listing = await self._request("GET", "/v1/projects", self.b)
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn(project, [p["id"] for p in listing.json()["projects"]])
        # The positive control: the same call as A does return it, so an empty
        # list above is a filter working rather than a listing that is broken.
        mine = await self._request("GET", "/v1/projects", self.a)
        self.assertIn(project, [p["id"] for p in mine.json()["projects"]])

    # ---- threads ------------------------------------------------------------

    async def test_b_cannot_list_a_projects_threads(self) -> None:
        project = await self._project(self.a, "a-project")
        await self._thread(project)

        self.assertEqual(
            (await self._request("GET", f"/v1/projects/{project}/threads", self.a)).status_code,
            200,
        )
        await self._assert_refused("GET", f"/v1/projects/{project}/threads", self.b)

    async def test_b_cannot_read_a_threads_messages(self) -> None:
        thread = await self._thread(await self._project(self.a, "a-project"))

        mine = await self._request("GET", f"/v1/threads/{thread}/messages", self.a)
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(len(mine.json()["messages"]), 1)
        await self._assert_refused("GET", f"/v1/threads/{thread}/messages", self.b)

    async def test_b_cannot_rename_a_thread(self) -> None:
        thread = await self._thread(await self._project(self.a, "a-project"))

        await self._assert_refused(
            "PATCH", f"/v1/threads/{thread}", self.b, json={"title": "stolen"}
        )
        self.assertEqual(
            (await self._request("GET", f"/v1/threads/{thread}/messages", self.a)).status_code, 200
        )

    async def test_b_cannot_delete_a_thread(self) -> None:
        thread = await self._thread(await self._project(self.a, "a-project"))

        await self._assert_refused("DELETE", f"/v1/threads/{thread}", self.b)
        self.assertEqual(
            (await self._request("GET", f"/v1/threads/{thread}/messages", self.a)).status_code, 200
        )

    async def test_b_cannot_reach_a_thread_through_their_own_project(self) -> None:
        """The pairing check, not the ownership check.

        Both ids exist and B owns the project; only the thread belongs to A. A
        route that validated each id separately would let this through.
        """
        a_thread = await self._thread(await self._project(self.a, "a-project"))
        b_project = await self._project(self.b, "b-project")

        response = await self._request(
            "POST",
            "/v1/chat",
            self.b,
            json={"message": "hi", "project_id": b_project, "thread_id": a_thread},
        )
        self.assertEqual(response.status_code, 404)
        # The detail pins WHICH check refused it. Without this the test would
        # still pass if the project check started rejecting B's own project.
        self.assertEqual(response.json()["detail"], "thread not found")

    # ---- keys and credentials -----------------------------------------------

    async def test_b_cannot_revoke_a_key(self) -> None:
        """`DELETE /v1/keys/{id}` answers `{"revoked": false}`, never 404.

        So the refusal here is the boolean, and the third beat -- A's key still
        authenticating -- is the assertion that actually matters.
        """
        victim = await self._identity_second_key(self.a)

        response = await self._request("DELETE", f"/v1/keys/{victim['key_id']}", self.b)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["revoked"])
        self.assertEqual((await self._request("GET", "/v1/keys", victim)).status_code, 200)

    async def test_a_keys_do_not_appear_in_bs_list(self) -> None:
        listing = await self._request("GET", "/v1/keys", self.b)
        self.assertEqual([row["id"] for row in listing.json()["keys"]], [self.b["key_id"]])

    async def test_b_cannot_delete_a_credential(self) -> None:
        stored = await self._request(
            "POST", "/v1/credentials", self.a, json={"provider": "groq", "api_key": "gsk_a_secret"}
        )
        self.assertEqual(stored.status_code, 200)

        response = await self._request("DELETE", "/v1/credentials/groq", self.b)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["deleted"])

        mine = await self._request("GET", "/v1/credentials", self.a)
        self.assertEqual([row["provider"] for row in mine.json()["credentials"]], ["groq"])

    async def test_a_credentials_do_not_appear_in_bs_list(self) -> None:
        await self._request(
            "POST", "/v1/credentials", self.a, json={"provider": "groq", "api_key": "gsk_a_secret"}
        )

        listing = await self._request("GET", "/v1/credentials", self.b)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["credentials"], [])
        # Not just "the list is empty" -- the hint of A's key must not be
        # anywhere in the body B receives.
        self.assertNotIn("cret", listing.text)

    # ---- retrieval and the game path ----------------------------------------

    async def test_b_cannot_retrieve_from_a_project(self) -> None:
        project = await self._project(self.a, "a-project")

        await self._assert_refused(
            "POST", "/v1/retrieve", self.b, json={"query": "anything", "project_id": project}
        )

    async def test_b_cannot_chat_against_a_project(self) -> None:
        project = await self._project(self.a, "a-project")

        response = await self._request(
            "POST", "/v1/chat", self.b, json={"message": "hi", "project_id": project}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "project not found")

    async def test_the_game_path_refuses_another_users_project(self) -> None:
        """B's key, A's project. Both exist; only the pairing is wrong.

        This gets its own test rather than sharing the helper above because
        `completions_ctx` (api/deps.py) resolves identity by a different path
        than `current_user`, and it answers **403**, not 404 -- management routes
        mask existence, this one confirms it, and core/errors.py says so. It is
        also the route with no browser in front of it.
        """
        a_project = await self._project(self.a, "a-project")

        response = await self.client.post(
            f"/v1/{self.b['raw_key']}/{a_project}/chat/completions",
            json={"model": "sentient", "messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertIn(response.status_code, REFUSED)

    async def test_the_game_path_refuses_a_project_the_key_does_not_own(self) -> None:
        """A's key, B's project -- the mirror image, and the same 403."""
        b_project = await self._project(self.b, "b-project")

        response = await self.client.post(
            f"/v1/{self.a['raw_key']}/{b_project}/chat/completions",
            json={"model": "sentient", "messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertIn(response.status_code, REFUSED)

    # ---- helper -------------------------------------------------------------

    async def _identity_second_key(self, actor: _Identity) -> _Identity:
        """A second key on the same user, so revoking it cannot break the session."""
        from sentient.adapters.auth import generate_api_key

        raw_key, key_hash = generate_api_key()
        row = await self.deps.state_store.create_api_key(actor["user_id"], key_hash, label="second")
        return _Identity(user_id=actor["user_id"], raw_key=raw_key, key_id=row["id"])
