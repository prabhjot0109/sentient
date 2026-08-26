"""Rate limiting, as arithmetic. No I/O, no framework.

`core/` rules apply, and they buy something concrete here: `now` is an argument
rather than a call to a clock, so "an idle hour must not buy an hour's burst" is
an assertion instead of a sleep.

**In-process on purpose.** Every other stateful component in this system is
already per-worker -- `ObjectRegistry`, `IngestQueue`, `SessionLocks`,
`RuntimeCache`. Making the limiter the one piece that needs Redis would buy a
shared store for the cheapest component in the system, and X5 (horizontal scale)
is deferred until D5 shows one box is the constraint. The cost is stated rather
than hidden: **with N replicas the effective limit is N x the configured one.**
See README, "Rate limits".
"""

from __future__ import annotations

from cachetools import LRUCache


class TokenBucket:
    """Capacity tokens, refilled at `refill_per_second`, never above capacity.

    A fixed window would let a caller spend a whole minute's budget in 50 ms and
    do it again 10 ms after the boundary -- a 2x burst at the worst possible
    moment. A bucket smooths that for the same arithmetic and the same memory.
    """

    __slots__ = ("_capacity", "_refill", "_stamp", "_tokens")

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = float(capacity)
        self._refill = float(refill_per_second)
        self._tokens = float(capacity)
        self._stamp = 0.0

    def _advance(self, now: float) -> None:
        # max(0, ...) because a caller handing us a smaller `now` must not mint
        # negative elapsed time and drain the bucket. time.monotonic() will not
        # do that, but a bucket that only holds while its caller is careful is a
        # bucket with an invariant living somewhere else.
        elapsed = max(0.0, now - self._stamp)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)
        self._stamp = now

    def take(self, now: float, cost: int = 1) -> bool:
        """Spend `cost` tokens if they are there. A refusal costs nothing --
        a client that keeps retrying must not push its own recovery further away."""
        self._advance(now)
        if self._tokens < cost:
            return False
        self._tokens -= cost
        return True

    def retry_after(self, now: float, cost: int = 1) -> float:
        """Seconds until `cost` tokens exist. 0.0 when they already do."""
        self._advance(now)
        missing = max(0.0, cost - self._tokens)
        return missing / self._refill if self._refill > 0 else float("inf")


class BucketRegistry:
    """One bucket per identity, bounded.

    LRU rather than a plain dict: the unauthenticated surface is keyed on client
    host, so an unbounded dict would turn a flood into a memory leak -- the
    limiter becoming the outage it exists to prevent. Evicting a bucket forgives
    whatever that identity had spent, which is the right way to be wrong: the
    entry evicted is the least recently used one, so it belongs to a caller who
    is not currently flooding.
    """

    __slots__ = ("_buckets", "_capacity", "_refill")

    def __init__(self, capacity: int, refill_per_second: float, maxsize: int = 4096) -> None:
        self._capacity = capacity
        self._refill = refill_per_second
        self._buckets: LRUCache[str, TokenBucket] = LRUCache(maxsize=maxsize)

    def __len__(self) -> int:
        return len(self._buckets)

    def allow(self, identity: str, now: float, cost: int = 1) -> tuple[bool, float]:
        """`(allowed, seconds_to_wait)`. The second value is 0.0 when allowed."""
        bucket = self._buckets.get(identity)
        if bucket is None:
            bucket = TokenBucket(self._capacity, self._refill)
            self._buckets[identity] = bucket
        if bucket.take(now, cost):
            return True, 0.0
        return False, bucket.retry_after(now, cost)
