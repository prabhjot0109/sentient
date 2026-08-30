from __future__ import annotations

import io
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import numpy as np
from cryptography.fernet import Fernet


def wav_bytes(amplitude: float, seconds: float = 1.5, sample_rate: int = 16000) -> bytes:
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    pcm = (np.clip(amplitude * np.sin(2 * np.pi * 220 * t), -1, 1) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


SPEECH = wav_bytes(0.21)
SILENCE = wav_bytes(0.0)


class STTCredentialResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwarded_groq_key_wins_over_environment(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_from_env"}, clear=False):
            provider, key, source = await resolve_stt_credential(
                None, settings, authorization="Bearer gsk_from_mantella", user_id=None
            )
        self.assertEqual((provider, key), ("groq", "gsk_from_mantella"))
        self.assertIn("forward", source.lower())

    async def test_forwarded_openai_key_selects_openai(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        provider, key, _ = await resolve_stt_credential(
            None, settings, authorization="Bearer sk-abc123", user_id=None
        )
        self.assertEqual((provider, key), ("openai", "sk-abc123"))

    async def test_a_sentient_product_key_is_never_used_as_a_provider_key(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider, key, _ = await resolve_stt_credential(
                None, settings, authorization="Bearer sk-sent-abcdef", user_id=None
            )
        # sk-sent-… is identity, not an STT credential; forwarding it upstream would
        # leak a Sentient key to Groq and 401 there anyway.
        self.assertIsNone(provider)
        self.assertIsNone(key)

    async def test_stored_credential_beats_env_when_no_bearer(self):
        from sentient.adapters.stt.client import resolve_stt_credential
        from sentient.core.crypto import encrypt_key

        secret = Fernet.generate_key().decode()
        settings = SimpleNamespace(sentient_secret_key=secret)
        store = SimpleNamespace()

        async def get_credential(user_id, provider):
            if provider == "groq":
                return {"encrypted_key": encrypt_key("gsk_from_vault", secret)}
            return None

        store.get_credential = get_credential
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_from_env"}, clear=False):
            provider, key, source = await resolve_stt_credential(
                store, settings, authorization=None, user_id="user-1"
            )
        self.assertEqual((provider, key), ("groq", "gsk_from_vault"))
        self.assertIn("stored", source.lower())

    async def test_an_unusable_stored_credential_degrades_to_env(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=Fernet.generate_key().decode())
        store = SimpleNamespace()

        async def get_credential(user_id, provider):
            return {"encrypted_key": "not-a-fernet-token"}

        store.get_credential = get_credential
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_env"}, clear=False):
            provider, key, source = await resolve_stt_credential(
                store, settings, authorization=None, user_id="user-1"
            )
        # A corrupt vault row must not take transcription down.
        self.assertEqual((provider, key), ("groq", "gsk_env"))
        self.assertIn("env", source.lower())

    async def test_env_is_the_floor(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_env"}, clear=False):
            provider, key, source = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertEqual((provider, key), ("groq", "gsk_env"))
        self.assertIn("env", source.lower())

    async def test_no_credential_anywhere_resolves_to_nothing(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider, key, _ = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertIsNone(provider)
        self.assertIsNone(key)


class UpstreamModelTests(unittest.TestCase):
    def test_whisper_1_is_remapped_for_groq(self):
        from sentient.adapters.stt.client import upstream_model

        # Groq only serves the large-v3 family; whisper-1 is OpenAI-only and 400s.
        self.assertEqual(upstream_model("groq", "whisper-1"), "whisper-large-v3-turbo")

    def test_groq_model_is_passed_through(self):
        from sentient.adapters.stt.client import upstream_model

        self.assertEqual(upstream_model("groq", "whisper-large-v3"), "whisper-large-v3")

    def test_openai_falls_back_to_its_only_model(self):
        from sentient.adapters.stt.client import upstream_model

        self.assertEqual(upstream_model("openai", "whisper-large-v3-turbo"), "whisper-1")


class TranscriptionEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # GET /v1/audio/transcriptions/recent resolves identity now, so it reads the
        # state store. This class used to inherit whichever store a previous test
        # left on deps, which is a temp directory that has since been deleted.
        import tempfile

        from sentient.adapters.state.sqlite_store import SQLiteStateStore
        from sentient.api import deps

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        original = deps.state_store
        self.addCleanup(lambda: setattr(deps, "state_store", original))
        deps.state_store = SQLiteStateStore(str(Path(self.tmp.name) / "state.db"))

    async def _post(self, audio: bytes, **kwargs):
        from sentient.api import app as api

        transport = httpx.ASGITransport(app=api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/audio/transcriptions",
                files={"file": ("mic.wav", audio, "audio/wav")},
                data={"model": "whisper-large-v3-turbo"},
                **kwargs,
            )

    async def test_transcription_is_returned_and_uses_the_forwarded_key(self):
        import sentient.adapters.stt.client as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="hello there")
        with patch.object(stt, "stt_client", return_value=fake) as build:
            response = await self._post(SPEECH, headers={"Authorization": "Bearer gsk_forwarded"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "hello there")
        # The third argument is the self-hosted base URL, None for a real provider.
        build.assert_called_once_with("groq", "gsk_forwarded", None)

    async def test_text_invented_from_silence_is_discarded(self):
        import sentient.adapters.stt.client as stt

        fake = MagicMock()
        # Whisper's signature hallucination on a dead mic.
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="Thank you.")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(SILENCE, headers={"Authorization": "Bearer gsk_forwarded"})

        self.assertEqual(response.status_code, 200)
        # Empty => Mantella replays its "could not detect speech" cue instead of
        # making the NPC answer a line the player never spoke.
        self.assertEqual(response.json()["text"], "")

    async def test_healthy_audio_is_never_discarded(self):
        import sentient.adapters.stt.client as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="Thank you.")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(SPEECH, headers={"Authorization": "Bearer gsk_forwarded"})

        self.assertEqual(response.json()["text"], "Thank you.")

    async def test_missing_credentials_are_rejected_before_any_upstream_call(self):
        import sentient.adapters.stt.client as stt

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(stt, "stt_client") as build,
        ):
            response = await self._post(SPEECH)

        self.assertEqual(response.status_code, 400)
        build.assert_not_called()

    async def test_upstream_failure_surfaces_as_bad_gateway(self):
        import sentient.adapters.stt.client as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.side_effect = RuntimeError("groq is down")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(SPEECH, headers={"Authorization": "Bearer gsk_forwarded"})

        self.assertEqual(response.status_code, 502)

    async def test_optional_fields_are_only_sent_when_set(self):
        import sentient.adapters.stt.client as stt
        from sentient.api import app as api

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="hi")
        transport = httpx.ASGITransport(app=api.app)
        with patch.object(stt, "stt_client", return_value=fake):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                await client.post(
                    "/v1/audio/transcriptions",
                    files={"file": ("mic.wav", SPEECH, "audio/wav")},
                    data={"model": "whisper-large-v3-turbo", "language": "default"},
                    headers={"Authorization": "Bearer gsk_f"},
                )

        sent = fake.audio.transcriptions.create.call_args.kwargs
        # The SDKs serialise an explicit None, and "default" is Mantella's
        # placeholder for auto-detect, not an ISO-639-1 code.
        self.assertNotIn("language", sent)
        self.assertNotIn("prompt", sent)

    async def test_recent_endpoint_reports_transcriptions_and_silence_count(self):
        import sentient.adapters.stt.client as stt
        from sentient.api import app as api
        from sentient.services import transcription

        transcription._STT_HISTORY.clear()
        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="hello")
        with patch.object(stt, "stt_client", return_value=fake):
            await self._post(SPEECH, headers={"Authorization": "Bearer gsk_f"})
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="Thank you.")
        with patch.object(stt, "stt_client", return_value=fake):
            await self._post(SILENCE, headers={"Authorization": "Bearer gsk_f"})

        transport = httpx.ASGITransport(app=api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            body = (await client.get("/v1/audio/transcriptions/recent")).json()

        self.assertEqual(body["count"], 2)
        self.assertEqual(body["empty_transcriptions"], 1)
        # Newest first, and no key material anywhere in the payload.
        self.assertEqual(body["transcriptions"][0]["text"], "")
        self.assertNotIn("gsk_f", str(body))

    async def test_history_is_bounded(self):
        from sentient.services import transcription

        bucket = transcription.ANONYMOUS_BUCKET
        transcription._STT_HISTORY.clear()
        for i in range(transcription._STT_HISTORY_LIMIT + 10):
            transcription.record_history(bucket, {"time": str(i), "text": "x"})

        stored = transcription._STT_HISTORY[bucket]
        self.assertEqual(len(stored), transcription._STT_HISTORY_LIMIT)
        # Oldest dropped, newest kept.
        self.assertEqual(stored[-1]["time"], str(transcription._STT_HISTORY_LIMIT + 9))

    async def test_no_raw_key_is_returned_on_any_path(self):
        import sentient.adapters.stt.client as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="hi")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(
                SPEECH, headers={"Authorization": "Bearer gsk_super_secret"}
            )

        self.assertNotIn("gsk_super_secret", response.text)


