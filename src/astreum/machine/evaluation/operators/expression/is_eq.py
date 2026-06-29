from typing import Any, List

from astreum.machine.models.expression import Expr, bytes_


def expr_equal(x: Any, y: Any) -> bool:
    if x is y:
        return True
    if x._tag == "int" and y._tag == "int":
        return x.value == y.value
    if x._tag == "bytes" and y._tag == "bytes":
        return x.value == y.value
    if x._tag == "symbol" and y._tag == "symbol":
        return x.value == y.value
    if x._tag == "link" and y._tag == "link":
        return expr_equal(x._head, y._head) and expr_equal(x._tail, y._tail)
    return False


def handle_stack_is_eq(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()
    machine.meter.charge_bytes(min(a.size(), b.size()) + 1)
    result = expr_equal(a, b)
    stack.append(bytes_(b"\x01" if result else b"\x00"))
