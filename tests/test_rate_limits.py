"""D6: the rate limiter, both halves.

The arithmetic is tested without a clock or a server -- `TokenBucket` takes
`now` as an argument precisely so that "an idle hour must not buy an hour's
burst" is a two-line assertion instead of a sleep.
"""

from __future__ import annotations

import unittest

from sentient.core.limits import BucketRegistry, TokenBucket


class TokenBucketTests(unittest.TestCase):
    def test_a_fresh_bucket_allows_up_to_capacity(self):
        bucket = TokenBucket(capacity=3, refill_per_second=1)
        self.assertTrue(bucket.take(now=0))
        self.assertTrue(bucket.take(now=0))
        self.assertTrue(bucket.take(now=0))
        self.assertFalse(bucket.take(now=0))

    def test_it_refills_over_time(self):
        bucket = TokenBucket(capacity=3, refill_per_second=1)
        for _ in range(3):
            bucket.take(now=0)
        self.assertFalse(bucket.take(now=0.5))
        self.assertTrue(bucket.take(now=1.0))

    def test_it_never_refills_past_capacity(self):
        # An idle hour must not buy an hour's burst. This is the whole reason a
        # bucket beats a fixed window and it is the easiest part to get wrong.
        bucket = TokenBucket(capacity=3, refill_per_second=1)
        bucket.take(now=0)
        for _ in range(3):
            self.assertTrue(bucket.take(now=3600))
        self.assertFalse(bucket.take(now=3600))

    def test_retry_after_is_when_the_next_token_lands(self):
        bucket = TokenBucket(capacity=1, refill_per_second=2)
        bucket.take(now=0)
        self.assertAlmostEqual(bucket.retry_after(now=0), 0.5, places=3)

    def test_retry_after_is_zero_while_the_bucket_still_has_tokens(self):
        bucket = TokenBucket(capacity=2, refill_per_second=1)
        self.assertEqual(bucket.retry_after(now=0), 0.0)

    def test_a_refused_take_costs_nothing(self):
        # A rejected request must not drain the bucket further, or a client that
        # keeps retrying would push its own recovery further away every time.
        bucket = TokenBucket(capacity=1, refill_per_second=1)
        bucket.take(now=0)
        for _ in range(10):
            self.assertFalse(bucket.take(now=0))
        self.assertTrue(bucket.take(now=1.0))

    def test_time_never_goes_backwards(self):
        # perf_counter is monotonic, but a bucket handed a smaller `now` must not
        # mint negative elapsed time and silently drain itself.
        bucket = TokenBucket(capacity=2, refill_per_second=1)
        bucket.take(now=10)
        self.assertTrue(bucket.take(now=5))


class BucketRegistryTests(unittest.TestCase):
    def test_two_identities_do_not_share_a_budget(self):
        registry = BucketRegistry(capacity=1, refill_per_second=1)
        self.assertEqual(registry.allow("user-a", now=0)[0], True)
        self.assertEqual(registry.allow("user-a", now=0)[0], False)
        self.assertEqual(registry.allow("user-b", now=0)[0], True)

    def test_a_refusal_reports_how_long_to_wait(self):
        registry = BucketRegistry(capacity=1, refill_per_second=2)
        registry.allow("user-a", now=0)
        allowed, retry_after = registry.allow("user-a", now=0)
        self.assertFalse(allowed)
        self.assertAlmostEqual(retry_after, 0.5, places=3)

    def test_it_evicts_rather_than_growing_without_bound(self):
        # An unauthenticated flood from many hosts must not become a memory leak
        # -- the limiter becoming the outage it exists to prevent.
        registry = BucketRegistry(capacity=1, refill_per_second=1, maxsize=2)
        for index in range(50):
            registry.allow(f"host-{index}", now=0)
        self.assertLessEqual(len(registry), 2)
