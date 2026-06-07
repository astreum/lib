from typing import List

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL
from astreum.machine.evaluation.operators.main import OPERATOR_LIST, apply_operator


def evaluation(machine, expr: Expr, stack: List[Expr] = [], env: Env = Env()) -> List[Expr]:

    # ATOM: Symbol
    if isinstance(expr, Expr.Symbol):
        # Operators
        if expr.value in OPERATOR_LIST:
            stack = apply_operator(machine, expr, stack, env)
        else:
        # Variable
            bound = env.get(expr.value)
            if bound is None:
                machine.meter.charge_bytes(expr.size() + 1)
                stack.append(Expr.Link(None, None))
            else:
                machine.meter.charge_bytes(expr.size() + bound.size())
                stack.append(bound)
        return stack

    # ATOM: Bytes
    if isinstance(expr, Expr.Bytes):
        machine.meter.charge_bytes(expr.size())
        stack.append(expr)
        return stack

    # LINK: Pair of Atoms
    if isinstance(expr, Expr.Link):
        # If the list starts with 'quote', treat as quotation
        if (isinstance(expr.head, Expr.Symbol) and expr.head.value == "quote"):
            if expr.tail is None:
                # (quote) with no argument – push nil
                machine.meter.charge_bytes(1)
                stack.append(NIL)
            else:
                # push the tail expression itself, unevaluated
                machine.meter.charge_bytes(expr.tail.size())
                stack.append(expr.tail)
            return stack
        if expr.head is not None:
            stack = evaluation(machine, expr.head, stack, env)
        if expr.tail is not None:
            stack = evaluation(machine, expr.tail, stack, env)
        return stack
