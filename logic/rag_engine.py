from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI

from logic.config import load_rag_settings
from logic.ingestion import ArchivesIngestion
from logic.persona import SENTINEL_SYSTEM_PROMPT

load_dotenv()


class NPCBrain:
    def __init__(self, api_key: str | None = None):
        self.settings = load_rag_settings(api_key)
        self.ingestion = ArchivesIngestion(api_key=api_key, settings=self.settings)
        self.vector_store = self.ingestion.ensure_index()

        if not self.settings.llm_api_key:
            raise ValueError("API Key not found. Please provide one or set it in .env")

        self.api_key = self.settings.llm_api_key
        self.model_name = self.settings.llm_model
        self.base_url = self.settings.llm_base_url

        self.llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.settings.request_timeout,
        )

        self.prompt = ChatPromptTemplate.from_messages(
            [
                SENTINEL_SYSTEM_PROMPT,
                HumanMessagePromptTemplate.from_template(
                    "Question: {input}\n\nAnswer using only the archive context above."
                ),
            ]
        )
        self.document_prompt = PromptTemplate.from_template(
            "[Source: {source}{page_label} | chunk {chunk_id}]\n{page_content}"
        )

    def _build_chain(self, top_k: int | None = None):
        if not self.vector_store:
            return None

        document_chain = create_stuff_documents_chain(
            self.llm,
            self.prompt,
            document_prompt=self.document_prompt,
            document_separator="\n\n---\n\n",
        )

        resolved_top_k = max(top_k or self.settings.top_k, 1)
        search_kwargs: dict[str, Any] = {"k": resolved_top_k}
        search_type = self.settings.search_type

        if search_type == "mmr":
            search_kwargs.update(
                {
                    "fetch_k": max(self.settings.fetch_k, resolved_top_k),
                    "lambda_mult": self.settings.lambda_mult,
                }
            )

        retriever = self.vector_store.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs,
        )
        return create_retrieval_chain(retriever, document_chain)

    def refresh_knowledge(self):
        self.vector_store = self.ingestion.ensure_index()

    def rebuild_knowledge(self, source_path: str | None = None):
        self.vector_store = self.ingestion.rebuild_index(source_path)

    def _serialize_match(
        self,
        document: Document,
        score: float | None = None,
    ) -> dict[str, Any]:
        metadata = dict(document.metadata)
        return {
            "content": document.page_content,
            "score": score,
            "metadata": metadata,
            "source": metadata.get("source", "unknown"),
            "page_label": metadata.get("page_label", ""),
            "chunk_id": metadata.get("chunk_id"),
        }

    def retrieve(self, question: str, k: int | None = None) -> list[dict[str, Any]]:
        matches = self.ingestion.retrieve(question, k=k)
        return [self._serialize_match(document, score) for document, score in matches]

    def ask_with_context(
        self,
        question: str,
        *,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        if not self.vector_store:
            self.refresh_knowledge()

        if not self.vector_store:
            return {
                "answer": "The Archives are empty. Please upload game manuals to specify my knowledge.",
                "sources": [],
                "top_k": top_k or self.settings.top_k,
            }

        chain = self._build_chain(top_k)
        if chain is None:
            return {
                "answer": "The Archives are empty. Please upload game manuals to specify my knowledge.",
                "sources": [],
                "top_k": top_k or self.settings.top_k,
            }

        response = chain.invoke({"input": question})
        context_documents = response.get("context", [])
        sources = [self._serialize_match(document) for document in context_documents]
        return {
            "answer": response["answer"],
            "sources": sources,
            "top_k": top_k or self.settings.top_k,
        }

    def ask(self, question: str, *, top_k: int | None = None):
        return self.ask_with_context(question, top_k=top_k)["answer"]

    def learn_from_file(self, path: str):
        self.vector_store = self.ingestion.ingest(path)
        return "Knowledge assimilated into the Archives."

    def add_documents(self, source_path: str):
        self.rebuild_knowledge(source_path)
        return "Archives rebuilt successfully."

    def query(self, question: str):
        return self.ask(question)


class NeuralRAG(NPCBrain):
    pass
