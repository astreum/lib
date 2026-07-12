from typing import List

from astreum.expression import Expr, NIL, bytes_, get_expr_tag, link, str_, symbol
from astreum.machine import OpError
from astreum.machine.operators._if import is_truthy
from astreum.machine.operators.sequence._closure import run_iteration_step


def _filter_bytes(machine, fn, env, value):
    out = bytearray()
    for i in range(len(value.value)):
        machine.meter.charge_bytes(1)
        elem = bytes_(value.value[i:i + 1])
        ok = run_iteration_step(machine, fn, env, [elem])
        if is_truthy(ok):
            out.extend(elem.value)
    machine.meter.charge_bytes(len(out))
    return bytes_(bytes(out))


def _filter_str(machine, fn, env, value):
    chars = []
    for ch in value.value:
        machine.meter.charge_bytes(len(ch.encode("utf-8")))
        elem = str_(ch)
        ok = run_iteration_step(machine, fn, env, [elem])
        if is_truthy(ok):
            chars.append(elem.value)
    joined = "".join(chars)
    machine.meter.charge_bytes(len(joined.encode("utf-8")))
    return str_(joined)


def _filter_link(machine, fn, env, value):
    kept = []
    current = value
    while current._tag == "link" and current._head is not None:
        machine.meter.charge_bytes(current._head.size())
        ok = run_iteration_step(machine, fn, env, [current._head])
        if is_truthy(ok):
            kept.append(current._head)
        if current._tail is NIL or current._tail is None:
            break
        current = current._tail
    cost = sum(e.size() for e in kept)
    machine.meter.charge_bytes(cost + len(kept))
    out = NIL
    for elem in reversed(kept):
        out = link(elem, out)
    return out


def handle_stack_filter(machine, stack: List[Expr], env) -> None:
    fn = stack.pop()
    value = stack.pop()
    value_tag = get_expr_tag(value)
    fn_tag = get_expr_tag(fn)

    if value_tag == "bytes":
        result = _filter_bytes(machine, fn, env, value)
    elif value_tag == "str":
        result = _filter_str(machine, fn, env, value)
    elif value_tag == "link":
        result = _filter_link(machine, fn, env, value)
    else:
        raise OpError(f"filter of {value_tag} and {fn_tag}")

    stack.append(result)


def handle_stack_filter_with_result(machine, stack, env):
    try:
        handle_stack_filter(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
