"""Tests for BloomTree and BloomNode: insert and search."""
import os
import unittest

from src.astreum.crypto.bloom_tree import BloomNode, BloomTree, bloom_search


def make_variants(tx_hash: bytes, sender: bytes, receiver: bytes) -> list[bytes]:
    """Build 7 forced-combinatorial search variants (128 bytes each)."""
    z = b"\x00" * 32
    return [
        tx_hash + z + z + z,
        z + sender + z + z,
        z + z + receiver + z,
        tx_hash + sender + z + z,
        tx_hash + z + receiver + z,
        z + sender + receiver + z,
        tx_hash + sender + receiver + z,
    ]


class TestBloomTree(unittest.TestCase):

    def test_empty_search(self):
        results = bloom_search(None, os.urandom(128))
        self.assertEqual(results, [])

    def test_single_block_insert_and_search(self):
        tree = BloomTree(0)
        block_hash = os.urandom(32)
        tx_hash = os.urandom(32)
        sender = os.urandom(32)
        receiver = os.urandom(32)
        variants = make_variants(tx_hash, sender, receiver)

        tree.insert(0, block_hash, variants)

        # Search by tx hash variant
        self.assertEqual(bloom_search(tree.root, variants[0]), [block_hash])
        # Search by sender variant
        self.assertEqual(bloom_search(tree.root, variants[1]), [block_hash])
        # Search by receiver variant
        self.assertEqual(bloom_search(tree.root, variants[2]), [block_hash])

    def test_single_block_search_miss(self):
        tree = BloomTree(0)
        block_hash = os.urandom(32)
        variants = make_variants(os.urandom(32), os.urandom(32), os.urandom(32))

        tree.insert(0, block_hash, variants)
        self.assertEqual(bloom_search(tree.root, os.urandom(128)), [])

    def test_two_blocks_different_paths(self):
        tree = BloomTree(0)
        h1 = os.urandom(32)
        h2 = os.urandom(32)
        v1 = make_variants(os.urandom(32), os.urandom(32), os.urandom(32))
        v2 = make_variants(os.urandom(32), os.urandom(32), os.urandom(32))

        tree.insert(0, h1, v1)
        tree.insert(512, h2, v2)

        self.assertEqual(bloom_search(tree.root, v1[0]), [h1])
        self.assertEqual(bloom_search(tree.root, v2[0]), [h2])

    def test_leaf_returns_exact_block_hash(self):
        tree = BloomTree(0)
        block_hash = os.urandom(32)
        variants = make_variants(os.urandom(32), os.urandom(32), os.urandom(32))

        tree.insert(42, block_hash, variants)
        self.assertEqual(bloom_search(tree.root, variants[0]), [block_hash])

    def test_node_levels(self):
        """Root is level 0, children are level+1, leaf is level 10."""
        tree = BloomTree(0)
        variants = make_variants(os.urandom(32), os.urandom(32), os.urandom(32))

        tree.insert(0, os.urandom(32), variants)

        root = tree.root
        self.assertEqual(root.level, 0)
        self.assertEqual(root.width, 1024)
        self.assertFalse(root.is_leaf)

        # Walk down to leaf via left path
        node = root
        level = 0
        while not node.is_leaf:
            level += 1
            # offset 0 always goes left
            node = node.left
            self.assertEqual(node.level, level)
            self.assertEqual(node.width, 1024 >> level)

        self.assertEqual(node.level, 10)
        self.assertTrue(node.is_leaf)
        self.assertEqual(node.width, 1)
        self.assertIsNotNone(node.start_hash)

    def test_internal_nodes_no_start_hash(self):
        """Internal nodes should have start_hash=None."""
        tree = BloomTree(0)
        variants = make_variants(os.urandom(32), os.urandom(32), os.urandom(32))
        tree.insert(0, os.urandom(32), variants)

        # Root is internal, no start_hash
        self.assertIsNone(tree.root.start_hash)

        # Left child of root is internal (level 1, not leaf), no start_hash
        self.assertIsNone(tree.root.left.start_hash)


if __name__ == "__main__":
    unittest.main()
