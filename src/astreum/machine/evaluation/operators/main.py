from typing import List

from src.astreum.machine.models.expression import Expr

from src.astreum.machine.evaluation.operators.arithmetic.add import handle_stack_add
from src.astreum.machine.evaluation.operators.arithmetic.nand import handle_stack_nand
from src.astreum.machine.evaluation.operators.arithmetic._not import handle_stack_not
from src.astreum.machine.evaluation.operators._def import handle_stack_def
from src.astreum.machine.evaluation.operators.expression.link import handle_stack_link
from src.astreum.machine.evaluation.operators.expression.head import handle_stack_head
from src.astreum.machine.evaluation.operators.expression.tail import handle_stack_tail
from src.astreum.machine.evaluation.operators.expression.is_atom import handle_stack_is_atom
from src.astreum.machine.evaluation.operators.expression.is_eq import handle_stack_is_eq
from src.astreum.machine.evaluation.operators._if import handle_stack_if
from src.astreum.machine.evaluation.operators._fn import handle_stack_fn
from src.astreum.machine.evaluation.operators.actors.spawn import handle_stack_spawn
from src.astreum.machine.evaluation.operators.actors.send import handle_stack_send
from src.astreum.machine.evaluation.operators.actors.receive import handle_stack_receive


OPERATOR_LIST = ["+", "!&", "!", "fn", "def", "link", "head", "tail", "is_atom", "is_eq", "spawn", "send", "receive"]


def apply_operator(machine, symbol: Expr.Symbol, stack: List[Expr], env) -> List[Expr]:
    if symbol.value == "+":
        handle_stack_add(machine, stack)

    elif symbol.value == "!&":
        handle_stack_nand(machine, stack)

    elif symbol.value == "!":
        handle_stack_not(machine, stack)

    elif symbol.value == "fn":
        handle_stack_fn(machine, stack, env)

    elif symbol.value == "if":
        return handle_stack_if(machine, stack, env)

    elif symbol.value == "def":
        handle_stack_def(machine, stack, env)

    elif symbol.value == "link":
        handle_stack_link(machine, stack)

    elif symbol.value == "head":
        handle_stack_head(machine, stack)

    elif symbol.value == "tail":
        handle_stack_tail(machine, stack)

    elif symbol.value == "is_atom":
        handle_stack_is_atom(machine, stack)

    elif symbol.value == "is_eq":
        handle_stack_is_eq(machine, stack)

    elif symbol.value == "spawn":
        if not machine.allow_threading:
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_spawn(machine, stack, env)

    elif symbol.value == "send":
        if not machine.allow_threading:
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_send(machine, stack)

    elif symbol.value == "receive":
        if not machine.allow_threading:
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_receive(machine, stack)

    return stack
