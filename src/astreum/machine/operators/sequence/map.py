from typing import List

from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError
from astreum.machine.operators.sequence._closure import run_iteration_step


def _map_bytes(machine, fn, env, value):
    out = bytearray()
    cost = 0
    for i in range(len(value.value)):
        machine.meter.charge_bytes(1)
        elem = bytes_(value.value[i:i + 1])
        result = run_iteration_step(machine, fn, env, [elem])
        if result._tag != "bytes":
            raise OpError(
                f"map fn produced {result._tag}, expected bytes"
            )
        out.extend(result.value)
        cost += result.size()
    final = bytes_(bytes(out))
    machine.meter.charge_bytes(len(out))
    return final


def _map_str(machine, fn, env, value):
    chars = []
    cost = 0
    for ch in value.value:
        machine.meter.charge_bytes(len(ch.encode("utf-8")))
        elem = str_(ch)
        result = run_iteration_step(machine, fn, env, [elem])
        if result._tag != "str":
            raise OpError(
                f"map fn produced {result._tag}, expected str"
            )
        chars.append(result.value)
        cost += len(result.value.encode("utf-8"))
    final = str_("".join(chars))
    machine.meter.charge_bytes(cost)
    return final


def _map_link(machine, fn, env, value):
    elems = []
    current = value
    while current._tag == "link" and current._head is not None:
        machine.meter.charge_bytes(current._head.size())
        result = run_iteration_step(machine, fn, env, [current._head])
        elems.append(result)
        if current._tail is NIL or current._tail is None:
            break
        current = current._tail
    cost = sum(e.size() for e in elems)
    machine.meter.charge_bytes(cost + len(elems))
    out = NIL
    for elem in reversed(elems):
        out = link(elem, out)
    return out


def handle_stack_map(machine, stack: List[Expr], env) -> None:
    fn = stack.pop()
    value = stack.pop()

    if value._tag == "bytes":
        result = _map_bytes(machine, fn, env, value)
    elif value._tag == "str":
        result = _map_str(machine, fn, env, value)
    elif value._tag == "link":
        result = _map_link(machine, fn, env, value)
    else:
        raise OpError(f"map of {value._tag} and {fn._tag}")

    stack.append(result)


def handle_stack_map_with_result(machine, stack, env):
    try:
        handle_stack_map(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
