import os
import sys

# Add current directory to path so we can import logic modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from logic.rag_engine import NeuralRAG


def main():
    print("--- NeuralNPC Sentinel Verification ---")

    # Check for API Key
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print(
            "[!] No API Key found in env. Please set OPENROUTER_API_KEY or OPENAI_API_KEY in .env"
        )
        print("    Skipping live query verification.")
        # We can still test ingestion though
        try:
            print("[*] Testing Ingestion Module...")
            rag = (
                NeuralRAG()
            )  # This might fail if it tries to init LLM immediately without key
        except ValueError as e:
            print(f"[+] Caught expected error matching missing key: {e}")
            print("[*] Ingestion logic is importable and RAG class exists.")
        return

    try:
        rag = NeuralRAG()

        # 1. Ingest Data
        print("[*] Ingesting 'data/lore.txt'...")
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
