from __future__ import annotations

import contextlib
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine.models.expression import Expr, resolve_inner_exprs, resolve_list_exprs
from astreum.node import Node
from astreum.communication.object_response.object_found import (
    OBJECT_FOUND_ATOM_PAYLOAD,
    OBJECT_FOUND_LIST_PAYLOAD,
)
from astreum.storage.advertisments import advertise_exprs
from astreum.storage.actions.set import _hot_storage_set
from tests.storage.utils import generate_nearest_expr, generate_nearest_expr_list


class TestStorageIndexing(unittest.TestCase):
    def setUp(self) -> None:
        self._nodes: list[Node] = []

    def tearDown(self) -> None:
        for node in self._nodes:
            self._shutdown_node(node)

    def _register_node(self, node: Node) -> Node:
        self._nodes.append(node)
        return node

    @staticmethod
    def _shutdown_node(node: Node) -> None:
        for attr in ("socket",):
            sock = getattr(node, attr, None)
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()

    @staticmethod
    def _get_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _connect_nodes(self) -> tuple[Node, Node]:
        node_a_port = self._get_free_port()
        node_a = self._register_node(
            Node({"incoming_port": node_a_port, "default_seed": None, "verbose": True})
        )

        node_a_thread = threading.Thread(target=node_a.connect, daemon=True)
        node_a_thread.start()
        node_a_thread.join(timeout=5)
        self.assertTrue(node_a.is_connected)

        bootstrap_host = "127.0.0.1"
        bootstrap_port = node_a.config["incoming_port"]
        node_b_port = self._get_free_port()

        node_b = self._register_node(
            Node(
                {
                    "incoming_port": node_b_port,
                    "default_seed": None,
                    "additional_seeds": [f"{bootstrap_host}:{bootstrap_port}"],
                    "verbose": True,
                }
            )
        )

        node_b_thread = threading.Thread(target=node_b.connect, daemon=True)
        node_b_thread.start()
        node_b_thread.join(timeout=5)

        self.assertTrue(node_b.is_connected)

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

        while time.time() < deadline:
            if node_b.get_peer(node_b_peer_key):
                break
            time.sleep(0.1)
        else:
            self.fail("node_b did not register node_a before timeout")

        return node_a, node_b

    def test_closest_atom_advertisement(self) -> None:
        """
        Test that an advertisement for an expr closer to node_b is indexed by node_b.
        1. Connect node_a and node_b.
        2. Create an expr closest to node_b.
        3. Advertise it immediately from node_a.
        4. Wait for the object to be seen in node_b index.
        5. Fetch the expr and list from node_b.
        """
        node_a, node_b = self._connect_nodes()

        print(f"Node A ID: {node_a.relay_public_key_bytes.hex()}")
        print(f"Node B ID: {node_b.relay_public_key_bytes.hex()}")

        def wait_for_index(expr_id: bytes, label: str) -> None:
            deadline = time.time() + 10
            print(f"Waiting for {label} to appear in Node B's index...")
            while time.time() < deadline:
                provider_id = node_b.storage_index.get(expr_id)
                if provider_id is not None:
                    print(f"{label} found in index! Provider ID: {provider_id}")
                    return
                time.sleep(0.1)
            self.fail(f"Node B did not index the advertised {label}")

        def wait_for_expr(expr_id: bytes, label: str) -> None:
            deadline = time.time() + 10
            print(f"Waiting for {label} to be fetched by Node B...")
            while time.time() < deadline:
                expr = node_b.get_expr(expr_id)
                if expr is not None:
                    print(f"{label} fetched by Node B.")
                    return
                time.sleep(0.1)
            self.fail(f"Node B did not fetch the advertised {label}")

        def wait_for_list(root_id: bytes, label: str, expected_size: int) -> None:
            deadline = time.time() + 10
            print(f"Waiting for {label} to be fetched by Node B...")
            while time.time() < deadline:
                header = node_b.get_expr_list(root_id)
                if header is not None:
                    items, _ = resolve_list_exprs(node_b, header)
                    self.assertEqual(
                        len(items),
                        expected_size,
                        "node_b returned an unexpected list size",
                    )
                    print(f"{label} fetched by Node B.")
                    return
                time.sleep(0.1)
            self.fail(f"Node B did not fetch the advertised {label}")

        target_expr = generate_nearest_expr(
            node_a.relay_public_key_bytes,
            node_b.relay_public_key_bytes,
        )
        expr_id = target_expr.hash()

        # Store in A so it can serve/advertise it
        exprs, _ = resolve_inner_exprs(node_a, target_expr)
        for expr in exprs:
            self.assertTrue(_hot_storage_set(node_a, expr), "node_a failed to store expr")

        # Advertise it immediately
        print("Advertising expr from Node A...")
        advertise_exprs(node_a, entries=[(expr_id, OBJECT_FOUND_ATOM_PAYLOAD, None)])
        wait_for_index(expr_id, "expr")
        wait_for_expr(expr_id, "expr")

        list_size = 4
        list_chain = generate_nearest_expr_list(
            node_a.relay_public_key_bytes,
            node_b.relay_public_key_bytes,
            list_size=list_size,
        )
        list_root_id = list_chain.hash()
        list_exprs, _ = resolve_inner_exprs(node_a, list_chain)
        for expr in list_exprs:
            self.assertTrue(_hot_storage_set(node_a, expr), "node_a failed to store list expr")

        print("Advertising list from Node A...")
        advertise_exprs(node_a, entries=[(list_root_id, OBJECT_FOUND_LIST_PAYLOAD, None)])
        wait_for_index(list_root_id, "list")
        wait_for_list(list_root_id, "list", list_size)


if __name__ == "__main__":
    unittest.main()
