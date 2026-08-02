from __future__ import annotations

import io
import os
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

import api
from logic.audio_diagnostics import analyse_wav, explain_empty_transcription
from logic.config import load_rag_settings


class FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        return [
            float(sum(ord(char) for char in lowered) % 997),
            float(len(lowered)),
            float(lowered.count("sentinel") * 10 + lowered.count("archives") * 5),
        ]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class BuildEmbeddingsProviderTests(unittest.TestCase):
    def test_google_provider_constructs_google_embeddings(self):
        import logic.ingestion as ingestion_module

        ingestion_module.build_embeddings.cache_clear()
        with patch.object(ingestion_module, "GoogleGenerativeAIEmbeddings") as mock_cls:
            mock_cls.return_value = "google-embeddings-instance"
            result = ingestion_module.build_embeddings(
                "google", "models/gemini-embedding-001", None, "AIzaTest"
            )

        mock_cls.assert_called_once_with(
            model="models/gemini-embedding-001",
            google_api_key="AIzaTest",
        )
        self.assertEqual(result, "google-embeddings-instance")
        ingestion_module.build_embeddings.cache_clear()


class BuildChatModelProviderTests(unittest.TestCase):
    def test_google_provider_constructs_chat_google_generative_ai(self):
        import logic.rag_engine as rag_engine_module

        rag_engine_module.build_chat_model.cache_clear()
        with patch.object(rag_engine_module, "ChatGoogleGenerativeAI") as mock_cls:
            mock_cls.return_value = "google-chat-instance"
            result = rag_engine_module.build_chat_model(
                "google", "gemini-2.5-flash", None, "AIzaTest", 60.0
            )

        mock_cls.assert_called_once_with(
            model="gemini-2.5-flash",
            google_api_key="AIzaTest",
            timeout=60.0,
        )
        self.assertEqual(result, "google-chat-instance")
        rag_engine_module.build_chat_model.cache_clear()

    def test_huggingface_provider_allows_no_api_key(self):
        import logic.rag_engine as rag_engine_module

        rag_engine_module.build_chat_model.cache_clear()
        with patch.object(rag_engine_module, "ChatHuggingFace") as mock_chat_cls, patch.object(
            rag_engine_module, "HuggingFaceEndpoint"
        ) as mock_endpoint_cls:
            mock_endpoint_cls.return_value = "endpoint-instance"
            mock_chat_cls.return_value = "hf-chat-instance"
            result = rag_engine_module.build_chat_model(
                "huggingface", "Qwen/Qwen2.5-7B-Instruct", None, None, 60.0
            )

        mock_endpoint_cls.assert_called_once_with(
            repo_id="Qwen/Qwen2.5-7B-Instruct",
            huggingfacehub_api_token=None,
            timeout=60.0,
        )
        mock_chat_cls.assert_called_once_with(llm="endpoint-instance")
        self.assertEqual(result, "hf-chat-instance")
        rag_engine_module.build_chat_model.cache_clear()


class SentientRAGTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.index_path = self.data_dir / "faiss_index"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.env_patcher = patch.dict(
            os.environ,
            {
                "DATA_DIR": str(self.data_dir),
                "FAISS_INDEX_PATH": str(self.index_path),
            },
            clear=False,
        )
        self.env_patcher.start()

        api.brain = None
        api.supabase_client = None
        api.get_default_archives.cache_clear()
        api.get_local_chat_store.cache_clear()

    def tearDown(self):
        self.env_patcher.stop()
        self.temp_dir.cleanup()

    def test_google_settings_enable_google_embeddings_and_llm(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "AIzaTest",
            },
            clear=False,
        ):
            settings = load_rag_settings()

        self.assertEqual(settings.llm_provider, "google")
        self.assertEqual(settings.embedding_provider, "google")
        self.assertEqual(settings.llm_model, "gemini-2.5-flash")
        self.assertEqual(settings.embedding_model, "models/gemini-embedding-001")

    def test_no_key_settings_fall_back_to_huggingface(self):
        settings = load_rag_settings()

        self.assertEqual(settings.llm_provider, "huggingface")
        self.assertEqual(settings.embedding_provider, "huggingface")
        self.assertEqual(settings.llm_model, "Qwen/Qwen2.5-7B-Instruct")
        self.assertEqual(settings.embedding_model, "BAAI/bge-base-en-v1.5")

    def test_upload_retrieve_and_delete_pipeline(self):
        lore_text = (
            "Sentinel is the guardian of the archives.\n"
            "The core technology is Retrieval Augmented Generation."
        )

        with patch("logic.ingestion.build_embeddings", return_value=FakeEmbeddings()):
            client = TestClient(api.app)

            upload_response = client.post(
                "/v1/upload",
                files={"file": ("lore.txt", lore_text.encode("utf-8"), "text/plain")},
            )
            self.assertEqual(upload_response.status_code, 200)
            self.assertTrue((self.data_dir / "lore.txt").exists())

            health_response = client.get("/health")
            self.assertEqual(health_response.status_code, 200)
            self.assertTrue(health_response.json()["index_loaded"])

            retrieve_response = client.post(
                "/v1/retrieve",
                json={"query": "Who guards the archives?", "top_k": 2},
            )
            self.assertEqual(retrieve_response.status_code, 200)
            payload = retrieve_response.json()
            self.assertTrue(payload["chunks"])
            self.assertEqual(payload["chunks"][0]["source"], "lore.txt")
            self.assertIn("guardian", payload["chunks"][0]["content"].lower())

            delete_response = client.delete("/v1/sources/lore.txt")
            self.assertEqual(delete_response.status_code, 200)
            self.assertFalse((self.data_dir / "lore.txt").exists())

    def test_refresh_knowledge_reflects_uploads_and_deletes_from_another_instance(self):
        """Regression test: NPCBrain.refresh_knowledge() must actually pick up
        index changes written by a *different* ArchivesIngestion instance, the
        way api.py's upload/delete handlers write via get_default_archives()
        while a long-lived NPCBrain holds its own ArchivesIngestion. Previously
        refresh_knowledge() was a no-op after the first load because
        load_index() returned its cached FAISS handle unconditionally."""
        with patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "AIzaTest", "RAG_SCORE_THRESHOLD": "0"},
            clear=False,
        ), patch("logic.ingestion.build_embeddings", return_value=FakeEmbeddings()):
            from logic.ingestion import ArchivesIngestion
            from npc_brain import NPCBrain

            brain = NPCBrain(api_key="AIzaTest")
            uploader = ArchivesIngestion(api_key="AIzaTest")

            doc1 = self.data_dir / "sentinel.txt"
            doc1.write_text("Sentinel is the guardian of the archives.", encoding="utf-8")
            uploader.add_file(str(doc1))
            brain.refresh_knowledge()
            sources = {match["source"] for match in brain.retrieve("archives", k=10)}
            self.assertIn("sentinel.txt", sources)

            doc2 = self.data_dir / "second.txt"
            doc2.write_text("A second archive document about lore.", encoding="utf-8")
            uploader.add_file(str(doc2))
            brain.refresh_knowledge()
            sources = {match["source"] for match in brain.retrieve("archives", k=10)}
            self.assertIn(
                "second.txt",
                sources,
                "newly uploaded document should be retrievable after refresh_knowledge()",
            )

            doc1.unlink()
            uploader.remove_file("sentinel.txt")
            brain.refresh_knowledge()
            sources = {match["source"] for match in brain.retrieve("archives", k=10)}
            self.assertNotIn(
                "sentinel.txt",
                sources,
                "deleted document should no longer be retrievable after refresh_knowledge()",
            )

    def test_chat_history_falls_back_to_local_store(self):
        client = TestClient(api.app)
        payload = {
            "client_id": "test-client",
            "title": "Sentinel chat",
            "preview": "Preview",
            "messages": [
                {
                    "id": "message-1",
                    "role": "user",
                    "content": "Hello Sentinel",
                    "timestamp": "2026-03-30T00:00:00+00:00",
                }
            ],
        }

        create_response = client.post("/v1/chats", json=payload)
        self.assertEqual(create_response.status_code, 200)
        created_chat = create_response.json()

        list_response = client.get("/v1/chats", params={"client_id": "test-client"})
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["count"], 1)

        get_response = client.get(
            f"/v1/chats/{created_chat['id']}",
            params={"client_id": "test-client"},
        )
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["title"], "Sentinel chat")

    def test_openai_chat_completions_endpoint(self):
        client = TestClient(api.app)
        payload = {
            "messages": [{"role": "user", "content": "Hello Dragonborn"}],
            "model": "gpt-4o-mini",
            "stream": False,
        }
        with patch("api.build_chat_model") as mock_build, patch("api.get_archives") as mock_archives:
            mock_llm = mock_build.return_value
            mock_llm.invoke.return_value.content = "Greetings traveler!"
            mock_archives.return_value.retrieve.return_value = []

            response = client.post("/v1/chat/completions", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["choices"][0]["message"]["content"], "Greetings traveler!")


def wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Encode mono float samples as 16-bit PCM WAV, matching Mantella's capture format."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes((np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def speech_like(seconds: float = 2.0, rms: float = 0.15, sample_rate: int = 16000) -> np.ndarray:
    """A tone mix scaled to a target RMS, standing in for a spoken utterance."""
    t = np.linspace(0, seconds, int(seconds * sample_rate), endpoint=False)
    wave_form = np.sin(2 * np.pi * 180 * t) + 0.5 * np.sin(2 * np.pi * 440 * t)
    current = float(np.sqrt(np.mean(np.square(wave_form))))
    return wave_form * (rms / current) if current else wave_form


class AudioDiagnosticsTests(unittest.TestCase):
    """Levels are taken from real Mantella captures: the recordings that failed
    measured 0.000-0.010 RMS, every one that transcribed measured 0.120-0.209."""

    def test_all_zero_capture_is_reported_as_silent(self):
        report = analyse_wav(wav_bytes(np.zeros(16000)))
        self.assertEqual(report.verdict, "SILENT")
        self.assertFalse(report.speech_plausible)

    def test_barely_open_mic_is_reported_as_very_quiet(self):
        # Mirrors mic_input_20260731_164448.wav: signal present, but ~15x too quiet.
        report = analyse_wav(wav_bytes(speech_like(seconds=1.5, rms=0.005)))
        self.assertEqual(report.verdict, "VERY_QUIET")
        self.assertFalse(report.speech_plausible)

    def test_healthy_utterance_is_ok(self):
        report = analyse_wav(wav_bytes(speech_like(seconds=2.0, rms=0.15)))
        self.assertEqual(report.verdict, "OK")
        self.assertTrue(report.speech_plausible)
        self.assertAlmostEqual(report.duration_s, 2.0, places=2)
        self.assertEqual(report.sample_rate, 16000)

    def test_brief_capture_is_reported_as_too_short(self):
        report = analyse_wav(wav_bytes(speech_like(seconds=0.2, rms=0.15)))
        self.assertEqual(report.verdict, "TOO_SHORT")

    def test_clipped_capture_is_flagged(self):
        report = analyse_wav(wav_bytes(np.ones(32000) * 1.5))
        self.assertEqual(report.verdict, "CLIPPING")

    def test_short_push_to_talk_hold_raises_a_warning(self):
        report = analyse_wav(wav_bytes(speech_like(seconds=0.5, rms=0.15)))
        self.assertTrue(any("push-to-talk" in w for w in report.warnings))

    def test_unparseable_payload_degrades_instead_of_raising(self):
        report = analyse_wav(b"not a wav file at all")
        self.assertEqual(report.verdict, "UNREADABLE")
        # Diagnostics must never be the reason a transcription is refused.
        self.assertTrue(report.speech_plausible)

    def test_empty_transcription_blames_the_model_when_audio_was_fine(self):
        report = analyse_wav(wav_bytes(speech_like(seconds=2.0, rms=0.15)))
        self.assertIn("STT model", explain_empty_transcription(report))

    def test_empty_transcription_blames_the_mic_when_audio_was_silent(self):
        report = analyse_wav(wav_bytes(np.zeros(16000)))
        self.assertIn("no signal", explain_empty_transcription(report))


