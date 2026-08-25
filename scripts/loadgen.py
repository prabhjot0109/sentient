"""V6 load harness. Not a test: it needs a live server and real providers, and
every backend gate is path-scoped to src/ and tests/, so it lives here.

Measures TTFT (time to first token) rather than total latency because TTFT is the
product's north star: a Skyrim NPC that starts speaking in 400 ms feels alive
even if the sentence takes three seconds to finish.

Usage:
    uv run python scripts/loadgen.py --project-map projects.json \
        --concurrency 10 --turns 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from typing import Any

import httpx

# 127.0.0.1, never localhost: Windows resolves localhost to ::1 first and uvicorn
# binds IPv4 only, costing a measured 208 ms per request -- which would land
# entirely inside the number this script exists to produce.
BASE = "http://127.0.0.1:8000"

PROMPT = "Greetings, traveller. What news from the road?"


async def one_turn(client: httpx.AsyncClient, api_key: str, project_id: str) -> dict[str, Any]:
    """One streamed completion over the Mantella route. Returns its timings."""
    started = time.perf_counter()
    ttft = None
    frames = 0

    body = {
        "model": "sentient",
        "stream": True,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    url = f"{BASE}/v1/{api_key}/{project_id}/chat/completions"

    try:
        async with client.stream("POST", url, json=body, timeout=120) as response:
            if response.status_code != 200:
                await response.aread()
                return {"ok": False, "status": response.status_code}
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                if line == "data: [DONE]":
                    break
                if ttft is None:
                    ttft = time.perf_counter() - started
                frames += 1
    except Exception as exc:  # noqa: BLE001 -- a harness must record failures, not raise them
        return {"ok": False, "status": type(exc).__name__}

    return {
        "ok": True,
        "ttft": ttft,
        "total": time.perf_counter() - started,
        "frames": frames,
    }


async def tenant(
    client: httpx.AsyncClient, api_key: str, project_id: str, turns: int
) -> list[dict[str, Any]]:
    return [await one_turn(client, api_key, project_id) for _ in range(turns)]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1))))
    return ordered[index]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-map", required=True, help='JSON: {"<api_key>": "<project_id>"}')
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--turns", type=int, default=5)
    args = parser.parse_args()

    with open(args.project_map) as handle:
        pairs = list(json.load(handle).items())

    # Wrap to --concurrency so N tenants can exceed the number of real keys.
    plan = [pairs[i % len(pairs)] for i in range(args.concurrency)]
    if args.concurrency > len(pairs):
        print(
            f"note: {args.concurrency} slots over {len(pairs)} distinct tenants, "
            f"so keys repeat and some slots share a vector tenant"
        )

    started = time.perf_counter()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(tenant(client, key, project, args.turns) for key, project in plan)
        )
    wall = time.perf_counter() - started

    flat = [item for batch in results for item in batch]
    ok = [item for item in flat if item["ok"]]
    ttfts = [item["ttft"] for item in ok if item["ttft"] is not None]
    totals = [item["total"] for item in ok]

    print(f"concurrency     {args.concurrency}  turns {args.turns}")
    print(f"requests        {len(flat)}  ok {len(ok)}  failed {len(flat) - len(ok)}")
    print(f"wall clock      {wall:.2f}s")
    print(f"TTFT   p50      {percentile(ttfts, 50) * 1000:.0f} ms")
    print(f"TTFT   p95      {percentile(ttfts, 95) * 1000:.0f} ms")
    print(f"total  p50      {percentile(totals, 50):.2f} s")
    print(f"total  p95      {percentile(totals, 95):.2f} s")
    if ttfts:
        print(f"TTFT   mean     {statistics.mean(ttfts) * 1000:.0f} ms")
    for item in flat:
        if not item["ok"]:
            print(f"  failure: {item['status']}")


if __name__ == "__main__":
    asyncio.run(main())
