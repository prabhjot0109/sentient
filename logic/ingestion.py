import os
from langchain_community.document_loaders import (
    TextLoader,
    DirectoryLoader,
    PyPDFLoader,
)
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


class ArchivesIngestion:
    def __init__(self, index_path="data/faiss_index"):
        self.index_path = index_path
        # Use a lightweight local model
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    def ingest(self, source_path: str):
        """
        Ingests documents from a file or directory.
        Supports .txt and .pdf
        """
        is_dir = os.path.isdir(source_path)
        docs = []

        if is_dir:
            # Load text files
            txt_loader = DirectoryLoader(
                source_path, glob="**/*.txt", loader_cls=TextLoader
            )
            docs.extend(txt_loader.load())
            # Load pdf files
            pdf_loader = DirectoryLoader(
                source_path, glob="**/*.pdf", loader_cls=PyPDFLoader
            )
            docs.extend(pdf_loader.load())
        else:
            if source_path.endswith(".pdf"):
                loader = PyPDFLoader(source_path)
            else:
                loader = TextLoader(source_path)
            docs.extend(loader.load())

        if not docs:
            print("No documents found to ingest.")
            return None

        # Split documents
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)

        # Create Vector Store
        db = FAISS.from_documents(splits, self.embeddings)

        # Save local index
        db.save_local(self.index_path)
        print(f"Archives updated. Index saved to {self.index_path}")
        return db

    def load_index(self):
        """
        Loads the existing FAISS index.
        """
        if os.path.exists(self.index_path):
            return FAISS.load_local(
                self.index_path, self.embeddings, allow_dangerous_deserialization=True
            )
        return None
