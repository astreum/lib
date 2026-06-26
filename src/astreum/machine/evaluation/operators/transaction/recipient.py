from astreum.machine.models.expression import Expr


def handle_stack_tx_recipient(machine, stack):
    value = machine.tx.recipient
    stack.append(Expr.Bytes(value))
    machine.meter.charge_bytes(len(value))
