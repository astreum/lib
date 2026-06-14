from typing import List

from astreum.machine.models.expression import Expr, NIL


def handle_stack_load(machine, stack: List[Expr]) -> None:
    if not stack:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    hash_expr = stack.pop()
    if not isinstance(hash_expr, Expr.Bytes) or len(hash_expr.value) != 32:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    if machine.node is None:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    resolved = machine.node.get_expr_full(hash_expr.value)
    if resolved is None:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    machine.meter.charge_bytes(resolved.size() * 2)
    stack.append(resolved)
