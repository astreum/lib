from astreum.machine.models.expression import Expr


def handle_stack_block_timestamp(machine, stack):
    value = Expr.Int(machine.block.timestamp)
    stack.append(value)
    machine.meter.charge_bytes(len(value._encoded()))
