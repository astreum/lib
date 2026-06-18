from typing import List

from astreum.machine.models.expression import Expr, NIL


def _compare_numbers(machine, stack: List[Expr], predicate) -> None:
    b = stack.pop()
    a = stack.pop()

    if isinstance(a, Expr.Int) and isinstance(b, Expr.Int):
        result = predicate(a.value, b.value)
    elif isinstance(a, Expr.Float) and isinstance(b, Expr.Float):
        result = predicate(a.value, b.value)
    else:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return

    stack.append(Expr.Bytes(b"\x01" if result else b"\x00"))


def handle_stack_less_than(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a < b)


def handle_stack_greater_than(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a > b)


def handle_stack_less_than_or_equal(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a <= b)


def handle_stack_greater_than_or_equal(machine, stack: List[Expr]) -> None:
    _compare_numbers(machine, stack, lambda a, b: a >= b)
