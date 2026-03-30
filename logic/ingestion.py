from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from logic.config import RAGSettings, load_rag_settings


@lru_cache(maxsize=16)
def build_embeddings(
    provider: str,
    model_name: str,
    base_url: str | None,
    api_key: str | None,
):
    if provider == "huggingface":
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    if not api_key:
        raise ValueError(
            f"{provider.title()} embeddings require an API key. Set it in the environment "
            "or send it from the client."
        )

    return OpenAIEmbeddings(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout=60,
    )


class ArchivesIngestion:
    SUPPORTED_EXTENSIONS = (".txt", ".pdf")
    MANIFEST_FILE = "manifest.json"

    def __init__(
        self,
        data_dir: str | None = None,
        index_path: str | None = None,
        *,
        api_key: str | None = None,
        settings: RAGSettings | None = None,
    ):
        self.settings = settings or load_rag_settings(api_key)
        self.data_dir = Path(data_dir or self.settings.data_dir)
        self.index_path = Path(index_path or self.settings.index_path)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self._vector_store: FAISS | None = None

    @property
    def embeddings(self):
        return build_embeddings(
            self.settings.embedding_provider,
            self.settings.embedding_model,
            self.settings.embedding_base_url,
            self.settings.embedding_api_key,
        )

    @property
    def manifest_path(self) -> Path:
        return self.index_path / self.MANIFEST_FILE

    def index_exists(self) -> bool:
        return self.index_path.exists() and self.manifest_path.exists()

    def get_index_metadata(self) -> dict[str, Any] | None:
        if not self.manifest_path.exists():
            return None

        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _manifest_matches_runtime(self, manifest: dict[str, Any] | None) -> bool:
        if not manifest:
            return False

        return (
            manifest.get("embedding_provider") == self.settings.embedding_provider
            and manifest.get("embedding_model") == self.settings.embedding_model
            and manifest.get("chunk_size") == self.settings.chunk_size
            and manifest.get("chunk_overlap") == self.settings.chunk_overlap
        )

    def _is_supported_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def _resolve_source_files(self, source_path: str | None = None) -> list[Path]:
        target_path = Path(source_path) if source_path else self.data_dir

        if target_path.is_file():
            return [target_path] if self._is_supported_file(target_path) else []

        if not target_path.exists():
            return []

        return sorted(
            path for path in target_path.rglob("*") if self._is_supported_file(path)
        )

    def list_sources(self) -> list[dict[str, str | int]]:
        return [
            {
                "name": path.name,
                "path": str(path),
                "size": path.stat().st_size,
            }
            for path in self._resolve_source_files()
        ]

    def _load_file(self, path: Path) -> list[Document]:
        if path.suffix.lower() == ".pdf":
            documents = PyPDFLoader(str(path)).load()
        else:
            documents = TextLoader(
                str(path), encoding="utf-8", autodetect_encoding=True
            ).load()

        for document in documents:
            page_number = document.metadata.get("page")
            document.metadata.update(
                {
                    "source": path.name,
                    "source_path": str(path),
                    "file_type": path.suffix.lower().lstrip("."),
                    "page_label": f", page {page_number + 1}"
                    if page_number is not None
                    else "",
                }
            )

        return documents

    def _load_documents(self, source_path: str | None = None) -> list[Document]:
        documents: list[Document] = []
        for file_path in self._resolve_source_files(source_path):
            documents.extend(self._load_file(file_path))
        return documents

    def _split_documents(self, documents: list[Document]) -> list[Document]:
        chunks = self.text_splitter.split_documents(documents)
        for index, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = index
            chunk.metadata["chunk_size"] = len(chunk.page_content)
        return chunks

    def _write_manifest(
        self,
        *,
        source_files: list[Path],
        chunks: list[Document],
    ) -> dict[str, Any]:
        manifest = {
            "embedding_provider": self.settings.embedding_provider,
            "embedding_model": self.settings.embedding_model,
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "source_count": len(source_files),
            "chunk_count": len(chunks),
            "sources": [path.name for path in source_files],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return manifest

    def reset_index(self):
        self._vector_store = None
        if self.index_path.exists():
            shutil.rmtree(self.index_path)

    def rebuild_index(self, source_path: str | None = None):
        source_files = self._resolve_source_files(source_path)
        documents = self._load_documents(source_path)

        self.reset_index()

        if not documents:
            return None

        chunks = self._split_documents(documents)
        db = FAISS.from_documents(chunks, self.embeddings)
        self.index_path.mkdir(parents=True, exist_ok=True)
        db.save_local(str(self.index_path))
        self._write_manifest(source_files=source_files, chunks=chunks)
        self._vector_store = db
        print(f"Archives updated. Index saved to {self.index_path}")
        return db

    def ingest(self, source_path: str):
        return self.rebuild_index(str(self.data_dir))

    def ensure_index(self):
        index = self.load_index()
        if index is not None:
            return index
        return self.rebuild_index(str(self.data_dir))

    def load_index(self):
        manifest = self.get_index_metadata()
        if not self.index_path.exists() or not self._manifest_matches_runtime(manifest):
            self._vector_store = None
            return None

        if self._vector_store is not None:
            return self._vector_store

        self._vector_store = FAISS.load_local(
            str(self.index_path),
            self.embeddings,
            allow_dangerous_deserialization=True,
        )
        return self._vector_store

    def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        fetch_k: int | None = None,
        search_type: str | None = None,
        lambda_mult: float | None = None,
    ) -> list[tuple[Document, float | None]]:
        vector_store = self.ensure_index()
        if vector_store is None:
            return []

        resolved_k = max(k or self.settings.top_k, 1)
        resolved_fetch_k = max(fetch_k or self.settings.fetch_k, resolved_k)
        resolved_search_type = (search_type or self.settings.search_type).lower()
        resolved_lambda_mult = lambda_mult or self.settings.lambda_mult

        if resolved_search_type == "similarity":
            try:
                return vector_store.similarity_search_with_relevance_scores(
                    query,
                    k=resolved_k,
                )
            except Exception:
                documents = vector_store.similarity_search(query, k=resolved_k)
                return [(document, None) for document in documents]

        documents = vector_store.max_marginal_relevance_search(
            query,
            k=resolved_k,
            fetch_k=resolved_fetch_k,
            lambda_mult=resolved_lambda_mult,
        )
        return [(document, None) for document in documents]
