import os
import shutil
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


class ArchivesIngestion:
    SUPPORTED_EXTENSIONS = (".txt", ".pdf")

    def __init__(self, data_dir="data", index_path="data/faiss_index"):
        self.data_dir = Path(data_dir)
        self.index_path = Path(index_path)
        embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-base-en-v1.5")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=150,
            separators=["\n\n", "\n", ". ", " ", ""],
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
            chunk.metadata.setdefault("chunk_id", index)
        return chunks

    def reset_index(self):
        if self.index_path.exists():
            shutil.rmtree(self.index_path)

    def rebuild_index(self, source_path: str | None = None):
        documents = self._load_documents(source_path)

        self.reset_index()

        if not documents:
            return None

        chunks = self._split_documents(documents)
        db = FAISS.from_documents(chunks, self.embeddings)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        db.save_local(str(self.index_path))
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
        if self.index_path.exists():
            return FAISS.load_local(
                str(self.index_path),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
        return None
