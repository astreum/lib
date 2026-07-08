from astreum.machine.models.expression import Expr, NIL, bytes_, link, str_, symbol
from astreum.machine.models.op_error import OpError


def handle_stack_block_previous_block_hash(machine, stack, env):
    value = machine.block.previous_block_hash
    stack.append(bytes_(value))
    machine.meter.charge_bytes(len(value))


def handle_stack_block_previous_block_hash_with_result(machine, stack, env):
    try:
        handle_stack_block_previous_block_hash(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
