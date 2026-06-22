from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError


def handle_stack_symbol(machine, stack: List[Expr]) -> None:
    v = stack.pop()
    if isinstance(v, Expr.Bytes):
        try:
            val = v.value.decode("utf-8")
        except UnicodeDecodeError:
            raise OpError("symbol: bytes are not valid UTF-8")
        result = Expr.Symbol(val)
        machine.meter.charge_bytes(v.size())
        stack.append(result)
    elif isinstance(v, (Expr.String, Expr.Int, Expr.Float)):
        result = Expr.Symbol(str(v.value))
        machine.meter.charge_bytes(result.size())
        stack.append(result)
    elif isinstance(v, Expr.Symbol):
        machine.meter.charge_bytes(v.size())
        stack.append(v)
    else:
        raise OpError(f"symbol of {type(v).__name__.lower()}")
