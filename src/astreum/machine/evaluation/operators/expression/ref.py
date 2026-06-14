from typing import List

from astreum.machine.models.expression import Expr, NIL, ZERO32


def _ref_thunk(h: bytes) -> Expr:
    return Expr.Link(Expr.Bytes(h), Expr.Link(Expr.Symbol("ref"), None))


def handle_stack_ref(machine, stack: List[Expr]) -> None:
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

    resolved = machine.node.get_expr(hash_expr.value)
    if resolved is None:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    if isinstance(resolved, Expr.Link):
        if (resolved.head is None and resolved.tail is None
                and resolved.head_hash is None and resolved.tail_hash is None):
            machine.meter.charge_bytes(70)
            stack.append(NIL)
            return

        head_h = resolved.head_hash
        if head_h is None:
            head_h = resolved.head.hash() if resolved.head is not None else ZERO32

        tail_h = resolved.tail_hash
        if tail_h is None:
            tail_h = resolved.tail.hash() if resolved.tail is not None else ZERO32

        machine.meter.charge_bytes(70)
        stack.append(Expr.Link(_ref_thunk(head_h), _ref_thunk(tail_h)))
    else:
        machine.meter.charge_bytes(resolved.size())
        stack.append(resolved)