class STTProviderResolutionTests(unittest.TestCase):
    def test_forwarded_groq_key_wins_over_environment(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env"}, clear=False):
            provider, key = api._resolve_stt_provider("Bearer gsk_forwarded")
        self.assertEqual((provider, key), ("groq", "gsk_forwarded"))

    def test_forwarded_openai_key_selects_openai(self):
        provider, key = api._resolve_stt_provider("Bearer sk-forwarded")
        self.assertEqual((provider, key), ("openai", "sk-forwarded"))

    def test_environment_is_used_when_no_header_is_forwarded(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_env", "OPENAI_API_KEY": ""}, clear=False):
            provider, key = api._resolve_stt_provider(None)
        self.assertEqual((provider, key), ("groq", "gsk_env"))

    def test_no_credential_anywhere_resolves_to_nothing(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
            self.assertEqual(api._resolve_stt_provider(None), (None, None))


class AudioTranscriptionEndpointTests(unittest.TestCase):
    def setUp(self):
        api._STT_HISTORY.clear()
        self.client = TestClient(api.app)
        self.audio = wav_bytes(speech_like(seconds=2.0, rms=0.15))

        # Transcription clients are cached and reused across utterances (that reuse
        # is what saves the TLS handshake), so a client built from one test's mock
        # would otherwise be handed to every later test.
        api._stt_client.cache_clear()

        # A successful transcription kicks off a speculative lore lookup. Stub the
        # retrieval so the tests exercise that wiring without embedding over the
        # network on a background thread.
        api._lore_prefetch = None
        lore_patch = patch.object(api, "_retrieve_lore", return_value=[])
        lore_patch.start()
        self.addCleanup(lore_patch.stop)

    def _post(self, text: str, **kwargs):
        transcript = SimpleNamespace(text=text)
        # Each call installs its own mock, so the cached client from a previous
        # call has to go -- in production that cache is per-process and lives for
        # the life of the server, which is the point of it.
        api._stt_client.cache_clear()
        with patch("groq.Groq") as mock_groq:
            mock_groq.return_value.audio.transcriptions.create.return_value = transcript
            response = self.client.post(
                "/v1/audio/transcriptions",
                files={"file": ("mic.wav", self.audio, "audio/wav")},
                headers={"Authorization": "Bearer gsk_test"},
                **kwargs,
            )
        return response, mock_groq

    def test_transcription_is_returned_and_upstream_uses_forwarded_key(self):
        response, mock_groq = self._post("Who is Miraak?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"text": "Who is Miraak?"})
        mock_groq.assert_called_once_with(api_key="gsk_test")

    def test_whisper_1_is_remapped_to_a_model_groq_actually_serves(self):
        transcript = SimpleNamespace(text="hello")
        with patch("groq.Groq") as mock_groq:
            mock_groq.return_value.audio.transcriptions.create.return_value = transcript
            self.client.post(
                "/v1/audio/transcriptions",
                files={"file": ("mic.wav", self.audio, "audio/wav")},
                data={"model": "whisper-1"},
                headers={"Authorization": "Bearer gsk_test"},
            )
        sent = mock_groq.return_value.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(sent["model"], "whisper-large-v3-turbo")

    def test_placeholder_language_is_not_forwarded_upstream(self):
        transcript = SimpleNamespace(text="hello")
        with patch("groq.Groq") as mock_groq:
            mock_groq.return_value.audio.transcriptions.create.return_value = transcript
            self.client.post(
                "/v1/audio/transcriptions",
                files={"file": ("mic.wav", self.audio, "audio/wav")},
                data={"language": "default"},
                headers={"Authorization": "Bearer gsk_test"},
            )
        sent = mock_groq.return_value.audio.transcriptions.create.call_args.kwargs
        self.assertNotIn("language", sent)

    def test_empty_transcription_still_succeeds_and_is_recorded(self):
        response, _ = self._post("   ")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"text": ""})
        self.assertEqual(api._STT_HISTORY[-1]["text"], "")
        self.assertEqual(api._STT_HISTORY[-1]["audio"]["verdict"], "OK")

    def test_transcription_invented_from_silence_is_discarded(self):
        # Groq really does return "Thank you." for mic_input_20260731_164722.wav,
        # which is an all-zero capture. That must never reach the NPC.
        self.audio = wav_bytes(np.zeros(16000))
        response, _ = self._post("Thank you.")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"text": ""})
        self.assertEqual(api._STT_HISTORY[-1]["discarded_hallucination"], "Thank you.")
        self.assertEqual(api._STT_HISTORY[-1]["audio"]["verdict"], "SILENT")

    def test_transcription_from_healthy_audio_is_never_discarded(self):
        response, _ = self._post("Who is Miraak?")

        self.assertEqual(response.json(), {"text": "Who is Miraak?"})
        self.assertEqual(api._STT_HISTORY[-1]["discarded_hallucination"], "")

    def test_text_response_format_returns_bare_text(self):
        response, _ = self._post("Who is Miraak?", data={"response_format": "text"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Who is Miraak?")

    def test_client_is_reused_across_utterances(self):
        """Building a client per utterance costs a fresh TCP + TLS handshake."""
        transcript = SimpleNamespace(text="hello")
        with patch("groq.Groq") as mock_groq:
            mock_groq.return_value.audio.transcriptions.create.return_value = transcript
            for _ in range(3):
                self.client.post(
                    "/v1/audio/transcriptions",
                    files={"file": ("mic.wav", self.audio, "audio/wav")},
                    headers={"Authorization": "Bearer gsk_test"},
                )

        self.assertEqual(mock_groq.call_count, 1)
        self.assertEqual(
            mock_groq.return_value.audio.transcriptions.create.call_count, 3
        )

    def test_successful_transcription_prefetches_its_own_lore(self):
        """The completion request that follows should find the lookup already done."""
        self._post("Who is Miraak?")

        pending = api.take_prefetched_lore("Who is Miraak?")
        self.assertIsNotNone(pending)
        self.assertEqual(pending.result(timeout=5), [])
        api._retrieve_lore.assert_called_once()
        self.assertEqual(api._retrieve_lore.call_args.args[0], "Who is Miraak?")

    def test_discarded_hallucination_does_not_prefetch_lore(self):
        self.audio = wav_bytes(np.zeros(16000))
        self._post("Thank you.")

        self.assertIsNone(api.take_prefetched_lore("Thank you."))
        api._retrieve_lore.assert_not_called()

    def test_upstream_failure_surfaces_as_bad_gateway(self):
        with patch("groq.Groq") as mock_groq:
            mock_groq.return_value.audio.transcriptions.create.side_effect = RuntimeError("boom")
            response = self.client.post(
                "/v1/audio/transcriptions",
                files={"file": ("mic.wav", self.audio, "audio/wav")},
                headers={"Authorization": "Bearer gsk_test"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(api._STT_HISTORY[-1]["error"], "boom")

    def test_missing_credentials_are_rejected_before_any_upstream_call(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
            response = self.client.post(
                "/v1/audio/transcriptions",
                files={"file": ("mic.wav", self.audio, "audio/wav")},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("GROQ_API_KEY", response.json()["detail"])

    def test_recent_endpoint_reports_transcriptions_and_silence_count(self):
        self._post("Who is Miraak?")
        self._post("")

        payload = self.client.get("/v1/audio/transcriptions/recent").json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["empty_transcriptions"], 1)
        # Newest first, so the silent attempt leads.
        self.assertEqual(payload["transcriptions"][0]["text"], "")


if __name__ == "__main__":
    unittest.main()

