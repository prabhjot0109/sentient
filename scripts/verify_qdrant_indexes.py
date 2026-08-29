"""Check a live Qdrant deployment against the filters this backend actually sends.

A Qdrant Cloud cluster runs strict mode, so a filter on a payload field with no
keyword index is REFUSED rather than answered slowly -- and `services/chat`
catches that and answers ungrounded, which reaches a player as an NPC ignoring
its own lore. Run this after pointing a deployment at a new cluster:

    uv run python scripts/verify_qdrant_indexes.py

Constructing the backend repairs the indexes on its own (`_ensure_indexes_sync`
runs on every setup, not only at collection creation), so a first run that
reports missing fields and a second that reports none is the expected shape.
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()
from sentient.adapters.documents import build_embeddings  # noqa: E402
from sentient.adapters.retrieval.qdrant_store import _INDEXED_FIELDS, QdrantBackend  # noqa: E402
from sentient.core.config import load_rag_settings  # noqa: E402


async def main():
    s = load_rag_settings()
    print(
        "resolved:", s.vector_backend, s.embedding_provider, s.embedding_model, s.qdrant_collection
    )
    emb = build_embeddings(
        s.embedding_provider, s.embedding_model, s.embedding_base_url, s.embedding_api_key
    )
    b = QdrantBackend(s, emb)
    await b._ensure_ready()
    c = b._sync_client()
    schema = c.get_collection(s.qdrant_collection).payload_schema or {}
    print("indexed fields:", sorted(schema))
    print("missing:", [f for f in _INDEXED_FIELDS if f not in schema])
    print("points:", c.get_collection(s.qdrant_collection).points_count)
    pts, _ = c.scroll(collection_name=s.qdrant_collection, limit=1, with_payload=True)
    md = pts[0].payload["metadata"]
    print(
        "sample scope:", {k: md.get(k) for k in ("user_key", "project_id", "embedding_signature")}
    )
    hits = await b.retrieve(
        "who are you",
        k=4,
        min_score=0.0,
        user_key=md.get("user_key"),
        project_id=md.get("project_id"),
        embedding_signature=md.get("embedding_signature"),
    )
    print("filtered hits:", len(hits))
    for d, score in hits[:2]:
        print("  ", round(score, 3), d.metadata.get("source"), repr(d.page_content[:70]))


asyncio.run(main())
