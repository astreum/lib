import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.consensus.transaction.treasury.record import (
    TreasuryUserRecord,
    encode_treasury_user_record,
)
from astreum.storage.models.atom import AtomKind


class TestTreasuryRecord(unittest.TestCase):
    def test_encode_uses_expected_field_order(self):
        loans_root_hash = b"\x01" * 32
        record = TreasuryUserRecord(
            stake_balance=7,
            loans_root_hash=loans_root_hash,
            total_interest_paid=3,
        )

        record_head, atoms = encode_treasury_user_record(record)

        self.assertEqual(record_head, atoms[0].object_id())
        self.assertEqual([atom.kind for atom in atoms], [AtomKind.BYTES] * 3)
        self.assertEqual(atoms[0].data, b"\x07")
        self.assertEqual(atoms[1].data, loans_root_hash)
        self.assertEqual(atoms[2].data, b"\x03")


if __name__ == "__main__":
    unittest.main()
