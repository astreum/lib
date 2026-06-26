from astreum.machine.models.expression import Expr


def handle_stack_block_height(machine, stack):
    value = Expr.Int(machine.block.height)
    stack.append(value)
    machine.meter.charge_bytes(len(value._encoded()))
