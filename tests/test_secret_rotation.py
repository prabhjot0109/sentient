"""D8: rotating SENTIENT_SECRET_KEY without stranding what it encrypted.

The defect is not that rotation was hard -- it is that it was **silent**.
Changing the key made every stored credential fail to decrypt, and
`services/runtime.py:_stored_key` catches that and falls back to the environment
key. Nothing errors. The user's own key simply stops being used and someone
else's pays, and the first symptom is a bill.

So these tests are about the failure being impossible rather than merely
visible: with the previous key held for one deploy, nothing ever reaches that
fallback.
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from sentient.adapters.state.sqlite_store import SQLiteStateStore
from sentient.core.crypto import decrypt_key, encrypt_key, key_hint, rotate_token
from sentient.core.errors import InvalidRequest, VaultUnavailable
from sentient.services.credentials import rotate_vault_keys


class MultiKeyDecryptTests(unittest.TestCase):
    def setUp(self):
        self.old = Fernet.generate_key().decode()
        self.new = Fernet.generate_key().decode()

    def test_a_row_written_with_the_old_key_still_decrypts(self):
        token = encrypt_key("gsk_written_before_the_rotation", self.old)
        self.assertEqual(
            decrypt_key(token, self.new, (self.old,)), "gsk_written_before_the_rotation"
        )

    def test_new_writes_use_the_new_key(self):
        # Proven by decrypting with ONLY the new key: if writes had gone to the
        # old one this would raise.
        token = encrypt_key("gsk_written_after", self.new)
        self.assertEqual(decrypt_key(token, self.new), "gsk_written_after")

    def test_a_row_written_with_neither_key_raises_rather_than_returning_none(self):
        # The primitive must not answer "no key" the same way a caller answers
        # "no credential"; that is the one place the two differ, and conflating
        # them is what let a rotation look like an empty vault.
        stranger = Fernet.generate_key().decode()
        token = encrypt_key("gsk_from_another_deployment", stranger)
        with self.assertRaises(InvalidToken):
            decrypt_key(token, self.new, (self.old,))

    def test_rotating_a_token_makes_it_readable_by_the_new_key_alone(self):
        token = rotate_token(encrypt_key("gsk_secret", self.old), self.new, (self.old,))
        self.assertEqual(decrypt_key(token, self.new), "gsk_secret")

    def test_rotation_is_idempotent(self):
        # Operators re-run commands. A second pass must not nest one ciphertext
        # inside another; it produces a fresh IV over the same plaintext.
        once = rotate_token(encrypt_key("gsk_secret", self.old), self.new, (self.old,))
        twice = rotate_token(once, self.new, (self.old,))
        self.assertNotEqual(once, twice)
        self.assertEqual(decrypt_key(twice, self.new), "gsk_secret")

    def test_more_than_one_previous_key_is_accepted(self):
        # Comma-separated, so two rotations can be in flight at once -- which is
        # what happens when step 3 of the first is skipped.
        older = Fernet.generate_key().decode()
        token = encrypt_key("gsk_ancient", older)
        self.assertEqual(decrypt_key(token, self.new, (self.old, older)), "gsk_ancient")


class RotateCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))
        self.old = Fernet.generate_key().decode()
        self.new = Fernet.generate_key().decode()

    def _settings(self, secret: str | None, previous: tuple[str, ...]):
        from sentient.core.config import load_rag_settings

        return replace(
            load_rag_settings(), sentient_secret_key=secret, sentient_secret_keys_old=previous
        )

    async def _seed(self, count: int, secret: str) -> list[str]:
        raws = []
        for index in range(count):
            user = await self.store.ensure_user(f"vault-user-{index}")
            raw = f"gsk_stored_secret_{index}"
            raws.append(raw)
            await self.store.upsert_credential(
                user["id"], "groq", encrypt_key(raw, secret), key_hint(raw)
            )
        return raws

    async def test_it_re_encrypts_every_row(self):
        raws = await self._seed(3, self.old)

        report = await rotate_vault_keys(self.store, self._settings(self.new, (self.old,)))

        self.assertEqual(report["rotated"], 3)
        self.assertEqual(report["unreadable"], [])
        # The point of the whole exercise: every row now reads under the NEW key
        # with no previous key held, so step 3 can drop it safely.
        stored = sorted(
            decrypt_key(row["encrypted_key"], self.new)
            for row in await self.store.list_all_credentials()
        )
        self.assertEqual(stored, sorted(raws))

    async def test_it_leaves_the_hint_and_the_owner_alone(self):
        # key_hint is derived from the plaintext and does not change under
        # re-encryption. Rewriting it would be a silent way to corrupt the one
        # thing the console shows the user about their own key.
        await self._seed(1, self.old)
        before = (await self.store.list_all_credentials())[0]
        hint_before = (await self.store.get_credential(before["user_id"], "groq"))["key_hint"]

        await rotate_vault_keys(self.store, self._settings(self.new, (self.old,)))

        after = (await self.store.list_all_credentials())[0]
        self.assertEqual(after["id"], before["id"])
        self.assertEqual(after["user_id"], before["user_id"])
        self.assertEqual(
            (await self.store.get_credential(after["user_id"], "groq"))["key_hint"], hint_before
        )

    async def test_it_is_idempotent(self):
        raws = await self._seed(2, self.old)
        settings = self._settings(self.new, (self.old,))

        await rotate_vault_keys(self.store, settings)
        second = await rotate_vault_keys(self.store, settings)

        self.assertEqual(second["rotated"], 2)
        self.assertEqual(
            sorted(
                decrypt_key(row["encrypted_key"], self.new)
                for row in await self.store.list_all_credentials()
            ),
            sorted(raws),
        )

    async def test_it_reports_the_row_count_it_changed(self):
        await self._seed(5, self.old)
        report = await rotate_vault_keys(self.store, self._settings(self.new, (self.old,)))
        self.assertEqual(report["rotated"], 5)

    async def test_an_unreadable_row_is_named_and_does_not_strand_the_others(self):
        """One row from a third key must not abort the run.

        These are exactly the credentials that will fall back to the env key once
        the old key is removed, so the report names them -- by user and provider,
        never by key material.
        """
        await self._seed(2, self.old)
        stranger = await self.store.ensure_user("vault-user-stranger")
        await self.store.upsert_credential(
            stranger["id"],
            "groq",
            encrypt_key("gsk_from_elsewhere", Fernet.generate_key().decode()),
            key_hint("gsk_from_elsewhere"),
        )

        report = await rotate_vault_keys(self.store, self._settings(self.new, (self.old,)))

        self.assertEqual(report["rotated"], 2)
        self.assertEqual(report["unreadable"], [{"user_id": stranger["id"], "provider": "groq"}])

    async def test_it_refuses_to_run_without_the_old_key(self):
        # The dangerous order: SENTIENT_SECRET_KEY already changed, the old key
        # never set. Every row would fail to decrypt and a long list of failures
        # reads far too much like "already done".
        await self._seed(1, self.old)
        with self.assertRaises(InvalidRequest):
            await rotate_vault_keys(self.store, self._settings(self.new, ()))

    async def test_it_refuses_to_run_with_no_vault_configured(self):
        with self.assertRaises(VaultUnavailable):
            await rotate_vault_keys(self.store, self._settings(None, (self.old,)))


if __name__ == "__main__":
    unittest.main()
