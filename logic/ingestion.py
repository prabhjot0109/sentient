from __future__ import annotations

import io
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from logic.config import RAGSettings, load_rag_settings
from logic.persona import GENERIC_PERSONA

# OCR is optional: scanned/image-only PDFs need it, but text PDFs don't, and the
# Tesseract binary may not be installed. Import lazily so ingestion never hard-fails.
try:
    import pymupdf
    import pytesseract
    from PIL import Image

    _OCR_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depends on the environment
    pymupdf = None  # type: ignore[assignment]
    pytesseract = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]
    _OCR_IMPORT_ERROR = exc


# Guards the FAISS merge + save step in ArchivesIngestion.add_file so concurrent
# uploads (each running in its own worker thread) can't write the on-disk index
# at the same time. Module-level because multiple ArchivesIngestion instances
# can point at the same index_path (e.g. one per API key).
_INDEX_WRITE_LOCK = threading.Lock()


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

    if provider == "google":
        return GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=api_key,
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
    # A page with fewer real characters than this is treated as scanned/empty and
    # sent through OCR. Keeps genuinely sparse pages from triggering needless OCR.
    OCR_MIN_CHARS = 10

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

    def _ocr_pdf_pages(self, path: Path, documents: list[Document]) -> None:
        """Fill in page contents that came back empty (scanned pages) via OCR.

        Mutates the documents in place. Best-effort: if OCR deps or the Tesseract
        binary are missing, log once and leave the extracted text untouched.
        """
        pages_needing_ocr = [
            document
            for document in documents
            if len((document.page_content or "").strip()) < self.OCR_MIN_CHARS
        ]
        if not pages_needing_ocr:
            return

        if pymupdf is None or pytesseract is None or Image is None:
            print(
                f"OCR skipped for '{path.name}': OCR dependencies unavailable "
                f"({_OCR_IMPORT_ERROR}). Install pymupdf, pytesseract and the "
                "Tesseract binary to read scanned PDFs."
            )
            return

        tesseract_cmd = os.getenv("TESSERACT_CMD")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        try:
            pdf = pymupdf.open(str(path))
        except Exception as exc:
            print(f"OCR skipped for '{path.name}': could not open for rendering ({exc}).")
            return

        try:
            for document in pages_needing_ocr:
                page_index = document.metadata.get("page")
                if page_index is None or page_index >= pdf.page_count:
                    continue
                try:
                    pixmap = pdf[page_index].get_pixmap(dpi=200)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                    text = pytesseract.image_to_string(image)
                except Exception as exc:
                    print(f"OCR failed on page {page_index + 1} of '{path.name}': {exc}")
                    continue
                if text.strip():
                    document.page_content = text
        finally:
            pdf.close()

    def _load_file(self, path: Path) -> list[Document]:
        if path.suffix.lower() == ".pdf":
            documents = PyPDFLoader(str(path)).load()
            self._ocr_pdf_pages(path, documents)
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

    def _infer_persona(self, chunks: list[Document]) -> str:
        """Derive a one-line persona from the corpus so the standalone chat voice
        fits whatever was uploaded. Best-effort: falls back to a generic persona."""
        # Imported lazily to avoid a circular import (rag_engine imports ingestion).
        from logic.persona import GENERIC_PERSONA, infer_persona_descriptor

        if not chunks:
            return GENERIC_PERSONA

        sample = "\n\n".join(chunk.page_content for chunk in chunks[:8])
        try:
            from logic.rag_engine import build_chat_model

            llm = build_chat_model(
                self.settings.llm_provider,
                self.settings.llm_model,
                self.settings.llm_base_url,
                self.settings.llm_api_key,
                self.settings.request_timeout,
            )
            return infer_persona_descriptor(llm, sample)
        except Exception as exc:
            print(f"Persona inference failed, using generic persona: {exc}")
            return GENERIC_PERSONA

    def _write_manifest(
        self,
        *,
        source_names: list[str],
        chunk_count: int,
        persona: str,
    ) -> dict[str, Any]:
        manifest = {
            "embedding_provider": self.settings.embedding_provider,
            "embedding_model": self.settings.embedding_model,
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "source_count": len(source_names),
            "chunk_count": chunk_count,
            "sources": source_names,
            "persona": persona,
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

        if not documents:
            self.reset_index()
            return None

        # Build the new index and infer its persona before touching the old
        # one on disk. If embedding fails partway (rate limit, quota, network
        # blip), the previous working index is left intact instead of being
        # wiped and never replaced.
        chunks = self._split_documents(documents)
        db = FAISS.from_documents(chunks, self.embeddings)
        persona = self._infer_persona(chunks)

        self.reset_index()
        self.index_path.mkdir(parents=True, exist_ok=True)
        db.save_local(str(self.index_path))
        self._write_manifest(
            source_names=[path.name for path in source_files],
            chunk_count=len(chunks),
            persona=persona,
        )
        self._vector_store = db
        print(f"Archives updated. Index saved to {self.index_path}")
        return db

    def ingest(self, source_path: str):
        return self.rebuild_index(str(self.data_dir))

    def add_file(self, file_path: str) -> dict[str, Any] | None:
        """Embed a single new file and merge it into the existing index.

        Unlike `rebuild_index`, this never re-loads or re-embeds files that
        are already indexed, so uploading one more document doesn't get
        slower as the Archives grow. Loading/splitting/embedding the new file
        happens outside the lock (safe to run concurrently across uploads);
        only the FAISS merge + save is serialized so concurrent uploads can't
        corrupt the on-disk index.
        """
        path = Path(file_path)
        documents = self._load_file(path)
        if not documents:
            return self.get_index_metadata()

        chunks = self._split_documents(documents)
        new_store = FAISS.from_documents(chunks, self.embeddings)

        with _INDEX_WRITE_LOCK:
            existing = self.load_index()
            if existing is not None:
                existing.merge_from(new_store)
                db = existing
            else:
                db = new_store

            self.index_path.mkdir(parents=True, exist_ok=True)
            db.save_local(str(self.index_path))
            self._vector_store = db

            manifest = self.get_index_metadata() or {}
            persona = manifest.get("persona") or self._infer_persona(chunks)
            total_chunks = manifest.get("chunk_count", 0) + len(chunks)
            source_names = [path.name for path in self._resolve_source_files()]

            result = self._write_manifest(
                source_names=source_names, chunk_count=total_chunks, persona=persona
            )

        print(f"Archives updated with '{path.name}'. Index saved to {self.index_path}")
        return result

    def remove_file(self, filename: str) -> dict[str, Any] | None:
        """Remove one source's chunks from the index in place.

        Unlike the old delete flow (full `rebuild_index`), this never
        re-embeds the sources that are staying, so deleting a file doesn't
        cost an API call per remaining chunk. Pure in-memory FAISS ops plus
        a save, serialized behind the same lock `add_file` uses.
        """
        with _INDEX_WRITE_LOCK:
            vector_store = self.load_index()
            manifest = self.get_index_metadata() or {}
            if vector_store is None:
                return manifest or None

            ids_to_remove = [
                doc_id
                for doc_id, document in vector_store.docstore._dict.items()
                if document.metadata.get("source") == filename
            ]
            remaining_sources = [
                name for name in manifest.get("sources", []) if name != filename
            ]

            if not remaining_sources:
                self.reset_index()
                return None

            if ids_to_remove:
                vector_store.delete(ids_to_remove)

            self.index_path.mkdir(parents=True, exist_ok=True)
            vector_store.save_local(str(self.index_path))
            self._vector_store = vector_store

            total_chunks = max(manifest.get("chunk_count", 0) - len(ids_to_remove), 0)
            persona = manifest.get("persona") or GENERIC_PERSONA

            return self._write_manifest(
                source_names=remaining_sources, chunk_count=total_chunks, persona=persona
            )

    def ensure_index(self):
        index = self.load_index()
        if index is not None:
            return index
        return self.rebuild_index(str(self.data_dir))

    def invalidate_cache(self) -> None:
        """Drop the in-memory FAISS handle so the next load re-reads from disk.

        Needed because add_file/remove_file are often called on a different
        ArchivesIngestion instance than the one a long-lived caller (e.g.
        NPCBrain) holds -- that instance's own on-disk write doesn't touch
        this instance's cached `_vector_store`.
        """
        self._vector_store = None

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
        min_score: float | None = None,
    ) -> list[tuple[Document, float | None]]:
        vector_store = self.ensure_index()
        if vector_store is None:
            return []

        resolved_k = max(k or self.settings.top_k, 1)
        resolved_fetch_k = max(fetch_k or self.settings.fetch_k, resolved_k)
        resolved_search_type = (search_type or self.settings.search_type).lower()
        resolved_lambda_mult = lambda_mult or self.settings.lambda_mult
        threshold = self.settings.score_threshold if min_score is None else min_score

        if resolved_search_type == "similarity":
            try:
                scored = vector_store.similarity_search_with_relevance_scores(
                    query,
                    k=resolved_k,
                )
            except Exception:
                documents = vector_store.similarity_search(query, k=resolved_k)
                return [(document, None) for document in documents]

            if threshold > 0:
                scored = [(doc, score) for doc, score in scored if score >= threshold]
            return scored

        documents = vector_store.max_marginal_relevance_search(
            query,
            k=resolved_k,
            fetch_k=resolved_fetch_k,
            lambda_mult=resolved_lambda_mult,
        )
        return [(document, None) for document in documents]
