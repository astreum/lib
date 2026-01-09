from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.node import Node  # noqa: E402
from astreum.utils.config import DEFAULT_SEED  # noqa: E402


class TestDefaultSeed(unittest.TestCase):
    def test_default_seed_none_no_bootstrap(self) -> None:
        node = Node({"default_seed": None, "additional_seeds": []})
        peers = node.bootstrap_peers
        self.assertIsInstance(peers, list)
        self.assertEqual(peers, [])
        self.assertNotIn(DEFAULT_SEED, peers)

    def test_default_seed_none_uses_additional(self) -> None:
        node = Node({"default_seed": None, "additional_seeds": ["1.2.3.4:55"]})
        peers = node.bootstrap_peers
        self.assertEqual(peers, ["1.2.3.4:55"])

    def test_bootstrap_peers_cached(self) -> None:
        node = Node({"default_seed": None, "additional_seeds": ["1.2.3.4:55"]})
        peers_first = node.bootstrap_peers
        node.config["additional_seeds"].append("1.2.3.5:55")
        peers_second = node.bootstrap_peers
        self.assertIs(peers_first, peers_second)
        self.assertEqual(peers_second, ["1.2.3.4:55"])

    def test_default_seed_none_no_bootstrap_ping(self) -> None:
        node = Node({"default_seed": None, "additional_seeds": []})
        incoming_socket = mock.MagicMock()
        incoming_socket.getsockname.return_value = ("0.0.0.0", 12345)
        outgoing_socket = mock.MagicMock()
        with mock.patch(
            "astreum.communication.setup.socket.socket",
            side_effect=[incoming_socket, outgoing_socket],
        ), mock.patch(
            "astreum.communication.setup.threading.Thread",
        ) as thread_cls, mock.patch(
            "astreum.communication.setup.enqueue_outgoing",
        ) as enqueue_outgoing_mock:
            thread_cls.return_value = mock.MagicMock()
            node.connect()
        enqueue_outgoing_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
