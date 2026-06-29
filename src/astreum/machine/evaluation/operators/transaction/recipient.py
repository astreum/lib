from astreum.machine.models.expression import Expr, bytes_


def handle_stack_tx_recipient(machine, stack):
    value = machine.tx.recipient
    stack.append(bytes_(value))
    machine.meter.charge_bytes(len(value))
