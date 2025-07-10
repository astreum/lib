"""Unit tests for the fixed-height MerkleTree (unittest style).

Tests cover:
  - single-leaf construction and get
  - multiple leaves retrieval
  - updating existing leaves
  - out-of-bounds get returns None
  - out-of-bounds put raises IndexError

Assumes the code under test lives at `src/astreum/models/merkle.py`.
"""

import unittest

from src.astreum.models.merkle import MerkleTree


class TestMerkleTree(unittest.TestCase):
    def setUp(self):
        # Build a tree with three leaves: a, b, c
        self.leaves = [b'a', b'b', b'c']
        self.tree = MerkleTree.from_leaves(self.leaves, node_get=lambda _h: None)

    def test_single_leaf_get(self):
        """A single-leaf tree returns its only value, out-of-range returns None."""
        # Use a dedicated single-leaf tree, not the 3-leaf fixture
        single = MerkleTree.from_leaves([b'x'], node_get=lambda _h: None)
        self.assertEqual(single.get(0), b'x')
        self.assertIsNone(single.get(1))

    def test_multiple_leaves_get(self):
        """A multi-leaf tree returns each leaf at the correct index."""
        for idx, val in enumerate(self.leaves):
            with self.subTest(idx=idx):
                self.assertEqual(self.tree.get(idx), val)

    def test_update_leaf(self):
        """Updating an existing leaf overwrites only that leaf."""
        self.tree.put(1, b'b-updated')
        self.assertEqual(self.tree.get(1), b'b-updated')
        # Ensure other leaves remain unchanged
        self.assertEqual(self.tree.get(0), b'a')
        self.assertEqual(self.tree.get(2), b'c')

    def test_get_out_of_bounds(self):
        """Getting an index beyond capacity returns None."""
        self.assertIsNone(self.tree.get(100))

    def test_put_out_of_bounds_raises(self):
        """Putting beyond capacity raises IndexError."""
        with self.assertRaises(IndexError):
            self.tree.put(5, b'oops')


if __name__ == '__main__':
    unittest.main(verbosity=2)
