from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_maybe(
    machine, stack: List[Expr], env
) -> List[Expr]:
    if not stack:
        raise OpError("stack underflow")
    tagged = stack.pop()

    if tagged._tag != "link" or tagged._tail is None or tagged._tail._tag != "symbol":
        raise OpError("maybe of non-tagged value")

    tag = tagged._tail.value
    if tag == "some":
        stack.append(tagged._head)
    elif tag == "none":
        raise OpError("maybe of none value")
    else:
        raise OpError(f"maybe of unknown tag: {tag}")

    return stack
