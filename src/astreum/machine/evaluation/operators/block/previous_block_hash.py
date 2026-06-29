from astreum.machine.models.expression import Expr, bytes_


def handle_stack_block_previous_block_hash(machine, stack):
    value = machine.block.previous_block_hash
    stack.append(bytes_(value))
    machine.meter.charge_bytes(len(value))
