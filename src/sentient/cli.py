"""The `sentient` console script: a retrieval/answer smoke check, and D8's
vault-key rotation.

The sys.path.append this file used to carry is gone: R9 made the repo a real
installed package, so `import sentient` resolves from any working directory.
"""

import argparse
import asyncio
import os
from time import perf_counter

from sentient.adapters.documents import ArchivesIngestion
from sentient.core.config import load_rag_settings
from sentient.services.rag import NPCBrain


async def _main():
    print("--- NeuralNPC Sentinel Verification ---")
    settings = load_rag_settings()
    archives = ArchivesIngestion()

    print(
        f"[*] Runtime: llm={settings.llm_provider}:{settings.llm_model} | "
        f"embeddings={settings.embedding_provider}:{settings.embedding_model} | "
        f"search={settings.search_type} | top_k={settings.top_k}"
    )

    # Check for API Key
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("[!] No API Key found in env. Please set GOOGLE_API_KEY or OPENAI_API_KEY in .env")
        print("    Running retrieval-only verification.")

        print("[*] Rebuilding FAISS index from 'data/'...")
        await archives.rebuild_index("data")

        print("[*] Inspecting retrieval results for: Who is Sentinel?")
        started_at = perf_counter()
        matches = await archives.retrieve("Who is Sentinel?", k=settings.top_k)
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
        rag = NPCBrain()

        # 1. Ingest Data
        print("[*] Rebuilding FAISS index from 'data/'...")
        await rag.add_documents("data")

        # 2. Query
        question = "Who is Sentinel?"
        print(f"[*] Querying: {question}")
        result = await rag.ask_with_context(question)

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


async def _rotate_secret() -> int:
    """D8 step 2: re-encrypt every stored credential under the current key.

    **Secrets come from the environment, never from flags.** The plan sketched
    `--old <key> --new <key>`; a vault key typed on a command line lands in shell
    history and in every process listing on the box, which is a worse outcome
    than the problem this command exists to fix. The three-step procedure already
    puts both keys in the environment, so there is nothing for a flag to add.
    """
    from sentient.adapters.state import get_state_store
    from sentient.core.errors import InvalidRequest, VaultUnavailable
    from sentient.services.credentials import rotate_vault_keys

    settings = load_rag_settings()
    print(
        f"[*] Vault rotation | store={settings.db_backend} | "
        f"previous keys held={len(settings.sentient_secret_keys_old)}"
    )
    try:
        report = await rotate_vault_keys(get_state_store(settings), settings)
    except (InvalidRequest, VaultUnavailable) as exc:
        print(f"[!] {exc}")
        return 1

    print(f"[*] Re-encrypted {report['rotated']} credential(s).")
    for row in report["unreadable"]:
        # Loud, and per row: these are the credentials that will silently fall
        # back to the env key once SENTIENT_SECRET_KEY_OLD is removed.
        print(
            f"[!] UNREADABLE user={row['user_id']} provider={row['provider']} "
            f"-- decrypts under neither key; the user must re-enter it"
        )
    if report["unreadable"]:
        return 2
    print("[*] Safe to remove SENTIENT_SECRET_KEY_OLD and deploy again.")
    return 0


def main() -> None:
    """Synchronous entry point for the console script.

    No subcommand runs the smoke check, which is what `sentient` did before this
    file grew a second job.
    """
    parser = argparse.ArgumentParser(prog="sentient")
    parser.add_subparsers(dest="command").add_parser(
        "rotate-secret",
        help="re-encrypt every stored credential under SENTIENT_SECRET_KEY",
    )
    args = parser.parse_args()

    if args.command == "rotate-secret":
        raise SystemExit(asyncio.run(_rotate_secret()))
    asyncio.run(_main())


if __name__ == "__main__":
    main()
