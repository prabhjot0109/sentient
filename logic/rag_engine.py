from __future__ import annotations

from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI

from logic.config import load_rag_settings
from logic.ingestion import ArchivesIngestion
from logic.persona import build_system_prompt

load_dotenv()


@lru_cache(maxsize=16)
def build_chat_model(
    provider: str,
    model_name: str,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
):
    if provider == "google":
        # Gemini Flash "thinks" before replying by default, which adds latency we
        # don't want for short, spoken in-character answers. thinking_budget=0
        # skips that reasoning pass and returns the answer directly.
        # max_retries=2 (default 6) because the langchain client retries 429s
        # with exponential backoff regardless of cause; a daily quota error
        # isn't transient, so retrying it 6 times just makes every request
        # hang for up to a minute before failing anyway.
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            timeout=timeout,
            thinking_budget=0,
            max_retries=2,
        )

    if provider == "huggingface":
        return ChatHuggingFace(
            llm=HuggingFaceEndpoint(
                repo_id=model_name,
                huggingfacehub_api_token=api_key,
                timeout=timeout,
            )
        )

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )


class NPCBrain:
    def __init__(self, api_key: str | None = None):
        self.settings = load_rag_settings(api_key)
        self.ingestion = ArchivesIngestion(api_key=api_key, settings=self.settings)
        self.vector_store = self.ingestion.ensure_index()

        if self.settings.llm_provider in ("google", "openai") and not self.settings.llm_api_key:
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
        if not self.vector_store:
            return None

        return create_stuff_documents_chain(
            self.llm,
            self.prompt,
            document_prompt=self.document_prompt,
            document_separator="\n\n---\n\n",
        )

    def refresh_knowledge(self):
        self.ingestion.invalidate_cache()
        self.vector_store = self.ingestion.ensure_index()
        self._rebuild_prompt()

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

    def _answer_without_context(self, question: str) -> str:
        """Answer from general knowledge when the Archives have nothing to ground on.
        We never refuse — the persona simply answers and flags it isn't from sources."""
        prompt_value = self.prompt.format_prompt(input=question, context="")
        result = self.llm.invoke(prompt_value.to_messages())
        return str(result.content)

    def ask_with_context(
        self,
        question: str,
        *,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        if not self.vector_store:
            self.refresh_knowledge()

        # Retrieve once, with relevance scores, then ground generation on those exact
        # chunks. This keeps the reported sources (and their scores) identical to what
        # the model actually read, and lets the frontend show retrieval quality.
        matches = self.ingestion.retrieve(question, k=top_k) if self.vector_store else []
        documents = [document for document, _ in matches]

        document_chain = self._build_document_chain()
        if document_chain is not None and documents:
            answer = document_chain.invoke({"input": question, "context": documents})
        else:
            # No Archives yet, or nothing relevant retrieved: still answer.
            answer = self._answer_without_context(question)

        sources = [self._serialize_match(document, score) for document, score in matches]
        return {
            "answer": answer,
            "sources": sources,
            "top_k": top_k or self.settings.top_k,
        }

    def ask(self, question: str, *, top_k: int | None = None):
        return self.ask_with_context(question, top_k=top_k)["answer"]

    def add_documents(self, source_path: str):
        self.rebuild_knowledge(source_path)
        return "Archives rebuilt successfully."
