from typing import List

from astreum.machine.models.expression import Expr, symbol, FLOAT_TAGS, _expr_to_fp64
from astreum.machine.models.op_error import OpError


def handle_stack_symbol(machine, stack: List[Expr]) -> None:
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
