from astreum.machine.models.expression import Expr
from astreum.utils.integer import int_to_bytes


def handle_stack_block_height(machine, stack):
    height = machine.block.height
    value = int_to_bytes(height)
    stack.append(Expr.Bytes(value))
    machine.meter.charge_bytes(len(value))
