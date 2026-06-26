from astreum.machine.models.expression import Expr
from astreum.utils.integer import int_to_bytes


def handle_stack_block_chain_id(machine, stack):
    value = int_to_bytes(machine.block.chain_id)
    stack.append(Expr.Bytes(value))
    machine.meter.charge_bytes(len(value))
