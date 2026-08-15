from __future__ import annotations

import asyncio
import io
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from sentient.adapters.llm.models import build_chat_model
from sentient.adapters.llm.persona import GENERIC_PERSONA, infer_persona_descriptor
from sentient.core.config import RAGSettings, load_rag_settings

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
    """Loads/splits/OCRs source documents and delegates all vector storage and
    retrieval to a VectorBackend (FAISS by default). The document-processing
    helpers stay synchronous; the I/O methods are coroutines that offload the
    sync CPU work with asyncio.to_thread and await the backend's async ops."""

    SUPPORTED_EXTENSIONS = (".txt", ".pdf")
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

        from sentient.adapters.retrieval.factory import get_vector_backend

        self.backend = get_vector_backend(self.settings, self.index_path, self.embeddings)

    @property
    def embeddings(self):
        return build_embeddings(
            self.settings.embedding_provider,
            self.settings.embedding_model,
            self.settings.embedding_base_url,
            self.settings.embedding_api_key,
        )

    def index_exists(self) -> bool:
        return self.backend.exists()

    def get_index_metadata(self) -> dict[str, Any] | None:
        return self.backend.metadata()

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
        if not chunks:
            return GENERIC_PERSONA

        sample = "\n\n".join(chunk.page_content for chunk in chunks[:8])
        try:
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

    def invalidate_cache(self) -> None:
        """Drop the backend's in-memory handle so the next load re-reads from disk.

        Needed because add_file/remove_file are often called on a different
        ArchivesIngestion instance than the one a long-lived caller (e.g.
        NPCBrain) holds -- that instance's own on-disk write doesn't touch
        this instance's cached store.
        """
        self.backend.invalidate_cache()

    def reset_index(self):
        self.backend.reset()

    def clear_project(self, user_key: str | None, project_id: str) -> None:
        self.backend.clear_project(user_key, project_id)

    async def rebuild_index(
        self,
        source_path: str | None = None,
        *,
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ):
        source_files = await asyncio.to_thread(self._resolve_source_files, source_path)
        documents = await asyncio.to_thread(self._load_documents, source_path)
        if not documents:
            await asyncio.to_thread(self.backend.reset)
            return None

        # Split, then infer the persona off the event loop (the LLM call inside
        # _infer_persona is synchronous), before handing chunks to the backend.
        chunks = await asyncio.to_thread(self._split_documents, documents)
        persona = await asyncio.to_thread(self._infer_persona, chunks)
        return await self.backend.index(
            chunks,
            source_names=[path.name for path in source_files],
            persona=persona,
            user_key=user_key,
            project_id=project_id,
            embedding_signature=embedding_signature,
        )

    async def ingest(
        self,
        source_path: str,
        *,
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ):
        return await self.rebuild_index(
            str(self.data_dir),
            user_key=user_key,
            project_id=project_id,
            embedding_signature=embedding_signature,
        )

    async def add_file(
        self,
        file_path: str,
        *,
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> dict[str, Any] | None:
        """Embed a single new file and merge it into the existing index.

        Unlike rebuild_index, this never re-loads or re-embeds files that are
        already indexed. Loading/splitting/persona run off the loop; the backend
        serializes the merge+save so concurrent uploads stay index-safe.
        """
        path = Path(file_path)
        documents = await asyncio.to_thread(self._load_file, path)
        if not documents:
            metadata = await asyncio.to_thread(self.backend.metadata)
            return {**(metadata or {}), "added_chunk_count": 0}

        chunks = await asyncio.to_thread(self._split_documents, documents)
        manifest = await asyncio.to_thread(self.backend.metadata) or {}
        persona = manifest.get("persona") or await asyncio.to_thread(
            self._infer_persona, chunks
        )
        source_files = await asyncio.to_thread(self._resolve_source_files)
        metadata = await self.backend.add(
            chunks,
            source_names=[path.name for path in source_files],
            persona=persona,
            user_key=user_key,
            project_id=project_id,
            embedding_signature=embedding_signature,
        )
        return {**(metadata or {}), "added_chunk_count": len(chunks)}

    async def remove_file(self, filename: str) -> dict[str, Any] | None:
        return await self.backend.remove(filename)

    async def ensure_index(self):
        if self.backend.exists():
            return None
        return await self.rebuild_index(str(self.data_dir))

    async def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        fetch_k: int | None = None,
        search_type: str | None = None,
        lambda_mult: float | None = None,
        min_score: float | None = None,
        user_key: str | None = None,
        project_id: str | None = None,
        embedding_signature: str | None = None,
    ) -> list[tuple[Document, float | None]]:
        # Forward tenant/project/signature filters to the backend (FAISS ignores
        # them; Qdrant payload-filters). Callers always pass them so R4 routing
        # cannot TypeError when a project-scoped completion resolves.
        return await self.backend.retrieve(
            query,
            k=k,
            search_type=search_type,
            min_score=min_score,
            user_key=user_key,
            project_id=project_id,
            embedding_signature=embedding_signature,
        )
