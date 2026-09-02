"""X2 — measure whether a retrieval config change made grounding better or worse.

Until this existed, every knob in `project_configs` was adjustable and
unjudgeable. That makes an eval set the prerequisite for any quality claim,
rather than an optional extra.

    uv run python scripts/eval_retrieval.py --rebuild
    RAG_HYBRID=true VECTOR_BACKEND=qdrant uv run python scripts/eval_retrieval.py --rebuild

**Two rules that come from measurements this project already paid for.**

1. **Print the resolved config before any number.** V1's Finding 2 was a false
   positive produced by a harness that silently resolved a different embedding
   provider than the server. A number with no provider, model, backend and
   threshold beside it is not evidence. This script refuses to report anything
   until it has printed all four.

2. **Never average across backends.** `RAG_SCORE_THRESHOLD` is a cosine floor on
   FAISS and a **rank-fusion artefact** on Qdrant, where measured gibberish
   scores 0.5 and clears a configured 0.2. One number over both is meaningless,
   so the report names the backend it belongs to and nothing else.

A script rather than a test: it needs a real embedding provider and a real index,
and `tests/` forbids network. Nothing here imports from `tests/`, and CI never
runs it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sentient.adapters.documents import ArchivesIngestion  # noqa: E402
from sentient.core.config import load_rag_settings  # noqa: E402

_EVALS = Path(__file__).resolve().parents[1] / "evals" / "retrieval.json"


@dataclass
class Result:
    case: dict
    hit: bool
    top_score: float | None
    matched: str | None


def _print_resolved_config(settings, index_path: Path, k: int) -> None:
    """Rule 1. Everything a reader needs to know what these numbers describe."""
    print("resolved configuration")
    print("-" * 64)
    for label, value in (
        ("vector backend", settings.vector_backend),
        (
            "qdrant collection",
            settings.qdrant_collection if settings.vector_backend == "qdrant" else "-",
        ),
        ("hybrid (RAG_HYBRID)", settings.hybrid),
        ("sparse model", settings.sparse_model if settings.hybrid else "-"),
        ("embedding provider", settings.embedding_provider),
        ("embedding model", settings.embedding_model),
        ("embedding key set", bool(settings.embedding_api_key)),
        ("search type", settings.search_type),
        ("score threshold", settings.score_threshold),
        ("top_k / fetch_k", f"{k} / {settings.fetch_k}"),
        ("chunk size / overlap", f"{settings.chunk_size} / {settings.chunk_overlap}"),
        ("data dir", settings.data_dir),
        ("index path", index_path),
    ):
        print(f"  {label:22s} {value}")
    print("-" * 64)
    print()


def _hit(case: dict, chunks: list[tuple[object, float | None]]) -> tuple[bool, str | None]:
    """Any expected string in any returned chunk.

    Substrings rather than a pinned chunk id on purpose: `RAG_CHUNK_SIZE` is one
    of the knobs being evaluated, so boundaries move between runs and an id
    would make this measure the chunker instead of the retrieval.
    """
    haystack = "\n".join(document.page_content for document, _ in chunks)
    for expected in case["expect_any"]:
        if expected in haystack:
            return True, expected
    return False, None


async def run(k: int, rebuild: bool) -> int:
    settings = load_rag_settings()
    archives = ArchivesIngestion(settings=settings)
    _print_resolved_config(settings, archives.index_path, k)

    if rebuild:
        print(f"indexing {settings.data_dir} ...", flush=True)
        metadata = await archives.rebuild_index(str(archives.data_dir))
        print(f"indexed: {metadata}\n", flush=True)
    elif not archives.index_exists():
        print("no index, and --rebuild was not passed. Nothing to measure.")
        return 2

    cases = json.loads(_EVALS.read_text(encoding="utf-8"))["cases"]
    results: list[Result] = []

    for case in cases:
        # min_score=0.0, deliberately, and not the configured threshold. The
        # threshold is one of the things under evaluation; applying it here would
        # hide the scores the report is trying to show, and on Qdrant it is inert
        # below 0.5 anyway.
        chunks = await archives.retrieve(case["query"], k=k, min_score=0.0)
        hit, matched = _hit(case, chunks) if case["expect_any"] else (False, None)
        top = chunks[0][1] if chunks else None
        results.append(Result(case=case, hit=hit, top_score=top, matched=matched))

    _report(results, k, settings)
    return 0 if _passes(results) else 1


def _by_kind(results: list[Result], kind: str) -> list[Result]:
    return [r for r in results if r.case["kind"] == kind]


def _score(result: Result) -> float:
    return result.top_score if result.top_score is not None else float("nan")


def _passes(results: list[Result]) -> bool:
    """The one hard failure: a nonsense query outranking a real one.

    Recall is a number to compare across configurations, not a bar to clear, so
    it is reported rather than asserted. This is different -- a configuration
    where gibberish outscores prose is broken whatever its recall says, and it is
    the exact shape of V1's finding.
    """
    real = [_score(r) for r in results if r.case["kind"] != "nonsense" and r.top_score is not None]
    nonsense = [_score(r) for r in _by_kind(results, "nonsense") if r.top_score is not None]
    if not real or not nonsense:
        return True
    return max(nonsense) < min(real)


def _report(results: list[Result], k: int, settings) -> None:
    print(f"per-case, recall@{k}")
    print("-" * 64)
    for result in results:
        nonsense = result.case["kind"] == "nonsense"
        mark = "    " if nonsense else ("HIT " if result.hit else "MISS")
        score = "     -" if result.top_score is None else f"{result.top_score:6.4f}"
        print(f"  {mark} {score}  {result.case['id']:22s} {result.case['query'][:38]}")
    print()

    print(f"recall@{k} by kind -- backend={settings.vector_backend}, hybrid={settings.hybrid}")
    print("-" * 64)
    for kind in ("prose", "proper_noun"):
        group = _by_kind(results, kind)
        if not group:
            continue
        hits = sum(1 for r in group if r.hit)
        print(f"  {kind:14s} {hits}/{len(group)}  ({hits / len(group):.0%})")
    print()

    real = [r for r in results if r.case["kind"] != "nonsense" and r.top_score is not None]
    nonsense = [r for r in _by_kind(results, "nonsense") if r.top_score is not None]
    print("score separation")
    print("-" * 64)
    if not real or not nonsense:
        print("  not measurable: the backend returned no scores")
        return

    worst_real = min(real, key=_score)
    best_nonsense = max(nonsense, key=_score)
    gap = _score(worst_real) - _score(best_nonsense)
    print(f"  worst real query     {_score(worst_real):6.4f}  {worst_real.case['id']}")
    print(f"  best nonsense query  {_score(best_nonsense):6.4f}  {best_nonsense.case['id']}")
    print(f"  gap                  {gap:+6.4f}")
    print()

    if gap <= 0:
        print("  FAIL: a nonsense query outranks a real one.")
        print("  This is V1's finding: a rare token can rank BELOW plausible prose under")
        print("  dense-only retrieval. Try RAG_HYBRID=true on Qdrant and re-run.")
    else:
        print("  PASS: every real query outranks every nonsense one.")

    if settings.vector_backend == "qdrant" and settings.hybrid:
        print()
        print("  NOTE: these are rank-fusion scores, not similarities. Gibberish has")
        print("  measured 0.5 here while clearing a configured RAG_SCORE_THRESHOLD of 0.2,")
        print("  so read the SEPARATION above and never the absolute values.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="index DATA_DIR before measuring. Required on a first run.",
    )
    parser.add_argument("-k", type=int, default=None, help="chunks per query (default RAG_TOP_K)")
    args = parser.parse_args()

    if os.getenv("PYTHON_DOTENV_DISABLED"):
        print("PYTHON_DOTENV_DISABLED is set; .env will not be read.", file=sys.stderr)

    k = args.k or load_rag_settings().top_k
    return asyncio.run(run(k, args.rebuild))


if __name__ == "__main__":
    raise SystemExit(main())
