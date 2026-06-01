"""Tests for BloomFilter: insert and test with specific element counts."""
import os
import unittest

from src.astreum.crypto.bloom_filter import BloomFilter, bloom_insert, bloom_test


class TestBloomFilterCounts(unittest.TestCase):

    def _test_count(self, n: int):
        bf = BloomFilter()
        elements = [os.urandom(32) for _ in range(n)]

        for e in elements:
            bloom_insert(bf, e)

        self.assertEqual(bf.count, n, f"count should be {n}")

        # No false negatives
        for e in elements:
            self.assertTrue(bloom_test(bf, e), f"element should test positive")

        # Expected tier count
        cum = 0
        expected_tiers = 0
        cap = 1
        while cum < n:
            cum += cap
            expected_tiers += 1
            cap = 1 << expected_tiers
        self.assertEqual(len(bf.tiers), expected_tiers,
                         f"expected {expected_tiers} tiers, got {len(bf.tiers)}")

    def test_count_1(self):
        self._test_count(1)

    def test_count_2(self):
        self._test_count(2)

    def test_count_3(self):
        self._test_count(3)

    def test_count_7(self):
        self._test_count(7)

    def test_count_17(self):
        self._test_count(17)

    def test_count_31(self):
        self._test_count(31)

    def test_count_61(self):
        self._test_count(61)

    def test_count_127(self):
        self._test_count(127)

    def test_count_257(self):
        self._test_count(257)


if __name__ == "__main__":
    unittest.main()
