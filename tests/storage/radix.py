from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.expression import Expr, bytes_, ZERO32
from astreum.node import Node
from astreum.storage.radix import (
    RadixTree,
    get_from_radix_tree,
    get_all_from_radix_tree,
    put_in_radix_tree,
    clone_radix_tree,
)


class TestRadixTree(unittest.TestCase):
    def setUp(self):
        self.storage_node = Node({"default_seed": None, "verbose": False})
        self.trie = RadixTree()

    # ------------------------------------------------------------------
    # Basic put / get
    # ------------------------------------------------------------------

    def test_single_insert_and_get(self):
        key = b"\xAA\xBB\xCC"
        value = bytes_(b"value1")
        put_in_radix_tree(self.trie, self.storage_node, key, value)
        result = get_from_radix_tree(self.trie, self.storage_node, key)
        self.assertIsNotNone(result)
        self.assertEqual(result.value, value.value)

    def test_update_existing_key(self):
        key = b"\x01"
        put_in_radix_tree(self.trie, self.storage_node, key, bytes_(b"v1"))
        put_in_radix_tree(self.trie, self.storage_node, key, bytes_(b"v2"))
        result = get_from_radix_tree(self.trie, self.storage_node, key)
        self.assertIsNotNone(result)
        self.assertEqual(result.value, b"v2")

    def test_multiple_keys(self):
        kv = {
            b"\x00": bytes_(b"a"),
            b"\x01": bytes_(b"b"),
            b"\x10": bytes_(b"c"),
            b"\xAB\xCD": bytes_(b"d"),
        }
        for k, v in kv.items():
            put_in_radix_tree(self.trie, self.storage_node, k, v)
        for k, v in kv.items():
            result = get_from_radix_tree(self.trie, self.storage_node, k)
            self.assertIsNotNone(result)
            self.assertEqual(result.value, v.value)

    def test_missing_key_returns_none(self):
        self.assertIsNone(get_from_radix_tree(self.trie, self.storage_node, b"\xFF"))

    def test_empty_tree(self):
        self.assertIsNone(get_from_radix_tree(self.trie, self.storage_node, b"\x01"))

    def test_empty_tree_root_zero(self):
        trie = RadixTree(root_hash=ZERO32)
        self.assertIsNone(get_from_radix_tree(trie, self.storage_node, b"\x01"))

    # ------------------------------------------------------------------
    # get_all
    # ------------------------------------------------------------------

    def test_get_all_empty_tree(self):
        self.assertEqual(get_all_from_radix_tree(self.trie, self.storage_node), {})

    def test_get_all_single_entry(self):
        key = b"\xAA\xBB\xCC"
        value = bytes_(b"value1")
        put_in_radix_tree(self.trie, self.storage_node, key, value)
        result = get_all_from_radix_tree(self.trie, self.storage_node)
        self.assertEqual(len(result), 1)
        self.assertIn(key, result)
        self.assertEqual(result[key].value, value.value)

    def test_get_all_multiple_entries(self):
        kv = {
            b"\x00": bytes_(b"a"),
            b"\x01": bytes_(b"b"),
            b"\x10": bytes_(b"c"),
            b"\xAB\xCD": bytes_(b"d"),
        }
        for k, v in kv.items():
            put_in_radix_tree(self.trie, self.storage_node, k, v)
        result = get_all_from_radix_tree(self.trie, self.storage_node)
        self.assertEqual(len(result), len(kv))
        for k, v in kv.items():
            self.assertIn(k, result)
            self.assertEqual(result[k].value, v.value)

    def test_get_all_after_overwrite(self):
        key = b"\x01"
        put_in_radix_tree(self.trie, self.storage_node, key, bytes_(b"v1"))
        put_in_radix_tree(self.trie, self.storage_node, key, bytes_(b"v2"))
        result = get_all_from_radix_tree(self.trie, self.storage_node)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[key].value, b"v2")

    def test_get_all_excludes_absent(self):
        put_in_radix_tree(self.trie, self.storage_node, b"\x00", bytes_(b"a"))
        put_in_radix_tree(self.trie, self.storage_node, b"\x01", bytes_(b"b"))
        result = get_all_from_radix_tree(self.trie, self.storage_node)
        self.assertNotIn(b"\xFF", result)
        self.assertNotIn(b"\x02", result)

    def test_get_all_shared_prefix(self):
        put_in_radix_tree(self.trie, self.storage_node, b"\xAB", bytes_(b"v1"))
        put_in_radix_tree(self.trie, self.storage_node, b"\xAC", bytes_(b"v2"))
        result = get_all_from_radix_tree(self.trie, self.storage_node)
        self.assertEqual(len(result), 2)
        self.assertIn(b"\xAB", result)
        self.assertIn(b"\xAC", result)
        self.assertEqual(result[b"\xAB"].value, b"v1")
        self.assertEqual(result[b"\xAC"].value, b"v2")

    def test_get_all_root_only(self):
        put_in_radix_tree(self.trie, self.storage_node, b"\xFF", bytes_(b"root"))
        result = get_all_from_radix_tree(self.trie, self.storage_node)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[b"\xFF"].value, b"root")


    # ------------------------------------------------------------------
    # clone
    # ------------------------------------------------------------------

    def test_clone_radix_tree_empty(self):
        cloned = clone_radix_tree(self.trie)
        self.assertIsNotNone(cloned)
        self.assertIsNone(cloned.root_hash)

    def test_clone_radix_tree_populated(self):
        put_in_radix_tree(self.trie, self.storage_node, b"\xAB", bytes_(b"original"))
        cloned = clone_radix_tree(self.trie)

        self.assertIsNot(cloned, self.trie)
        self.assertEqual(
            get_from_radix_tree(cloned, self.storage_node, b"\xAB").value,
            b"original",
        )

        put_in_radix_tree(cloned, self.storage_node, b"\xAB", bytes_(b"mutated"))
        original_value = get_from_radix_tree(
            self.trie, self.storage_node, b"\xAB"
        ).value
        self.assertEqual(original_value, b"original", "clone must be a deep copy")

    # ------------------------------------------------------------------
    # Edge-case trie shapes
    # ------------------------------------------------------------------

    def test_shared_prefix_split(self):
        key1 = b"\xAB"
        key2 = b"\xAC"
        put_in_radix_tree(self.trie, self.storage_node, key1, bytes_(b"v1"))
        put_in_radix_tree(self.trie, self.storage_node, key2, bytes_(b"v2"))
        self.assertEqual(
            get_from_radix_tree(self.trie, self.storage_node, key1).value, b"v1"
        )
        self.assertEqual(
            get_from_radix_tree(self.trie, self.storage_node, key2).value, b"v2"
        )

    def test_append_leaf(self):
        put_in_radix_tree(self.trie, self.storage_node, b"\x00", bytes_(b"root"))
        put_in_radix_tree(
            self.trie, self.storage_node, b"\x00\x01", bytes_(b"child")
        )
        self.assertEqual(
            get_from_radix_tree(self.trie, self.storage_node, b"\x00").value,
            b"root",
        )
        self.assertEqual(
            get_from_radix_tree(self.trie, self.storage_node, b"\x00\x01").value,
            b"child",
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)
