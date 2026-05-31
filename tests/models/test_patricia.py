import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.storage.models.trie import Trie


class TestTrie(unittest.TestCase):
    def setUp(self):
        self.storage_node = MagicMock()
        self.storage_node.get_expr.return_value = None
        self.trie = Trie()

    def test_single_insert_and_get(self):
        key = b"\xAA\xBB\xCC"
        value = b"value1"
        self.trie.put(self.storage_node, key, value)
        result = self.trie.get(self.storage_node, key)
        self.assertIsNotNone(result, "Inserted key should be found")
        self.assertEqual(result, value, "Stored value should round-trip")

    def test_update_existing_key(self):
        key = b"\x01"
        self.trie.put(self.storage_node, key, b"v1")
        self.trie.put(self.storage_node, key, b"v2")
        result = self.trie.get(self.storage_node, key)
        self.assertIsNotNone(result)
        self.assertEqual(result, b"v2", "Latest value should win")

    def test_multiple_keys(self):
        kv = {
            b"\x00": b"a",
            b"\x01": b"b",
            b"\x10": b"c",
            b"\xAB\xCD": b"d",
        }
        for k, v in kv.items():
            self.trie.put(self.storage_node, k, v)
        for k, v in kv.items():
            result = self.trie.get(self.storage_node, k)
            self.assertIsNotNone(result)
            self.assertEqual(result, v)

    def test_missing_key_returns_none(self):
        self.assertIsNone(self.trie.get(self.storage_node, b"\xFF"))


if __name__ == '__main__':
    unittest.main(verbosity=2)
