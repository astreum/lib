import sys
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.node import Node  # noqa: E402


class TestNodeValidation(unittest.TestCase):
    def test_validate_initializes_genesis_block(self) -> None:
        node = Node()
        node.connect()

        secret_key = Ed25519PrivateKey.generate()
        node.validate(secret_key)

        self.assertIsNotNone(node.latest_block_hash)
        self.assertIsNotNone(node.latest_block)

        latest_hash = node.latest_block_hash or b""
        hash_str = (
            latest_hash.hex()
            if isinstance(latest_hash, (bytes, bytearray))
            else str(latest_hash)
        )
        print(f"latest_block_hash: {hash_str}")

        initial_hash = node.latest_block_hash
        timeout = time.time() + 5
        while time.time() < timeout:
            current_hash = node.latest_block_hash
            if current_hash != initial_hash and current_hash is not None:
                new_hash_str = (
                    current_hash.hex()
                    if isinstance(current_hash, (bytes, bytearray))
                    else str(current_hash)
                )
                print(f"new latest_block_hash: {new_hash_str}")
                break
            time.sleep(0.1)
        else:
            print("latest_block_hash did not change before timeout")


if __name__ == "__main__":
    unittest.main()
