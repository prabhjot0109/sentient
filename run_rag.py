import os
import sys

# Add current directory to path so we can import logic modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from logic.ingestion import ArchivesIngestion
from logic.rag_engine import NeuralRAG


def main():
    print("--- NeuralNPC Sentinel Verification ---")
    archives = ArchivesIngestion()

    # Check for API Key
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print(
            "[!] No API Key found in env. Please set OPENROUTER_API_KEY or OPENAI_API_KEY in .env"
        )
        print("    Running retrieval-only verification.")

        print("[*] Rebuilding FAISS index from 'data/'...")
        archives.rebuild_index("data")

        print("[*] Inspecting retrieval results for: Who is Sentinel?")
        store = archives.load_index()
        if not store:
            print("[!] No index could be built. Add PDF or TXT files under data/.")
            return

        matches = store.similarity_search_with_relevance_scores("Who is Sentinel?", k=3)
        for rank, (document, score) in enumerate(matches, start=1):
            source = document.metadata.get("source", "unknown")
            snippet = document.page_content.replace("\n", " ")[:140]
            print(f"    {rank}. {source} | score={score:.4f} | {snippet}")
        return

    try:
        rag = NeuralRAG()

        # 1. Ingest Data
        print("[*] Rebuilding FAISS index from 'data/'...")
        rag.add_documents("data")

        # 2. Query
        question = "Who is Sentinel?"
        print(f"[*] Querying: {question}")
        answer = rag.query(question)

        print("\n=== SENTINEL RESPONSE ===")
        print(answer)
        print("=========================\n")

    except Exception as e:
        print(f"[!] Error during verification: {e}")


if __name__ == "__main__":
    main()
