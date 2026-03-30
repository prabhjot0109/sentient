import os
import sys
from time import perf_counter

# Add current directory to path so we can import logic modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from logic.config import load_rag_settings
from logic.ingestion import ArchivesIngestion
from logic.rag_engine import NeuralRAG


def main():
    print("--- NeuralNPC Sentinel Verification ---")
    settings = load_rag_settings()
    archives = ArchivesIngestion()

    print(
        f"[*] Runtime: llm={settings.llm_provider}:{settings.llm_model} | "
        f"embeddings={settings.embedding_provider}:{settings.embedding_model} | "
        f"search={settings.search_type} | top_k={settings.top_k}"
    )

    # Check for API Key
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print(
            "[!] No API Key found in env. Please set OPENROUTER_API_KEY or OPENAI_API_KEY in .env"
        )
        print("    Running retrieval-only verification.")

        print("[*] Rebuilding FAISS index from 'data/'...")
        archives.rebuild_index("data")

        print("[*] Inspecting retrieval results for: Who is Sentinel?")
        started_at = perf_counter()
        matches = archives.retrieve("Who is Sentinel?", k=settings.top_k)
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)

        if not matches:
            print("[!] No index could be built. Add PDF or TXT files under data/.")
            return

        print(f"[*] Retrieval latency: {elapsed_ms} ms")
        for rank, (document, score) in enumerate(matches, start=1):
            source = document.metadata.get("source", "unknown")
            snippet = document.page_content.replace("\n", " ")[:140]
            score_text = f"{score:.4f}" if score is not None else "n/a"
            print(f"    {rank}. {source} | score={score_text} | {snippet}")
        return

    try:
        rag = NeuralRAG()

        # 1. Ingest Data
        print("[*] Rebuilding FAISS index from 'data/'...")
        rag.add_documents("data")

        # 2. Query
        question = "Who is Sentinel?"
        print(f"[*] Querying: {question}")
        result = rag.ask_with_context(question)

        print("\n=== SENTINEL RESPONSE ===")
        print(result["answer"])
        print("=========================\n")

        if result["sources"]:
            print("[*] Retrieved context:")
            for rank, source in enumerate(result["sources"], start=1):
                snippet = source["content"].replace("\n", " ")[:140]
                print(f"    {rank}. {source['source']}{source['page_label']} | {snippet}")

    except Exception as e:
        print(f"[!] Error during verification: {e}")


if __name__ == "__main__":
    main()
