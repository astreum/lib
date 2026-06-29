from astreum.machine.models.expression import Expr, int_
from astreum.machine.models.expression.expr import _encode_int


def handle_stack_block_timestamp(machine, stack):
    value = int_(machine.block.timestamp)
    stack.append(value)
    machine.meter.charge_bytes(len(_encode_int(value._value)))
