from astreum.machine.models.expression import Expr


def handle_stack_tx_sender(machine, stack):
    value = machine.tx.sender
    stack.append(Expr.Bytes(value))
    machine.meter.charge_bytes(len(value))
