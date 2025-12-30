import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from logic.persona import SENTINEL_SYSTEM_PROMPT
from logic.ingestion import ArchivesIngestion
from dotenv import load_dotenv

load_dotenv()


class NPCBrain:
    def __init__(self, api_key=None):
        self.ingestion = ArchivesIngestion()
        self.vector_store = self.ingestion.load_index()

        # Configure LLM (OpenRouter/OpenAI compatible)
        # Prioritize passed api_key, then environment variables

        key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

        if not key:
            raise ValueError("API Key not found. Please provide one or set it in .env")

        self.llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "openai/gpt-3.5-turbo"),
            openai_api_key=key,
            openai_api_base=base_url,
        )

        self.conversation_chain = self._build_chain()

    def _build_chain(self):
        if not self.vector_store:
            return None

        prompt = ChatPromptTemplate.from_messages(
            [
                SENTINEL_SYSTEM_PROMPT,
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )

        document_chain = create_stuff_documents_chain(self.llm, prompt)

        retriever = self.vector_store.as_retriever()
        retrieval_chain = create_retrieval_chain(retriever, document_chain)

        return retrieval_chain

    def ask(self, question: str):
        if not self.conversation_chain:
            # Try reloading index from disk in case it was just created
            self.vector_store = self.ingestion.load_index()
            self.conversation_chain = self._build_chain()

            if not self.conversation_chain:
                return "The Archives are empty. Please upload Game Manuals to specificy my knowledge."

        response = self.conversation_chain.invoke({"input": question})
        return response["answer"]

    def learn_from_file(self, path: str):
        self.vector_store = self.ingestion.ingest(path)
        # Rebuild chain with new store
        self.conversation_chain = self._build_chain()
        return "Knowledge assimilated into the Archives."
