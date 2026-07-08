from typing import List

from astreum.machine.models.expression import Expr, NIL, ZERO32, link, str_, symbol
from astreum.machine.models.op_error import OpError
from astreum.storage.get.full import get_expr_full


def handle_stack_load(machine, stack: List[Expr], env) -> None:
    if not stack:
        machine.meter.charge_bytes(1)
        raise OpError("stack underflow")

    hash_expr = stack.pop()

    if hash_expr._tag != "bytes":
        raise OpError(f"load requires 32-byte hash, got {hash_expr._tag.lower()}")
    if len(hash_expr.value) != 32:
        raise OpError(f"load requires 32-byte hash, got {len(hash_expr.value)} bytes")

    if hash_expr.value == ZERO32:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    if machine.node is None:
        raise OpError("load requires a node connection")

    resolved = get_expr_full(machine.node, hash_expr.value)
    if resolved is None:
        raise OpError("load: expression not found")

    machine.meter.charge_bytes(resolved.size() * 2)
    stack.append(resolved)


def handle_stack_load_with_result(machine, stack, env):
    try:
        handle_stack_load(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
