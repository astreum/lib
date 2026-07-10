from typing import List

from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError
from astreum.machine.operators.sequence._closure import run_iteration_step


def _each_bytes(machine, fn, env, value):
    machine.meter.charge_bytes(len(value.value))
    for i in range(len(value.value)):
        elem = bytes_(value.value[i:i + 1])
        machine.meter.charge_bytes(1)
        run_iteration_step(machine, fn, env, [elem])


def _each_str(machine, fn, env, value):
    machine.meter.charge_bytes(len(value.value.encode("utf-8")))
    for ch in value.value:
        elem = str_(ch)
        machine.meter.charge_bytes(len(ch.encode("utf-8")))
        run_iteration_step(machine, fn, env, [elem])


def _each_link(machine, fn, env, value):
    current = value
    while current._tag == "link" and current._head is not None:
        machine.meter.charge_bytes(current._head.size())
        run_iteration_step(machine, fn, env, [current._head])
        if current._tail is NIL or current._tail is None:
            break
        current = current._tail


def handle_stack_each(machine, stack: List[Expr], env) -> None:
    fn = stack.pop()
    value = stack.pop()

    if value._tag == "bytes":
        _each_bytes(machine, fn, env, value)
    elif value._tag == "str":
        _each_str(machine, fn, env, value)
    elif value._tag == "link":
        _each_link(machine, fn, env, value)
    else:
        raise OpError(f"each of {value._tag} and {fn._tag}")

    stack.append(value)


def handle_stack_each_with_result(machine, stack, env):
    try:
        handle_stack_each(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
