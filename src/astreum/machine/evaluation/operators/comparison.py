from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def _compare_numbers(machine, stack: List[Expr], predicate, verb: str) -> None:
    b = stack.pop()
    a = stack.pop()

    if isinstance(a, Expr.Int) and isinstance(b, Expr.Int):
        result = predicate(a.value, b.value)
    elif isinstance(a, Expr.Float) and isinstance(b, Expr.Float):
        result = predicate(a.value, b.value)
    else:
        raise OpError(
            f"{verb} of {type(a).__name__.lower()} and {type(b).__name__.lower()}"
        )

    result_expr = Expr.Bytes(b"\x01" if result else b"\x00")
    machine.meter.charge_bytes(result_expr.size())
    stack.append(result_expr)


def handle_stack_less_than(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a < b, "less than")


def handle_stack_greater_than(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a > b, "greater than")


def handle_stack_less_than_or_equal(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a <= b, "less than or equal")


def handle_stack_greater_than_or_equal(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a >= b, "greater than or equal")
