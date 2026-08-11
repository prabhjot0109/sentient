from __future__ import annotations

import io
import unittest
import wave
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
        from logic.stt import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_from_env"}, clear=False):
            provider, key, source = await resolve_stt_credential(
                None, settings, authorization="Bearer gsk_from_mantella", user_id=None
            )
        self.assertEqual((provider, key), ("groq", "gsk_from_mantella"))
        self.assertIn("forward", source.lower())

    async def test_forwarded_openai_key_selects_openai(self):
        from logic.stt import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        provider, key, _ = await resolve_stt_credential(
            None, settings, authorization="Bearer sk-abc123", user_id=None
        )
        self.assertEqual((provider, key), ("openai", "sk-abc123"))

    async def test_a_sentient_product_key_is_never_used_as_a_provider_key(self):
        from logic.stt import resolve_stt_credential

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
        from logic.credentials import encrypt_key
        from logic.stt import resolve_stt_credential

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
        from logic.stt import resolve_stt_credential

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
        from logic.stt import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_env"}, clear=False):
            provider, key, source = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertEqual((provider, key), ("groq", "gsk_env"))
        self.assertIn("env", source.lower())

    async def test_no_credential_anywhere_resolves_to_nothing(self):
        from logic.stt import resolve_stt_credential

        settings = SimpleNamespace(sentient_secret_key=None)
        with patch.dict("os.environ", {}, clear=True):
            provider, key, _ = await resolve_stt_credential(
                None, settings, authorization=None, user_id=None
            )
        self.assertIsNone(provider)
        self.assertIsNone(key)


class UpstreamModelTests(unittest.TestCase):
    def test_whisper_1_is_remapped_for_groq(self):
        from logic.stt import upstream_model

        # Groq only serves the large-v3 family; whisper-1 is OpenAI-only and 400s.
        self.assertEqual(upstream_model("groq", "whisper-1"), "whisper-large-v3-turbo")

    def test_groq_model_is_passed_through(self):
        from logic.stt import upstream_model

        self.assertEqual(
            upstream_model("groq", "whisper-large-v3"), "whisper-large-v3"
        )

    def test_openai_falls_back_to_its_only_model(self):
        from logic.stt import upstream_model

        self.assertEqual(upstream_model("openai", "whisper-large-v3-turbo"), "whisper-1")


class TranscriptionEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def _post(self, audio: bytes, **kwargs):
        import api

        transport = httpx.ASGITransport(app=api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/audio/transcriptions",
                files={"file": ("mic.wav", audio, "audio/wav")},
                data={"model": "whisper-large-v3-turbo"},
                **kwargs,
            )

    async def test_transcription_is_returned_and_uses_the_forwarded_key(self):
        import logic.stt as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="hello there")
        with patch.object(stt, "stt_client", return_value=fake) as build:
            response = await self._post(
                SPEECH, headers={"Authorization": "Bearer gsk_forwarded"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "hello there")
        build.assert_called_once_with("groq", "gsk_forwarded")

    async def test_text_invented_from_silence_is_discarded(self):
        import logic.stt as stt

        fake = MagicMock()
        # Whisper's signature hallucination on a dead mic.
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="Thank you.")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(
                SILENCE, headers={"Authorization": "Bearer gsk_forwarded"}
            )

        self.assertEqual(response.status_code, 200)
        # Empty => Mantella replays its "could not detect speech" cue instead of
        # making the NPC answer a line the player never spoke.
        self.assertEqual(response.json()["text"], "")

    async def test_healthy_audio_is_never_discarded(self):
        import logic.stt as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="Thank you.")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(
                SPEECH, headers={"Authorization": "Bearer gsk_forwarded"}
            )

        self.assertEqual(response.json()["text"], "Thank you.")

    async def test_missing_credentials_are_rejected_before_any_upstream_call(self):
        import logic.stt as stt

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(stt, "stt_client") as build,
        ):
            response = await self._post(SPEECH)

        self.assertEqual(response.status_code, 400)
        build.assert_not_called()

    async def test_upstream_failure_surfaces_as_bad_gateway(self):
        import logic.stt as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.side_effect = RuntimeError("groq is down")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(
                SPEECH, headers={"Authorization": "Bearer gsk_forwarded"}
            )

        self.assertEqual(response.status_code, 502)

    async def test_optional_fields_are_only_sent_when_set(self):
        import api
        import logic.stt as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="hi")
        transport = httpx.ASGITransport(app=api.app)
        with patch.object(stt, "stt_client", return_value=fake):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
        import api
        import logic.stt as stt

        api._STT_HISTORY.clear()
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
        import api

        api._STT_HISTORY.clear()
        for i in range(api._STT_HISTORY_LIMIT + 10):
            api._record_stt_history({"time": str(i), "text": "x"})

        self.assertEqual(len(api._STT_HISTORY), api._STT_HISTORY_LIMIT)
        # Oldest dropped, newest kept.
        self.assertEqual(api._STT_HISTORY[-1]["time"], str(api._STT_HISTORY_LIMIT + 9))

    async def test_no_raw_key_is_returned_on_any_path(self):
        import logic.stt as stt

        fake = MagicMock()
        fake.audio.transcriptions.create.return_value = SimpleNamespace(text="hi")
        with patch.object(stt, "stt_client", return_value=fake):
            response = await self._post(
                SPEECH, headers={"Authorization": "Bearer gsk_super_secret"}
            )

        self.assertNotIn("gsk_super_secret", response.text)


if __name__ == "__main__":
    unittest.main()
