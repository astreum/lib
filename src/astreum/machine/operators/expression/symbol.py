from typing import List

from astreum.expression import Expr, NIL, symbol, FLOAT_TAGS, _expr_to_fp64, link, str_
from astreum.machine import OpError


def handle_stack_symbol(machine, stack: List[Expr], env) -> None:
    v = stack.pop()
    if v._tag == "bytes":
        try:
            val = v.value.decode("utf-8")
        except UnicodeDecodeError:
            raise OpError("symbol: bytes are not valid UTF-8")
        result = symbol(val)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "int"):
        result = symbol(str(v.value))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag in FLOAT_TAGS:
        decoded = _expr_to_fp64(v)
        result = symbol(str(decoded))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "symbol":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"symbol of {v._tag}")


def handle_stack_symbol_with_result(machine, stack, env):
    try:
        handle_stack_symbol(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
