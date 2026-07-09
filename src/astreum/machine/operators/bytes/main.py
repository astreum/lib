from struct import pack
from typing import List

from astreum.expression import Expr, NIL, bytes_, FLOAT_TAGS, _float_to_bytes, link, str_, symbol
from astreum.expression.expr import _encode_int
from astreum.machine import OpError


def handle_stack_bytes(machine, stack: List[Expr], env) -> None:
    v = stack.pop()
    if v._tag == "int":
        result = bytes_(_encode_int(v._value))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in FLOAT_TAGS:
        # Encode float to its wire bytes representation
        result = bytes_(_float_to_bytes(v._tag, v._value))
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif v._tag in ("str", "symbol"):
        result = bytes_(v.value.encode("utf-8"))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif v._tag == "bytes":
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"bytes of {v._tag}")


def handle_stack_bytes_with_result(machine, stack, env):
    try:
        handle_stack_bytes(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
