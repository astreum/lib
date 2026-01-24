from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.node import Node
from astreum.storage.cold.get import get_atom_from_cold_storage
from astreum.storage.cold.insert import insert_atom_into_cold_storage
from astreum.storage.models.atom import Atom, AtomKind


class TestColdStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.node = Node(
            {
                "cold_storage_path": self.temp_dir.name,
                "cold_storage_scale": "KB",
                "default_seed": None,
                "verbose": False,
            }
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _make_atom(value: int) -> Atom:
        data = value.to_bytes(64, "big", signed=False)
        return Atom(data=data, kind=AtomKind.BYTES)

    def test_compaction_merges_to_level_2(self) -> None:
        level_2_path = Path(self.temp_dir.name) / "level_2"
        expected: dict[bytes, bytes] = {}

        max_atoms = 64
        for value in range(1, max_atoms + 1):
            atom = self._make_atom(value)
            atom_id = atom.object_id()
            expected[atom_id] = atom.data
            stored = insert_atom_into_cold_storage(self.node, atom)
            self.assertTrue(stored, "failed to store atom")
            if level_2_path.exists() and any(level_2_path.glob("*_index")):
                break
        else:
            self.fail("cold storage did not merge into level_2")

        self.assertTrue(level_2_path.exists(), "level_2 directory missing")
        self.assertTrue(any(level_2_path.glob("*_data")), "level_2 data file missing")
        level_1_path = Path(self.temp_dir.name) / "level_1"
        if level_1_path.exists():
            self.assertFalse(
                any(level_1_path.glob("*_index")),
                "level_1 index files should be cleared after merge",
            )
            self.assertFalse(
                any(level_1_path.glob("*_data")),
                "level_1 data files should be cleared after merge",
            )

        rng = random.Random(1337)
        sample_size = min(5, len(expected))
        for atom_id in rng.sample(list(expected.keys()), k=sample_size):
            atom = get_atom_from_cold_storage(self.node, atom_id)
            self.assertIsNotNone(atom, "missing atom after compaction")
            self.assertEqual(atom.data, expected[atom_id], "atom data mismatch")


if __name__ == "__main__":
    unittest.main()
