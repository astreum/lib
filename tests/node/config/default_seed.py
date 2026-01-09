from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.communication.util import get_bootstrap_peers  # noqa: E402
from astreum.node import Node  # noqa: E402
from astreum.utils.config import DEFAULT_SEED  # noqa: E402


class TestDefaultSeed(unittest.TestCase):
    def test_default_seed_none_no_bootstrap(self) -> None:
        node = Node({"default_seed": None, "additional_seeds": []})
        peers = get_bootstrap_peers(node)
        self.assertIsInstance(peers, list)
        self.assertEqual(peers, [])
        self.assertNotIn(DEFAULT_SEED, peers)

    def test_default_seed_none_uses_additional(self) -> None:
        node = Node({"default_seed": None, "additional_seeds": ["1.2.3.4:55"]})
        peers = get_bootstrap_peers(node)
        self.assertEqual(peers, ["1.2.3.4:55"])

    def test_bootstrap_peers_cached(self) -> None:
        node = Node({"default_seed": None, "additional_seeds": ["1.2.3.4:55"]})
        peers_first = get_bootstrap_peers(node)
        node.config["additional_seeds"].append("1.2.3.5:55")
        peers_second = get_bootstrap_peers(node)
        self.assertIs(peers_first, peers_second)
        self.assertEqual(peers_second, ["1.2.3.4:55"])


if __name__ == "__main__":
    unittest.main()
