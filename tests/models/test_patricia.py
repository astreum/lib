import unittest

from src.astreum.models.patricia import PatriciaTrie


class TestPatriciaTrie(unittest.TestCase):
    def setUp(self):
        # create empty trie with stubbed external node_get
        self.trie = PatriciaTrie(node_get=lambda _h: None)

    def test_single_insert_and_get(self):
        """Inserting a single key then retrieving it should return the correct value."""
        key = b"\xAA\xBB\xCC"
        value = b"value1"
        self.trie.put(key, value)
        result = self.trie.get(key)
        self.assertIsNotNone(result, "Inserted key should be found")
        self.assertEqual(result, value, "Stored value should round-trip")

    def test_update_existing_key(self):
        """Overwriting the same key should update its stored value."""
        key = b"\x01"
        self.trie.put(key, b"v1")
        self.trie.put(key, b"v2")
        result = self.trie.get(key)
        self.assertIsNotNone(result)
        self.assertEqual(result, b"v2", "Latest value should win")

    def test_multiple_keys(self):
        """Inserting multiple distinct keys should allow retrieving each correctly."""
        kv = {
            b"\x00": b"a",
            b"\x01": b"b",
            b"\x10": b"c",
            b"\xAB\xCD": b"d",
        }
        for k, v in kv.items():
            self.trie.put(k, v)
        for k, v in kv.items():
            result = self.trie.get(k)
            self.assertIsNotNone(result)
            self.assertEqual(result, v)

    def test_missing_key_returns_none(self):
        """Looking up a non-existent key should return None."""
        self.assertIsNone(self.trie.get(b"\xFF"))


if __name__ == '__main__':
    unittest.main(verbosity=2)
