from typing import Any, List

from astreum.machine.models.expression import Expr


def expr_equal(x: Any, y: Any) -> bool:
    if x is y:
        return True
    if isinstance(x, Expr.Bytes) and isinstance(y, Expr.Bytes):
        return x.value == y.value
    if isinstance(x, Expr.Symbol) and isinstance(y, Expr.Symbol):
        return x.value == y.value
    if isinstance(x, Expr.Link) and isinstance(y, Expr.Link):
        return expr_equal(x.head, y.head) and expr_equal(x.tail, y.tail)
    return False


def handle_stack_is_eq(machine, stack: List[Expr]) -> None:
    b = stack.pop()
    a = stack.pop()
    machine.meter.charge_bytes(min(a.size(), b.size()) + 1)
    result = expr_equal(a, b)
    stack.append(Expr.Bytes(b"\x01" if result else b"\x00"))
