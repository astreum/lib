from astreum.machine.models.expression import Expr


def handle_stack_tx_amount(machine, stack):
    value = Expr.Int(machine.tx.amount)
    stack.append(value)
    machine.meter.charge_bytes(len(value._encoded()))
