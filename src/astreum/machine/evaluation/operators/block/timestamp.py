from astreum.machine.models.expression import Expr, NIL, int_, link, str_, symbol
from astreum.machine.models.expression.expr import _encode_int
from astreum.machine.models.op_error import OpError


def handle_stack_block_timestamp(machine, stack, env):
    value = int_(machine.block.timestamp)
    stack.append(value)
    machine.meter.charge_bytes(len(_encode_int(value._value)))


def handle_stack_block_timestamp_with_result(machine, stack, env):
    try:
        handle_stack_block_timestamp(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
