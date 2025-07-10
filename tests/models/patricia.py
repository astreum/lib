import pytest

from src.astreum.models.patricia import PatriciaTrie


def _make_trie() -> PatriciaTrie:
    """Helper that creates an empty trie with a dummy external getter."""
    return PatriciaTrie(node_get=lambda _hash: None)


# ---------------------------------------------------------------------------
# single‑key round‑trip
# ---------------------------------------------------------------------------

def test_single_insert_and_get():
    trie = _make_trie()
    key = b"\xAA\xBB\xCC"  # three‑byte key (24 bits)
    value = b"value1"

    trie.put(key, value)
    node = trie.get(key)

    assert node is not None, "Inserted key should be found"
    assert node.value == value, "Stored value should round‑trip"


# ---------------------------------------------------------------------------
# overwrite existing key
# ---------------------------------------------------------------------------

def test_update_existing_key():
    trie = _make_trie()
    key = b"\x01"

    trie.put(key, b"v1")
    trie.put(key, b"v2")  # overwrite

    node = trie.get(key)
    assert node is not None
    assert node.value == b"v2", "Latest value should win"


# ---------------------------------------------------------------------------
# multiple distinct keys
# ---------------------------------------------------------------------------

def test_multiple_keys():
    trie = _make_trie()
    kv_pairs = {
        b"\x00": b"a",
        b"\x01": b"b",
        b"\x10": b"c",
        b"\xAB\xCD": b"d",
    }

    for k, v in kv_pairs.items():
        trie.put(k, v)

    for k, v in kv_pairs.items():
        node = trie.get(k)
        assert node is not None
        assert node.value == v


# ---------------------------------------------------------------------------
# non‑existent lookup
# ---------------------------------------------------------------------------

def test_missing_key_returns_none():
    trie = _make_trie()
    assert trie.get(b"\xFF") is None
