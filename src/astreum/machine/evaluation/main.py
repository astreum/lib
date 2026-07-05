from typing import List, Optional, Tuple

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL, symbol, str_, link
from astreum.machine.models.meter import MeterExceededError
from astreum.machine.models.op_error import OpError
from astreum.machine.evaluation.operators.main import OPERATOR_LIST, apply_operator

STACK_VOID_OPS = {"drop", "dup", "swap", "rot", "dip"}


def _resolve_op(name: str) -> Tuple[Optional[str], bool]:
    """Resolve a symbol name for dispatch.
    Returns (stem, tagged_results_flag):
      (name, False)   -> bare operator, run via apply_operator
      (stem, True)    -> <primitive>? form, run via _tag_results
      (None, False)   -> not an operator (unbound)."""
    if name in OPERATOR_LIST:
        return (name, False)
    if name.endswith("?") and name[:-1] in OPERATOR_LIST:
        return (name[:-1], True)
    return (None, False)


def _tag_results(machine, stem: str, stack: List[Expr], env: Env) -> List[Expr]:
    try:
        stack = apply_operator(machine, symbol(stem), stack, env)
    except MeterExceededError:
        raise
    except IndexError:
        machine.meter.charge_bytes(1)
        stack.append(link(str_("stack underflow"), symbol("err")))
        return stack
    except OpError as exc:
        machine.meter.charge_bytes(1)
        stack.append(link(str_(str(exc)), symbol("err")))
        return stack
    except Exception as exc:
        machine.meter.charge_bytes(1)
        stack.append(link(str_(str(exc) or type(exc).__name__), symbol("err")))
        return stack

    if stem in STACK_VOID_OPS:
        stack.append(NIL)

    if not stack:
        machine.meter.charge_bytes(1)
        stack.append(link(NIL, symbol("ok")))
        return stack

    machine.meter.charge_bytes(1)
    stack[-1] = link(stack[-1], symbol("ok"))
    return stack


def evaluation(machine, expr: Expr, stack: List[Expr] = [], env: Env = Env()) -> List[Expr]:

    # ATOM: Symbol
    if expr._tag == "symbol":
        stem, tagged_results_flag = _resolve_op(expr.value)

        if machine.mode == "deterministic":
            # ? is a no-op in deterministic mode: strip suffix, run bare.
            # No tagged tuples on the stack -> consensus reproducibility preserved.
            if tagged_results_flag:
                tagged_results_flag = False
            if stem is not None:
                try:
                    stack = apply_operator(machine, symbol(stem), stack, env)
                except OpError:
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
            elif stem is not None:
                if stem in ("fn", "box") and tagged_results_flag:
                    try:
                        stack = apply_operator(machine, symbol(stem), stack, env)
                    except OpError as exc:
                        machine.meter.charge_bytes(1)
                        stack.append(link(str_(str(exc)), symbol("err")))
                        return stack
                    result = stack[-1]
                    if (
                        result._tag == "link"
                        and result._tail is not None
                        and result._tail._tag == "symbol"
                        and result._tail.value in ("ok", "err")
                    ):
                        return stack
                    machine.meter.charge_bytes(1)
                    stack[-1] = link(result, symbol("ok"))
                    return stack
                if tagged_results_flag:
                    stack = _tag_results(machine, stem, stack, env)
                else:
                    try:
                        stack = apply_operator(machine, symbol(stem), stack, env)
                    except OpError:
                        machine.meter.charge_bytes(1)
                        stack.append(NIL)
            else:
                machine.meter.charge_bytes(expr.size() + 1)
                stack.append(link(None, None))
        return stack

    # ATOM: Bytes / Int / Float / String
    if expr._tag in ("bytes", "int", "float", "str"):
        machine.meter.charge_bytes(expr.size())
        stack.append(expr)
        return stack

    # LINK: Pair of Atoms
    if expr._tag == "link":
        # If the list starts with 'quote', treat as quotation
        if (expr._head is not None and expr._head._tag == "symbol" and expr._head.value == "'"):
            if expr._tail is None or expr._tail is NIL:
                # (quote) with no argument – push nil
                machine.meter.charge_bytes(1)
                stack.append(NIL)
            else:
                # push the argument itself, unevaluated
                machine.meter.charge_bytes(expr._tail._head.size())
                stack.append(expr._tail._head)
            return stack
        if expr._head is not None:
            stack = evaluation(machine, expr._head, stack, env)
        if expr._tail is not None:
            stack = evaluation(machine, expr._tail, stack, env)
        return stack
