from typing import List

from src.astreum.machine.models.expression import Expr


def handle_stack_nand(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()

    # Charge: 2 bytes per byte of the wider operand
    w = max(len(a.value), len(b.value), 1)
    machine.meter.charge_bytes(w * 2)

    au = int.from_bytes(a.value.rjust(w, b"\x00"), "big", signed=False)
    bu = int.from_bytes(b.value.rjust(w, b"\x00"), "big", signed=False)
    mask = (1 << (w * 8)) - 1
    result_bytes = (~(au & bu) & mask).to_bytes(w, "big", signed=False)
    stack.append(Expr.Bytes(result_bytes))
