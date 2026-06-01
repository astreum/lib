import sys
import socket
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.node import Node  # noqa: E402
from astreum.machine.models.expression import Expr, resolve_inner_exprs  # noqa: E402
from astreum.validation.models.block import Block  # noqa: E402
from astreum.communication.difficulty import message_difficulty  # noqa: E402


class TestNodeValidation(unittest.TestCase):
    @staticmethod
    def _get_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def test_latest_block_stored_locally(self) -> None:
        port = self._get_free_port()
        node = Node(
            config={
                "incoming_port": port,
                "default_seed": None,
                "additional_seeds": [],
                "storage_index_interval": 1,
                "verbose": True,
                "atom_fetch_interval": 1,
                "verbose": True,
            }
        )
        try:
            secret_key = Ed25519PrivateKey.generate()
            node.validate(secret_key)

            time.sleep(5)
            latest_hash = node.latest_block_hash
            self.assertIsNotNone(latest_hash)

            loaded = Block.from_storage(node, latest_hash)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.expr_id, latest_hash)
        finally:
            node.disconnect()

    def test_validate_initializes_genesis_block(self) -> None:
        node = Node()
        node.connect()

        secret_key = Ed25519PrivateKey.generate()
        node.validate(secret_key)

        self.assertIsNotNone(node.latest_block_hash)
        self.assertIsNotNone(node.latest_block)


        initial_hash = node.latest_block_hash
        timeout = time.time() + 10
        while time.time() < timeout:
            current_hash = node.latest_block_hash
            if current_hash != initial_hash and current_hash is not None:
                break
            time.sleep(0.1)
        

    def test_latest_block_loads_from_default_seed(self) -> None:
        port_a = self._get_free_port()
        node_a = Node(
            config={
                "incoming_port": port_a,
                "default_seed": None,
                "additional_seeds": [],
                "storage_index_interval": 1,
                "atom_fetch_interval": 1,
                "verbose": False,
                "logger_name": "node a",
            }
        )
        node_a.connect()
        node_b = None
        try:
            secret_key = Ed25519PrivateKey.generate()
            node_a.validate(secret_key)

            timeout = time.time() + 10
            while time.time() < timeout:
                latest_a = node_a.latest_block
                if latest_a is not None and int(latest_a.height or 0) >= 1:
                    break
                time.sleep(0.1)
            self.assertIsNotNone(node_a.latest_block)

            port_a = node_a.config["incoming_port"]
            port_b = self._get_free_port()
            node_b = Node(
                config={
                    "incoming_port": port_b,
                    "default_seed": f"127.0.0.1:{port_a}",
                    "additional_seeds": [],
                    "storage_index_interval": 1,
                    "atom_fetch_interval": 8,
                    "verbose": False,
                    "logger_name": "node b",
                }
            )
            node_b.connect()

            node_a_peer_key = getattr(node_b, "relay_public_key_bytes", None)
            node_b_peer_key = getattr(node_a, "relay_public_key_bytes", None)
            self.assertIsNotNone(node_a_peer_key)
            self.assertIsNotNone(node_b_peer_key)

            deadline = time.time() + 10
            while time.time() < deadline:
                if node_a.get_peer(node_a_peer_key):
                    break
                time.sleep(0.1)
            else:
                self.fail("node_a did not register node_b before timeout")

            deadline = time.time() + 10
            while time.time() < deadline:
                if node_b.get_peer(node_b_peer_key):
                    break
                time.sleep(0.1)
            else:
                self.fail("node_b did not register node_a before timeout")

            time.sleep(5)
            timeout = time.time() + 5
            while time.time() < timeout:
                if node_b.latest_block_hash is not None:
                    break
                time.sleep(0.1)

            latest_hash = node_b.latest_block_hash
            self.assertIsNotNone(
                latest_hash,
                "node B should receive latest_block_hash after connecting to node A",
            )
            self.assertTrue(
                latest_hash in node_a.storage_index or latest_hash in node_b.storage_index,
                "latest_block_hash should appear in node storage index",
            )

            node_a_block = Block.from_storage(node_a, latest_hash)
            self.assertIsNotNone(
                node_a_block,
                "node A should load latest block from storage",
            )

            node_a_header = node_a.get_expr_list(latest_hash)
            self.assertIsNotNone(
                node_a_header,
                "node A should load latest block header from storage",
            )
            node_a_header_items, _ = resolve_inner_exprs(node_a, node_a_header)
            self.assertIsNotNone(
                node_a_block.body_hash,
                "node A should have a block body list hash",
            )
            body_expr = node_a.get_expr_list(node_a_block.body_hash)
            self.assertIsNotNone(
                body_expr,
                "node A should load block body list from storage",
            )
            body_items, _ = resolve_inner_exprs(node_a, body_expr)
            self.assertTrue(
                node_a_block.body_hash in node_a.storage_index or node_a_block.body_hash in node_b.storage_index,
                "block body hash should appear in node storage index",
            )

            loaded_block = None
            for _ in range(3):
                header_b = node_b.get_expr_list(latest_hash)
                self.assertIsNotNone(
                    header_b,
                    "node B should load latest block header from storage",
                )
                header_b_items, _ = resolve_inner_exprs(node_b, header_b)
                node_a_header_hashes = [expr.hash() for expr in node_a_header_items]
                header_hashes = [expr.hash() for expr in header_b_items]
                self.assertEqual(
                    node_a_header_hashes,
                    header_hashes,
                    "node B header list should match node A",
                )
                if header_b_items and len(header_b_items) >= 4:
                    body_node = header_b_items[0]
                    if isinstance(body_node, Expr.Link):
                        body_b = node_b.get_expr_list(body_node.hash())
                        self.assertIsNotNone(
                            body_b,
                            "node B should load block details list from storage",
                        )
                        body_b_items, _ = resolve_inner_exprs(node_b, body_b)
                        node_a_body_hashes = [expr.hash() for expr in body_items]
                        body_hashes = [expr.hash() for expr in body_b_items]
                        self.assertEqual(
                            node_a_body_hashes,
                            body_hashes,
                            "node B details list should match node A",
                        )
                loaded_block = Block.from_storage(node_b, latest_hash)
                if loaded_block is not None:
                    break
                time.sleep(3)

            self.assertIsNotNone(
                loaded_block,
                "node B should load latest block from storage",
            )
        finally:
            if node_b is not None:
                node_b.disconnect()
            node_a.disconnect()


if __name__ == "__main__":

    unittest.main()
