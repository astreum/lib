from astreum.machine.models.expression import Expr


def handle_stack_block_chain_id(machine, stack):
    value = Expr.Int(machine.block.chain_id)
    stack.append(value)
    machine.meter.charge_bytes(len(value._encoded()))
