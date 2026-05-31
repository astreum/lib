from typing import List

from src.astreum.machine.models.expression import Expr


def handle_stack_add(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    # Charge: 2 bytes per byte of the wider operand
    max_byte_width = max(len(a.value), len(b.value))
    machine.meter.charge_bytes(max_byte_width * 2)

    a_int = int.from_bytes(a.value, "big")
    b_int = int.from_bytes(b.value, "big")
    result_bytes = (a_int + b_int).to_bytes((a_int + b_int).bit_length() or 1, "big")
    stack.append(Expr.Bytes(result_bytes))

