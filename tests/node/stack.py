import unittest
import importlib.util
from pathlib import Path

# Load src/astreum/_node.py directly to avoid package-level circular imports
_node_path = Path(__file__).resolve().parents[2] / "src" / "astreum" / "_node.py"
_spec = importlib.util.spec_from_file_location("_astreum_low_node", str(_node_path))
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)

Node = getattr(_mod, "Node")
Meter = getattr(_mod, "Meter")
int_to_tc = getattr(_mod, "int_to_tc")
tc_to_int = getattr(_mod, "tc_to_int")


class TestLowLevelStack(unittest.TestCase):
    def setUp(self):
        self.node = Node()

    def test_add_two_numbers(self):
        # Prepare two 1-byte two's-complement integers: 2 and 3
        a = int_to_tc(2, 1)
        b = int_to_tc(3, 1)

        # Program: push 2, push 3, add
        code = [a, b, b"add"]
        meter = Meter()

        result_bytes = self.node.low_eval(code, meter)
        result_int = tc_to_int(result_bytes)

        self.assertEqual(result_int, 5)

    def test_add_nand_jump_and_heap_ops(self):
        # Build a program that touches add, nand, jump, heap_set, heap_get
        # 1) Store 2+3 under key 'k'
        # 2) Compute 0xF0 NAND 0x0F and store under key 'm'
        # 3) Jump over a poison literal
        # 4) Load both values and NAND them for the final result

        code = [
            b"k", int_to_tc(2, 1), int_to_tc(3, 1), b"add", b"heap_set",
            b"m", b"\xf0", b"\x0f", b"nand", b"heap_set",
            int_to_tc(13, 1), b"jump",  # jump to index 13 (skip next literal)
            b"X",  # poison literal (should be skipped)
            b"k", b"heap_get",
            b"m", b"heap_get",
            b"nand",
        ]

        meter = Meter()
        result_bytes = self.node.low_eval(code, meter)

        # 2+3 = 5 stored under 'k'; 0xF0 NAND 0x0F = 0xFF under 'm'.
        # 5 NAND 0xFF = ~0x05 & 0xFF = 0xFA
        self.assertEqual(result_bytes, b"\xfa")

    def test_subtract_with_twos_complement(self):
        # Compute 7 - 3 using two's complement: -b = nand(b,b) + 1, then a + (-b)
        code = [
            b"t",                               # key to store -B
            int_to_tc(3, 1), int_to_tc(3, 1), b"nand",  # ~3
            int_to_tc(1, 1), b"add",           # ~3 + 1 => -3
            b"heap_set",                        # store -3 under key 't'
            int_to_tc(7, 1),                    # A = 7
            b"t", b"heap_get",                  # fetch -3
            b"add",                             # 7 + (-3) = 4
        ]

        meter = Meter()
        result_bytes = self.node.low_eval(code, meter)
        self.assertEqual(tc_to_int(result_bytes), 4)


if __name__ == "__main__":
    unittest.main()
