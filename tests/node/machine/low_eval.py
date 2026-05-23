import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import Meter  # noqa: E402
from astreum.machine.evaluations.low_evaluation import (  # noqa: E402
    int_to_tc,
    tc_to_int,
)
from astreum.node import Node  # noqa: E402


class TestLowEval(unittest.TestCase):
    def setUp(self):
        self.node = Node()

    def test_subtract_3_minus_2(self):
        # 3 - 2 = 1 via stack operations: -2 = nand(2,2) + 1, then 3 + (-2)
        code = [
            int_to_tc(2, 1), int_to_tc(2, 1), b"nand",  # ~2
            int_to_tc(1, 1), b"add",                    # ~2 + 1 = -2
            int_to_tc(3, 1), b"add",                    # 3 + (-2) = 1
        ]

        meter = Meter()
        result = self.node.low_eval(code, meter)
        self.assertEqual(tc_to_int(result.value), 1)


if __name__ == "__main__":
    unittest.main()
