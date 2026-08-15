from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate

from sentient.adapters.documents import ArchivesIngestion
from sentient.adapters.llm.models import build_chat_model
from sentient.adapters.llm.persona import build_system_prompt
from sentient.core.config import RAGSettings, load_rag_settings

load_dotenv()


class NPCBrain:
    def __init__(self, api_key: str | None = None, *, settings: RAGSettings | None = None):
        # `settings` lets a caller that has already resolved a runtime context hand
        # it in, instead of having it re-derived from api_key alone: resolving from
        # an LLM key also re-resolves *embeddings* from that key, which can land the
        # brain in a different embedding space than the index was built with.
        self.settings = settings or load_rag_settings(api_key)
        self.ingestion = ArchivesIngestion(api_key=api_key, settings=self.settings)

        if self.settings.llm_provider != "huggingface" and not self.settings.llm_api_key:
            raise ValueError("API Key not found. Please provide one or set it in .env")

        self.api_key = self.settings.llm_api_key
        self.model_name = self.settings.llm_model
        self.base_url = self.settings.llm_base_url

        self.llm = build_chat_model(
            self.settings.llm_provider,
            self.model_name,
            self.base_url,
            self.api_key,
            self.settings.request_timeout,
        )

        self.document_prompt = PromptTemplate.from_template(
            "[Source: {source}{page_label} | chunk {chunk_id}]\n{page_content}"
        )
        self._rebuild_prompt()

    def _rebuild_prompt(self):
        """(Re)build the chat prompt around the persona inferred from the current
        Archives, so the voice tracks whatever documents are loaded."""
        metadata = self.ingestion.get_index_metadata()
        descriptor = metadata.get("persona") if metadata else None
        self.prompt = ChatPromptTemplate.from_messages(
            [
                build_system_prompt(descriptor),
                HumanMessagePromptTemplate.from_template("Question: {input}"),
            ]
        )

    def _build_document_chain(self):
        return create_stuff_documents_chain(
            self.llm,
            self.prompt,
            document_prompt=self.document_prompt,
            document_separator="\n\n---\n\n",
        )

    async def refresh_knowledge(self):
        self.ingestion.invalidate_cache()
        if not self.ingestion.index_exists():
            await self.ingestion.rebuild_index(str(self.ingestion.data_dir))
        self._rebuild_prompt()

    async def rebuild_knowledge(self, source_path: str | None = None):
        await self.ingestion.rebuild_index(source_path)

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

    async def retrieve(self, question: str, k: int | None = None) -> list[dict[str, Any]]:
        matches = await self.ingestion.retrieve(question, k=k)
        return [self._serialize_match(document, score) for document, score in matches]

    async def ask_with_context(
        self,
        question: str,
        *,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        # Retrieve once, with relevance scores, then ground generation on those exact
        # chunks. This keeps the reported sources (and their scores) identical to what
        # the model actually read, and lets the frontend show retrieval quality.
        matches = await self.ingestion.retrieve(question, k=top_k)
        documents = [document for document, _ in matches]

        document_chain = self._build_document_chain()
        if document_chain is not None and documents:
            answer = await document_chain.ainvoke({"input": question, "context": documents})
        else:
            # No Archives yet, or nothing relevant retrieved: still answer in-persona.
            result = await self.llm.ainvoke(
                self.prompt.format_prompt(input=question, context="").to_messages()
            )
            answer = str(result.content)

        sources = [self._serialize_match(document, score) for document, score in matches]
        return {
            "answer": answer,
            "sources": sources,
            "top_k": top_k or self.settings.top_k,
        }

    async def ask(self, question: str, *, top_k: int | None = None):
        return (await self.ask_with_context(question, top_k=top_k))["answer"]

    async def add_documents(self, source_path: str):
        await self.rebuild_knowledge(source_path)
        return "Archives rebuilt successfully."
