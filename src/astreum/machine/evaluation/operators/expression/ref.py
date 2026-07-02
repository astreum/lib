from typing import List

from astreum.machine.models.expression import Expr, NIL, ZERO32, link, bytes_, symbol
from astreum.machine.models.op_error import OpError
from astreum.storage.actions.get import get_expr


def _ref_thunk(h: bytes) -> Expr:
    return link(bytes_(h), symbol("ref"))


def handle_stack_ref(machine, stack: List[Expr]) -> None:
    if not stack:
        machine.meter.charge_bytes(1)
        raise OpError("stack underflow")

    hash_expr = stack.pop()

    if hash_expr._tag != "bytes":
        raise OpError(f"ref requires 32-byte hash, got {hash_expr._tag}")
    if len(hash_expr.value) != 32:
        raise OpError(f"ref requires 32-byte hash, got {len(hash_expr.value)} bytes")

    if hash_expr.value == ZERO32:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    if machine.node is None:
        raise OpError("ref requires a node connection")

    resolved = get_expr(machine.node, hash_expr.value)
    if resolved is None:
        raise OpError("ref: expression not found")

    if resolved._tag == "link":
        if (resolved._head is None and resolved._tail is None
                and resolved._head_hash is None and resolved._tail_hash is None):
            raise OpError("ref: expression not found")

        head_h = resolved._head_hash
        if head_h is None:
            head_h = resolved._head.hash() if resolved._head is not None else ZERO32

        tail_h = resolved._tail_hash
        if tail_h is None:
            tail_h = resolved._tail.hash() if resolved._tail is not None else ZERO32

        machine.meter.charge_bytes(70)
        stack.append(link(_ref_thunk(head_h), _ref_thunk(tail_h)))
    else:
        machine.meter.charge_bytes(resolved.size())
        stack.append(resolved)
