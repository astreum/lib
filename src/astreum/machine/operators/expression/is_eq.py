from typing import Any, List

from astreum.expression import Expr, NIL, bytes_, FLOAT_TAGS, _expr_to_fp64, link, str_, symbol
from astreum.machine import OpError


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
    # Float comparison: same tag, compare decoded fp64 values
    if x._tag in FLOAT_TAGS and y._tag in FLOAT_TAGS:
        if x._tag != y._tag:
            return False
        return _expr_to_fp64(x) == _expr_to_fp64(y)
    return False


def handle_stack_is_eq(machine, stack: List[Expr], env) -> None:
    b = stack.pop()
    a = stack.pop()
    machine.meter.charge_bytes(min(a.size(), b.size()) + 1)
    result = expr_equal(a, b)
    stack.append(bytes_(b"\x01" if result else b"\x00"))


def handle_stack_is_eq_with_result(machine, stack, env):
    try:
        handle_stack_is_eq(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
