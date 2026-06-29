from astreum.machine.models.expression import Expr, bytes_


def handle_stack_tx_sender(machine, stack):
    value = machine.tx.sender
    stack.append(bytes_(value))
    machine.meter.charge_bytes(len(value))
