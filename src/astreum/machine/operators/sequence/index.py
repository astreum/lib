from typing import List

from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError


def _index_bytes(value, k):
    if k < 0 or k >= len(value.value):
        raise OpError(
            f"index {k} out of bounds for bytes of length {len(value.value)}"
        )
    return bytes_(value.value[k:k + 1]), 1


def _index_str(value, k):
    chars = list(value.value)
    if k < 0 or k >= len(chars):
        raise OpError(
            f"index {k} out of bounds for str of length {len(chars)}"
        )
    result = str_(chars[k])
    encoded = result.value.encode("utf-8")
    return result, len(encoded)


def _index_link(value, k):
    if k < 0:
        raise OpError(
            f"index {k} out of bounds for link"
        )
    current = value
    walked = 0
    while current._tag == "link" and current._head is not None:
        if walked == k:
            head = current._head
            return head, head.size()
        walked += 1
        if current._tail is NIL or current._tail is None:
            raise OpError(
                f"index {k} out of bounds for link of length {walked}"
            )
        current = current._tail

    raise OpError(
        f"index {k} out of bounds for link of length {walked}"
    )


def handle_stack_index(machine, stack: List[Expr], env) -> None:
    index = stack.pop()
    value = stack.pop()

    if index._tag != "int":
        raise OpError(
            f"index of {value._tag} by {index._tag}"
        )

    if value._tag == "bytes":
        result, cost = _index_bytes(value, index.value)
    elif value._tag == "str":
        result, cost = _index_str(value, index.value)
    elif value._tag == "link":
        result, cost = _index_link(value, index.value)
    else:
        raise OpError(
            f"index of {value._tag} by int"
        )

    machine.meter.charge_bytes(cost)
    stack.append(result)


def handle_stack_index_with_result(machine, stack, env):
    try:
        handle_stack_index(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
