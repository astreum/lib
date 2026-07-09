from typing import List

from astreum.expression import Expr, NIL, bytes_, FLOAT_TAGS, _expr_to_fp64, link, str_, symbol
from astreum.machine import OpError


def _compare_numbers(machine, stack: List[Expr], predicate, verb: str) -> None:
    b = stack.pop()
    a = stack.pop()

    if a._tag == "int" and b._tag == "int":
        result = predicate(a.value, b.value)
    elif a._tag in FLOAT_TAGS and b._tag in FLOAT_TAGS:
        # Comparison requires same type, compare decoded fp64 values
        if a._tag != b._tag:
            raise OpError(f"{verb} of {a._tag} and {b._tag}")
        a_decoded = _expr_to_fp64(a)
        b_decoded = _expr_to_fp64(b)
        result = predicate(a_decoded, b_decoded)
    else:
        raise OpError(
            f"{verb} of {a._tag} and {b._tag}"
        )

    result_expr = bytes_(b"\x01" if result else b"\x00")
    machine.meter.charge_bytes(result_expr.size())
    stack.append(result_expr)


def handle_stack_less_than(machine, stack: List[Expr], env) -> None:
    _compare_numbers(machine, stack, lambda a, b: a < b, "less than")


def handle_stack_greater_than(machine, stack: List[Expr], env) -> None:
    _compare_numbers(machine, stack, lambda a, b: a > b, "greater than")


def handle_stack_less_than_or_equal(machine, stack: List[Expr], env) -> None:
    _compare_numbers(machine, stack, lambda a, b: a <= b, "less than or equal")


def handle_stack_greater_than_or_equal(machine, stack: List[Expr], env) -> None:
    _compare_numbers(machine, stack, lambda a, b: a >= b, "greater than or equal")


def handle_stack_less_than_with_result(machine, stack, env):
    try:
        handle_stack_less_than(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))


def handle_stack_greater_than_with_result(machine, stack, env):
    try:
        handle_stack_greater_than(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))


def handle_stack_less_than_or_equal_with_result(machine, stack, env):
    try:
        handle_stack_less_than_or_equal(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))


def handle_stack_greater_than_or_equal_with_result(machine, stack, env):
    try:
        handle_stack_greater_than_or_equal(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
