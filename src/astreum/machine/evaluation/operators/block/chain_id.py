from astreum.machine.models.expression import Expr, int_
from astreum.machine.models.expression.expr import _encode_int


def handle_stack_block_chain_id(machine, stack):
    value = int_(machine.block.chain_id)
    stack.append(value)
    machine.meter.charge_bytes(len(_encode_int(value._value)))
