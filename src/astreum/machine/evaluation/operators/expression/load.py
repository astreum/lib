from typing import List

from astreum.machine.models.expression import Expr, NIL, ZERO32
from astreum.machine.models.op_error import OpError


def handle_stack_load(machine, stack: List[Expr]) -> None:
    if not stack:
        machine.meter.charge_bytes(1)
        raise OpError("stack underflow")

    hash_expr = stack.pop()

    if not isinstance(hash_expr, Expr.Bytes):
        raise OpError(f"load requires 32-byte hash, got {type(hash_expr).__name__.lower()}")
    if len(hash_expr.value) != 32:
        raise OpError(f"load requires 32-byte hash, got {len(hash_expr.value)} bytes")

    if hash_expr.value == ZERO32:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    if machine.node is None:
        raise OpError("load requires a node connection")

    resolved = machine.node.get_expr_full(hash_expr.value)
    if resolved is None:
        raise OpError("load: expression not found")

    machine.meter.charge_bytes(resolved.size() * 2)
    stack.append(resolved)
