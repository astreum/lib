from typing import List

from astreum.machine.environment import Env
from astreum.expression import Expr, NIL, link, FLOAT_TAGS
from astreum.machine import OpError
from astreum.machine.operators.main import OPERATOR_LIST, apply_operator


def evaluation(machine, expr: Expr, stack: List[Expr] = [], env: Env = Env()) -> List[Expr]:

    if expr._tag == "symbol":
        if machine.mode == "deterministic":
            if expr.value in OPERATOR_LIST:
                try:
                    stack = apply_operator(machine, expr, stack, env)
                except (OpError, IndexError):
                    machine.meter.charge_bytes(1)
                    stack.append(NIL)
            else:
                bound = env.get(expr.value)
                if bound is None:
                    machine.meter.charge_bytes(expr.size() + 1)
                    stack.append(link(None, None))
                else:
                    machine.meter.charge_bytes(expr.size() + bound.size())
                    stack.append(bound)
        else:
            bound = env.get(expr.value)
            if bound is not None:
                machine.meter.charge_bytes(expr.size() + bound.size())
                stack.append(bound)
            elif expr.value in OPERATOR_LIST:
                try:
                    stack = apply_operator(machine, expr, stack, env)
                except (OpError, IndexError):
                    machine.meter.charge_bytes(1)
                    stack.append(NIL)
            else:
                machine.meter.charge_bytes(expr.size() + 1)
                stack.append(link(None, None))
        return stack

    if expr._tag in ("bytes", "int", "str") or expr._tag in FLOAT_TAGS:
        machine.meter.charge_bytes(expr.size())
        stack.append(expr)
        return stack

    if expr._tag == "link":
        if expr._head is not None and expr._head._tag == "symbol" and expr._head.value == "'":
            if expr._tail is None or expr._tail is NIL:
                machine.meter.charge_bytes(1)
                stack.append(NIL)
            else:
                machine.meter.charge_bytes(expr._tail._head.size())
                stack.append(expr._tail._head)
            return stack
        if expr._head is not None:
            stack = evaluation(machine, expr._head, stack, env)
        if expr._tail is not None:
            stack = evaluation(machine, expr._tail, stack, env)
        return stack
