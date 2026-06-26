from astreum.machine.models.expression import Expr


def handle_stack_block_previous_block_hash(machine, stack):
    value = machine.block.previous_block_hash
    stack.append(Expr.Bytes(value))
    machine.meter.charge_bytes(len(value))