if __name__ == "__main__":
    unittest.main()


class TranscriptionHistoryScopingTests(unittest.TestCase):
    """The buffer holds transcribed player speech; it must not be shared.

    Keyed on `user_key`, not `user_id`, so the anonymous bucket has one spelling.
    `resolve_identity` reports no Sentient identity as None while `current_user`
    reports it as the default user's row id, and the two routes have to agree or
    the local single-user diagnostic always reads empty.
    """

    def setUp(self):
        from sentient.services import transcription

        transcription._STT_HISTORY.clear()
        self.addCleanup(transcription._STT_HISTORY.clear)

    def test_history_is_partitioned_by_user(self):
        from sentient.services import transcription

        transcription.record_history("user-a", {"time": "00:00:01", "text": "alice speaking"})
        transcription.record_history("user-b", {"time": "00:00:02", "text": "bob speaking"})

        alice = transcription.recent_history("user-a", 20)
        self.assertEqual(alice["count"], 1)
        self.assertEqual(alice["transcriptions"][0]["text"], "alice speaking")

        bob = transcription.recent_history("user-b", 20)
        self.assertEqual(bob["count"], 1)
        self.assertEqual(bob["transcriptions"][0]["text"], "bob speaking")

    def test_anonymous_history_is_its_own_bucket(self):
        from sentient.services import transcription

        transcription.record_history(transcription.ANONYMOUS_BUCKET, {"time": "1", "text": "anon"})
        self.assertEqual(transcription.recent_history("user-a", 20)["count"], 0)
        self.assertEqual(
            transcription.recent_history(transcription.ANONYMOUS_BUCKET, 20)["count"], 1
        )

    def test_the_anonymous_bucket_matches_what_current_user_resolves_to(self):
        """Anonymous POST and anonymous GET must name the same bucket. resolve_user's
        no-credential branch returns the literal "default" as user_key; this pins the
        buffer to that same literal so the two cannot drift apart."""
        from sentient.services import transcription

        self.assertEqual(transcription.ANONYMOUS_BUCKET, "default")

    def test_the_bucket_for_an_identified_caller_is_their_user_key(self):
        from sentient.adapters.auth import user_key_of
        from sentient.services import transcription

        self.assertEqual(transcription.history_bucket("uid-7"), user_key_of("uid-7"))
        self.assertEqual(transcription.history_bucket(None), transcription.ANONYMOUS_BUCKET)

    def test_each_bucket_is_bounded_independently(self):
        from sentient.services import transcription

        for i in range(transcription._STT_HISTORY_LIMIT + 10):
            transcription.record_history("user-a", {"time": str(i), "text": f"line {i}"})
        transcription.record_history("user-b", {"time": "x", "text": "one line"})

        self.assertEqual(
            transcription.recent_history("user-a", 200)["count"],
            transcription._STT_HISTORY_LIMIT,
        )
        self.assertEqual(transcription.recent_history("user-b", 200)["count"], 1)


