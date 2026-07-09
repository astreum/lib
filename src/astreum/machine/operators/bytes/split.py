from typing import List

from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError


def handle_stack_split(machine, stack: List[Expr], env) -> None:
    index = stack.pop()
    value = stack.pop()

    if value._tag != "bytes" or index._tag != "int":
        raise OpError(
            f"split of {value._tag} at {index._tag}"
        )

    if index.value < 0 or index.value > len(value.value):
        raise OpError(
            f"split index {index.value} out of bounds for bytes of length {len(value.value)}"
        )

    left = bytes_(value.value[:index.value])
    right = bytes_(value.value[index.value:])
    machine.meter.charge_bytes(left.size() + right.size())
    stack.append(link(left, right))


def handle_stack_split_with_result(machine, stack, env):
    try:
        handle_stack_split(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
