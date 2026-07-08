from typing import List

from astreum.machine.models.expression import Expr, bytes_
from astreum.machine.models.op_error import OpError


def handle_stack_is(machine, stack: List[Expr], env=None) -> None:
    if len(stack) < 2:
        raise OpError("stack underflow")
    tag_sym = stack.pop()
    val = stack.pop()
    if tag_sym._tag != "symbol":
        raise OpError("is requires a symbol")
    target = tag_sym.value
    if val._tag == "link" and val._tail is not None and val._tail._tag == "symbol":
        match = val._tail.value == target
    else:
        match = val._tag == target
    machine.meter.charge_bytes(1)
    stack.append(bytes_(b"\x01" if match else b"\x00"))