# A Neon Auth JWT, shaped like the real thing: three dot-separated base64url
# segments with a leading "eyJ". The signature is deliberate nonsense -- nothing
# in the credential resolver should ever verify it, and proving it never reaches
# a provider is the whole point of the class below.
FAKE_JWT = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyJ9.c2lnbmF0dXJl"


class JwtIsNeverAProviderKeyTests(unittest.IsolatedAsyncioTestCase):
    """A console identity token must never reach a third-party STT provider.

    `resolve_stt_credential` used to end with an unconditional "try the forwarded
    key against Groq anyway" branch. That is right for an unrecognised *provider*
    key and catastrophic for an identity token: with no vault key and no env key,
    a user's JWT was transmitted to Groq as an API key. Latent until the console
    started sending one, which is exactly what the voice work does.
    """

    async def test_a_jwt_is_not_classified_as_a_provider_key(self):
        from sentient.adapters.stt.client import provider_of_key

        self.assertIsNone(provider_of_key(FAKE_JWT))

    async def test_a_jwt_does_not_leak_when_no_other_credential_resolves(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider, key, source = await resolve_stt_credential(
                None, settings, authorization=f"Bearer {FAKE_JWT}", user_id=None
            )
        self.assertIsNone(provider)
        self.assertIsNone(key)
        self.assertEqual(source, "none")

    async def test_a_jwt_does_not_displace_the_env_key(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_from_env"}, clear=True):
            provider, key, _ = await resolve_stt_credential(
                None, settings, authorization=f"Bearer {FAKE_JWT}", user_id=None
            )
        self.assertEqual((provider, key), ("groq", "gsk_from_env"))

    async def test_an_unrecognised_provider_key_is_still_tried(self):
        """The forwarded-key fallback is preserved for everything that is NOT a JWT."""
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider, key, source = await resolve_stt_credential(
                None, settings, authorization="Bearer some-unknown-shape", user_id=None
            )
        self.assertEqual((provider, key), ("groq", "some-unknown-shape"))
        self.assertIn("unrecognised", source)


class ProviderSelectionTests(unittest.IsolatedAsyncioTestCase):
    """Selection, not inference. The gap H9 names.

    `provider_of_key` infers the provider from whichever key happened to be
    pasted. That makes the choice an accident of credential shape, so an explicit
    `STT_PROVIDER` is authoritative here: it is tried alone rather than moved to
    the front of the list. Silent provider substitution is the exact failure V1
    recorded when a harness quietly resolved a different embedding provider than
    the server, and a wrong-but-working answer is the expensive kind.
    """

    async def test_an_explicit_provider_is_used_even_when_another_is_available(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None, stt_provider="openai")
        env = {"GROQ_API_KEY": "gsk_from_env", "OPENAI_API_KEY": "sk-from-env"}
        with patch.dict("os.environ", env, clear=True):
            provider, key, _ = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertEqual((provider, key), ("openai", "sk-from-env"))

    async def test_an_explicit_provider_does_not_silently_fall_back(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None, stt_provider="openai")
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_from_env"}, clear=True):
            provider, key, source = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertIsNone(provider)
        self.assertEqual(source, "none")

    async def test_no_explicit_provider_keeps_the_groq_then_openai_order(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        env = {"GROQ_API_KEY": "gsk_from_env", "OPENAI_API_KEY": "sk-from-env"}
        with patch.dict("os.environ", env, clear=True):
            provider, key, _ = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertEqual((provider, key), ("groq", "gsk_from_env"))


class CustomEndpointTests(unittest.IsolatedAsyncioTestCase):
    """Any OpenAI-compatible transcription server, including a local one.

    This is the multi-provider extension point AND the lowest-latency option:
    whisper.cpp, faster-whisper-server and LocalAI all serve OpenAI-shaped
    `/v1/audio/transcriptions`, so pointing STT_BASE_URL at one on the same
    machine removes the provider network hop entirely. It costs no new
    dependency -- the `openai` SDK is already here and takes a base_url.
    """

    async def test_a_custom_endpoint_resolves_without_any_api_key(self):
        """whisper.cpp in server mode requires no secret, so a key must be optional."""
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(
            sentient_secret_key=None,
            stt_provider="custom",
            stt_base_url="http://127.0.0.1:8080/v1",
        )
        with patch.dict("os.environ", {}, clear=True):
            provider, _, source = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertEqual(provider, "custom")
        self.assertIn("custom", source)

    async def test_a_custom_endpoint_needs_a_base_url_to_be_selectable(self):
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None, stt_provider="custom")
        with patch.dict("os.environ", {}, clear=True):
            provider, _, _ = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertIsNone(provider)

    def test_a_custom_endpoint_passes_the_requested_model_through(self):
        """No remapping: a self-hosted server names its models whatever it likes."""
        from sentient.adapters.stt.client import upstream_model

        self.assertEqual(upstream_model("custom", "ggml-large-v3"), "ggml-large-v3")


class ConsoleIdentityTests(unittest.IsolatedAsyncioTestCase):
    """The console authenticates with a JWT; Mantella sends a provider key.

    Both arrive in `Authorization: Bearer` on this one route, so the header means
    two different things depending on who is calling. `resolve_identity` has to
    pick identity out of it WITHOUT ever treating a Whisper credential as a login
    attempt -- a JWKS verify on Mantella's key would be a wasted round trip on the
    critical path of every spoken line, and a confusing 401 when it failed.
    """

    async def test_a_bearer_jwt_resolves_sentient_identity(self):
        from sentient.services import transcription as service

        resolved = {}

        async def fake_resolve_user(state, settings, *, jwt_token=None, api_key=None, cache=None):
            resolved["jwt"] = jwt_token
            resolved["api_key"] = api_key
            return ("user-123", "key-123")

        with patch("sentient.adapters.auth.resolve_user", fake_resolve_user):
            user_id = await service.resolve_identity(
                None, SimpleNamespace(), None, None, authorization=f"Bearer {FAKE_JWT}"
            )

        self.assertEqual(user_id, "user-123")
        self.assertEqual(resolved["jwt"], FAKE_JWT)
        self.assertIsNone(resolved["api_key"])

    async def test_a_forwarded_provider_key_is_never_treated_as_a_login(self):
        from sentient.services import transcription as service

        called = False

        async def fake_resolve_user(*args, **kwargs):
            nonlocal called
            called = True
            return ("user-123", "key-123")

        with patch("sentient.adapters.auth.resolve_user", fake_resolve_user):
            user_id = await service.resolve_identity(
                None, SimpleNamespace(), None, None, authorization="Bearer gsk_mantella"
            )

        self.assertIsNone(user_id)
        self.assertFalse(called, "a Whisper key must not cost a JWKS round trip")

    async def test_an_api_key_still_resolves_identity(self):
        """Mantella's own Sentient product key path, unchanged."""
        from sentient.services import transcription as service

        resolved = {}

        async def fake_resolve_user(state, settings, *, jwt_token=None, api_key=None, cache=None):
            resolved["api_key"] = api_key
            return ("user-123", "key-123")

        with patch("sentient.adapters.auth.resolve_user", fake_resolve_user):
            user_id = await service.resolve_identity(
                None, SimpleNamespace(), None, "sk-sent-abc", authorization=None
            )

        self.assertEqual(user_id, "user-123")
        self.assertEqual(resolved["api_key"], "sk-sent-abc")

    async def test_anonymous_stays_anonymous(self):
        """The single-user local mode: no credential at all is not an error."""
        from sentient.services import transcription as service

        user_id = await service.resolve_identity(
            None, SimpleNamespace(), None, None, authorization=None
        )
        self.assertIsNone(user_id)


class MantellaIdentityTests(unittest.IsolatedAsyncioTestCase):
    """Mantella can only send ONE credential to the Whisper URL.

    Its config has a single secret field for that endpoint (`GPT_SECRET_KEY.txt`),
    forwarded as `Authorization: Bearer`, and no header for `X-API-Key` at all. A
    Sentient product key put there was already refused as a provider secret --
    correctly -- but nothing then read it as identity either, so every in-game
    utterance arrived anonymous: the server's env key instead of the player's
    vault key, and diagnostics dropped into the shared "default" bucket where the
    console (reading its own) could never see them.
    """

    async def test_a_sentient_key_in_the_bearer_header_resolves_identity(self):
        from sentient.services import transcription as service

        seen = {}

        async def fake_resolve_user(state, settings, *, jwt_token=None, api_key=None, cache=None):
            seen["jwt"] = jwt_token
            seen["api_key"] = api_key
            return ("user-123", "key-123")

        with patch("sentient.adapters.auth.resolve_user", fake_resolve_user):
            user_id = await service.resolve_identity(
                None, SimpleNamespace(), None, None, authorization="Bearer sk-sent-abcdef"
            )

        self.assertEqual(user_id, "user-123")
        self.assertEqual(seen["api_key"], "sk-sent-abcdef")
        self.assertIsNone(seen["jwt"], "a product key is not a JWT and must not be verified as one")

    async def test_an_explicit_api_key_header_still_wins(self):
        """X-API-Key is the unambiguous identity header; Bearer is the overloaded one."""
        from sentient.services import transcription as service

        seen = {}

        async def fake_resolve_user(state, settings, *, jwt_token=None, api_key=None, cache=None):
            seen["api_key"] = api_key
            return ("user-123", "key-123")

        with patch("sentient.adapters.auth.resolve_user", fake_resolve_user):
            await service.resolve_identity(
                None,
                SimpleNamespace(),
                None,
                "sk-sent-from-header",
                authorization="Bearer sk-sent-from-bearer",
            )

        self.assertEqual(seen["api_key"], "sk-sent-from-header")

    async def test_a_whisper_key_is_still_not_identity(self):
        from sentient.services import transcription as service

        called = False

        async def fake_resolve_user(*args, **kwargs):
            nonlocal called
            called = True
            return ("user-123", "key-123")

        with patch("sentient.adapters.auth.resolve_user", fake_resolve_user):
            user_id = await service.resolve_identity(
                None, SimpleNamespace(), None, None, authorization="Bearer gsk_mantella"
            )

        self.assertIsNone(user_id)
        self.assertFalse(called)

    async def test_a_sentient_key_is_still_never_sent_to_a_provider(self):
        """Reading it as identity must not also make it a candidate credential."""
        from sentient.adapters.stt.client import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider, key, _ = await resolve_stt_credential(
                None, settings, authorization="Bearer sk-sent-abcdef", user_id="user-123"
            )
        self.assertIsNone(provider)
        self.assertIsNone(key)
