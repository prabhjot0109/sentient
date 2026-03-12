import os
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import PromptTemplate
from logic.persona import SENTINEL_SYSTEM_PROMPT
from logic.ingestion import ArchivesIngestion
from dotenv import load_dotenv

load_dotenv()


class NPCBrain:
    def __init__(self, api_key=None):
        self.ingestion = ArchivesIngestion()
        self.vector_store = self.ingestion.ensure_index()
        key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

        if not key:
            raise ValueError("API Key not found. Please provide one or set it in .env")

        is_openrouter = bool(os.getenv("OPENROUTER_API_KEY")) or key.startswith(
            "sk-or-"
        )
        default_model = "openai/gpt-4o-mini" if is_openrouter else "gpt-4o-mini"
        default_base_url = (
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            if is_openrouter
            else None
        )

        self.api_key = key
        self.model_name = os.getenv("MODEL_NAME", default_model)
        self.base_url = default_base_url

        self.llm = ChatOpenAI(
            model=self.model_name,
            openai_api_key=key,
            openai_api_base=self.base_url,
        )

        self.conversation_chain = self._build_chain()

    def _build_chain(self):
        if not self.vector_store:
            return None

        prompt = ChatPromptTemplate.from_messages(
            [
                SENTINEL_SYSTEM_PROMPT,
                HumanMessagePromptTemplate.from_template(
                    "Question: {input}\n\nAnswer using only the archive context above."
                ),
            ]
        )

        document_prompt = PromptTemplate.from_template(
            "[Source: {source}{page_label}]\n{page_content}"
        )
        document_chain = create_stuff_documents_chain(
            self.llm,
            prompt,
            document_prompt=document_prompt,
            document_separator="\n\n---\n\n",
        )

        retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 4, "fetch_k": 12, "lambda_mult": 0.65},
        )
        retrieval_chain = create_retrieval_chain(retriever, document_chain)

        return retrieval_chain

    def refresh_knowledge(self):
        self.vector_store = self.ingestion.ensure_index()
        self.conversation_chain = self._build_chain()

    def rebuild_knowledge(self, source_path: str | None = None):
        self.vector_store = self.ingestion.rebuild_index(source_path)
        self.conversation_chain = self._build_chain()

    def retrieve(self, question: str, k: int = 4) -> list[dict[str, Any]]:
        if not self.vector_store:
            self.refresh_knowledge()

        if not self.vector_store:
            return []

        try:
            matches = self.vector_store.similarity_search_with_relevance_scores(
                question, k=k
            )
            return [
                {
                    "content": document.page_content,
                    "score": score,
                    "metadata": document.metadata,
                }
                for document, score in matches
            ]
        except Exception:
            matches = self.vector_store.similarity_search(question, k=k)
            return [
                {
                    "content": document.page_content,
                    "score": None,
                    "metadata": document.metadata,
                }
                for document in matches
            ]

    def ask(self, question: str):
        if not self.conversation_chain:
            self.refresh_knowledge()

            if not self.conversation_chain:
                return "The Archives are empty. Please upload game manuals to specify my knowledge."

        response = self.conversation_chain.invoke({"input": question})
        return response["answer"]

    def learn_from_file(self, path: str):
        self.vector_store = self.ingestion.ingest(path)
        self.conversation_chain = self._build_chain()
        return "Knowledge assimilated into the Archives."

    def add_documents(self, source_path: str):
        self.rebuild_knowledge(source_path)
        return "Archives rebuilt successfully."

    def query(self, question: str):
        return self.ask(question)


class NeuralRAG(NPCBrain):
    pass
