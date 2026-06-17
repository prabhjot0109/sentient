from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

import api
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


if __name__ == "__main__":
    unittest.main()
