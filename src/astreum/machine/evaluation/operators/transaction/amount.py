from astreum.machine.models.expression import Expr
from astreum.utils.integer import int_to_bytes


def handle_stack_tx_amount(machine, stack):
    value = int_to_bytes(machine.tx.amount)
    stack.append(Expr.Bytes(value))
    machine.meter.charge_bytes(len(value))
