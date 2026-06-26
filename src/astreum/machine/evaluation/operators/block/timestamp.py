from astreum.machine.models.expression import Expr
from astreum.utils.integer import int_to_bytes


def handle_stack_block_timestamp(machine, stack):
    ts = machine.block.timestamp or 0
    value = int_to_bytes(ts)
    stack.append(Expr.Bytes(value))
    machine.meter.charge_bytes(len(value))
