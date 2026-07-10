from typing import List

from astreum.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine import OpError
from astreum.machine.operators._if import is_truthy
from astreum.machine.operators.sequence._closure import run_iteration_step


def handle_stack_find(machine, stack: List[Expr], env) -> None:
    fn = stack.pop()
    value = stack.pop()

    def make_not_found():
        return link(str_("not found"), symbol("err"))

    if value is NIL:
        stack.append(make_not_found())
        return

    if value._tag == "bytes":
        for i in range(len(value.value)):
            machine.meter.charge_bytes(1)
            elem = bytes_(value.value[i:i + 1])
            ok = run_iteration_step(machine, fn, env, [elem])
            if is_truthy(ok):
                machine.meter.charge_bytes(elem.size())
                stack.append(link(elem, symbol("ok")))
                return
        stack.append(make_not_found())
        return

    if value._tag == "str":
        for ch in value.value:
            elem = str_(ch)
            machine.meter.charge_bytes(len(ch.encode("utf-8")))
            ok = run_iteration_step(machine, fn, env, [elem])
            if is_truthy(ok):
                machine.meter.charge_bytes(elem.size())
                stack.append(link(elem, symbol("ok")))
                return
        stack.append(make_not_found())
        return

    if value._tag == "link":
        current = value
        while current._tag == "link" and current._head is not None:
            machine.meter.charge_bytes(current._head.size())
            ok = run_iteration_step(machine, fn, env, [current._head])
            if is_truthy(ok):
                machine.meter.charge_bytes(current._head.size())
                stack.append(link(current._head, symbol("ok")))
                return
            if current._tail is NIL or current._tail is None:
                break
            current = current._tail
        stack.append(make_not_found())
        return

    raise OpError(f"find of {value._tag} and {fn._tag}")


def handle_stack_find_with_result(machine, stack, env):
    try:
        handle_stack_find(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
